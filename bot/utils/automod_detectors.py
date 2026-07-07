"""
Fungsi deteksi untuk Auto Moderation (Stage 6).

Semua fungsi di sini murni (pure function) — tidak menyentuh Discord API
atau database, supaya mudah di-test terpisah dari logic bot.
"""

from __future__ import annotations

import re

INVITE_REGEX = re.compile(
    r"(discord\.gg/|discord(?:app)?\.com/invite/)[a-zA-Z0-9-]+", re.IGNORECASE
)

LINK_REGEX = re.compile(r"https?://[^\s]+", re.IGNORECASE)

SCAM_KEYWORDS = (
    "free nitro", "nitro gratis", "steam gift", "airdrop gratis", "claim your reward",
    "you have won", "kamu memenangkan", "double your", "gratis skin", "free robux",
    "verify your account", "verifikasi akun kamu", "crypto giveaway", "klaim hadiah",
)


def contains_invite(content: str) -> bool:
    return bool(INVITE_REGEX.search(content))


def contains_link(content: str) -> bool:
    return bool(LINK_REGEX.search(content))


def caps_percentage(content: str) -> float:
    """Persentase huruf kapital dari total huruf alfabet di pesan. 0 kalau tidak ada huruf."""
    letters = [c for c in content if c.isalpha()]
    if not letters:
        return 0.0
    upper = sum(1 for c in letters if c.isupper())
    return (upper / len(letters)) * 100


def is_excessive_caps(content: str, min_length: int, threshold_percent: int) -> bool:
    if len(content) < min_length:
        return False
    return caps_percentage(content) >= threshold_percent


def contains_badword(content: str, badwords: list[str]) -> str | None:
    """Return kata terlarang pertama yang ketemu (word-boundary match), atau None."""
    lowered = content.lower()
    for word in badwords:
        pattern = r"\b" + re.escape(word.lower()) + r"\b"
        if re.search(pattern, lowered):
            return word
    return None


def looks_like_scam(content: str) -> bool:
    """Heuristik sederhana: ada kata kunci scam umum DAN ada link di pesan yang sama."""
    lowered = content.lower()
    has_keyword = any(keyword in lowered for keyword in SCAM_KEYWORDS)
    return has_keyword and contains_link(content)


def count_mentions(mention_count: int, role_mention_count: int, mentions_everyone: bool) -> int:
    total = mention_count + role_mention_count
    if mentions_everyone:
        total += 1
    return total
