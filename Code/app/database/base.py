from sqlalchemy import BigInteger, Integer
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# PostgreSQL dùng BIGINT đúng Data Dictionary; SQLite dùng INTEGER để test
# vẫn tự tăng khóa chính chính xác.
BIGINT_PK = BigInteger().with_variant(Integer, "sqlite")
