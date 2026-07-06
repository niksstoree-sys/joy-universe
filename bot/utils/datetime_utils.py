"""
Utility tanggal/waktu untuk Event System (Stage 3).

Semua waktu disimpan di database dalam UTC ('YYYY-MM-DD HH:MM:SS'). Modul ini
menangani konversi dari input user (tanggal + jam + timezone lokal, misal WIB)
ke UTC untuk disimpan, dan sebaliknya untuk ditampilkan kembali ke user.
"""

from __future__ import annotations

import calendar
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DB_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# Alias timezone umum Indonesia supaya user tidak wajib hafal nama IANA lengkap
TIMEZONE_ALIASES = {
    "wib": "Asia/Jakarta",
    "wita": "Asia/Makassar",
    "wit": "Asia/Jayapura",
}


def resolve_timezone_name(tz_input: str) -> str:
    return TIMEZONE_ALIASES.get(tz_input.strip().lower(), tz_input.strip())


def parse_local_to_utc(date_str: str, time_str: str, tz_name: str) -> datetime:
    """
    Konversi tanggal+jam lokal (di timezone tz_name) menjadi datetime UTC (aware).
    Raises ValueError dengan pesan bahasa Indonesia kalau input tidak valid.
    """
    resolved_tz = resolve_timezone_name(tz_name)
    try:
        tz = ZoneInfo(resolved_tz)
    except ZoneInfoNotFoundError:
        raise ValueError(
            f"Timezone `{tz_name}` tidak dikenali. Contoh valid: `WIB`, `WITA`, `WIT`, `Asia/Jakarta`, `UTC`."
        )

    try:
        naive = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        raise ValueError(
            "Format tanggal/jam salah. Gunakan `YYYY-MM-DD` untuk tanggal dan `HH:MM` untuk jam. "
            "Contoh: `2026-07-10` `19:00`"
        )

    local_dt = naive.replace(tzinfo=tz)
    return local_dt.astimezone(timezone.utc)


def utc_to_db_string(dt_utc: datetime) -> str:
    return dt_utc.astimezone(timezone.utc).strftime(DB_DATETIME_FORMAT)


def db_string_to_utc(value: str) -> datetime:
    return datetime.strptime(value, DB_DATETIME_FORMAT).replace(tzinfo=timezone.utc)


def now_db_string() -> str:
    return utc_to_db_string(datetime.now(timezone.utc))


def format_for_display(db_value: str, tz_name: str = "Asia/Jakarta") -> str:
    """Format waktu UTC dari database menjadi string yang mudah dibaca di timezone tertentu."""
    dt_utc = db_string_to_utc(db_value)
    resolved_tz = resolve_timezone_name(tz_name)
    try:
        tz = ZoneInfo(resolved_tz)
    except ZoneInfoNotFoundError:
        tz = timezone.utc
        resolved_tz = "UTC"
    local_dt = dt_utc.astimezone(tz)
    return f"{local_dt.strftime('%d %B %Y, %H:%M')} ({tz_name.upper()})"


def format_discord_timestamp(db_value: str, style: str = "F") -> str:
    """Format ke Discord timestamp tag <t:epoch:style> — otomatis menyesuaikan timezone tiap user."""
    dt_utc = db_string_to_utc(db_value)
    epoch = int(dt_utc.timestamp())
    return f"<t:{epoch}:{style}>"


def compute_next_occurrence(dt_utc: datetime, repeat_type: str) -> datetime | None:
    """Hitung jadwal berikutnya berdasarkan repeat_type. None kalau 'once' (tidak berulang)."""
    if repeat_type == "daily":
        return dt_utc + timedelta(days=1)
    if repeat_type == "weekly":
        return dt_utc + timedelta(weeks=1)
    if repeat_type == "monthly":
        year = dt_utc.year + (dt_utc.month // 12)
        month = (dt_utc.month % 12) + 1
        last_day = calendar.monthrange(year, month)[1]
        day = min(dt_utc.day, last_day)
        return dt_utc.replace(year=year, month=month, day=day)
    return None  # "once"


REPEAT_LABELS = {
    "once": "Sekali",
    "daily": "Harian",
    "weekly": "Mingguan",
    "monthly": "Bulanan",
}
