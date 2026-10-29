"""Failing-first tests for the runtime admin auth boundary and review workflow (task 010 / P8b).

Contract:
- The expected token is read from ``os.environ`` at request time; a missing
  configuration returns a clear server configuration error and never a secret.
- Only ``Authorization: Bearer <token>`` or ``X-Admin-Token`` are accepted:
  missing token -> 401, wrong token -> 403.
- Every ``/api/admin/*`` handler enforces ``require_admin`` itself, before it
  touches the database.
- ``GET /api/admin/sources`` and ``GET /api/admin/reviews`` return internal rows
  only to an authorized request.
- ``POST /api/admin/articles/{id}/review`` accepts only allowlisted actions;
  publishing requires a real article that already went through an authenticated
  PENDING_REVIEW step. SAMPLE/DRAFT can never be auto-published.
- ``POST /api/admin/provider-models/{id}/verification`` accepts an allowlisted
  status plus explicit evidence/note and never fabricates quota or freshness.
- No token value appears in source, bundle, JSON or logs.
"""
from __future__ import annotations

import asyncio
from contextlib import ExitStack, closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request

from backend.app import auth, database, migrate
from backend.app.auth import AdminConfigurationError
from backend.app.main import (
    ADMIN_REVIEW_FIELDS,
    ADMIN_SOURCE_FIELDS,
    ARTICLE_REVIEW_ACTIONS,
    VERIFICATION_STATUSES,
    admin_article_review,
    admin_provider_model_verification,
    admin_reviews,
    admin_sources,
    app,
    import_file,
    list_articles,
    list_models,
    require_admin,
)
from backend.app.migrate import apply_migration

ROOT = Path(__file__).resolve().parents[2]
ADMIN_TOKEN_ENV = "ADMIN_TOKEN"

#: Token công khai duy nhất được phép xuất hiện trong repo (dùng bởi lệnh verify).
FORBIDDEN_TOKEN_LITERAL = "local-" + "test-token"


def fresh_token() -> str:
    """Token ngẫu nhiên cho từng test — không hardcode giá trị nào trong mã nguồn."""
    return "unit-" + secrets.token_hex(16)


def make_request(
    method: str = "GET",
    path: str = "/api/admin/sources",
    token: str | None = None,
    header: str = "authorization",
    raw_headers: list[tuple[bytes, bytes]] | None = None,
    json_body: object | None = None,
) -> Request:
    """Request tối thiểu, đủ để handler đọc header và body như qua HTTP thật."""
    headers: list[tuple[bytes, bytes]] = list(raw_headers or [])
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
            "query_string": b"",
            "root_path": "",
            "headers": headers,
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 50000),
        },
        receive,
    )


def call(coroutine_or_value):
    if asyncio.iscoroutine(coroutine_or_value):
        return asyncio.run(coroutine_or_value)
    return coroutine_or_value


# --------------------------------------------------------------------- 1. token


class AdminTokenConfigurationTests(unittest.TestCase):
    """ADMIN_TOKEN chỉ đọc từ environment, tại thời điểm request."""

    def test_expected_token_is_read_from_environment_at_request_time(self) -> None:
        first, second = fresh_token(), fresh_token()
        with patch.dict(os.environ, {ADMIN_TOKEN_ENV: first}):
            self.assertEqual(auth.expected_admin_token(), first)
        with patch.dict(os.environ, {ADMIN_TOKEN_ENV: second}):
            self.assertEqual(auth.expected_admin_token(), second)

    def test_missing_configuration_raises_configuration_error(self) -> None:
        with patch.dict(os.environ, {ADMIN_TOKEN_ENV: ""}):
            with self.assertRaises(AdminConfigurationError) as ctx:
                auth.expected_admin_token()
        self.assertIn(ADMIN_TOKEN_ENV, str(ctx.exception))
        self.assertTrue(str(ctx.exception).strip())

    def test_unconfigured_server_returns_configuration_error_without_secret(self) -> None:
        request = make_request(token="whatever")
        with patch.dict(os.environ, {ADMIN_TOKEN_ENV: ""}):
            with self.assertRaises(HTTPException) as ctx:
                require_admin(request)
        self.assertEqual(ctx.exception.status_code, 500)
        self.assertIn(ADMIN_TOKEN_ENV, str(ctx.exception.detail))
        self.assertNotIn("whatever", str(ctx.exception.detail))

    def test_missing_credential_is_401_even_when_token_unconfigured(self) -> None:
        """Regression: thiếu credential là lỗi người gọi -> 401, kiểm tra TRƯỚC cấu hình
        server; request chưa xác thực không bao giờ rơi vào nhánh 500 của ADMIN_TOKEN."""
        request = make_request()
        with patch.dict(os.environ, {ADMIN_TOKEN_ENV: ""}):
            with self.assertRaises(HTTPException) as ctx:
                require_admin(request)
        self.assertEqual(ctx.exception.status_code, 401)


class AdminAuthBoundaryTests(unittest.TestCase):
    """401 khi thiếu token, 403 khi sai token; chỉ nhận Bearer / X-Admin-Token."""

    def setUp(self) -> None:
        self.token = fresh_token()
        self._env = patch.dict(os.environ, {ADMIN_TOKEN_ENV: self.token})
        self._env.start()
        self.addCleanup(self._env.stop)

    def test_missing_token_is_401(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            require_admin(make_request())
        self.assertEqual(ctx.exception.status_code, 401)

    def test_empty_bearer_value_is_401(self) -> None:
        request = make_request(raw_headers=[(b"authorization", b"Bearer   ")])
        with self.assertRaises(HTTPException) as ctx:
            require_admin(request)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_wrong_token_is_403(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            require_admin(make_request(token=fresh_token()))
        self.assertEqual(ctx.exception.status_code, 403)

    def test_correct_bearer_token_is_accepted(self) -> None:
        self.assertIsNone(require_admin(make_request(token=self.token)))

    def test_correct_x_admin_token_header_is_accepted(self) -> None:
        self.assertIsNone(
            require_admin(make_request(token=self.token, header="x-admin-token"))
        )

    def test_unsupported_authorization_scheme_is_403(self) -> None:
        request = make_request(raw_headers=[(b"authorization", f"Basic {self.token}".encode())])
        with self.assertRaises(HTTPException) as ctx:
            require_admin(request)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_wrong_token_response_never_echoes_the_expected_token(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            require_admin(make_request(token=fresh_token()))
        self.assertNotIn(self.token, json.dumps({"detail": str(ctx.exception.detail)}))

    def test_rotating_the_environment_token_invalidates_the_old_one(self) -> None:
        self.assertIsNone(require_admin(make_request(token=self.token)))
        with patch.dict(os.environ, {ADMIN_TOKEN_ENV: fresh_token()}):
            with self.assertRaises(HTTPException) as ctx:
                require_admin(make_request(token=self.token))
        self.assertEqual(ctx.exception.status_code, 403)

    def test_non_ascii_token_never_crashes_the_comparison(self) -> None:
        # Header HTTP là latin-1, nên token ngoài ASCII không round-trip được:
        # hợp đồng là "không crash, chỉ từ chối 403", không phải xác thực thành công.
        token = "tökén-ưu-đãi-💙"
        with patch.dict(os.environ, {ADMIN_TOKEN_ENV: token}):
            with self.assertRaises(HTTPException) as ctx:
                require_admin(make_request(token=token))
            self.assertEqual(ctx.exception.status_code, 403)
            with self.assertRaises(HTTPException) as ctx2:
                require_admin(make_request(token=fresh_token()))
            self.assertEqual(ctx2.exception.status_code, 403)


# ------------------------------------------------------------ 2. route coverage


def _function_names(code) -> set[str]:
    """Tên global mà một function object tham chiếu, gồm cả hàm lồng nhau."""
    names = set(code.co_names)
    for constant in code.co_consts:
        if hasattr(constant, "co_names"):
            names |= _function_names(constant)
    return names


class AdminRouteCoverageTests(unittest.TestCase):
    """Mọi route /api/admin/* phải tự gọi require_admin trước khi chạm dữ liệu."""

    def admin_routes(self):
        return [r for r in app.routes if str(getattr(r, "path", "")).startswith("/api/admin")]

    def test_admin_routes_exist_and_each_handler_enforces_require_admin(self) -> None:
        routes = self.admin_routes()
        self.assertTrue(routes, "phải tồn tại route /api/admin/*")
        paths = {route.path for route in routes}
        self.assertIn("/api/admin/import", paths)
        self.assertIn("/api/admin/sources", paths)
        self.assertIn("/api/admin/reviews", paths)
        self.assertIn("/api/admin/articles/{article_id}/review", paths)
        self.assertIn("/api/admin/provider-models/{provider_model_id}/verification", paths)
        for route in routes:
            names = _function_names(route.endpoint.__code__)
            self.assertIn(
                "require_admin", names, f"{route.path} không tự kiểm tra quyền admin"
            )

    def test_unauthenticated_admin_calls_fail_before_touching_the_database(self) -> None:
        def forbidden_connection():
            raise AssertionError("admin handler chạm database trước khi xác thực")

        with patch("backend.app.main.get_connection", side_effect=forbidden_connection):
            cases = [
                (admin_sources, make_request()),
                (admin_reviews, make_request()),
                (admin_article_review, make_request("POST", json_body={"action": "PENDING_REVIEW"})),
                (admin_provider_model_verification, make_request("POST", json_body={})),
                (import_file, make_request("POST")),
            ]
            for handler, request in cases:
                with self.assertRaises(HTTPException) as ctx:
                    if handler is admin_article_review:
                        call(handler(1, request))
                    elif handler is admin_provider_model_verification:
                        call(handler(1, request))
                    else:
                        call(handler(request))
                self.assertEqual(ctx.exception.status_code, 401, handler.__name__)

    def test_wrong_token_is_rejected_on_the_manual_import_route(self) -> None:
        with patch.dict(os.environ, {ADMIN_TOKEN_ENV: fresh_token()}):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(import_file(make_request("POST", token=fresh_token())))
        self.assertEqual(ctx.exception.status_code, 403)


# ------------------------------------------------------- 3. admin review flow

ARTICLE_FIELDS_PUBLIC = {"id", "title", "url", "source", "category", "summary", "published_at", "created_at"}


class AdminWorkflowTestCase(unittest.TestCase):
    """DB tạm đầy đủ schema 12 bảng; không bao giờ chạm backend/data/radar.db."""

    def setUp(self) -> None:
        self._live_db_path = database.DB_PATH
        self._live_existed = self._live_db_path.exists()
        self._live_stat = self._live_db_path.stat() if self._live_existed else None

        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.temp_data_dir = Path(self._tmpdir.name) / "data"
        self.temp_data_dir.mkdir(parents=True, exist_ok=True)
        self.temp_db_path = self.temp_data_dir / "radar.db"

        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(database, "DATA_DIR", self.temp_data_dir))
        stack.enter_context(patch.object(database, "DB_PATH", self.temp_db_path))
        stack.enter_context(patch.object(migrate, "DATA_DIR", self.temp_data_dir))
        stack.enter_context(patch.object(migrate, "DB_PATH", self.temp_db_path))

        self.token = fresh_token()
        stack.enter_context(patch.dict(os.environ, {ADMIN_TOKEN_ENV: self.token}))

        apply_migration()
        self._insert_fixtures()

    def tearDown(self) -> None:
        self.assertEqual(
            self._live_db_path.exists(),
            self._live_existed,
            "Test admin không được tạo/xoá backend/data/radar.db thật",
        )
        if self._live_existed and self._live_stat is not None:
            after = self._live_db_path.stat()
            self.assertEqual(after.st_size, self._live_stat.st_size)
            self.assertEqual(after.st_mtime_ns, self._live_stat.st_mtime_ns)

    def _insert_fixtures(self) -> None:
        with closing(database.get_connection()) as conn:
            conn.execute(
                """INSERT INTO sources (source_id, name, type, url, collection_method,
                       priority, status, last_checked_at, data_origin)
                   VALUES ('src-real', 'Real Source', 'rss', 'https://real.example.test/feed',
                       'rss', 3, 'active', NULL, 'REAL')"""
            )
            conn.execute(
                """INSERT INTO sources (source_id, name, type, collection_method, priority,
                       status, data_origin)
                   VALUES ('src-sample', 'SAMPLE Source', 'manual', 'manual_import', 9,
                       'active', 'SAMPLE')"""
            )
            conn.execute(
                """INSERT INTO articles (id, title, url, source, category, summary,
                       published_at, data_origin, article_status, normalized_title, content_hash)
                   VALUES (1, 'Real draft article', 'https://real.example.test/a', 'src-real',
                       'tip-trick', 'Real draft body', NULL, 'REAL', 'DRAFT',
                       'Real draft article', 'hash-real-1')"""
            )
            conn.execute(
                """INSERT INTO articles (id, title, url, source, category, summary,
                       published_at, data_origin, article_status)
                   VALUES (900001, 'SAMPLE article', NULL, 'src-sample', 'tip-trick',
                       'SAMPLE body', NULL, 'SAMPLE', 'DRAFT')"""
            )
            conn.execute(
                """INSERT INTO providers (provider_id, name, website, data_origin)
                   VALUES ('prov-real', 'Real Provider', 'https://prov.example.test', 'REAL')"""
            )
            conn.execute(
                """INSERT INTO models (model_id, model_name, organization, data_origin)
                   VALUES ('model-real', 'Real Model', 'Org', 'REAL')"""
            )
            conn.execute(
                """INSERT INTO provider_models (id, provider_id, model_id, api_model_id,
                       official_url, free_status, rate_limit, daily_quota, card_required,
                       verification_status, last_verified, data_origin)
                   VALUES (1, 'prov-real', 'model-real', 'model-real-api',
                       'https://prov.example.test/model-real', 'FREE_API', '10 rpm', 1000, 0,
                       'UNVERIFIED', NULL, 'REAL')"""
            )
            conn.execute(
                """INSERT INTO provider_models (id, provider_id, model_id, free_status,
                       daily_quota, verification_status, data_origin)
                   VALUES (900001, 'prov-real', 'model-real', 'FREE_API', 999999,
                       'UNVERIFIED', 'SAMPLE')"""
            )
            conn.commit()

    # -- tiện ích đọc DB tạm ------------------------------------------------

    def rows(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with closing(database.get_connection()) as conn:
            return conn.execute(sql, params).fetchall()

    def article_row(self, article_id: int) -> sqlite3.Row:
        return self.rows(
            "SELECT article_status, published_at, data_origin FROM articles WHERE id = ?",
            (article_id,),
        )[0]

    def review_rows(self, article_id: int) -> list[sqlite3.Row]:
        return self.rows(
            """SELECT review_status, reviewer_note, reviewed_at, data_origin
               FROM editorial_reviews WHERE article_id = ? ORDER BY id""",
            (article_id,),
        )

    # -- tiện ích gọi endpoint --------------------------------------------

    def request(self, **kwargs) -> Request:
        kwargs.setdefault("token", self.token)
        return make_request(**kwargs)

    def review(self, article_id: int, payload: dict, token: str | None = None):
        request = make_request("POST", json_body=payload, token=self.token if token is None else token)
        return asyncio.run(admin_article_review(article_id, request))

    def verify(self, provider_model_id: int, payload: dict):
        request = make_request("POST", json_body=payload, token=self.token)
        return asyncio.run(admin_provider_model_verification(provider_model_id, request))


class AdminReadEndpointTests(AdminWorkflowTestCase):
    def test_sources_returns_internal_registry_rows_only_when_authorized(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            admin_sources(make_request())
        self.assertEqual(ctx.exception.status_code, 401)

        rows = admin_sources(self.request(path="/api/admin/sources"))
        self.assertEqual([row["source_id"] for row in rows], ["src-real", "src-sample"])
        for row in rows:
            self.assertEqual(set(row), set(ADMIN_SOURCE_FIELDS))
        self.assertIn("data_origin", rows[0], "admin phải thấy được nhãn SAMPLE/REAL")

    def test_reviews_returns_review_records_with_article_status(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            admin_reviews(make_request())
        self.assertEqual(ctx.exception.status_code, 401)

        self.review(1, {"action": "PENDING_REVIEW", "note": "looks fine"})
        rows = admin_reviews(self.request(path="/api/admin/reviews"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(set(rows[0]), set(ADMIN_REVIEW_FIELDS))
        self.assertEqual(rows[0]["article_id"], 1)
        self.assertEqual(rows[0]["review_status"], "PENDING_REVIEW")
        self.assertEqual(rows[0]["article_status"], "PENDING_REVIEW")
        self.assertEqual(rows[0]["reviewer_note"], "looks fine")


class AdminArticleReviewTests(AdminWorkflowTestCase):
    def test_action_allowlist_is_enforced(self) -> None:
        self.assertEqual(ARTICLE_REVIEW_ACTIONS, ("PENDING_REVIEW", "REJECTED", "PUBLISHED"))
        for action in ("DRAFT", "ARCHIVED", "", None, 7):
            with self.assertRaises(HTTPException) as ctx:
                self.review(1, {"action": action})
            self.assertEqual(ctx.exception.status_code, 422, action)
        self.assertIsInstance(self.review(1, {"action": "PENDING_REVIEW"}), dict)

    def test_unknown_or_malformed_body_is_rejected(self) -> None:
        for payload in ({}, {"action": "PENDING_REVIEW", "sneaky": "1"}, {"note": "no action"}):
            with self.assertRaises(HTTPException) as ctx:
                self.review(1, payload)
            self.assertEqual(ctx.exception.status_code, 422, payload)

        raw = make_request("POST", token=self.token, raw_headers=[(b"content-type", b"application/json")])
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(admin_article_review(1, raw))
        self.assertEqual(ctx.exception.status_code, 422)

    def test_non_integer_or_missing_article_is_rejected(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            self.review(424242, {"action": "PENDING_REVIEW"})
        self.assertEqual(ctx.exception.status_code, 404)

    def test_publish_requires_a_prior_authenticated_pending_review_step(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            self.review(1, {"action": "PUBLISHED", "note": "skip the queue"})
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(self.article_row(1)["article_status"], "DRAFT")
        self.assertEqual(self.review_rows(1), [])
        self.assertEqual(list_articles(), [], "bài chưa duyệt không được lọt ra feed công khai")

    def test_status_alone_is_not_enough_publish_needs_the_authenticated_ledger_step(self) -> None:
        # Bảng articles tự gán PENDING_REVIEW (không qua workflow có xác thực)
        # vẫn KHÔNG được phép publish — phải có bản ghi editorial_reviews thật.
        with closing(database.get_connection()) as conn:
            conn.execute("UPDATE articles SET article_status = 'PENDING_REVIEW' WHERE id = 1")
            conn.commit()
        with self.assertRaises(HTTPException) as ctx:
            self.review(1, {"action": "PUBLISHED", "note": "no ledger step"})
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(self.article_row(1)["article_status"], "PENDING_REVIEW")
        self.assertEqual(self.review_rows(1), [])

    def test_pending_review_then_publish_is_recorded_transactionally(self) -> None:
        first = self.review(1, {"action": "PENDING_REVIEW", "note": "queue it"})
        self.assertEqual(first["article_status"], "PENDING_REVIEW")
        self.assertEqual(first["review_status"], "PENDING_REVIEW")
        self.assertEqual(self.article_row(1)["article_status"], "PENDING_REVIEW")
        self.assertEqual(list_articles(), [], "PENDING_REVIEW chưa phải PUBLISHED")

        second = self.review(1, {"action": "PUBLISHED"})
        self.assertEqual(second["article_status"], "PUBLISHED")
        self.assertIsNotNone(self.article_row(1)["published_at"])

        ledger = self.review_rows(1)
        self.assertEqual([row["review_status"] for row in ledger], ["PENDING_REVIEW", "PUBLISHED"])
        self.assertEqual({row["data_origin"] for row in ledger}, {"REAL"})

        published = list_articles()
        self.assertEqual([article["id"] for article in published], [1])
        self.assertEqual(set(published[0]), ARTICLE_FIELDS_PUBLIC)
        for leaked in ("data_origin", "review_status", "reviewer_note", "normalized_title", "content_hash"):
            self.assertNotIn(leaked, published[0])

    def test_reject_records_rejection_and_returns_article_to_draft(self) -> None:
        self.review(1, {"action": "PENDING_REVIEW"})
        rejected = self.review(1, {"action": "REJECTED", "note": "off topic"})
        self.assertEqual(rejected["review_status"], "REJECTED")
        self.assertEqual(rejected["article_status"], "DRAFT")
        # Schema articles CHECK chỉ cho DRAFT/PENDING_REVIEW/PUBLISHED: từ chối
        # nghĩa là quay về DRAFT, còn lý do nằm trong editorial_reviews.
        self.assertEqual(self.article_row(1)["article_status"], "DRAFT")
        self.assertEqual(
            [row["review_status"] for row in self.review_rows(1)], ["PENDING_REVIEW", "REJECTED"]
        )
        with self.assertRaises(HTTPException) as ctx:
            self.review(1, {"action": "PUBLISHED"})
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(list_articles(), [])

    def test_reviewing_a_draft_twice_without_pending_step_is_conflict(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            self.review(1, {"action": "REJECTED"})
        self.assertEqual(ctx.exception.status_code, 409)

    def test_already_published_article_is_terminal(self) -> None:
        self.review(1, {"action": "PENDING_REVIEW"})
        self.review(1, {"action": "PUBLISHED"})
        for action in ("PENDING_REVIEW", "REJECTED", "PUBLISHED"):
            with self.assertRaises(HTTPException) as ctx:
                self.review(1, {"action": action})
            self.assertEqual(ctx.exception.status_code, 409, action)
        self.assertEqual(len(self.review_rows(1)), 2)

    def test_sample_article_can_never_be_reviewed_or_published(self) -> None:
        for action in ("PENDING_REVIEW", "PUBLISHED", "REJECTED"):
            with self.assertRaises(HTTPException) as ctx:
                self.review(900001, {"action": action, "note": "sample"})
            self.assertEqual(ctx.exception.status_code, 409, action)
        self.assertEqual(self.review_rows(900001), [])
        self.assertEqual(self.article_row(900001)["article_status"], "DRAFT")
        self.assertEqual(list_articles(), [])

    def test_failed_transition_writes_nothing(self) -> None:
        with self.assertRaises(HTTPException):
            self.review(1, {"action": "PUBLISHED"})
        self.assertEqual(self.review_rows(1), [])
        with closing(database.get_connection()) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM editorial_reviews").fetchone()[0], 0)
            self.assertFalse(conn.in_transaction)


class AdminProviderModelVerificationTests(AdminWorkflowTestCase):
    def test_status_allowlist_matches_schema_values(self) -> None:
        self.assertEqual(
            VERIFICATION_STATUSES,
            ("VERIFIED", "UNVERIFIED", "STALE", "EXPIRED", "NEEDS_REVIEW"),
        )
        for status in ("FREE_API", "OK", "", None, 3):
            with self.assertRaises(HTTPException) as ctx:
                self.verify(1, {"status": status, "evidence": "https://prov.example.test/x"})
            self.assertEqual(ctx.exception.status_code, 422, status)

    def test_explicit_evidence_or_note_is_required(self) -> None:
        for payload in (
            {"status": "VERIFIED"},
            {"status": "VERIFIED", "evidence": "   "},
            {"status": "VERIFIED", "evidence": "", "note": None},
            {"status": "VERIFIED", "evidence": 5},
        ):
            with self.assertRaises(HTTPException) as ctx:
                self.verify(1, payload)
            self.assertEqual(ctx.exception.status_code, 422, payload)

    def test_unknown_or_sample_provider_model_is_rejected(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            self.verify(424242, {"status": "VERIFIED", "evidence": "no such row"})
        self.assertEqual(ctx.exception.status_code, 404)

        with self.assertRaises(HTTPException) as ctx:
            self.verify(900001, {"status": "VERIFIED", "evidence": "sample row"})
        self.assertEqual(ctx.exception.status_code, 409)

    def test_verification_is_recorded_without_touching_quota_fields(self) -> None:
        before = self.rows(
            "SELECT daily_quota, rate_limit, verification_status, last_verified FROM provider_models WHERE id = 1"
        )[0]
        self.assertEqual(before["verification_status"], "UNVERIFIED")
        self.assertIsNone(before["last_verified"])

        evidence = "https://prov.example.test/model-real#pricing"
        result = self.verify(1, {"status": "VERIFIED", "evidence": evidence, "note": "checked page"})
        self.assertEqual(result["verification_status"], "VERIFIED")

        after = self.rows(
            """SELECT daily_quota, rate_limit, verification_status, last_verified
               FROM provider_models WHERE id = 1"""
        )[0]
        self.assertEqual(after["verification_status"], "VERIFIED")
        self.assertIsNotNone(after["last_verified"])
        self.assertEqual(after["daily_quota"], before["daily_quota"], "không được bịa quota")
        self.assertEqual(after["rate_limit"], before["rate_limit"], "không được bịa rate limit")

        records = self.rows(
            """SELECT provider_model_id, verification_status, method, evidence, note, verified_at, data_origin
               FROM verification_records ORDER BY id"""
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["provider_model_id"], 1)
        self.assertEqual(records[0]["verification_status"], "VERIFIED")
        self.assertEqual(records[0]["evidence"], evidence)
        self.assertEqual(records[0]["note"], "checked page")
        self.assertEqual(records[0]["data_origin"], "REAL")
        datetime.fromisoformat(records[0]["verified_at"])

    def test_unverified_status_does_not_claim_freshness(self) -> None:
        self.verify(1, {"status": "NEEDS_REVIEW", "note": "page layout changed"})
        row = self.rows(
            "SELECT verification_status, last_verified, daily_quota FROM provider_models WHERE id = 1"
        )[0]
        self.assertEqual(row["verification_status"], "NEEDS_REVIEW")
        self.assertIsNone(row["last_verified"], "NEEDS_REVIEW không được gắn mốc đã xác minh")
        self.assertEqual(row["daily_quota"], 1000)

    def test_verification_body_rejects_unknown_fields(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            self.verify(1, {"status": "VERIFIED", "evidence": "x", "daily_quota": 999999})
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(
            self.rows("SELECT daily_quota FROM provider_models WHERE id = 1")[0]["daily_quota"], 1000
        )


class AdminPublicBoundaryTests(AdminWorkflowTestCase):
    def test_public_endpoints_never_expose_internal_or_admin_fields(self) -> None:
        self.review(1, {"action": "PENDING_REVIEW", "note": "internal queue note"})
        self.review(1, {"action": "PUBLISHED", "note": "internal publish note"})
        self.verify(1, {"status": "VERIFIED", "evidence": "internal evidence", "note": "internal note"})

        article = list_articles()[0]
        self.assertEqual(set(article), ARTICLE_FIELDS_PUBLIC)

        models = list_models()
        model_ids = {row["model_id"] for row in models}
        self.assertEqual(model_ids, {"model-real"})
        for row in models:
            for leaked in ("data_origin", "raw_content", "provenance", "internal_note", "evidence"):
                self.assertNotIn(leaked, row)

    def test_admin_responses_are_json_serialisable_without_tokens(self) -> None:
        self.review(1, {"action": "PENDING_REVIEW"})
        payload = json.dumps(
            {
                "sources": admin_sources(self.request()),
                "reviews": admin_reviews(self.request()),
                "verification": self.verify(1, {"status": "UNVERIFIED", "note": "recheck"}),
            }
        )
        self.assertNotIn(self.token, payload)


class AdminSecretScanTests(unittest.TestCase):
    """Không token nào xuất hiện trong mã nguồn/bundle."""

    def test_no_token_literal_in_backend_or_frontend_source(self) -> None:
        # Quét MÃ NGUỒN THẬT (backend/app + frontend), không quét test harness —
        # test phải gán token ngẫu nhiên để chạy, đó không phải secret hardcode.
        haystack = []
        for pattern in ("backend/app/**/*.py", "src/**/*.js", "src/**/*.jsx", "index.html"):
            for path in ROOT.glob(pattern):
                if path.is_file():
                    haystack.append(path.read_text(encoding="utf-8", errors="replace"))
        text = "\n".join(haystack)
        self.assertNotIn(FORBIDDEN_TOKEN_LITERAL, text)
        self.assertIsNone(
            re.search(r"ADMIN_TOKEN\s*[:=]\s*[\"'][^\"']+[\"']", text),
            "ADMIN_TOKEN không được hardcode trong mã nguồn",
        )
        self.assertIsNone(re.search(r"(?i)admin[_-]?token\s*=\s*[\"'][^\"']+[\"']", text))

    def test_built_bundle_has_no_token_when_present(self) -> None:
        dist = ROOT / "dist"
        if not dist.exists():
            self.skipTest("dist/ chưa build — bundle scan do checks/p5.py lo")
        for path in dist.rglob("*"):
            if path.is_file() and path.suffix.lower() in (".js", ".html", ".css", ".json"):
                text = path.read_text(encoding="utf-8", errors="replace")
                self.assertNotIn(FORBIDDEN_TOKEN_LITERAL, text)
                self.assertIsNone(re.search(r"ADMIN_TOKEN\s*[:=]\s*[\"'][^\"']+[\"']", text))

    def test_module_docstring_documents_environment_only_configuration(self) -> None:
        source = (ROOT / "backend" / "app" / "auth.py").read_text(encoding="utf-8")
        self.assertIn("os.environ", source)
        self.assertIn(ADMIN_TOKEN_ENV, source)


if __name__ == "__main__":
    unittest.main()
