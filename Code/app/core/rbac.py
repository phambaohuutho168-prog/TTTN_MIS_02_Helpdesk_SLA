from enum import Enum


class RoleCode(str, Enum):
    REQUESTER = "REQUESTER"
    PROCESSOR = "PROCESSOR"
    ADMIN = "ADMIN"


# CV025 sẽ đặt dependency kiểm tra quyền trong
# app/api/dependencies/authorization.py. Tuyệt đối không nhận vai trò từ
# X-User-Role hoặc dữ liệu do client tự khai báo; vai trò phải đọc từ database.
