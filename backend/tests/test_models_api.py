"""Failing-first tests for the public Model/Provider Explorer API (Phase 7).

Contract (task 007):
- GET /api/models returns an explicit public column set (never SELECT *, never
  raw/provenance/internal/registry data) and excludes SAMPLE rows.
- One model joins to many provider rows so provider-specific quota/status/
  verification stay distinct.
- Only the documented query parameters are allowed; invalid values → 422.
- Capability columns are nullable; NULL is never treated as true.
- quota_min/context_min/verified_within_days use non-negative ints; NULL quota
  and UNVERIFIED/NULL verification are never presented as satisfying the filter.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from fastapi import HTTPException, Request

from backend.app.main import (
    PUBLIC_MODEL_FIELDS,
    _unknown_models_query_keys,
    list_models,
    public_models,
)

#: Chỉ các field public được phép xuất hiện trong từng row.
EXPECTED_KEYS = {
    "model_id", "model_name", "organization",
    "provider_id", "provider_name", "website", "official_url",
    "api_model_id", "free_status", "rate_limit", "daily_quota",
    "account_required", "card_required", "context_window",
    "supports_vision", "supports_tools", "supports_json",
    "verification_status", "last_verified", "valid_until",
}


def _utc(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def make_models_db() -> sqlite3.Connection:
    """DB tạm cô lập với dữ liệu LOCAL TEST rõ ràng + một row SAMPLE bị loại."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE providers (
            provider_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            website TEXT,
            api_base_url TEXT,
            data_origin TEXT NOT NULL DEFAULT 'REAL',
            created_at TEXT
        );
        CREATE TABLE models (
            model_id TEXT PRIMARY KEY,
            model_name TEXT NOT NULL,
            organization TEXT,
            context_window INTEGER,
            supports_vision INTEGER,
            supports_tools INTEGER,
            supports_json INTEGER,
            data_origin TEXT NOT NULL DEFAULT 'REAL',
            created_at TEXT
        );
        CREATE TABLE provider_models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            api_model_id TEXT,
            official_url TEXT,
            free_status TEXT,
            rate_limit TEXT,
            daily_quota INTEGER,
            account_required INTEGER,
            card_required INTEGER,
            context_window INTEGER,
            supports_vision INTEGER,
            supports_tools INTEGER,
            supports_json INTEGER,
            verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED',
            last_verified TEXT,
            valid_until TEXT,
            data_origin TEXT NOT NULL DEFAULT 'REAL',
            internal_note TEXT
        );
        """
    )
    recent = _utc(2)
    old = _utc(400)
    conn.executemany(
        "INSERT INTO providers (provider_id, name, website, api_base_url, data_origin) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            ("prov-a", "Provider A", "https://provider-a.example.test", None, "REAL"),
            ("prov-b", "Provider B", None, None, "REAL"),
        ],
    )
    conn.executemany(
        "INSERT INTO models (model_id, model_name, organization, context_window, "
        "supports_vision, supports_tools, supports_json, data_origin) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("m-gpt", "GPT Local Test", "Org Test", 128000, 1, 1, 1, "REAL"),
            ("m-other", "Other Local Test", "Org Test", 8192, 1, None, 0, "REAL"),
        ],
    )
    conn.executemany(
        """INSERT INTO provider_models (
            id, provider_id, model_id, api_model_id, official_url, free_status,
            rate_limit, daily_quota, account_required, card_required,
            context_window, supports_vision, supports_tools, supports_json,
            verification_status, last_verified, valid_until, data_origin, internal_note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            # 1: m-gpt tại prov-a — FREE_API, có API, không cần thẻ, xác minh gần đây.
            (1, "prov-a", "m-gpt", "gpt-test-api", "https://provider-a.example.test/gpt",
             "FREE_API", "10 rpm/min", 1000, 0, 0, 128000, 1, 1, 1,
             "VERIFIED", recent, recent, "REAL", "internal secret A"),
            # 2: m-gpt tại prov-b — web-only, PAID, cần thẻ, chưa xác minh.
            (2, "prov-b", "m-gpt", None, None, "PAID", None, None, 1, 1,
             None, None, 1, None, "UNVERIFIED", None, None, "REAL", "internal secret B"),
            # 3: m-other tại prov-a — có API, FREE_CREDIT, không cần thẻ, tools NULL,
            #    xác minh cũ (ngoài window).
            (3, "prov-a", "m-other", "other-test-api",
             "https://provider-a.example.test/other", "FREE_CREDIT", None, 5000,
             0, 0, 8192, 1, None, 0, "VERIFIED", old, old, "REAL", "internal secret C"),
            # 4: m-other tại prov-b — mọi thứ UNKNOWN/UNVERIFIED/NULL.
            (4, "prov-b", "m-other", None, None, "UNKNOWN", None, None, None, None,
             None, None, None, None, "UNVERIFIED", None, None, "REAL", "internal secret D"),
            # 99: SAMPLE — phải bị loại khỏi mọi kết quả public.
            (99, "prov-a", "m-gpt", "sample-api", None, "FREE_API", None, 999999,
             0, 0, 999999, 1, 1, 1, "VERIFIED", recent, recent, "SAMPLE", "sample note"),
        ],
    )
    conn.commit()
    return conn


class ModelsPublicShapeContractTests(unittest.TestCase):
    """Hình dạng response và việc loại trừ SAMPLE / dữ liệu nội bộ."""

    def test_unfiltered_returns_only_public_fields_excluding_sample_and_internal(self) -> None:
        conn = make_models_db()
        with patch("backend.app.main.get_connection", return_value=conn):
            rows = list_models()
        conn.close()

        # SAMPLE row (id 99) bị loại; còn đúng 4 row REAL.
        self.assertEqual(len(rows), 4)
        self.assertEqual([r["model_id"] for r in rows], ["m-gpt", "m-gpt", "m-other", "m-other"])

        # Một model xuất hiện dưới nhiều provider với trạng thái riêng biệt.
        gpt = [r for r in rows if r["model_id"] == "m-gpt"]
        self.assertEqual([r["provider_id"] for r in gpt], ["prov-a", "prov-b"])
        self.assertEqual([r["free_status"] for r in gpt], ["FREE_API", "PAID"])
        self.assertEqual([r["verification_status"] for r in gpt], ["VERIFIED", "UNVERIFIED"])

        for row in rows:
            self.assertEqual(set(row), EXPECTED_KEYS, f"không được thừa/thiếu field: {row}")
            self.assertNotIn("internal_note", row)
            self.assertNotIn("data_origin", row)
            self.assertNotIn("provenance", row)
            self.assertNotIn("api_base_url", row)
            self.assertNotIn("raw", row)

    def test_sample_rows_never_appear_as_factual_data(self) -> None:
        conn = make_models_db()
        with patch("backend.app.main.get_connection", return_value=conn):
            rows = list_models()
        conn.close()
        self.assertNotIn("sample-api", [r["api_model_id"] for r in rows])
        self.assertFalse(any(r["daily_quota"] == 999999 for r in rows))


class ModelsPublicFilterContractTests(unittest.TestCase):
    """Bộ lọc tham số hoá — từng filter trả đúng tập kết quả."""

    def run_query(self, **filters):
        conn = make_models_db()
        try:
            with patch("backend.app.main.get_connection", return_value=conn):
                return list_models(**filters)
        finally:
            conn.close()

    def ids(self, rows) -> list[tuple[str, str]]:
        # provider_models.id không được expose — dùng cặp model/provider thay thế.
        return sorted((r["model_id"], r["provider_id"]) for r in rows)

    def test_free_status_exact_filter(self) -> None:
        rows = self.run_query(free_status="FREE_API")
        self.assertEqual(self.ids(rows), [("m-gpt", "prov-a")])

    def test_access_api_requires_non_null_api_model_id(self) -> None:
        rows = self.run_query(access="api")
        self.assertEqual(self.ids(rows), [("m-gpt", "prov-a"), ("m-other", "prov-a")])
        self.assertTrue(all(r["api_model_id"] for r in rows))

    def test_access_web_only_requires_null_api_model_id(self) -> None:
        rows = self.run_query(access="web_only")
        self.assertEqual(self.ids(rows), [("m-gpt", "prov-b"), ("m-other", "prov-b")])
        self.assertTrue(all(r["api_model_id"] is None for r in rows))

    def test_provider_filter_by_id_and_by_name_is_exact_and_parameterized(self) -> None:
        by_id = self.run_query(provider="prov-a")
        by_name = self.run_query(provider="Provider A")
        self.assertEqual(self.ids(by_id), self.ids(by_name))
        self.assertEqual(self.ids(by_id), [("m-gpt", "prov-a"), ("m-other", "prov-a")])

    def test_provider_injection_shaped_value_matches_nothing(self) -> None:
        rows = self.run_query(provider="' OR '1'='1")
        self.assertEqual(rows, [])

    def test_card_required_filter(self) -> None:
        need = self.run_query(card_required="1")
        no_need = self.run_query(card_required="0")
        self.assertEqual(self.ids(need), [("m-gpt", "prov-b")])
        # card_required NULL (id 4) không thoả điều kiện 0 lẫn 1.
        self.assertEqual(
            self.ids(no_need),
            [("m-gpt", "prov-a"), ("m-other", "prov-a")],
        )

    def test_capability_text_imposes_no_extra_constraint(self) -> None:
        rows = self.run_query(capability="text")
        self.assertEqual(len(rows), 4)

    def test_capability_tools_requires_non_null_true(self) -> None:
        rows = self.run_query(capability="tools")
        # id 3 có supports_tools NULL -> KHÔNG được tính là tools.
        self.assertEqual(self.ids(rows), [("m-gpt", "prov-a"), ("m-gpt", "prov-b")])

    def test_context_min_requires_non_null_satisfying_value(self) -> None:
        rows = self.run_query(context_min="100000")
        self.assertEqual(self.ids(rows), [("m-gpt", "prov-a")])

    def test_quota_min_requires_non_null_satisfying_value(self) -> None:
        rows = self.run_query(quota_min="2000")
        self.assertEqual(self.ids(rows), [("m-other", "prov-a")])

    def test_verified_within_days_excludes_unverified_null_and_stale(self) -> None:
        rows = self.run_query(verified_within_days="30")
        # Chỉ id 1: VERIFIED + last_verified gần đây. id 2 UNVERIFIED/NULL,
        # id 3 VERIFIED nhưng 400 ngày trước, id 4 UNVERIFIED/NULL đều bị loại.
        self.assertEqual(self.ids(rows), [("m-gpt", "prov-a")])


class ModelsPublicValidationContractTests(unittest.TestCase):
    """Giá trị không hợp lệ phải bị từ chối với 422."""

    def assert_422(self, **filters) -> None:
        with self.assertRaises(HTTPException) as cm:
            with patch("backend.app.main.get_connection"):
                list_models(**filters)
        self.assertEqual(cm.exception.status_code, 422, filters)

    def test_invalid_free_status_rejected(self) -> None:
        self.assert_422(free_status="TOTALLY_FREE")

    def test_invalid_access_rejected(self) -> None:
        self.assert_422(access="both")

    def test_invalid_card_required_rejected(self) -> None:
        self.assert_422(card_required="2")
        self.assert_422(card_required="true")

    def test_invalid_capability_rejected(self) -> None:
        self.assert_422(capability="audio")

    def test_non_negative_int_params_reject_negative_and_non_numeric(self) -> None:
        for name in ("context_min", "quota_min", "verified_within_days"):
            self.assert_422(**{name: "-1"})
            self.assert_422(**{name: "abc"})
            self.assert_422(**{name: "1.5"})

    def test_empty_provider_rejected(self) -> None:
        self.assert_422(provider="   ")


class ModelsPublicRouteTests(unittest.TestCase):
    """Route GET /api/models: tham số lạ bị chặn 422."""

    def make_request(self, query_string: bytes) -> Request:
        return Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/models",
                "raw_path": b"/api/models",
                "query_string": query_string,
                "headers": [],
                "scheme": "http",
                "server": ("test", 80),
                "client": ("test", 80),
            }
        )

    def test_unknown_query_parameter_rejected_422(self) -> None:
        self.assertEqual(_unknown_models_query_keys({"free_status"}), [])
        self.assertEqual(_unknown_models_query_keys({"sneaky": "1"}), ["sneaky"])
        with self.assertRaises(HTTPException) as cm:
            public_models(self.make_request(b"sneaky=1"))
        self.assertEqual(cm.exception.status_code, 422)

    def test_known_query_parameter_served(self) -> None:
        conn = make_models_db()
        try:
            with patch("backend.app.main.get_connection", return_value=conn):
                rows = public_models(self.make_request(b"free_status=FREE_API"))
        finally:
            conn.close()
        self.assertEqual(
            sorted((r["model_id"], r["provider_id"]) for r in rows),
            [("m-gpt", "prov-a")],
        )

    def test_constant_matches_endpoint_contract(self) -> None:
        self.assertEqual(set(PUBLIC_MODEL_FIELDS), EXPECTED_KEYS)


if __name__ == "__main__":
    unittest.main()
