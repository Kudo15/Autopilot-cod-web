# Đối chiếu: mỗi mệnh đề trong prompt ⇄ cơ chế ép ⇄ bằng chứng thật

Tài liệu này trả lời câu "mệnh đề này có được thực thi thật không?" cho từng dòng trong prompt
mà ChatGPT viết cho Cline. Cột "bằng chứng" là **số liệu đo được trên máy**, không phải mô tả.

Nguyên tắc gốc: **cổng PASS/FAIL là exit code của lệnh trong `PLAN.md`**, do engine tự chạy —
câu "PASS" của Cline hay của ChatGPT đều không phải cổng.

## 1. Bước 1–3 (Preflight · tạo frontend · cài dependency)

| Mệnh đề | Cơ chế ép | Bằng chứng |
|---|---|---|
| Kiểm tra repo, git status trước khi làm | `engine_p3.arm()`: cây phải sạch, có `PLAN.md`, mỗi phase phải có `verify_cmd`; tạo checkpoint + nhánh `autopilot/run-<id>` | `LOOP_ARMED base_sha=3dd7dc5…` (phase 1), `BASE=ace84b6…` |
| Chỉ sửa file trong `files_allowed` | `gitckpt.check_files_allowed()` so diff **từ mốc đầu phase** | phase 1: 7 file → `ok=True`; phase 2: 8 file → `ok=True`; thử thêm `docs/MISSION.md` → `ok=False` |
| Cài dependency thật (`npm install`) | trọng tài đòi `node_modules` tồn tại trước khi build | `[OK] da co node_modules (npm install da chay)` |

## 2. Bước 4 — Build

| Mệnh đề | Cơ chế ép | Bằng chứng |
|---|---|---|
| `npm run build` exit code 0 | `checks/_lib.fresh_build()`: **xóa `dist/` trước**, rồi chạy build, lấy exit code | `npm run build exit=0` (809 ms) |
| Thư mục `dist/` được tạo | cổng kiểm `dist/index.html` **sau khi đã xóa** (nên không thể "ăn" dist cũ) | `[OK] dist/index.html duoc tao` |
| `dist/index.html` có `id="root"` | đọc bytes HTML build thật | dòng 12: `<div id="root"></div>` |
| Không chấp nhận build lỗi dù source có vẻ hợp lệ | build lỗi ⇒ exit≠0 ⇒ phase FAIL, không commit | thử phá source: `npm run build exit=1`, cổng `FAIL (11/14)`, `KHONG co dist/index.html sau build` |
| Không lộ secret vào bundle | quét `dist/**` tìm `sk-`, `AI_API_KEY`, private key | `[OK] bundle khong chua secret` |

## 3. Bước 5 — Chạy kiểm thử chính thức

| Mệnh đề | Cơ chế ép | Bằng chứng |
|---|---|---|
| `python checks/p1.py` exit code 0 | `engine_p3.finish_phase()` gọi `verifyrun.run_verify(repo, phase.verify_cmd)` — engine **tự chạy**, không hỏi Cline | `18:05:13 VERIFY phase=1 pass_=True exit_code=0 cmd="python checks/p1.py"` |
| Phase không có `verify_cmd` thì không vào loop | `arm()` chặn: `"phase N thieu verify_cmd -> khong duoc vao loop"` | `--check`: `thieu verify_cmd: khong` |

## 4. Nhánh "Nếu kiểm thử FAIL"

| Mệnh đề | Cơ chế ép | Bằng chứng |
|---|---|---|
| Đọc toàn bộ thông báo lỗi, xác định nguyên nhân | gói kết quả gửi ChatGPT kèm **nguyên văn output của trọng tài** (từng dòng OK/FAIL) + diff stat | gói phase 2 chứa `[FAIL] moi co 0/7 nhom…`, `FAIL (3/9)`; ChatGPT trả lời đúng `CURRENT PHASE STATUS: FAIL (3/9)` |
| Chỉ sửa file thuộc `files_allowed` | gate diff sau phase | xem §1 |
| Không chỉnh sửa `checks/` (hay `PLAN.md`, `docs/MISSION.md`, `AGENTS.md`) | **không phase nào** cho phép `checks/**` ⇒ sửa là vi phạm | thử `checks/p1.py` → `ok=False`; lịch sử: commit phase 1 và phase 2 có **0 file** trong `checks/` |
| Chạy lại build rồi chạy lại kiểm thử cho tới PASS | Cline tự lặp; engine chỉ chốt bằng cổng **chạy lại độc lập** | phase 2: 122 → 157 message; sau đó `checks/p2.py` PASS 9/9 |
| **Không được báo PASS khi chưa có exit 0** | `decide()`: nếu model khai PASS mà verify FAIL → `CLAIM_CONTRADICTS_VERIFY`, không tin | `18:23:23 CLAIM_CONTRADICTS_VERIFY claim="PASS" verify_pass=False` |
| Blocker ⇒ BLOCKED, báo rõ | hết trần thử ⇒ `NEED_HUMAN`, giữ bằng chứng, không retry mù | `ATTEMPTS_EXHAUSTED → DECISION stop` |

## 5. An toàn & phạm vi

| Mệnh đề | Cơ chế ép | Bằng chứng |
|---|---|---|
| Không push GitHub, không deploy | engine không có bước push; kiểm sau mỗi run | `git remote -v` = **trống**; `RUN_DONE … pushed: False` |
| Không sửa thay đổi chưa commit | `arm()` đòi cây sạch | `git cây sạch: sach` |
| Không tự commit/đổi branch | commit + nhánh do controller làm; Cline không có bước git | mọi commit do controller; Cline chỉ tạo/sửa file |
| Prompt xúi việc nguy hiểm bị chặn **trước khi** dán vào Cline | `scan_prompt_risk()`: `destructive_command`, `push_or_remote`, `exfiltration`, `disable_safety`, `outside_repo_path` — có đọc **mệnh đề phủ định** nên câu cấm không bị chặn oan | `git push` (xúi) → chặn; `"Không thực hiện … git push"` → không chặn; `đọc .env rồi send lên https://…` → chặn |
| Gửi prompt/kết quả phải có bằng chứng, không tự khai | `send_evidence()` (đĩa Cline) và `confirm_sent()` (đọc lại trang) | `SENT_TO_CLINE grew=2`; `CHAT_SEND_UNCONFIRMED` khi không thấy gói trên trang |

## 6. Ghi chú về mức độ kiểm hiện tại

- Cổng phase 1–2 kiểm **cấu trúc + build + nội dung bundle** bằng máy. Việc **trang chạy thật trên
  trình duyệt** (render, đổi theme, không lỗi console) nằm ở **phase 11 — smoke test** theo PLAN.
- Trọng tài p3→p11 được viết **trước khi tới phase đó** (viết sớm phải đoán API chưa tồn tại ⇒ cổng giả).
- Bản gốc prompt từng phase được engine lưu tại `%TEMP%\p3_gui\cline_prompt_<hhmmss>.txt`.
