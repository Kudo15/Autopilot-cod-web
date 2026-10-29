# Remaining Gaps — fresh evidence register

## Beta update 2026-10-29 (đọc trước)

Kết quả Beta: **PASS_WITH_WARNINGS (BETA LOCAL)** — hồ sơ đầy đủ: [`../FINAL_ACCEPTANCE_BETA.md`](../FINAL_ACCEPTANCE_BETA.md).
Bản cập nhật này **supersedes** các con số phiên 2026-10-27 dưới đây (giữ nguyên làm lịch sử, không xoá):
Node 22.11.0 → **26.13.0** (build không còn cảnh báo Vite Node floor); full backend **453/453** →
**466 tests OK** (kèm ResourceWarning SQLite); Playwright **3 passed** → **4 passed**; scheduler
in-memory (deferred-to-request) → task bền **`VuHocAIRadar-Daily`** trên Task Scheduler (Ready;
manual trigger 2026-10-29 21:08, LastTaskResult 0; next run 2026-10-30 07:00 — **NOT_VERIFIED** cho
chạy tự động tương lai). Verdict reviewer độc lập: **WAIVED** theo user — các dòng
"IMPLEMENTED; REVIEW NOT_VERIFIED" bên dưới **không** tự đổi thành PASS.

Ngày: 2026-10-29 (SEA Standard Time, UTC+07)  
Worktree: `D:\anhvuxd_2026\VUHOCAI\Project\Autopilot cod web`  
Harness: Hermes GUI, source `cli`, bounded continuation pid 26252  
Nguyên tắc: Mỗi mục Definition-of-Done (DoD) được gán đúng nhãn `PASS`, `FAIL`, `BLOCKED`, hoặc `NOT_VERIFIED` kèm bằng chứng thực tế đo trong phiên audit.

## 1. Bảng đối chiếu Definition-of-Done (DoD)

| DoD item (MISSION / finish-all.md) | Trạng thái | Lệnh / Quan sát bằng chứng | Phân loại & Rủi ro |
|---|---|---|---|
| P1 frontend scaffold & build | **PASS** | `python checks/p1.py` exit 0 (15/15 checks) | Xong; package.json/index.html/#root/bundle sạch secret |
| P2 UI layout, 7 nhóm, dark/light, 3 states | **PASS** | `python checks/p2.py` exit 0 (9/9 checks) | Xong; 7/7 nhãn có mặt trong dist |
| P3 FastAPI backend, SQLite, health/articles | **PASS** | `python checks/p3.py` exit 0 (13/13 checks) | Xong; uvicorn cổng tạm, SQLite 14 bảng, health ok |
| P4 Schema 12 bảng, idempotent migration & seed | **PASS** | `python checks/p4.py` exit 0 (15/15 checks) | Xong; 12 bảng MISSION, 24 bản ghi trước/sau, 58 ô SAMPLE |
| P5 Nối FE↔BE proxy /api và feed SQLite | **PASS** | `python checks/p5.py` exit 0 (11/11 checks) | Xong; proxy 8000, 1 bài từ DB, build exit 0 |
| Frontend production build (`npm run build`) | **PASS (warning)** | `npm run build` exit 0, 43 modules, dist/index.html + assets | Node 22.11.0 thấp hơn floor Vite khuyến nghị 22.12+; build vẫn thành công |
| Full backend regression suite (`unittest discover`) | **PASS** | Fresh current run: 453/453, exit 0 | Includes S1 (19/19), R1 (15/15), R2 (13/13) tests |
| Deterministic baseline fixtures | **PASS with minor residual** | `fresh_today_vn_timestamp()`; focused 3-test exit 0; reviewer ghi nhận race cực nhỏ nếu đúng VN midnight | Không chặn; có thể harden bằng clock injection trong follow-up |
| SQLite table & REAL/SAMPLE boundary | **PASS (verified)** | Truy vấn read-only `backend/data/radar.db`: 16 bảng; articles: REAL=1, SAMPLE=1 | Đạt; REAL id 900002 có provenance đầy đủ; SAMPLE nằm ở DRAFT/không tự public |
| Browser E2E suite & public/admin journeys | **PASS** | Playwright harness tồn tại; fresh `npx playwright test` chạy 3 passed, exit 0 (localhost, admin boundary + desktop + mobile) | Không còn blocker ở harness; reviewer độc lập Q2 mobile chưa có verdict |
| Mobile/desktop public/private browser proof | **PASS (fresh)** | Browser thật: desktop + mobile feed, 7 nhóm, public allowlist/provenance và admin 401 đều đạt; 3 passed, exit 0 | Giữ assertion strict; reviewer Q2 mobile NOT_VERIFIED do session bị dừng |
| Server-side source registry & isolation | **PASS (verified)** | `source-registry/sources.json` tồn tại; dist bundle grep 0 match marker registry/provenance | Đạt ranh giới bảo mật: registry nằm ngoài frontend bundle |
| Permitted external collection path (RSS/Atom) | **PASS (bounded live)** | Hermes GUI D1 ran one live fetch against `https://hnrss.org/frontpage`: outbound policy ACCEPTED, `status=SUCCESS`, `data_origin=REAL`, 20 items inserted into an in-memory SQLite DB, `collection_runs.status=SUCCESS`; real `backend/data/radar.db` md5/size/mtime unchanged | Live transport and persistence path verified once; feed freshness remains a source-property and is not asserted as editorial truth |
| Process-safe Daily Radar scheduler | **IMPLEMENTED; REVIEW NOT_VERIFIED** | Durable `radar_schedule_runs`, lease/reclaim/bounded retry, completed idempotence, fake-clock tests; focused 19/19 and full 453/453 | Hermes independent reviewer stalled; keep review gate explicit |
| Promotion Radar lifecycle & public allowlist | **IMPLEMENTED; REVIEW NOT_VERIFIED** | API `/api/offers`, verified offer lifecycle, SAMPLE/expiry/CTA boundary tests và UI `PromotionView` đã có; Hermes reviewer chưa trả verdict | Cần independent review thành công trước khi gọi PASS |
| GitHub repository explorer | **IMPLEMENTED; REVIEW NOT_VERIFIED** | Additive catalog schema, bounded `/api/repositories`, GitHub canonical/REAL+VERIFIED gates, UI `RepositoryView`, focused tests; Hermes reviewer chưa trả verdict | Cần independent review thành công trước khi gọi PASS |
| Local startup script (`scripts/dev.ps1 -Check`) | **PASS (fresh)** | `pwsh -NoProfile -File scripts/dev.ps1 -Check` exit 0; real `-AutoStopSeconds 8 -NoInstall` smoke started backend/frontend on 127.0.0.1:8000/5173, health + root HTTP UP, migration OK, clean auto-stop exit 0 | Node 22.11 warning remains informational; ports free after smoke |
| Backup & restore scripts | **PASS (fixture drill)** | Backup/restore trên `.team/ops-drill` tạo bản sao và restore thành công; DB gốc không bị thay đổi; 49 SQLite objects khớp | Drill dùng bản sao workspace, chưa restore đè DB production/local thật |
| Secret boundary (không lộ secret ra bundle/code) | **PASS (verified)** | p1/p4/p5 fresh check PASS; grep dist/assets không tìm thấy `sk-`, `ADMIN_TOKEN`, `AI_API_KEY` | Đạt |

## 4. Final acceptance evidence — 2026-10-27

- Fresh full backend suite: **453/453 PASS**, exit 0.
- Fresh frontend build: **PASS**, `npm run build` exit 0; Vite still warns that Node `22.11.0` is below its recommended `22.12+` floor.
- Fresh browser suite: **3 passed** (admin boundary, public desktop, public mobile), exit 0.
- Fresh referee checks: P1 `15/15`, P2 `9/9`, P3 `13/13`, P4 `15/15`, P5 `11/11`, all exit 0.
- `git diff --check`: exit 0; only normal LF/CRLF conversion warnings.
- Final verdict: **NOT_READY**. Live RSS and startup gates are now closed by bounded fresh evidence. Human Gate remains for independent Hermes reviewer verdicts for Q2/R1/S1+R2/O1; no unsupported component approval is claimed.

### PLAN Phase 6–11 focused contract run

To complement the referee checks that exist only for P1–P5, the coordinator ran the focused test modules covering the remaining PLAN contracts (import/normalize, model filters, change/quota, collectors/registry/RSS, editorial gateway/rules, inbox/editorial/admin, Daily Radar, scheduler, startup, and backup scripts):

`uv run python -m unittest backend.tests.test_importers backend.tests.test_normalize backend.tests.test_models_api backend.tests.test_radar_changes backend.tests.test_collectors_registry backend.tests.test_collectors_rss backend.tests.test_editorial_gateway backend.tests.test_editorial_rules backend.tests.test_inbox_editorial backend.tests.test_inbox_admin_api backend.tests.test_radar_daily backend.tests.test_radar_scheduler backend.tests.test_startup_script backend.tests.test_backup_scripts`

Result: **311 tests PASS**, exit 0. This proves the local focused contracts; it does not close the separate live-RSS or independent-review Human Gates.

## 2. Khoảng trống theo mức ưu tiên (Priority Gap Register)

| Priority | Mã | Khoảng trống | Trạng thái | Hành động khắc phục kế tiếp |
|---|---|---|---|---|
| **CLOSED** | G1 | Daily Radar fresh REAL signal bị phân loại `SIGNAL_WEAK` (2 tests hỏng) | **PASS** | Q1 worker + reviewer: fixture động, production logic giữ nguyên, focused/full tests xanh |
| **CLOSED** | G2 | `test_admin_workflow` trả 500 thay vì 401 khi chạy không có `ADMIN_TOKEN` | **PASS** | Q1 worker + reviewer: auth-before-config ordering, auth-before-DB giữ nguyên |
| **CLOSED** | G3 | Thiếu harness Browser E2E trong repo | **PASS** | Q2 worker thêm Playwright config/specs; fresh suite 3/3 exit 0 |
| **CLOSED** | G4 | Tách biệt public/private chưa được kiểm chứng qua trình duyệt thật | **PASS (fresh)** | Q2 browser flows xác nhận public allowlist/provenance sạch và admin endpoints 401 |
| **CLOSED** | G5 | Chưa chứng minh thu thập nguồn thật có mạng (live collection) | **PASS** | D1 Hermes GUI bounded run: hnrss.org/frontpage, 20 REAL items, collection_run SUCCESS in-memory, real DB unchanged |
| **HIGH** | G6 | Scheduler chạy định kỳ chưa có cơ chế khóa tiến trình an toàn khi restart | **IMPLEMENTED; REVIEW NOT_VERIFIED** | Durable scheduler and 19 focused tests pass; reviewer verdict still missing |
| **MEDIUM** | G7 | Promotion Radar & Repository Explorer chưa có màn hình/API lọc chuyên dụng | **IMPLEMENTED; REVIEW NOT_VERIFIED** | R1/R2 API+UI+tests đã có; independent review chưa kết thúc |
| **MEDIUM** | G8 | Drill backup/restore chưa chạy thử nghiệm trên bản sao DB thật | **CLOSED (fixture)** | Đã chạy backup/restore trên bản sao `.team/ops-drill`; không đụng DB gốc |
| **CLOSED** | G9 | Cổng 8000 bị tiến trình python uvicorn cũ chiếm giữ (PID 17468) | **PASS** | PID no longer present; `scripts/dev.ps1 -Check` exit 0 and bounded real startup smoke completed cleanly |
| **LOW** | G10 | Node.js v22.11.0 thấp hơn floor Vite v7 (yêu cầu 22.12+) | **CẢNH BÁO** | Nâng Node lên 22.12+ hoặc giữ nguyên vì build hiện tại vẫn exit 0 |

## 3. Ranh giới giữa Bằng chứng Fresh và Báo cáo Lịch sử

1. **`docs/QA_REPORT.md` (2026-10-25)**: Báo cáo cũ tuyên bố 330 tests OK. Hiện tại suite đã có 404 tests và có 2 failure thật (trôi ngày) — tài liệu QA cũ là **LỊCH SỬ**, không còn giá trị chứng nhận hiện trạng.
2. **`.team/audit.md` (2026-10-24)**: Báo cáo audit P0 cũ ghi nhận Phase 5 FAIL. Hiện tại Phase 5 đã **PASS fresh** (11/11).
3. **Mọi kết luận trong tài liệu này** đều được đối chiếu trực tiếp từ lệnh thực thi trên máy trong phiên 2026-10-27.
