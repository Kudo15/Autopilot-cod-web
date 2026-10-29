# Task R1 — Promotion Radar lifecycle + public allowlist

## Mục tiêu

Hoàn thiện Promotion Radar trong Autopilot cod web. Người dùng public cần xem
được các offer thật đã xác minh và còn hiệu lực; dữ liệu SAMPLE, EXPIRED,
UNVERIFIED, thiếu official CTA hoặc hết hạn tuyệt đối không được xuất hiện như
ưu đãi active. Admin cần có đường review/xác minh offer an toàn.

## Phạm vi được phép sửa

Chỉ được sửa các file sau (và file test/e2e mới nằm trong các thư mục này):

- `backend/app/main.py`
- `backend/app/migrate.py` (chỉ additive schema nếu thật sự cần)
- `backend/tests/test_promotion_radar.py` (tạo mới) và test backend hẹp liên quan
- `src/data/groups.js`
- `src/App.jsx`
- `src/components/PromotionView.jsx` (tạo mới)
- `src/components/admin/AdminView.jsx` và `src/components/admin/adminClient.js` nếu cần
- `src/styles.css`
- `e2e/promotion*.spec.js` (tạo mới nếu cần)
- `.team/results/**` chỉ là output

Không sửa `checks/`, `PLAN.md`, `docs/MISSION.md`, `backend/data/radar.db`,
Vu-Agent-Room-PC, hay các phần không liên quan.

## Hợp đồng bắt buộc

1. Tạo GET public `/api/offers` với query allowlist nhỏ, bounded `limit` (mặc
   định và tối đa rõ ràng), filter `q`, `provider`, `offer_type`, `status` nếu
   cần. Unknown query -> 422.
2. Public response chỉ trả cột allowlist: title, provider, offer type,
   description/terms, starts_at/ends_at, account_required, card_required,
   verification_status, last_verified/valid_until, official CTA URL. Không trả
   code nội bộ, raw snapshots, reviewer note, secret, hoặc provenance nội bộ.
3. Public mặc định chỉ gồm `data_origin='REAL'`, `verification_status='VERIFIED'`,
   chưa hết hạn tại `now`, và có official URL hợp lệ `https://` hoặc `http://`.
   SAMPLE/EXPIRED/UNVERIFIED/thiếu CTA không được coi là active. Nếu filter
   status cho phép xem lịch sử, phải gắn trạng thái rõ và không gọi là active.
4. Admin POST `/api/admin/offers/{id}/verification` (hoặc endpoint tương đương)
   phải gọi `require_admin` trước DB, yêu cầu status/evidence/note/method hợp lệ,
   không verify SAMPLE, ghi `verification_records` liên kết offer, cập nhật
   `offers.verification_status`, `last_verified` chỉ khi VERIFIED; không bịa
   quota/credit.
5. UI nhóm `ai-deals` gọi `/api/offers`, có loading/error/empty, search/filter,
   card hiển thị eligibility (account/card), expiry/verification rõ ràng và
   CTA chính thức bằng link an toàn. Không render code/SAMPLE.
6. Viết test backend bằng DB tạm cho allowlist, SAMPLE/expiry/CTA boundary,
   unknown query, admin auth ordering và verification lifecycle. Nếu thêm e2e,
   test phải chạy browser thật localhost, không đánh dấu expected-failure.
7. Không gọi internet trong test; không seed dữ liệu thật; không thay đổi DB thật.

## Verify bắt buộc

- focused `uv run python -m unittest ...test_promotion_radar...` exit 0
- full `uv run python -m unittest discover -s backend/tests -p "test_*.py" -v` exit 0
- `npm run build` exit 0
- nếu có e2e: `npx playwright test e2e/promotion*.spec.js` exit 0
- `git diff --check` và kiểm tra đúng files_allowed

## Báo cáo cuối worker

Phải có đúng các marker:

`[ĐÃ LÀM]` files + endpoint/UI summary

`[BẰNG CHỨNG]` exact commands + exit codes + test counts

`[RULING]` PASS hoặc NOT_VERIFIED (không bịa PASS)

`## Bước tiếp theo` remaining caveat nếu có.
