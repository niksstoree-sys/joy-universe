# JOY UNIVERSE

Bot Discord multifungsi (moderasi, leveling, welcome/leave, event) dengan tema kuning premium (`#FFD54A`). Dibangun dengan `discord.py 2.x`, `aiosqlite`, arsitektur modular.

## Status Pengembangan (Roadmap Bertahap)

- [x] **Tahap 1 — Struktur Project, Database, Command Handler** ✅ *(selesai)*
- [x] **Tahap 2 — Welcome & Leave System** ✅ *(selesai)*
- [x] **Tahap 3 — Event System** ✅ *(selesai)*
- [x] **Tahap 4 — Leveling System (rank card, leaderboard image)** ✅ *(selesai)*
- [x] **Tahap 5 — Reaction Role & Auto Role** ✅ *(selesai)*
- [x] **Tahap 6 — Auto Moderation** ✅ *(selesai)*
- [x] **Tahap 7 — Moderation & Moderation Log** ✅ *(selesai)*
- [x] **Tahap 8 — Polish akhir** ✅ *(selesai)*

## Tahap 8 — Apa yang Diperbaiki

1. **Bug lama: error handler gak pernah ke-wire.** `bot/utils/error_handler.py` dibuat di Tahap 1 tapi baru sekarang benar-benar disambungkan ke `on_command_error` (prefix) dan `tree.on_error` (slash). Sebelumnya semua error cuma nge-print ke console tanpa pesan yang jelas ke user.
2. **Bug lama: Maintenance Mode gak benar-benar memblokir apa-apa.** `!maintenance on` cuma nyimpen status di DB tapi gak ada yang baca. Sekarang ada global check (`_global_maintenance_check` untuk prefix, `MaintenanceAwareTree.interaction_check` untuk slash) yang benar-benar memblokir command dari non-admin selama maintenance aktif.
3. **Slash command "dobel".** Ini terjadi kalau command pernah di-sync ke **global** dan ke **guild** secara bersamaan — Discord menampilkan keduanya sampai salah satu dibersihkan. `!sync` sekarang punya 4 opsi jelas:
   - `!sync global` — cara utama, berlaku di semua server (bisa telat sampai ~1 jam)
   - `!sync guild` — instan tapi cuma untuk server ini, cocok buat testing
   - `!sync cleanguild` — bersihkan command khusus guild ini (hilangkan dobel)
   - `!sync cleanglobal` — hapus semua command global (reset total)

   **Kalau slash command kamu sekarang dobel:** jalankan `!sync cleanguild` di server yang kena, lalu `!sync global` sekali lagi.

## Daftar Command Lengkap

| Kategori | Prefix | Slash |
|---|---|---|
| Core | `!help`, `!ping`, `!info` | `/help`, `/ping`, `/info` |
| Owner | `!maintenance`, `!reload`, `!sync`, `!shutdown`, `!noprefix`, `!addadmin`/`!removeadmin` | - (owner-only, sengaja gak di-slash) |
| Welcome | `!welcome ...` | `/welcome ...` |
| Leave | `!leave ...` | `/leave ...` |
| Event | `!event ...` | `/event ...` |
| Leveling | `!rank`, `!leaderboard`, `!prestige`, `!level ...` | `/rank`, `/leaderboard`, `/prestige`, `/level ...` |
| Auto Role | `!autorole ...` | `/autorole ...` |
| Reaction Role | `!reactionrole ...` (alias `!rr`) | `/reactionrole ...` |
| Auto Moderation | `!automod ...` | `/automod ...` |
| Moderation | `!ban`, `!softban`, `!kick`, `!unban`, `!mute`, `!unmute`, `!timeout`, `!untimeout`, `!warn`, `!warnings`, `!removewarn`, `!clearwarnings`, `!history`, `!slowmode`, `!lock`, `!unlock`, `!purge`, `!nickname`, `!role add/remove`, `!voicemute`, `!voiceunmute`, `!voicekick`, `!voicemove`, `!setmodlog`, `!setmuterole`, `!logconfig` | Padanan `/ban`, `/kick`, dst (kecuali `!logconfig`, `!role add/remove` jadi `/roleadd` `/roleremove`) |

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
