"""
Config loader untuk JOY UNIVERSE.

Semua nilai wajib berasal dari environment variables (.env saat lokal,
Railway Variables saat production). Tidak ada hardcode token/ID di kode.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _get_env(key: str, default: str | None = None, required: bool = False) -> str | None:
    value = os.getenv(key, default)
    if required and not value:
        raise RuntimeError(
            f"Environment variable `{key}` wajib diisi. Cek file .env atau Railway Variables."
        )
    return value


def _get_int_env(key: str, default: int | None = None) -> int | None:
    value = os.getenv(key)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        raise RuntimeError(f"Environment variable `{key}` harus berupa angka, ditemukan: {value!r}")


@dataclass(frozen=True)
class Config:
    token: str
    client_id: int | None
    guild_id: int | None
    owner_id: int

    database_url: str
    default_prefix: str
    default_color: int

    support_server: str | None
    invite_url: str | None
    topgg_token: str | None
    webhook_log: str | None
    railway_public_domain: str | None

    @classmethod
    def load(cls) -> "Config":
        default_color_hex = _get_env("DEFAULT_COLOR", "#FFD54A")
        return cls(
            token=_get_env("TOKEN", required=True),
            client_id=_get_int_env("CLIENT_ID"),
            guild_id=_get_int_env("GUILD_ID"),
            owner_id=_get_int_env("OWNER_ID", required=True) or 0,
            database_url=_get_env("DATABASE_URL", "data/joyuniverse.db"),
            default_prefix=_get_env("PREFIX", "!"),
            default_color=int(default_color_hex.lstrip("#"), 16),
            support_server=_get_env("SUPPORT_SERVER"),
            invite_url=_get_env("INVITE_URL"),
            topgg_token=_get_env("TOPGG_TOKEN"),
            webhook_log=_get_env("WEBHOOK_LOG"),
            railway_public_domain=_get_env("RAILWAY_PUBLIC_DOMAIN"),
        )


config = Config.load()
