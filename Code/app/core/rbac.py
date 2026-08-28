from enum import Enum


class RoleCode(str, Enum):
    REQUESTER = "REQUESTER"
    PROCESSOR = "PROCESSOR"
    ADMIN = "ADMIN"
