"""Harness kiểm chứng bề mặt Admin review UI (task 011).

Ba lớp kiểm chứng, tất cả đều dựa trên bằng chứng chạy thật:

1. ``AdminUiEndpointContractTests`` — gọi ĐÚNG hình dạng request mà UI gửi (header
   ``Authorization: Bearer <token>``, body ``{"action": …, "note": …}`` /
   ``{"status": …, "evidence": …, "note": …}``) vào các handler admin thật trên DB
   tạm, và kiểm tra 401/403/409/422 + việc token không xuất hiện trong phản hồi.
2. ``AdminUiSourceContractTests`` — quét mã nguồn frontend để chứng minh token
   không nằm trong bundle/mã nguồn, không có localStorage/dangerouslySetInnerHTML,
   có trạng thái loading/error/retry và đóng bằng bàn phím.
3. ``AdminUiClientHarnessTests`` — chạy THẬT module client
   (``backend/tests/admin_client_harness.mjs``) bằng Node với fetch giả.

Token trong test được sinh ngẫu nhiên tại runtime — không hardcode giá trị nào.
"""
from __future__ import annotations

import asyncio
from contextlib import ExitStack, closing
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request

from backend.app import database, migrate
from backend.app.main import (
    ADMIN_REVIEW_FIELDS,
    ADMIN_SOURCE_FIELDS,
    admin_article_review,
    admin_provider_model_verification,
    admin_reviews,
    admin_sources,
    app,
    list_articles,
)
from backend.app.migrate import apply_migration

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
ADMIN_DIR = SRC / "components" / "admin"
HARNESS = Path(__file__).resolve().parent / "admin_client_harness.mjs"
RENDER_HARNESS = Path(__file__).resolve().parent / "admin_ui_render_harness.mjs"
ADMIN_TOKEN_ENV = "ADMIN_TOKEN"

#: Token công khai duy nhất được phép xuất hiện trong repo (dùng bởi lệnh verify).
FORBIDDEN_TOKEN_LITERAL = "local-" + "test-token"

#: Trạng thái duyệt mà UI được phép hiển thị nút hành động.
UI_REVIEW_ACTIONS = ("PENDING_REVIEW", "REJECTED", "PUBLISHED")

#: Trạng thái xác minh UI được phép gửi đi.
UI_VERIFICATION_STATUSES = ("VERIFIED", "UNVERIFIED", "STALE", "EXPIRED", "NEEDS_REVIEW")


def fresh_token() -> str:
    """Token ngẫu nhiên cho từng test — không hardcode giá trị nào."""
    return "unit-" + secrets.token_hex(16)


def make_request(
    method: str = "GET",
    path: str = "/api/admin/reviews",
    token: str | None = None,
    json_body: object | None = None,
) -> Request:
    """Request tối thiểu giống hệt lời gọi HTTP mà adminClient.js tạo ra."""
    headers: list[tuple[bytes, bytes]] = []
    if token is not None:
        headers.append((b"authorization", f"Bearer {token}".encode()))
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


def call(value):
    return asyncio.run(value) if asyncio.iscoroutine(value) else value


class AdminUiFixtureCase(unittest.TestCase):
    """DB tạm đầy đủ schema; không bao giờ chạm backend/data/radar.db."""

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
            "Test UI không được tạo/xoá backend/data/radar.db thật",
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
                """INSERT INTO provider_models (id, provider_id, model_id, free_status,
                       daily_quota, rate_limit, verification_status, data_origin)
                   VALUES (1, 'prov-real', 'model-real', 'FREE_API', 1000, '10 rpm',
                       'UNVERIFIED', 'REAL')"""
            )
            conn.execute(
                """INSERT INTO provider_models (id, provider_id, model_id, free_status,
                       daily_quota, verification_status, data_origin)
                   VALUES (900001, 'prov-real', 'model-real', 'FREE_API', 999999,
                       'UNVERIFIED', 'SAMPLE')"""
            )
            conn.commit()

    # -- gọi endpoint theo đúng hình dạng UI -------------------------------

    def ui_reviews(self, token: str | None = None) -> list[dict]:
        return admin_reviews(
            make_request("GET", "/api/admin/reviews", token=self.token if token is None else token)
        )

    def ui_sources(self, token: str | None = None) -> list[dict]:
        return admin_sources(
            make_request("GET", "/api/admin/sources", token=self.token if token is None else token)
        )

    def ui_review(self, article_id: int, payload: dict, token: str | None = None):
        return call(
            admin_article_review(
                article_id,
                make_request(
                    "POST",
                    f"/api/admin/articles/{article_id}/review",
                    token=self.token if token is None else token,
                    json_body=payload,
                ),
            )
        )

    def ui_verify(self, provider_model_id: int, payload: dict, token: str | None = None):
        return call(
            admin_provider_model_verification(
                provider_model_id,
                make_request(
                    "POST",
                    f"/api/admin/provider-models/{provider_model_id}/verification",
                    token=self.token if token is None else token,
                    json_body=payload,
                ),
            )
        )

    def db_rows(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with closing(database.get_connection()) as conn:
            return conn.execute(sql, params).fetchall()


# ------------------------------------------------------- 1. hợp đồng endpoint


class AdminUiEndpointContractTests(AdminUiFixtureCase):
    """Bốn endpoint admin trả đúng thứ UI cần, và UI không thể vượt quyền."""

    def test_ui_token_boundary_matches_client_behaviour(self) -> None:
        #: Thiếu token -> 401; sai token -> 403; đúng token -> dữ liệu.
        with self.assertRaises(HTTPException) as missing:
            self.ui_reviews(token="")
        self.assertEqual(missing.exception.status_code, 401)

        with self.assertRaises(HTTPException) as wrong:
            self.ui_reviews(token=fresh_token())
        self.assertEqual(wrong.exception.status_code, 403)

        rows = self.ui_reviews()
        self.assertIsInstance(rows, list)

    def test_ui_review_rows_expose_only_the_declared_fields(self) -> None:
        self.ui_review(1, {"action": "PENDING_REVIEW", "note": "đưa vào hàng đợi"})
        rows = self.ui_reviews()
        self.assertEqual(len(rows), 1)
        self.assertEqual(set(rows[0]), set(ADMIN_REVIEW_FIELDS))
        self.assertEqual(rows[0]["article_id"], 1)
        self.assertEqual(rows[0]["review_status"], "PENDING_REVIEW")
        self.assertEqual(rows[0]["article_status"], "PENDING_REVIEW")

    def test_ui_pending_then_published_flow_publishes_to_the_public_feed(self) -> None:
        first = self.ui_review(1, {"action": "PENDING_REVIEW", "note": "hàng đợi"})
        self.assertEqual(first["article_status"], "PENDING_REVIEW")
        self.assertEqual(list_articles(), [], "PENDING_REVIEW chưa được lọt ra feed công khai")

        second = self.ui_review(1, {"action": "PUBLISHED"})
        self.assertEqual(second["article_status"], "PUBLISHED")
        led = [row["review_status"] for row in self.db_rows(
            "SELECT review_status FROM editorial_reviews WHERE article_id = 1 ORDER BY id"
        )]
        self.assertEqual(led, ["PENDING_REVIEW", "PUBLISHED"])
        self.assertEqual([article["id"] for article in list_articles()], [1])

    def test_ui_reject_returns_article_to_draft_and_server_explains_conflict(self) -> None:
        self.ui_review(1, {"action": "PENDING_REVIEW"})
        rejected = self.ui_review(1, {"action": "REJECTED", "note": "lệch chủ đề"})
        self.assertEqual(rejected["review_status"], "REJECTED")
        self.assertEqual(rejected["article_status"], "DRAFT")
        self.assertEqual(list_articles(), [])

        #: UI hiển thị nguyên văn lý do của server khi chuyển trạng thái sai.
        with self.assertRaises(HTTPException) as conflict:
            self.ui_review(1, {"action": "PUBLISHED"})
        self.assertEqual(conflict.exception.status_code, 409)
        self.assertTrue(str(conflict.exception.detail).strip())

    def test_ui_cannot_send_actions_or_fields_outside_the_client_allowlist(self) -> None:
        for payload in ({"action": "DRAFT"}, {"action": None}, {"note": "thiếu action"}):
            with self.assertRaises(HTTPException) as ctx:
                self.ui_review(1, payload)
            self.assertEqual(ctx.exception.status_code, 422, payload)

        #: client chỉ gửi action/note — field lạ vẫn bị server chặn (defence in depth).
        with self.assertRaises(HTTPException) as ctx:
            self.ui_review(1, {"action": "PENDING_REVIEW", "article_status": "PUBLISHED"})
        self.assertEqual(ctx.exception.status_code, 422)

    def test_ui_verification_requires_evidence_and_never_touches_quota(self) -> None:
        before = self.db_rows("SELECT daily_quota, rate_limit FROM provider_models WHERE id = 1")[0]

        result = self.ui_verify(
            1, {"status": "VERIFIED", "evidence": "https://prov.example.test/pricing"}
        )
        self.assertEqual(result["verification_status"], "VERIFIED")

        for payload in (
            {"status": "VERIFIED"},
            {"status": "VERIFIED", "evidence": "   ", "note": ""},
            {"status": "OK", "evidence": "https://prov.example.test/pricing"},
            {"status": "VERIFIED", "evidence": "x", "daily_quota": 999999},
        ):
            with self.assertRaises(HTTPException) as ctx:
                self.ui_verify(1, payload)
            self.assertEqual(ctx.exception.status_code, 422, payload)

        after = self.db_rows(
            "SELECT daily_quota, rate_limit FROM provider_models WHERE id = 1"
        )[0]
        self.assertEqual(after["daily_quota"], before["daily_quota"])
        self.assertEqual(after["rate_limit"], before["rate_limit"])

    def test_ui_sample_rows_stay_blocked_for_review_and_verification(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            self.ui_review(900001, {"action": "PENDING_REVIEW", "note": "sample"})
        self.assertEqual(ctx.exception.status_code, 409)
        with self.assertRaises(HTTPException) as ctx2:
            self.ui_verify(900001, {"status": "VERIFIED", "evidence": "sample row"})
        self.assertEqual(ctx2.exception.status_code, 409)
        self.assertEqual(list_articles(), [])

    def test_ui_sources_rows_are_registry_context_only(self) -> None:
        rows = self.ui_sources()
        self.assertEqual([row["source_id"] for row in rows], ["src-real", "src-sample"])
        for row in rows:
            self.assertEqual(set(row), set(ADMIN_SOURCE_FIELDS))
            for forbidden in ("raw_content", "provenance", "internal_note", "payload"):
                self.assertNotIn(forbidden, row)
        self.assertEqual({row["data_origin"] for row in rows}, {"REAL", "SAMPLE"})

    def test_ui_responses_never_contain_the_admin_token(self) -> None:
        self.ui_review(1, {"action": "PENDING_REVIEW", "note": "ghi chú nội bộ"})
        self.ui_review(1, {"action": "PUBLISHED"})
        verification = self.ui_verify(1, {"status": "VERIFIED", "evidence": "bằng chứng nội bộ"})
        payload = json.dumps(
            {
                "reviews": self.ui_reviews(),
                "sources": self.ui_sources(),
                "verification": verification,
            }
        )
        self.assertNotIn(self.token, payload)

        for bad_token in ("", fresh_token()):
            try:
                self.ui_reviews(token=bad_token)
            except HTTPException as error:
                self.assertNotIn(self.token, json.dumps({"detail": str(error.detail)}))


# ------------------------------------------------------- 2. hợp đồng mã nguồn


class AdminUiSourceContractTests(unittest.TestCase):
    """Bằng chứng tĩnh trên mã nguồn/bundle của frontend."""

    def read(self, path: Path) -> str:
        return path.read_text(encoding="utf-8", errors="replace")

    def src_files(self, pattern: str = "**/*") -> list[Path]:
        return [p for p in SRC.glob(pattern) if p.is_file()]

    def admin_files(self) -> list[Path]:
        return sorted(p for p in ADMIN_DIR.glob("*") if p.is_file())

    def test_admin_components_exist_and_are_wired_into_the_app(self) -> None:
        files = {p.name for p in self.admin_files()}
        for expected in (
            "AdminView.jsx",
            "AdminTokenForm.jsx",
            "ReviewPanel.jsx",
            "SourcePanel.jsx",
            "VerificationPanel.jsx",
            "adminClient.js",
        ):
            self.assertIn(expected, files)

        app_source = self.read(SRC / "App.jsx")
        self.assertIn("AdminView", app_source)
        self.assertIn("admin-radar", app_source)
        groups_source = self.read(SRC / "data" / "groups.js")
        self.assertIn("admin-radar", groups_source, "nhóm Admin Radar phải còn trong sidebar")

    def test_no_admin_view_regresses_the_existing_routes(self) -> None:
        app_source = self.read(SRC / "App.jsx")
        for kept in ("/api/articles", "ExplorerView", "GroupView", "free-model-explorer"):
            self.assertIn(kept, app_source)

    def test_client_calls_only_the_allowlisted_admin_endpoints(self) -> None:
        source = self.read(ADMIN_DIR / "adminClient.js")
        self.assertIn("/api/admin/reviews", source)
        self.assertIn("/api/admin/sources", source)
        self.assertIn("/api/admin/articles/", source)
        self.assertIn("/api/admin/provider-models/", source)
        #: Không có endpoint admin nào khác được gọi từ UI.
        for extra in ("/api/admin/import", "/api/admin/users", "/api/admin/settings"):
            self.assertNotIn(extra, source)

    def test_token_is_sent_as_bearer_header_from_an_argument(self) -> None:
        source = self.read(ADMIN_DIR / "adminClient.js")
        self.assertIn("Authorization", source)
        self.assertIn("Bearer ", source)
        #: Token phải là tham số của lời gọi, không phải hằng số trong module.
        self.assertRegex(source, r"function\s+adminHeaders\s*\(\s*token")
        self.assertNotRegex(source, r"Bearer\s+[A-Za-z0-9_\-]{12,}")

    def test_no_admin_code_and_no_token_touches_browser_persistence(self) -> None:
        #: Bề mặt admin (kể cả client thuần) tuyệt đối không dùng API lưu trữ bền.
        admin_files = self.admin_files()
        self.assertTrue(admin_files)
        for path in admin_files:
            text = self.read(path)
            #: Yêu cầu có tên miền/method theo sau (getItem, setItem, …) để không
            #: nhầm từ khoá trong bình luận/chuỗi mô tả thành truy cập thật.
            for api, pattern in (
                ("localStorage", r"\blocalStorage\s*\.\s*(?:get|set|remove|clear|key|length)"),
                ("sessionStorage", r"\bsessionStorage\s*\.\s*(?:get|set|remove|clear|key|length)"),
                ("indexedDB", r"\bindexedDB\s*\.\s*(?:open|deleteDatabase)"),
                ("document.cookie", r"\bdocument\s*\.\s*cookie\b"),
            ):
                self.assertIsNone(
                    re.search(pattern, text),
                    f"{path.name} truy cập {api} — token/phiên admin không được lưu bền",
                )

        #: Frontend chỉ lưu tuỳ chọn giao diện và bookmark bài viết; token admin
        #: không được lưu bền trong localStorage/session/cookie.
        storage_files = [
            path
            for path in self.src_files()
            if re.search(r"\bwindow\s*\.\s*localStorage\s*\.", self.read(path))
        ]
        self.assertEqual(
            sorted(path.name for path in storage_files),
            ["useBookmarks.js", "useTheme.js"],
            "chỉ theme/bookmark được dùng localStorage",
        )
        theme_source = self.read(SRC / "hooks" / "useTheme.js")
        self.assertIn("THEME_STORAGE_KEY", theme_source)
        self.assertNotRegex(theme_source, r"(?i)token")

    def test_article_and_review_text_is_rendered_as_text_never_html(self) -> None:
        for path in self.src_files():
            text = self.read(path)
            self.assertNotIn("dangerouslySetInnerHTML", text, path.name)
            self.assertNotIn("innerHTML", text, path.name)

    def test_token_input_is_masked_and_never_autofilled(self) -> None:
        source = self.read(ADMIN_DIR / "AdminTokenForm.jsx")
        self.assertIn('type="password"', source)
        self.assertIn('autoComplete="off"', source)
        #: Không có giá trị token mặc định nào trong component.
        self.assertNotRegex(source, r"useState\(\s*['\"][^'\"]{8,}['\"]\s*\)")

    def test_review_controls_cover_the_three_ui_actions_and_show_server_reasons(self) -> None:
        source = self.read(ADMIN_DIR / "ReviewPanel.jsx")
        for action in UI_REVIEW_ACTIONS:
            self.assertIn(action, source, f"thiếu hành động {action}")
        self.assertIn("ADMIN_REVIEW_ACTIONS", source, "nút hành động phải đi từ allowlist")
        #: Lý do 409/404/422 của server được hiển thị, không tự suy diễn lại.
        self.assertIn("describeAdminOutcome", source)

    def test_verification_controls_send_only_status_and_explicit_evidence(self) -> None:
        source = self.read(ADMIN_DIR / "VerificationPanel.jsx")
        self.assertIn("VERIFICATION_STATUSES", source)
        for forbidden in ("daily_quota", "rate_limit", "last_verified", "valid_until"):
            self.assertNotIn(forbidden, source, f"UI không được gửi {forbidden}")
        client_source = self.read(ADMIN_DIR / "adminClient.js")
        self.assertIn("invalid-evidence", client_source)

    def test_loading_empty_error_and_retry_states_are_present(self) -> None:
        review = self.read(ADMIN_DIR / "ReviewPanel.jsx")
        source = self.read(ADMIN_DIR / "SourcePanel.jsx")
        states = self.read(ADMIN_DIR / "AdminStates.jsx")
        for text in (review, source):
            self.assertIn("AdminLoading", text)
            self.assertIn("AdminError", text)
            self.assertIn("AdminEmpty", text)
            self.assertIn("onRetry", text)
        self.assertIn('role="alert"', states)
        self.assertIn('role="status"', states)

    def test_keyboard_close_and_focus_behaviour_are_present(self) -> None:
        source = self.read(ADMIN_DIR / "ReviewPanel.jsx")
        self.assertIn("Escape", source, "vùng ghi chú phải đóng được bằng Escape")
        self.assertIn("autoFocus", source)
        token_form = self.read(ADMIN_DIR / "AdminTokenForm.jsx")
        self.assertIn("'Enter'", token_form, "nhập token xong phải mở được bằng Enter")

    def test_no_token_literal_is_embedded_in_source_or_bundle(self) -> None:
        haystack = [self.read(path) for path in self.src_files()]
        haystack.append(self.read(ROOT / "index.html"))
        text = "\n".join(haystack)
        self.assertNotIn(FORBIDDEN_TOKEN_LITERAL, text)
        self.assertIsNone(re.search(r"ADMIN_TOKEN\s*[:=]\s*[\"'][^\"']+[\"']", text))
        self.assertIsNone(re.search(r"(?i)admin[_-]?token\s*=\s*[\"'][^\"']+[\"']", text))

        dist = ROOT / "dist"
        if dist.exists():
            bundle = "\n".join(
                self.read(path)
                for path in dist.rglob("*")
                if path.is_file() and path.suffix.lower() in (".js", ".html", ".css", ".json")
            )
            self.assertNotIn(FORBIDDEN_TOKEN_LITERAL, bundle)
            self.assertIsNone(re.search(r"ADMIN_TOKEN\s*[:=]\s*[\"'][^\"']+[\"']", bundle))
            self.assertIn("/api/admin/reviews", bundle, "bundle build phải chứa bề mặt admin")


# --------------------------------------------------- 3. chạy thật module client


class AdminUiClientHarnessTests(unittest.TestCase):
    """Chạy module client admin bằng Node với fetch giả (bằng chứng thực thi)."""

    def test_node_harness_passes_every_client_check(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node không có trong PATH — harness client chưa chạy được")

        result = subprocess.run(
            [node, str(HARNESS)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        output = (result.stdout or "") + (result.stderr or "")
        self.assertEqual(result.returncode, 0, f"harness client thất bại:\n{output[-2000:]}")
        self.assertIn("ALL PASS", output)
        self.assertNotIn("FAIL", output)

    def test_harness_itself_uses_a_runtime_generated_token(self) -> None:
        source = self.read_harness()
        self.assertIn("randomBytes", source, "harness phải sinh token tại runtime")
        self.assertNotIn(FORBIDDEN_TOKEN_LITERAL, source)

    def read_harness(self) -> str:
        return HARNESS.read_text(encoding="utf-8", errors="replace")


class AdminUiRenderHarnessTests(unittest.TestCase):
    """Render THẬT các component admin bằng React + react-dom/server (esbuild)."""

    def test_node_render_harness_renders_every_admin_state_safely(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node không có trong PATH — harness render chưa chạy được")
        if not (ROOT / "node_modules" / "esbuild").exists():
            self.skipTest("node_modules/esbuild chưa có — cần npm install để chạy harness render")

        result = subprocess.run(
            [node, str(RENDER_HARNESS)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
        output = (result.stdout or "") + (result.stderr or "")
        self.assertEqual(result.returncode, 0, f"harness render thất bại:\n{output[-2000:]}")
        self.assertIn("ALL PASS", output)
        self.assertNotIn("FAIL", output)

    def test_render_harness_uses_an_obvious_test_token_not_a_literal(self) -> None:
        source = RENDER_HARNESS.read_text(encoding="utf-8", errors="replace")
        self.assertNotIn(FORBIDDEN_TOKEN_LITERAL, source)
        self.assertNotIn("ADMIN_TOKEN", source)  #: harness không đụng env token


if __name__ == "__main__":
    unittest.main()
