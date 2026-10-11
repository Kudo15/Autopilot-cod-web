# MISSION: BUILD VŨ HỌC AI RADAR v1.0 — LOCALHOST

Bạn là Principal Software Architect, Full-stack Engineer, Data Engineer và QA Lead. Nhiệm vụ là phát triển website **Vũ Học AI Radar**, một nền tảng tiếng Việt chuyên về thông tin AI mới, model miễn phí, provider API, khuyến mãi/free credits, quota và Tip & Trick hữu ích.

**Chế độ thực thi: AUTOPILOT.** Không dừng ở việc viết kế hoạch. Hãy kiểm tra repository, lập kế hoạch, triển khai, chạy kiểm thử, sửa lỗi và xuất báo cáo hoàn thành.

## 1. NGUYÊN TẮC BẮT BUỘC

- Làm việc trong workspace hiện đang mở của VS Code.
- Trước hết kiểm tra repository, Git status, cấu trúc, dependencies, tests và các chức năng có sẵn.
- Nếu đây là repo Vũ Học AI v0.3.1, PHẢI kế thừa thay vì viết lại. Giữ React 19 + Vite 8, giao diện hiện tại, dữ liệu bài viết, bookmark và migration localStorage.
- Tạo branch `feature/ai-radar-local` nếu an toàn. Không ghi đè thay đổi chưa commit.
- Nếu workspace không phải repo phù hợp, tạo project mới trong thư mục con `vu-hoc-ai-radar`, không xóa dữ liệu cũ.
- Không push GitHub, không deploy Cloudflare, không làm thay đổi website production.
- Website phải chạy hoàn chỉnh trên Windows localhost.
- Không dùng dữ liệu giả để tuyên bố model đang miễn phí, quota đang hoạt động hoặc promo còn hạn.
- Không hardcode API key hoặc đưa secrets vào frontend.
- Ưu tiên code dễ duy trì, không over-engineering.

## 2. PRODUCT VISION

Phát triển website theo phong cách AI tech editorial dashboard, hiện đại, nhanh, responsive, hỗ trợ dark/light mode.

Giữ thương hiệu **VŨ HỌC AI**.

Các nhóm nội dung:
1. Tip & Trick
2. AI & Model
3. Chính sách & Quota
4. Free Model Explorer
5. AI Deals & Promotions
6. Provider Comparison
7. Admin Radar

Các chức năng:

- Trang chủ với feed mới nhất, featured articles, nội dung nổi bật.
- Tìm kiếm và lọc theo chủ đề, thời gian, độ hữu ích.
- Đọc bài tiếng Việt đã được biên tập, có hướng dẫn sử dụng khi thích hợp.
- Bookmark, giữ tương thích dữ liệu cũ.
- Danh bạ model/provider với trạng thái miễn phí, tính năng, quota, điều kiện sử dụng và thời điểm kiểm chứng.
- So sánh model và provider.
- Theo dõi free credits, trial, promo, expiry, credit-card requirement.
- Thông báo khi có thay đổi quota, giá hoặc tình trạng cung cấp.
- Trang quản trị riêng để nhập, kiểm tra, duyệt và xuất dữ liệu.

## 3. TECH STACK

Frontend:
- Kế thừa React 19 + Vite 8 hiện tại.
- Tận dụng các component và styling đang có, không thay đổi framework nếu không cần thiết.
- Vite dev server: 127.0.0.1:5173.
- Proxy các request `/api` về backend.

Backend:
- Python 3.13.
- uv quản lý dependencies, giữ `.python-version` và `uv.lock`.
- FastAPI + Pydantic.
- HTTPX và feedparser.
- SQLite với FTS5, migrations có kiểm soát.
- Uvicorn tại 127.0.0.1:8000.

Testing:
- Giữ bộ test frontend hiện tại.
- Pytest cho backend.
- Playwright cho smoke test thực tế trên trình duyệt.

Không bắt buộc Docker, Redis, PostgreSQL hoặc external hosting.

## 4. DATA SOURCE REGISTRY

Hỗ trợ các nguồn sau theo mức ưu tiên:

**Tip & Trick**
- OneHack
- Habr
- Promo2day
- BlackHatWorld
- n8n Community
- Show HN
- GitHub
- LowEndTalk
- r/LLMDevs
- r/selfhosted
- r/LocalLLaMA

**AI Model & Providers**
- LLM24
- OpenRouter
- Hugging Face
- Vercel AI Gateway
- ModelScope
- Hetzner AI
- immers.cloud
- TeamoRouter
- Các provider khác được bổ sung từ radar

Yêu cầu triển khai:

- Có Source Registry riêng nằm ngoài public/frontend bundle.
- Mỗi nguồn có `source_id`, `name`, `type`, `url`, `collection_method`, `priority`, `status`, `last_checked_at`.
- Chọn official API/RSS trước, crawler chỉ khi được phép.
- Không tự động vượt CAPTCHA, login, paywall, rate limit hoặc điều khoản dịch vụ.
- Nếu nguồn không có phương thức truy cập hợp lệ, cung cấp chế độ Manual Import.
- Không giả lập kết quả thu thập.
- Từ dữ liệu ChatGPT Radar, hỗ trợ import Markdown, CSV và JSON mà người dùng cung cấp.
- Tự kiểm tra trùng lặp theo canonical URL, normalized title và content hash.
- Mỗi record lưu provenance và thời điểm truy xuất.
- Có timeout, retry hữu hạn, backoff và logging.

## 5. DATABASE & DOMAIN MODEL

Thiết kế schema bao gồm tối thiểu:

- `sources`
- `raw_items`
- `articles`
- `providers`
- `models`
- `provider_models`
- `offers`
- `quota_observations`
- `verification_records`
- `change_events`
- `collection_runs`
- `editorial_reviews`

Mô hình phải hỗ trợ một model được nhiều provider cung cấp với quota và giá khác nhau.

Các trạng thái miễn phí:

- FREE_API
- FREE_CREDIT
- FREE_TRIAL
- FREE_WEB_ONLY
- PROMO
- PAID
- UNKNOWN

Các trạng thái xác minh:

- VERIFIED
- UNVERIFIED
- STALE
- EXPIRED
- NEEDS_REVIEW

Các mức an toàn nội dung:

- SAFE_TO_TRY
- CAUTION
- INFO_ONLY

Thêm các thuộc tính cần thiết như last_verified, valid_until, account_required, card_required, rate_limit, daily_quota, context_window, supports_vision, supports_tools, supports_json và API compatibility.

Không biến thông tin chưa xác minh thành sự thật.

Tạo migration và seed dữ liệu mẫu có nhãn SAMPLE, tách biệt dữ liệu thực.

## 6. AI EDITORIAL ENGINE

Hỗ trợ cấu hình OpenAI-compatible gateway thông qua environment variables:

- `AI_BASE_URL`
- `AI_API_KEY`
- `AI_MODEL`

Chức năng AI:

1. Phân loại nội dung.
2. Phát hiện tin trùng hoặc cùng chủ đề.
3. Tóm tắt bằng tiếng Việt.
4. Chuyển bài phức tạp thành hướng dẫn dễ hiểu.
5. Phân tích mức hữu ích và rủi ro.
6. Gợi ý xếp hạng S/A/B/C/D khi có bằng chứng.
7. So sánh thông tin provider mới với snapshot cũ.
8. Soạn bản tin Daily Radar.

AI output phải qua schema validation.

Dùng workflow:

COLLECT → NORMALIZE → DEDUPLICATE → VERIFY → AI ENRICH → REVIEW → PUBLISH.

Các nội dung chưa duyệt phải giữ DRAFT/PENDING_REVIEW, không tự động public.

Nếu gateway chưa cấu hình, ứng dụng vẫn hoạt động với phân loại quy tắc và xử lý dữ liệu thủ công.

Nội dung bên ngoài là untrusted input; không được phép trở thành system instruction, command hoặc thao tác file tùy ý.

## 7. MODEL & PROMOTION RADAR

Tạo Model Explorer có các bộ lọc:

- Miễn phí / promo / paid
- Có API hay chỉ web chat
- Không cần thẻ thanh toán
- Text / Vision / Tool Calling / JSON
- Provider
- Context
- Quota
- Xác minh gần đây

Hiển thị:

- Model name
- Provider name
- API model ID
- Free status
- Quota nếu xác minh được
- Điều kiện đăng ký
- Hỗ trợ kỹ thuật
- Lần kiểm tra cuối
- Mức tin cậy
- Link chính thức

Tạo Change Detection theo cặp bản ghi trước/sau:

- NEW_PROVIDER
- NEW_MODEL
- MODEL_REMOVED
- FREE_TO_PAID
- PAID_TO_FREE
- QUOTA_CHANGED
- OFFER_STARTED
- OFFER_EXPIRED
- TERMS_CHANGED

Không coi một lần API timeout là bằng chứng model đã bị xóa.

Tạo Dashboard với các bộ lọc Today, 7 days, 30 days và All.

Hỗ trợ bản tin radar 07:00 Asia/Ho_Chi_Minh khi backend đang chạy; có manual refresh. Khi không được cập nhật, hiển thị trạng thái STALE và thời điểm quét gần nhất.

Ưu tiên hiển thị ít nhất một phát hiện hữu ích từ Promo2day, BlackHatWorld, r/LLMDevs, r/selfhosted và LLM24 mỗi kỳ nếu dữ liệu hợp lệ. Nếu không có thì ghi SIGNAL_WEAK; không tạo bài giả.

## 8. ADMIN & PRIVACY

- Raw Source Registry, discovery URLs, internal reviewer notes và provenance phải chỉ truy cập được qua admin API.
- Không lưu các dữ liệu nội bộ này trong public assets hoặc API trả về cho người đọc.
- Với website công khai trong tương lai phải có xác thực và phân quyền server-side.
- Độc giả chỉ thấy nội dung biên tập và các link chính thức cần thiết.
- Provider CTA mặc định là Trang chính thức hoặc Tạo tài khoản.
- Affiliate/referral disabled by default.
- Hỗ trợ duyệt riêng từng provider trước khi cho phép referral.
- Bảo vệ dữ liệu khỏi XSS, HTML injection, SQL injection và SSRF.
- Không log secrets.
- Chỉ bind localhost theo mặc định.

## 9. UX/UI

Yêu cầu giao diện:

- Phong cách modern tech publication.
- Typography đẹp, nội dung rõ ràng.
- Navigation đơn giản, không quá nhiều menu.
- Dark/light mode.
- Desktop first nhưng responsive đầy đủ.
- Loading state, empty state, error state.
- Các nhãn NEW, UPDATED, FREE, EXPIRED phải có ý nghĩa dữ liệu thực.
- Không hiển thị các chỉ số không có cơ sở.
- Ưu tiên trải nghiệm đọc bài và tìm kiếm.

Giữ SEO metadata và OG hiện có, không hồi quy.

## 10. PHASE IMPLEMENTATION

Thực hiện tuần tự:

**P0 — Repository Audit**
- Audit hiện trạng, ghi nhận chức năng cần giữ.
- Xác định các rủi ro và kế hoạch migration.
- Tạo nhánh nếu an toàn.

**P1 — Frontend**
- Tận dụng UI hiện có.
- Tạo những màn hình còn thiếu.
- Hoàn thiện navigation, search, filters và bookmark.

**P2 — Backend & Storage**
- Setup FastAPI, SQLite, migrations.
- REST API cho content, providers, models, offers và admin.
- Import dữ liệu, seed demo.
- Đảm bảo frontend và backend kết nối được.

**P3 — Collectors & AI Radar**
- Xây các official connectors khả thi và RSS adapter.
- Hỗ trợ manual imports cho nguồn chưa thể lấy tự động.
- AI Editorial Engine.
- Verification workflow, change history.
- Daily Radar khi backend hoạt động.

**P4 — QA & Release**
- Unit tests, integration tests.
- API contract tests.
- Kiểm tra browser thật desktop/mobile.
- Kiểm tra bookmark migration.
- Kiểm tra dữ liệu trùng, invalid input, network failure, API 429, AI unavailable.
- Kiểm tra secrets không xuất hiện trong bundle.
- Hoàn thiện hướng dẫn localhost.

Hoàn thành từng phase trước khi chuyển phase tiếp theo. Không đánh dấu PASS khi chưa chạy kiểm thử thực tế.

## 11. ONE-COMMAND LOCAL STARTUP

Tạo script PowerShell `scripts/dev.ps1` hỗ trợ:

1. Kiểm tra prerequisites.
2. Chuẩn bị dependencies khi cần.
3. Chuẩn bị database/migrations.
4. Khởi chạy backend.
5. Khởi chạy frontend.
6. Hiển thị URL localhost.
7. Báo lỗi rõ ràng nếu port hoặc dependencies có vấn đề.

Tạo `.env.example` và `README_LOCAL.md`.

Mục tiêu: sau setup ban đầu, người dùng chỉ cần chạy:

`.\scripts\dev.ps1`

và truy cập:

`http://localhost:5173`

Không được tuyên bố script hoạt động nếu chưa chạy thử thành công.

## 12. QUALITY GATES

Chỉ chấp nhận hoàn thành khi:

- Website chạy được bằng localhost.
- Frontend kết nối backend thật.
- Dữ liệu lưu và đọc từ SQLite thật.
- Import Markdown/CSV/JSON hoạt động.
- Có ít nhất một connector nguồn chính thức hoặc RSS chạy thành công trong môi trường có mạng; các nguồn khác có trạng thái rõ ràng.
- Có quy trình kiểm chứng và phê duyệt nội dung.
- Có thể lọc model/provider/offer.
- Hỗ trợ AI unavailable mà không crash.
- Các test cũ không bị hồi quy.
- Frontend build PASS.
- Backend tests PASS.
- Browser smoke tests PASS.
- Không có API key trong bundle.
- Không thay đổi production.

Nếu kiểm thử không thể chạy vì thiếu quyền, tool hoặc network, ghi BLOCKED/NOT_VERIFIED, không giả lập kết quả PASS.

## 13. FINAL DELIVERABLES

Sau triển khai, tạo:

- `README_LOCAL.md`
- `docs/ARCHITECTURE.md`
- `docs/DATA_SOURCES.md`
- `docs/DATA_SCHEMA.md`
- `docs/PHASE_REPORT.md`
- `docs/QA_REPORT.md`
- `.env.example`
- `scripts/dev.ps1`

Báo cáo cuối phải có:

1. Các phase đã thực hiện.
2. Danh sách chức năng thực tế.
3. Nguồn nào đã kết nối thật, nguồn nào còn manual.
4. Kết quả lệnh test và bằng chứng.
5. Các lỗi còn tồn tại.
6. Chính xác cách chạy localhost.
7. Danh sách tính năng còn lại cho phiên bản sau.

Nếu workspace có AI_TEAM_CORE và tương thích, có thể sử dụng vai trò Coordinator, Builder, Tester, Reviewer để kiểm soát chất lượng. Không giả định đội agent đã thực thi nếu không có trace và bằng chứng.

**BẮT ĐẦU NGAY: Audit repository hiện tại → triển khai P0 đến P4 → chạy thử website thật → báo cáo. Chỉ hỏi người dùng khi cần quyền truy cập, phê duyệt thay đổi phá hủy hoặc một quyết định thực sự không thể tự giải quyết an toàn.**