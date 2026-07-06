# JOY UNIVERSE

Bot Discord multifungsi (moderasi, leveling, welcome/leave, event) dengan tema kuning premium (`#FFD54A`). Dibangun dengan `discord.py 2.x`, `aiosqlite`, arsitektur modular.

## Status Pengembangan (Roadmap Bertahap)

- [x] **Tahap 1 — Struktur Project, Database, Command Handler** ✅ *(selesai)*
- [x] **Tahap 2 — Welcome & Leave System** ✅ *(selesai)*
- [x] **Tahap 3 — Event System** ✅ *(selesai)*
- [x] **Tahap 4 — Leveling System (rank card, leaderboard image)** ✅ *(selesai)*
- [ ] Tahap 5 — Reaction Role & Auto Role
- [ ] Tahap 6 — Auto Moderation
- [ ] Tahap 7 — Moderation & Moderation Log
- [ ] Tahap 8 — Slash command lengkap semua fitur + polish akhir

## Struktur Project

```
joy-universe/
├── bot/
│   ├── main.py                  # Entry point
│   ├── core/
│   │   ├── bot.py               # Class JoyUniverse (custom commands.Bot)
│   │   └── config.py            # Loader environment variables
│   ├── cogs/
│   │   ├── owner.py             # Maintenance, reload, sync, shutdown, no-prefix
│   │   └── core_commands.py     # help, ping, info
│   ├── database/
│   │   ├── connection.py        # Wrapper aiosqlite + migration runner
│   │   └── migrations/001_init.sql
│   ├── services/
│   │   └── guild_config_service.py
│   ├── utils/
│   │   ├── embeds.py            # JoyEmbed (tema kuning konsisten)
│   │   ├── emojis.py            # EmojiManager (emoji custom server)
│   │   ├── error_handler.py     # Global error handler
│   │   └── logger.py
│   ├── views/                   # (disiapkan untuk Button/Select/Modal tahap berikutnya)
│   ├── models/                  # (disiapkan untuk dataclass model tahap berikutnya)
│   ├── assets/{fonts,images}/   # (disiapkan untuk rank card & welcome card - Tahap 4 & 2)
│   └── configs/emojis.json      # Mapping emoji custom
├── data/                        # Lokasi file database (mount sebagai Railway Volume)
├── .env.example
├── requirements.txt
├── Procfile
├── railway.toml
└── .gitignore
```

## Fitur yang Sudah Aktif di Tahap 1

- **Command System**: Prefix command (per-guild dari DB), Mention command (`@JOY UNIVERSE help`), No-Prefix command (khusus owner/user yang di-whitelist), Slash command dasar (`/help`, `/ping`, `/info`).
- **Database**: SQLite via `aiosqlite`, auto-migration saat startup, data persisten (tidak reset saat restart, asalkan `DATABASE_URL` mengarah ke Railway Volume).
- **Owner Mode**: `!maintenance on|off <reason>`, `!reload <cog|all>`, `!sync guild|global`, `!shutdown`, `!noprefix add/remove @user`, `!addadmin` / `!removeadmin` (owner asli via `OWNER_ID`).
- **Help System**: Pagination dengan Button, otomatis generate dari semua cog yang ter-load.
- **Error Handling**: Global handler untuk prefix & slash command, semua pesan konsisten pakai `JoyEmbed`.
- **Embed & Emoji System**: `JoyEmbed` (tema kuning `#FFD54A` default) dan `EmojiManager` (baca dari `configs/emojis.json` — **wajib kamu isi ID emoji custom server kamu di sini** sebelum deploy, supaya tidak muncul string emoji kosong).

## Cara Menjalankan Lokal

```bash
pip install -r requirements.txt
cp .env.example .env   # lalu isi TOKEN, OWNER_ID, dll
python -m bot.main
```

## Cara Deploy ke Railway

1. Push project ini ke GitHub repo.
2. Buat project baru di Railway, connect ke repo tersebut.
3. Tambahkan **Railway Volume**, mount ke `/app/data`.
4. Di Railway Variables, isi semua variabel dari `.env.example` — set `DATABASE_URL=/app/data/joyuniverse.db`.
5. Railway otomatis pakai `railway.toml` / `Procfile` untuk start command: `python -m bot.main`.

## Yang Perlu Kamu Isi Sebelum Bot Jalan Sempurna

1. `bot/configs/emojis.json` — ganti semua ID `0000000000000000` dengan emoji custom server kamu.
2. `.env` — isi `TOKEN`, `OWNER_ID` (wajib), sisanya opsional tapi disarankan.
