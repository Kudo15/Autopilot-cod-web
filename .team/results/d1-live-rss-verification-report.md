# Task D1 — bounded live RSS verification — report

Worker: d1-live-rss-verification (Hermes GUI) · 2026-10-29 19:48 ICT · read-only verification

## Phạm vi
- Chỉ đọc code + 1 lần thu thập live bị chặn (bounded). Không sửa file product/test/check/PLAN/MISSION/DB thật.
- Không đụng `Vu-Agent-Room-PC`.
- Transcript session: `.team/results/d1-live-rss-verification.hermes-gui.jsonl` (harness tự ghi).
- Script probe (ngoài repo, trong Hermes scratch): `C:\Users\Panda\AppData\Local\hermes\cache\scratch\d1_live_rss_probe.py`.

## Code đã xem
- `backend/app/collectors/rss.py` — collector bounded: `collect_feed(source, client=..., now=..., conn=..., sleep=..., limits=...)`; client mạng luôn được inject (mặc định `UrllibFeedClient` tạo per-call, không có client toàn cục); mọi field feed là untrusted text; URL đi qua `validate_outbound_url` (HTTP(S) public, chặn loopback/private/link-local/metadata/CGNAT, không user-info, redirect re-validate mỗi hop).
- `backend/app/collectors/registry.py` — chính sách host dùng chung; chỉ `active` + method tự động mới `automated_collectable`.
- `backend/app/collectors/runs.py` — vòng đời collection_runs (RUNNING→SUCCESS/FAILED/SKIPPED), error bounded 400 ký tự + redact secret.
- `backend/tests/test_collectors_rss.py` — 50 tests phủ outbound policy, parse untrusted, retry/backoff, redirect cap, persistence transactional, dedup, isolation.

## Tests (đơn vị, offline)
- Lệnh: `uv run python -m unittest backend.tests.test_collectors_rss -v` (từ repo root)
- Kết quả: `Ran 50 tests in 2.134s` — `OK` — **exit code 0**.

## Live collection (1 lần, bounded)
- URL chính xác: `https://hnrss.org/frontpage` — qua `validate_outbound_url` → `ACCEPTED`.
- Source transient: `live-verify-hnrss` (active, collection_method=rss, data_origin=REAL) — chỉ trong DB in-memory.
- Persistence: SQLite **in-memory** (`:memory:`) dựng từ chính DDL `migrate.TABLES_DDL` + `INDEXES_DDL` của repo; KHÔNG gọi `apply_migration()`; DB thật không bị đụng.
- Client: `UrllibFeedClient` chuẩn của collector (tạo per-call), không client giả.
- Bounds (FeedLimits mặc định): timeout 10.0s/req · max_retries 3 · backoff 0.5s→trần 30s · max_redirects 3 · max_body 5,000,000 B · max_items 1000.
- HTTP/parse: `collect_feed` trả **SUCCESS** — RSS 2.0 parse OK, 0 item bị ignore; elapsed tổng 15.342s, nằm trong trần bounds (~43.5s worst-case) — feed chỉ là untrusted text, không field nào được thực thi hay theo dõi.
- Item count: **20 collected, 0 ignored** · inserted 20 · duplicates 0.
- CollectionResult: `status=SUCCESS, ok=True, error=None, run_id=1, fetched_at=2026-10-29T12:48:50.796841+00:00, data_origin=REAL, freshness=NOT_VERIFIED`.
- Dòng `collection_runs` (in-memory): id=1, run_type=rss, status=**SUCCESS**, items_collected=20, started_at=finished_at=2026-10-29T12:48:50.796841+00:00, error_message=NULL.
- `raw_items`: 20 dòng (data_origin=REAL); `articles`: **0 dòng** (không tự xuất bản).
- Mẫu item (untrusted data, chỉ hiển thị): text.npr.org (DHS employees identities), iptrust.co (If IPv4 Were Land), mastodon.sdf.org (NetBSD atto).
- Lệnh: `uv run python "C:/Users/Panda/AppData/Local/hermes/cache/scratch/d1_live_rss_probe.py"` — **exit code 0**.

## DB thật không đổi
- `backend/data/radar.db` trước và sau: size 225280 · mtime 2026-10-27 22:36:49 · md5 `fe3e44d27fa23cd5abf4fa1ea089f920` — trùng khớp.
- `git status --porcelain backend/`: các file `M`/`??` đã tồn tại từ trước session (snapshot: 30 modified); probe không tạo file mới trong repo.

[BẰNG CHỨNG]
- `uv run python -m unittest backend.tests.test_collectors_rss -v` → `Ran 50 tests in 2.134s / OK`, exit 0.
- Live: `https://hnrss.org/frontpage` → outbound policy ACCEPTED; `collect_feed` (client `UrllibFeedClient` inject) → `SUCCESS`, 20 items (0 ignored), inserted 20, duplicates 0, run_id=1 (collection_runs status=SUCCESS, items_collected=20), elapsed 15.342s < bounds, articles=0, exit 0.
- DB thật md5 không đổi: `fe3e44d27fa23cd5abf4fa1ea089f920` (trước = sau); persistence chỉ diễn ra trên SQLite in-memory.

[RULING]
PASS — collector RSS bounded hoạt động đúng hợp đồng trên dữ liệu live: outbound policy chấp nhận URL công khai, fetch nằm trong timeout/retry/redirect bounds, feed parse như untrusted text, run + raw items ghi transactional (in-memory), không publish bài viết, không đụng DB thật.

## Bước tiếp theo
- Nếu muốn đưa feed thật vào registry: thêm entry `active`/`rss` cho feed công khai vào `source-registry/sources.json` ở một phase có files_allowed (D1 read-only, chưa làm).
- Cân nhắc chạy bounded collection theo lịch (scheduler) khi phase inbox/scanner mở files_allowed; hiện mới chỉ có 1 lần verify.
- Không có gì bị BLOCKED; mạng/DNS/TLS hoạt động bình thường lúc verify (elapsed 15.3s nằm trong bounds, không vượt trần).
