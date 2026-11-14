"""Authenticated local REST client for Fronius GEN24 configuration."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import secrets
from typing import Any

from aiohttp import ClientSession, ClientTimeout

_LOGGER = logging.getLogger(__name__)

LOGIN_PATH = "/api/commands/Login"
COMMON_STATUS_PATH = "/api/status/common"
POWER_LIMITS_PATH = "/api/config/limit_settings/powerLimits"
SOLARWEB_PATH = "/api/config/solarweb"
REST_TIMEOUT = ClientTimeout(total=10)


class FroniusRestError(RuntimeError):
    """Base Fronius REST error."""


class FroniusRestAuthenticationError(FroniusRestError):
    """Fronius REST authentication failed."""


class FroniusRestClient:
    """Access the GEN24 local configuration API using its digest variant."""

    def __init__(
        self,
        session: ClientSession,
        host: str,
        username: str,
        password: str,
    ) -> None:
        self._session = session
        self._base_url = f"http://{host}"
        self._username = username
        self._password = password
        self._challenge: dict[str, str] | None = None
        self._credential_hash: str | None = None
        self._nonce_count = 0
        self._lock = asyncio.Lock()

    @staticmethod
    def _hash(algorithm: str, value: str) -> str:
        return hashlib.new(algorithm, value.encode()).hexdigest()

    @staticmethod
    def _parse_challenge(value: str) -> dict[str, str]:
        fields: dict[str, str] = {}
        for key, quoted, bare in re.findall(
            r"(\w+)=(?:\"([^\"]*)\"|([^,\s]+))", value.removeprefix("Digest ")
        ):
            fields[key] = quoted or bare
        if not fields.get("realm") or not fields.get("nonce"):
            raise FroniusRestAuthenticationError("Invalid digest challenge")
        return fields

    def _authorization(self, method: str, path: str) -> str:
        if self._challenge is None or self._credential_hash is None:
            raise FroniusRestAuthenticationError("REST client is not authenticated")
        self._nonce_count += 1
        nc = str(self._nonce_count).zfill(8)
        cnonce = secrets.token_hex(8)
        qop = self._challenge.get("qop", "auth").split(",")[0]
        request_hash = self._hash("sha256", f"{method.upper()}:{path}")
        response = self._hash(
            "sha256",
            ":".join(
                (
                    self._credential_hash,
                    self._challenge["nonce"],
                    nc,
                    cnonce,
                    qop,
                    request_hash,
                )
            ),
        )
        return (
            f'Digest username="{self._username}", '
            f'realm="{self._challenge["realm"]}", '
            f'nonce="{self._challenge["nonce"]}", uri="{path}", '
            f'response="{response}", qop={qop}, nc={nc}, cnonce="{cnonce}"'
        )

    async def _authenticate(self) -> None:
        async with self._session.get(
            f"{self._base_url}{COMMON_STATUS_PATH}", timeout=REST_TIMEOUT
        ) as response:
            response.raise_for_status()
            common = await response.json()
        version = (
            common.get("authenticationOptions", {})
            .get("digest", {})
            .get(f"{self._username}HashingVersion", 0)
        )
        password_hash_algorithm = "md5" if version == 1 else "sha256"

        async with self._session.get(
            f"{self._base_url}{LOGIN_PATH}",
            params={"user": self._username},
            timeout=REST_TIMEOUT,
        ) as response:
            challenge_header = response.headers.get("X-WWW-Authenticate")
            if response.status != 401 or challenge_header is None:
                raise FroniusRestAuthenticationError(
                    "Fronius digest challenge was not returned"
                )
        self._challenge = self._parse_challenge(challenge_header)
        self._credential_hash = self._hash(
            password_hash_algorithm,
            f"{self._username}:{self._challenge['realm']}:{self._password}",
        )
        self._nonce_count = 0

        async with self._session.get(
            f"{self._base_url}{LOGIN_PATH}",
            params={"user": self._username},
            headers={"Authorization": self._authorization("GET", LOGIN_PATH)},
            timeout=REST_TIMEOUT,
        ) as response:
            if response.status != 200:
                raise FroniusRestAuthenticationError(
                    f"Fronius login failed with HTTP {response.status}"
                )

    async def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> Any:
        async with self._lock:
            if self._challenge is None:
                await self._authenticate()
            for attempt in range(2):
                async with self._session.request(
                    method,
                    f"{self._base_url}{path}",
                    headers={"Authorization": self._authorization(method, path)},
                    json=payload,
                    timeout=REST_TIMEOUT,
                ) as response:
                    if response.status == 401 and attempt == 0:
                        self._challenge = None
                        self._credential_hash = None
                        await self._authenticate()
                        continue
                    if response.status != 200:
                        body = await response.text()
                        raise FroniusRestError(
                            f"Fronius REST {method} {path} failed with "
                            f"HTTP {response.status}: {body}"
                        )
                    return await response.json()
        raise FroniusRestAuthenticationError("Fronius authentication retry failed")

    async def async_get_power_limits(self) -> dict[str, Any]:
        """Return the native feed-in-limit configuration."""
        return await self._request("GET", POWER_LIMITS_PATH)

    async def async_get_remote_control(self) -> dict[str, Any]:
        """Return the Solar.web remote-control configuration."""
        return await self._request("GET", SOLARWEB_PATH)

    async def _set_cloud_flag(self, key: str, enabled: bool) -> dict[str, Any]:
        before = await self.async_get_remote_control()
        flags = ("enableRemoteControl", "customerRemoteControlProfileActive",
                 "technicianRemoteControlProfileActive")
        if any(not isinstance(before.get(flag), bool) for flag in flags):
            raise FroniusRestError("Cloud profile readback unavailable")
        if key == "enableRemoteControl" and not enabled and before["technicianRemoteControlProfileActive"]:
            raise FroniusRestError("Regulatory cloud profile is active; master disable refused")
        payload = {key: enabled}
        result = await self._request("POST", SOLARWEB_PATH, payload)
        failures = sum((result.get(name, []) for name in
                        ("errors", "permissionFailure", "validationErrors", "writeFailure")), [])
        if failures or key not in result.get("writeSuccess", []):
            raise FroniusRestError("Cloud control write was not acknowledged")
        for _attempt in range(5):
            await asyncio.sleep(1)
            config = await self.async_get_remote_control()
            if any(config.get(flag) is not before[flag] for flag in flags if flag != key):
                raise FroniusRestError("An unrelated cloud profile changed; review required")
            if config.get(key) is enabled:return config
        raise FroniusRestError("Cloud control readback did not confirm the requested state")

    async def async_set_remote_control_enabled(self, enabled: bool) -> dict[str, Any]:
        """Change only the master; never implicitly enable either profile."""
        return await self._set_cloud_flag("enableRemoteControl", enabled)

    async def async_set_customer_profile_enabled(self, enabled: bool) -> dict[str, Any]:
        """Change optional customer/VPP control, preserving regulatory control."""
        return await self._set_cloud_flag("customerRemoteControlProfileActive", enabled)

    async def async_set_soft_export_limit(self, watts: int) -> dict[str, Any]:
        """Set and verify the native Smart Meter-following soft export limit."""
        if watts < 0:
            raise ValueError("Export limit cannot be negative")
        payload = {
            "exportLimits": {
                "activePower": {"softLimit": {"powerLimit": int(watts)}}
            }
        }
        result = await self._request("POST", POWER_LIMITS_PATH, payload)
        failures = (
            result.get("errors", [])
            + result.get("permissionFailure", [])
            + result.get("validationErrors", [])
            + result.get("writeFailure", [])
        )
        if failures or "powerLimit" not in result.get("writeSuccess", []):
            raise FroniusRestError(f"Export-limit write failed: {result}")

        config = await self.async_get_power_limits()
        actual = config["exportLimits"]["activePower"]["softLimit"][
            "powerLimit"
        ]
        if int(actual) != int(watts):
            raise FroniusRestError(
                f"Export-limit verification failed: expected {watts}, got {actual}"
            )
        return config
