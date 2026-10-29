"""Tests for Promotion Radar lifecycle and public allowlist contract (Task R1)."""
from __future__ import annotations

import asyncio
import os
import sqlite3
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from starlette.requests import Request

from backend.app.main import (
    OFFERS_DEFAULT_LIMIT,
    OFFERS_MAX_LIMIT,
    OFFERS_QUERY_PARAMS,
    PUBLIC_OFFER_FIELDS,
    admin_offer_verification,
    admin_offers,
    list_offers,
    public_offers,
)


def _utc(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


class DatabaseHelper:
    def __init__(self):
        import tempfile
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.path = self.tmp.name
        self._open_conns: list[sqlite3.Connection] = []
        self._init_schema()

    def _init_schema(self):
        conn = sqlite3.connect(self.path)
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
                data_origin TEXT NOT NULL DEFAULT 'REAL',
                created_at TEXT
            );
            CREATE TABLE provider_models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_id TEXT NOT NULL,
                model_id TEXT NOT NULL,
                daily_quota INTEGER,
                rate_limit TEXT,
                data_origin TEXT NOT NULL DEFAULT 'REAL',
                created_at TEXT
            );
            CREATE TABLE offers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_id TEXT,
                provider_model_id INTEGER,
                title TEXT NOT NULL,
                offer_type TEXT,
                code TEXT,
                description TEXT,
                terms TEXT,
                starts_at TEXT,
                ends_at TEXT,
                account_required INTEGER,
                card_required INTEGER,
                verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED',
                last_verified TEXT,
                valid_until TEXT,
                data_origin TEXT NOT NULL DEFAULT 'REAL',
                created_at TEXT
            );
            CREATE TABLE verification_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_model_id INTEGER NOT NULL,
                offer_id INTEGER,
                verification_status TEXT NOT NULL,
                method TEXT,
                evidence TEXT,
                note TEXT,
                verified_at TEXT NOT NULL,
                data_origin TEXT NOT NULL DEFAULT 'REAL',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.executemany(
            "INSERT INTO providers (provider_id, name, website, api_base_url, data_origin) VALUES (?, ?, ?, ?, ?)",
            [
                ("p-open", "OpenAI Local Test", "https://openai.example.test/claim-20", None, "REAL"),
                ("p-anth", "Anthropic Local Test", "https://anthropic.example.test/trial", None, "REAL"),
                ("p-unsafe", "Unsafe CTA Provider", "javascript:alert(1)", None, "REAL"),
                ("p-no-cta", "No CTA Provider", None, None, "REAL"),
                ("SAMPLE_p", "Sample Provider", "https://sample.example.test/offer", None, "SAMPLE"),
            ],
        )
        conn.executemany(
            "INSERT INTO models (model_id, model_name, data_origin) VALUES (?, ?, ?)",
            [("m-1", "Model One", "REAL"), ("m-2", "Model Two", "REAL")],
        )
        conn.executemany(
            "INSERT INTO provider_models (id, provider_id, model_id, daily_quota, rate_limit, data_origin) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (10, "p-open", "m-1", 1000, "10rpm", "REAL"),
                (20, "p-anth", "m-2", 5000, "50rpm", "REAL"),
                (99, "SAMPLE_p", "m-1", 999999, None, "SAMPLE"),
            ],
        )
        future = _utc(10)
        past = _utc(-5)
        recent = _utc(-1)
        conn.executemany(
            """INSERT INTO offers (
                id, provider_id, provider_model_id, title, offer_type, code,
                description, terms, starts_at, ends_at, account_required, card_required,
                verification_status, last_verified, valid_until,
                data_origin
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (1, "p-open", 10, "Free Credits $20 Active", "FREE_CREDIT", "SECRET_CODE_1",
                 "20 dollars trial credit", "New users only", _utc(-2), future,
                 1, 0, "VERIFIED", recent, future, "REAL"),
                (2, "p-anth", 20, "Anthropic Trial Active Open", "FREE_TRIAL", "SECRET_CODE_2",
                 "Free web trial", "No expiry set", None, None,
                 0, 0, "VERIFIED", recent, None, "REAL"),
                (3, "p-open", 10, "Expired by ends_at Offer", "FREE_CREDIT", "SECRET_CODE_3",
                 "Already expired", None, _utc(-30), past,
                 1, 0, "VERIFIED", recent, past, "REAL"),
                (4, "p-open", 10, "Expired by valid_until Offer", "FREE_CREDIT", "SECRET_CODE_4",
                 "Valid until passed", None, _utc(-30), None,
                 1, 0, "VERIFIED", recent, past, "REAL"),
                (5, "p-anth", 20, "Unverified Community Deal", "PROMO", "SECRET_CODE_5",
                 "Community reported", None, None, future,
                 0, 0, "UNVERIFIED", None, None, "REAL"),
                (6, "p-no-cta", 10, "No CTA Offer", "FREE_API", "SECRET_CODE_6",
                 "Missing CTA URL", None, None, future,
                 0, 0, "VERIFIED", recent, future, "REAL"),
                (7, "p-unsafe", 10, "Unsafe CTA Offer", "FREE_API", "SECRET_CODE_7",
                 "XSS attempt CTA", None, None, future,
                 0, 0, "VERIFIED", recent, future, "REAL"),
                (8, "p-open", 10, "Explicit EXPIRED status", "FREE_CREDIT", "SECRET_CODE_8",
                 "Explicitly marked expired", None, None, None,
                 0, 0, "EXPIRED", recent, None, "REAL"),
                (900, "SAMPLE_p", 99, "SAMPLE Offer Never Public", "FREE_CREDIT", "SAMPLE_SECRET",
                 "This is sample data", None, None, future,
                 0, 0, "VERIFIED", recent, future, "SAMPLE"),
            ],
        )
        conn.commit()
        conn.close()

    def get_connection(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        self._open_conns.append(conn)
        return conn

    def execute(self, *args, **kwargs):
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(*args, **kwargs)

    def close(self):
        for conn in self._open_conns:
            try:
                conn.close()
            except Exception:
                pass
        self._open_conns.clear()
        try:
            os.remove(self.path)
        except OSError:
            pass


def make_test_db():
    return DatabaseHelper()


def make_starlette_request(
    query_string: bytes = b"",
    method: str = "GET",
    path: str = "/api/offers",
    token: str | None = None,
    header: str = "authorization",
    json_body: object | None = None,
) -> Request:
    import json
    headers: list[tuple[bytes, bytes]] = []
    if token is not None:
        if header.lower() == "authorization":
            headers.append((b"authorization", f"Bearer {token}".encode()))
        else:
            headers.append((b"x-admin-token", token.encode()))
    body = b""
    if json_body is not None:
        body = json.dumps(json_body).encode("utf-8")
        headers.append((b"content-type", b"application/json"))
    state = {"read": False}

    async def receive() -> dict:
        if state["read"]:
            return {"type": "http.disconnect"}
        state["read"] = True
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "path": path,
            "raw_path": path.encode(),
            "query_string": query_string,
            "root_path": "",
            "headers": headers,
            "scheme": "http",
            "server": ("127.0.0.1", 8000),
            "client": ("127.0.0.1", 50000),
        },
        receive,
    )


class PublicOffersContractTests(unittest.TestCase):
    def test_default_returns_only_active_verified_real_with_safe_cta(self) -> None:
        db = make_test_db()
        try:
            with patch("backend.app.main.get_connection", side_effect=db.get_connection):
                rows = list_offers()
        finally:
            db.close()
        self.assertEqual([r["id"] for r in rows], [1, 2])
        for row in rows:
            self.assertTrue(row["is_active"])
            self.assertEqual(row["verification_status"], "VERIFIED")
            self.assertTrue(row["official_url"].startswith("http"))

    def test_public_fields_allowlist_never_leaks_code_or_internal_keys(self) -> None:
        db = make_test_db()
        try:
            with patch("backend.app.main.get_connection", side_effect=db.get_connection):
                rows = list_offers()
        finally:
            db.close()
        expected = set(PUBLIC_OFFER_FIELDS)
        for row in rows:
            self.assertEqual(set(row), expected)
            self.assertNotIn("code", row)
            self.assertNotIn("SECRET_CODE_1", str(row))
            self.assertNotIn("data_origin", row)

    def test_sample_offers_never_appear(self) -> None:
        db = make_test_db()
        try:
            with patch("backend.app.main.get_connection", side_effect=db.get_connection):
                rows = list_offers()
                history = list_offers(status="VERIFIED")
        finally:
            db.close()
        for r_set in (rows, history):
            self.assertNotIn(900, [r["id"] for r in r_set])
            self.assertNotIn("SAMPLE_p", [r["provider_id"] for r in r_set])

    def test_unverified_and_expired_never_appear_as_active(self) -> None:
        db = make_test_db()
        try:
            with patch("backend.app.main.get_connection", side_effect=db.get_connection):
                rows = list_offers()
        finally:
            db.close()
        active_ids = {r["id"] for r in rows}
        for bad_id in (3, 4, 5, 6, 7, 8):
            self.assertNotIn(bad_id, active_ids)

    def test_historical_status_filter_marks_is_active_accurately(self) -> None:
        db = make_test_db()
        try:
            with patch("backend.app.main.get_connection", side_effect=db.get_connection):
                unverified_rows = list_offers(status="UNVERIFIED")
                expired_rows = list_offers(status="EXPIRED")
        finally:
            db.close()
        self.assertEqual([r["id"] for r in unverified_rows], [5])
        self.assertFalse(unverified_rows[0]["is_active"])
        self.assertEqual([r["id"] for r in expired_rows], [8])
        self.assertFalse(expired_rows[0]["is_active"])

    def test_q_search_and_filters_parameterized(self) -> None:
        db = make_test_db()
        try:
            with patch("backend.app.main.get_connection", side_effect=db.get_connection):
                by_q = list_offers(q="Credits")
                by_provider = list_offers(provider="p-anth")
                by_type = list_offers(offer_type="FREE_CREDIT")
                empty = list_offers(q="NonExistentTerm")
        finally:
            db.close()
        self.assertEqual([r["id"] for r in by_q], [1])
        self.assertEqual([r["id"] for r in by_provider], [2])
        self.assertEqual([r["id"] for r in by_type], [1])
        self.assertEqual(empty, [])

    def test_bounded_limit_honored(self) -> None:
        db = make_test_db()
        try:
            with patch("backend.app.main.get_connection", side_effect=db.get_connection):
                rows_1 = list_offers(limit="1")
        finally:
            db.close()
        self.assertEqual(len(rows_1), 1)

    def test_unknown_query_parameters_rejected_422(self) -> None:
        req = make_starlette_request(query_string=b"sneaky=1&other=test")
        with self.assertRaises(HTTPException) as ctx:
            public_offers(req)
        self.assertEqual(ctx.exception.status_code, 422)

    def test_invalid_filter_values_rejected_422(self) -> None:
        for bad_kwargs in (
            {"status": "NOT_A_STATUS"},
            {"limit": "0"},
            {"limit": "9999"},
            {"provider": "   "},
            {"offer_type": "INVALID_TYPE"},
        ):
            with self.assertRaises(HTTPException) as ctx:
                list_offers(**bad_kwargs)
            self.assertEqual(ctx.exception.status_code, 422)

    def test_public_offers_endpoint_envelope(self) -> None:
        db = make_test_db()
        try:
            req = make_starlette_request(query_string=b"")
            with patch("backend.app.main.get_connection", side_effect=db.get_connection):
                res = public_offers(req)
        finally:
            db.close()
        self.assertIn("offers", res)
        self.assertIn("count", res)
        self.assertEqual(res["count"], len(res["offers"]))
        self.assertEqual(res["count"], 2)
        self.assertEqual([r["id"] for r in res["offers"]], [1, 2])
        self.assertEqual(res["offers"][0]["official_url"], "https://openai.example.test/claim-20")


class AdminOfferVerificationContractTests(unittest.TestCase):
    def test_auth_ordering_runs_require_admin_before_db(self) -> None:
        req = make_starlette_request(
            method="POST",
            path="/api/admin/offers/1/verification",
            token=None,
            json_body={"status": "VERIFIED", "evidence": "https://test.example", "note": "ok", "method": "manual"},
        )
        with patch("backend.app.main.get_connection") as mock_conn:
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(admin_offer_verification(1, req))
            mock_conn.assert_not_called()
        self.assertEqual(ctx.exception.status_code, 401)

    def test_sample_offer_cannot_be_verified_409(self) -> None:
        db = make_test_db()
        req = make_starlette_request(
            method="POST",
            path="/api/admin/offers/900/verification",
            token="valid-token",
            json_body={"status": "VERIFIED", "evidence": "https://test.example", "note": "ok", "method": "manual"},
        )
        try:
            with patch.dict(os.environ, {"ADMIN_TOKEN": "valid-token"}):
                with patch("backend.app.main.get_connection", side_effect=db.get_connection):
                    with self.assertRaises(HTTPException) as ctx:
                        asyncio.run(admin_offer_verification(900, req))
            self.assertEqual(ctx.exception.status_code, 409)
            self.assertIn("SAMPLE", str(ctx.exception.detail))
        finally:
            db.close()

    def test_verify_real_offer_updates_status_and_creates_record(self) -> None:
        db = make_test_db()
        req = make_starlette_request(
            method="POST",
            path="/api/admin/offers/5/verification",
            token="valid-token",
            json_body={
                "status": "VERIFIED",
                "evidence": "https://anthropic.example.test/pricing",
                "note": "Pricing page checked live",
                "method": "manual",
            },
        )
        try:
            with patch.dict(os.environ, {"ADMIN_TOKEN": "valid-token"}):
                with patch("backend.app.main.get_connection", side_effect=db.get_connection):
                    result = asyncio.run(admin_offer_verification(5, req))
            self.assertEqual(result["offer_id"], 5)
            self.assertEqual(result["verification_status"], "VERIFIED")
            self.assertIsNotNone(result["last_verified"])
            self.assertEqual(result["data_origin"], "REAL")
            row = db.execute("SELECT verification_status, last_verified FROM offers WHERE id = 5").fetchone()
            self.assertEqual(row["verification_status"], "VERIFIED")
            rec = db.execute("SELECT * FROM verification_records WHERE offer_id = 5 ORDER BY id DESC LIMIT 1").fetchone()
            self.assertIsNotNone(rec)
            self.assertEqual(rec["verification_status"], "VERIFIED")
            self.assertEqual(rec["evidence"], "https://anthropic.example.test/pricing")
            self.assertEqual(rec["provider_model_id"], 20)
        finally:
            db.close()

    def test_non_verified_status_does_not_fabricate_last_verified(self) -> None:
        db = make_test_db()
        old_last_verified = db.execute("SELECT last_verified FROM offers WHERE id = 1").fetchone()["last_verified"]
        req = make_starlette_request(
            method="POST",
            path="/api/admin/offers/1/verification",
            token="valid-token",
            json_body={"status": "STALE", "evidence": None, "note": "Checked and link seems broken", "method": "manual"},
        )
        try:
            with patch.dict(os.environ, {"ADMIN_TOKEN": "valid-token"}):
                with patch("backend.app.main.get_connection", side_effect=db.get_connection):
                    result = asyncio.run(admin_offer_verification(1, req))
            self.assertEqual(result["verification_status"], "STALE")
            self.assertEqual(result["last_verified"], old_last_verified)
            row = db.execute("SELECT verification_status, last_verified FROM offers WHERE id = 1").fetchone()
            self.assertEqual(row["last_verified"], old_last_verified)
        finally:
            db.close()

    def test_missing_evidence_and_note_rejected_422(self) -> None:
        req = make_starlette_request(
            method="POST",
            path="/api/admin/offers/1/verification",
            token="valid-token",
            json_body={"status": "VERIFIED", "evidence": None, "note": None, "method": "manual"},
        )
        with patch.dict(os.environ, {"ADMIN_TOKEN": "valid-token"}):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(admin_offer_verification(1, req))
        self.assertEqual(ctx.exception.status_code, 422)

    def test_admin_offers_list_requires_auth(self) -> None:
        req_unauth = make_starlette_request(path="/api/admin/offers", token=None)
        with patch("backend.app.main.get_connection") as mock_conn:
            with self.assertRaises(HTTPException) as ctx:
                admin_offers(req_unauth)
            mock_conn.assert_not_called()
        self.assertEqual(ctx.exception.status_code, 401)
        db = make_test_db()
        req_auth = make_starlette_request(path="/api/admin/offers", token="valid-token")
        try:
            with patch.dict(os.environ, {"ADMIN_TOKEN": "valid-token"}):
                with patch("backend.app.main.get_connection", side_effect=db.get_connection):
                    rows = admin_offers(req_auth)
            self.assertTrue(any(r["data_origin"] == "SAMPLE" for r in rows))
            self.assertTrue(any(r["data_origin"] == "REAL" for r in rows))
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
