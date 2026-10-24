"""ADMIN_TOKEN helper — ranh giới xác thực phía server cho mọi route /api/admin/*.

Hợp đồng (task 010 / P8b):
- Token kỳ vọng chỉ đọc từ ``os.environ`` tại thời điểm request; cấu hình thiếu
  sẽ trả về lỗi cấu hình server rõ ràng, KHÔNG bao giờ tiết lộ giá trị secret.
- Chỉ chấp nhận ``Authorization: Bearer <token>`` hoặc header ``X-Admin-Token``;
  thiếu token -> 401, sai token -> 403.
- Không token nào được hardcode, đóng gói, nằm trong JSON hay log.
- Header HTTP là latin-1, nên ADMIN_TOKEN thực tế phải là ASCII (token sinh ngẫu
  nhiên/hex là đủ); token ngoài ASCII sẽ bị từ chối 403 chứ không gây lỗi 500.
"""
from __future__ import annotations

import hmac
import os

from fastapi import HTTPException, Request

#: Tên biến môi trường duy nhất chứa token admin kỳ vọng.
ADMIN_TOKEN_ENV = "ADMIN_TOKEN"


class AdminConfigurationError(RuntimeError):
    """Server chưa cấu hình ADMIN_TOKEN — không thể thực thi yêu cầu admin."""


def expected_admin_token() -> str:
    """Đọc token kỳ vọng từ environment ngay tại thời điểm request."""
    token = os.environ.get(ADMIN_TOKEN_ENV, "")
    if not token:
        raise AdminConfigurationError(
            f"server is missing required {ADMIN_TOKEN_ENV} environment variable"
        )
    return token


def _supplied_credential(
    authorization: str | None, x_admin_token: str | None
) -> tuple[bool, str]:
    """Phân loại credential admin: (đã_trình?, token).

    - (False, "") — không header admin nào, hoặc ``Bearer`` trần (thiếu token) -> 401.
    - (True, "")  — có header nhưng scheme không hỗ trợ (vd Basic) -> 403.
    - (True, tok) — token ứng viên cần so khớp.
    """
    if authorization is not None and authorization.strip():
        if authorization.startswith("Bearer "):
            value = authorization[len("Bearer "):].strip()
            # "Bearer" không kèm giá trị = thiếu token, không phải token sai.
            return (bool(value), value)
        return (True, "")
    if x_admin_token is not None and x_admin_token.strip():
        return (True, x_admin_token.strip())
    return (False, "")


def require_admin(
    request: Request | None = None,
    *,
    authorization: str | None = None,
    x_admin_token: str | None = None,
) -> None:
    """Bảo vệ một route admin — gọi ở dòng đầu mỗi handler, TRƯỚC khi chạm DB.

    Nhận trực tiếp một starlette Request (đường đi bình thường), hoặc hai giá trị
    header khi cần kiểm tra tách rời. Token sai luôn trả về thông báo chung, không
    bao giờ echo token kỳ vọng.

    Raises:
        HTTPException 500: ADMIN_TOKEN chưa được cấu hình (không kèm secret).
        HTTPException 401: thiếu token.
        HTTPException 403: token không khớp / scheme không được hỗ trợ.
    """
    if request is not None:
        authorization = request.headers.get("authorization")
        x_admin_token = request.headers.get("x-admin-token")

    try:
        expected = expected_admin_token()
    except AdminConfigurationError as error:
        # Chỉ báo tên biến + lý do — tuyệt đối không in giá trị token nào.
        raise HTTPException(status_code=500, detail=str(error)) from error

    presented, supplied = _supplied_credential(authorization, x_admin_token)
    if not presented:
        raise HTTPException(status_code=401, detail="admin token is required")
    # So sánh hằng thời gian trên bytes: không crash với token chứa ký tự ngoài ASCII.
    if not supplied or not hmac.compare_digest(
        supplied.encode("utf-8"), expected.encode("utf-8")
    ):
        raise HTTPException(status_code=403, detail="invalid admin token")
    return None