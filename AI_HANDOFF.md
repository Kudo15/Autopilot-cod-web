# Vũ Học AI — Final Handoff & Acceptance Evidence

Ngày: 2026-10-29 (UTC+07)  
Harness: Hermes GUI (`.team/scripts/route.mjs`, source `cli`)  
Workspace: `D:\anhvuxd_2026\VUHOCAI\Project\Autopilot cod web`  
Branch: `autopilot/run-live`  

---

## 1. Bảng đối chiếu bằng chứng nghiệm thu (Acceptance Matrix)

| Hạng mục kiểm thử | Lệnh thực thi / Nguồn quan sát | Kết quả đo được | Đánh giá & Ranh giới |
|---|---|---|---|
| Referee Phase 1 | `PYTHONIOENCODING=utf-8 python checks/p1.py` | **PASS (15/15)** | Exit 0. Scaffold, cấu hình Vite, bundle sạch secret |
| Referee Phase 2 | `PYTHONIOENCODING=utf-8 python checks/p2.py` | **PASS (9/9)** | Exit 0. Layout 7 nhóm, theme dark/light, 3 trạng thái |
| Referee Phase 3 | `PYTHONIOENCODING=utf-8 python checks/p3.py` | **PASS (13/13)** | Exit 0. Backend FastAPI, SQLite, health/articles |
| Referee Phase 4 | `PYTHONIOENCODING=utf-8 python checks/p4.py` | **PASS (15/15)** | Exit 0. 12 bảng MISSION, migration/seed idempotent |
| Referee Phase 5 | `PYTHONIOENCODING=utf-8 python checks/p5.py` | **PASS (11/11)** | Exit 0. Proxy FE<->BE 8000, 1 bài từ DB, build sạch |
| Full Backend Regression | `uv run python -m unittest discover -s backend/tests -p "test_*.py"` | **PASS (453/453)** | Exit 0 (5.059s). Toàn bộ 453 tests backend đều xanh |
| Focused S1 (Scheduler) | `test_radar_scheduler.py` | **PASS (19/19)** | Exit 0. Lease/reclaim SQLite, bounded retry, fake clock |
| Focused R1 (Promotion) | `test_promotion_radar.py` | **PASS (15/15)** | Exit 0. Lifecycle ưu đãi, allowlist, CTA/expiry boundary |
| Focused R2 (Repository) | `test_repository_explorer.py` | **PASS (13/13)** | Exit 0. Additive catalog, canonical GitHub URL, license filter |
| Frontend Production Build | `npm run build` | **PASS (warning)** | Exit 0 (860ms). Cảnh báo Node 22.11.0 thấp hơn khuyến nghị 22.12+ |
| Playwright E2E | `npx playwright test` | **PASS (3/3)** | Exit 0 (23.7s). Admin boundary 401, public desktop, public mobile |
| Git Diff Check | `git diff --check` | **PASS** | Exit 0. Không có trailing whitespace / conflict marker |
| Backup / Restore Drill | `.team/ops-drill` scripts | **PASS (fixture drill)** | Khớp 49 SQLite objects; DB gốc được bảo toàn nguyên vẹn |
| Startup Script Preflight | `pwsh -NoProfile -File scripts/dev.ps1 -Check` + real smoke | **PASS (exit 0)** | Check xanh; `-AutoStopSeconds 8 -NoInstall` started 127.0.0.1:8000/5173, migration + health/root HTTP UP, clean stop |
| Live RSS Ingest | Hermes GUI D1 bounded live run | **PASS (bounded)** | `https://hnrss.org/frontpage`, outbound ACCEPTED, SUCCESS/REAL, 20 items into in-memory SQLite; real DB md5/size/mtime unchanged |
| REAL / SAMPLE Boundary | `backend/data/radar.db` (read-only) | **VERIFIED** | 16 bảng; articles: REAL=1 (id 900002, PUBLISHED), SAMPLE=1 (DRAFT) |
| Secret Boundary Scan | `dist/assets/*.js` | **VERIFIED** | Không chứa API key (`sk-`), `ADMIN_TOKEN`, hay `AI_API_KEY` |

---

## 2. Nhật ký Worker & Reviewer Độc lập

| Nhiệm vụ / Module | Trạng thái Worker | Trạng thái Reviewer Độc lập | Ghi chú & Rủi ro tồn đọng |
|---|---|---|---|
| Q1 (Baseline regression fix) | COMPLETED | **APPROVED** (`q1-regression-review`) | Sửa auth-before-DB & fixture trôi ngày |
| Q2 (Playwright E2E + Mobile CSS) | COMPLETED | **NOT_VERIFIED** (`q2-mobile-fix-review3/4`) | Test 3/3 passed; reviewer bị timeout/stalled |
| D1 (Live RSS verification) | COMPLETED (bounded evidence) | **NOT_VERIFIED** | Live probe completed and DB isolation verified; Hermes session stalled while rewriting an existing report, so no independent reviewer approval is implied |
| S1 (Process-safe scheduler) | COMPLETED | **NOT_VERIFIED** (`s1-r2-review`) | 19/19 tests passed; reviewer bị stalled |
| R1 (Promotion Radar) | COMPLETED | **NOT_VERIFIED** (`r1-promotion-review`) | 15/15 tests passed; reviewer bị stalled |
| R2 (Repository Explorer) | COMPLETED | **NOT_VERIFIED** (`s1-r2-review`) | 13/13 tests passed; reviewer bị stalled |
| O1 (Operations preflight drill) | COMPLETED | **NOT_VERIFIED** (`o1-preflight-review`) | Fresh preflight + real auto-stop smoke pass; independent reviewer verdict still missing |

---

## [ĐÃ LÀM]

- Đã thu thập và tái kiểm tra toàn bộ bằng chứng định lượng thực tế trên worktree hiện tại theo chuẩn F1.
- Kiểm chứng độc lập các trọng tài referee P1–P5 (tất cả 100% PASS, exit code 0).
- Chạy toàn bộ 453 unit tests backend với kết quả 453/453 PASS (bao gồm các bộ test tập trung cho S1, R1, R2).
- Chạy production build frontend Vite đạt exit code 0 và Playwright E2E thật đạt 3/3 tests passed.
- Đối chiếu ranh giới cơ sở dữ liệu SQLite (16 bảng, REAL/SAMPLE bảo đảm) và quét sạch ranh giới secret trong dist assets.
- Cập nhật tài liệu handoff và báo cáo khoảng trống đúng chuẩn không thổi phồng kết quả.

## [BẰNG CHỨNG]

- Referee: P1 (15/15), P2 (9/9), P3 (13/13), P4 (15/15), P5 (11/11) — tất cả exit 0.
- Backend Suite: `uv run python -m unittest discover -s backend/tests -p "test_*.py"` → `Ran 453 tests in 5.059s; OK; exit=0`.
- Focused Suites: `test_radar_scheduler` (19/19, exit 0), `test_promotion_radar` (15/15, exit 0), `test_repository_explorer` (13/13, exit 0).
- Frontend Build: `npm run build` → exit 0 (Vite v7.3.7, 43 modules, dist/index.html + assets).
- Playwright E2E: `npx playwright test` → 3 passed (23.7s, exit 0).
- Git Diff: `git diff --check` → exit 0.
- Database: `backend/data/radar.db` chứa 16 bảng; `articles` có 1 bản ghi REAL (PUBLISHED) và 1 bản ghi SAMPLE (DRAFT).
- Startup: `scripts/dev.ps1 -Check` → exit 0; bounded real smoke on 127.0.0.1:8000/5173 → migration and HTTP checks UP, clean stop exit 0.
- Live RSS: Hermes GUI bounded run against `https://hnrss.org/frontpage` → `status=SUCCESS`, `data_origin=REAL`, 20 inserted into in-memory SQLite, collection run SUCCESS; real DB checksum/size/mtime unchanged.

## [RULING] NOT_READY

Không được tuyên bố phát hành sản phẩm (production release) ở phiên này vì:
1. Các reviewer độc lập của Hermes cho Q2, R1, S1+R2, O1 đều bị stalled trước khi đưa ra verdict chính thức (`NOT_VERIFIED`).

## ## Human Gate

Người vận hành cần đưa ra các quyết định và hành động sau trước khi nghiệm thu:

1. **Phê duyệt Reviewer Gate**: Thực hiện rà soát thủ công hoặc chạy lại các phiên reviewer độc lập cho Q2, S1, R1, R2, O1 để chốt verdict chính thức.
2. **Nâng cấp môi trường Node.js (tùy chọn)**: Cân nhắc nâng cấp Node.js từ `22.11.0` lên `22.12+` để loại bỏ hoàn toàn cảnh báo của Vite.

## F2 independent review update — Hermes GUI

- Reviewer `f2-final-review` completed a read-only review through Hermes GUI (`.team/results/f2-final-review.hermes-gui.jsonl`).
- It independently reproduced backend `453/453`, build exit 0, Playwright `3 passed`, referee P1–P5 PASS, and `git diff --check` exit 0.
- Verdict: `CHANGES_REQUESTED`, not approval. Live RSS and startup gates were subsequently closed by bounded evidence; missing component-level reviewer verdicts remain. Node 22.11 is informational only.

- Follow-up narrow Q2 reviewer `f3-q2-review` was dispatched through Hermes GUI but stalled after a blocked arbitrary-code tool attempt; it was stopped without edits. Q2 independent-review status remains `NOT_VERIFIED`, while the fresh Playwright result remains `3 passed`.

- Follow-up narrow O1 reviewer `f4-o1-review` inspected the preflight and backup/restore files but stalled before a verdict; it was stopped without edits. O1 independent-review status remains `NOT_VERIFIED`.

- Additional PLAN coverage run for Phase 6–11 focused modules (importers, model filters, changes/quota, collectors, editorial, inbox/admin, Daily Radar, scheduler, startup, backup) completed **311/311 PASS**, exit 0. This is local contract evidence only and does not close live-RSS or reviewer Human Gates.

- Follow-up file-only R1 reviewer `f5-r1-review` also stalled before a verdict; it was stopped without edits. R1 independent-review status remains `NOT_VERIFIED`.

## Continuation audit — fresh progress

The resumed audit closed the live RSS and startup environment gates with fresh evidence. Independent Hermes component reviewers still have no formal verdict, so status remains **NOT_READY** and no release approval is claimed.
