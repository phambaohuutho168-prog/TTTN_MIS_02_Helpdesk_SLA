import hashlib
from datetime import datetime, timezone
from typing import Any, Protocol

from redis.asyncio import Redis
from redis.exceptions import WatchError

from app.core.config import settings
from app.database.redis import redis_client


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _ttl_from_claims(claims: dict[str, Any]) -> int:
    expires_at = int(claims["exp"])
    now = int(datetime.now(timezone.utc).timestamp())
    return max(expires_at - now, 1)


class SessionStore(Protocol):
    async def ping(self) -> bool: ...
    async def create_refresh_session(self, claims: dict[str, Any]) -> None: ...
    async def get_refresh_status(self, jti: str) -> str | None: ...
    async def rotate_refresh_session(
        self,
        old_claims: dict[str, Any],
        new_claims: dict[str, Any],
    ) -> bool: ...
    async def revoke_family(self, family_id: str) -> None: ...
    async def revoke_access(self, jti: str, exp: int) -> None: ...
    async def is_access_revoked(self, jti: str) -> bool: ...
    async def login_retry_after(self, email: str, ip_address: str) -> int: ...
    async def record_login_failure(self, email: str, ip_address: str) -> None: ...
    async def clear_login_failures(self, email: str, ip_address: str) -> None: ...


class RedisSessionStore:
    def __init__(self, client: Redis) -> None:
        self.client = client

    @staticmethod
    def refresh_key(jti: str) -> str:
        return f"auth:refresh:{_digest(jti)}"

    @staticmethod
    def family_key(family_id: str) -> str:
        return f"auth:family:{_digest(family_id)}"

    @staticmethod
    def access_key(jti: str) -> str:
        return f"auth:access:revoked:{_digest(jti)}"

    @staticmethod
    def login_key(email: str, ip_address: str) -> str:
        material = f"{email.strip().lower()}|{ip_address}"
        return f"auth:login:failures:{_digest(material)}"

    async def ping(self) -> bool:
        return bool(await self.client.ping())

    async def create_refresh_session(self, claims: dict[str, Any]) -> None:
        jti = str(claims["jti"])
        family_id = str(claims["family_id"])
        ttl = _ttl_from_claims(claims)
        member = _digest(jti)
        async with self.client.pipeline(transaction=True) as pipe:
            pipe.hset(
                self.refresh_key(jti),
                mapping={
                    "status": "active",
                    "user_id": str(claims["sub"]),
                    "family_id": family_id,
                },
            )
            pipe.expire(self.refresh_key(jti), ttl)
            pipe.sadd(self.family_key(family_id), member)
            pipe.expire(self.family_key(family_id), ttl)
            await pipe.execute()

    async def get_refresh_status(self, jti: str) -> str | None:
        return await self.client.hget(self.refresh_key(jti), "status")

    async def rotate_refresh_session(
        self,
        old_claims: dict[str, Any],
        new_claims: dict[str, Any],
    ) -> bool:
        old_jti = str(old_claims["jti"])
        old_key = self.refresh_key(old_jti)
        new_jti = str(new_claims["jti"])
        family_id = str(old_claims["family_id"])
        new_ttl = _ttl_from_claims(new_claims)

        for _ in range(3):
            async with self.client.pipeline(transaction=True) as pipe:
                try:
                    await pipe.watch(old_key)
                    status = await pipe.hget(old_key, "status")
                    if status != "active":
                        await pipe.unwatch()
                        return False
                    pipe.multi()
                    pipe.hset(old_key, "status", "used")
                    pipe.hset(
                        self.refresh_key(new_jti),
                        mapping={
                            "status": "active",
                            "user_id": str(new_claims["sub"]),
                            "family_id": family_id,
                        },
                    )
                    pipe.expire(self.refresh_key(new_jti), new_ttl)
                    pipe.sadd(self.family_key(family_id), _digest(new_jti))
                    pipe.expire(self.family_key(family_id), new_ttl)
                    await pipe.execute()
                    return True
                except WatchError:
                    continue
        return False

    async def revoke_family(self, family_id: str) -> None:
        family_key = self.family_key(family_id)
        members = await self.client.smembers(family_key)
        if not members:
            return
        async with self.client.pipeline(transaction=True) as pipe:
            for member in members:
                pipe.hset(f"auth:refresh:{member}", "status", "revoked")
            await pipe.execute()

    async def revoke_access(self, jti: str, exp: int) -> None:
        now = int(datetime.now(timezone.utc).timestamp())
        await self.client.set(self.access_key(jti), "1", ex=max(exp - now, 1))

    async def is_access_revoked(self, jti: str) -> bool:
        return bool(await self.client.exists(self.access_key(jti)))

    async def login_retry_after(self, email: str, ip_address: str) -> int:
        key = self.login_key(email, ip_address)
        attempts = int(await self.client.get(key) or 0)
        if attempts < settings.LOGIN_MAX_ATTEMPTS:
            return 0
        return max(await self.client.ttl(key), 1)

    async def record_login_failure(self, email: str, ip_address: str) -> None:
        key = self.login_key(email, ip_address)
        attempts = await self.client.incr(key)
        if attempts == 1:
            await self.client.expire(key, settings.LOGIN_RATE_LIMIT_SECONDS)

    async def clear_login_failures(self, email: str, ip_address: str) -> None:
        await self.client.delete(self.login_key(email, ip_address))


def get_session_store() -> SessionStore:
    return RedisSessionStore(redis_client)

