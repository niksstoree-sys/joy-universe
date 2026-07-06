"""
Database connection manager untuk JOY UNIVERSE.

Menyediakan satu shared aiosqlite connection yang dipakai di seluruh bot,
plus helper untuk menjalankan migration secara otomatis saat startup.
Didesain supaya data TIDAK reset saat bot restart/redeploy — file database
disimpan di path yang persist (contoh: Railway Volume mount di /app/data).
"""

from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

logger = logging.getLogger("joyuniverse.database")


class Database:
    """Wrapper tipis di atas aiosqlite untuk seluruh akses database bot."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self._connection: aiosqlite.Connection | None = None

    @property
    def connection(self) -> aiosqlite.Connection:
        if self._connection is None:
            raise RuntimeError(
                "Database belum di-connect. Panggil `await db.connect()` dulu di startup."
            )
        return self._connection

    async def connect(self) -> None:
        """Membuka koneksi ke database dan memastikan folder tujuan ada."""
        db_path = Path(self.database_url)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self._connection = await aiosqlite.connect(self.database_url)
        self._connection.row_factory = aiosqlite.Row

        # Pragma penting untuk stabilitas & concurrency di production
        await self._connection.execute("PRAGMA journal_mode = WAL;")
        await self._connection.execute("PRAGMA foreign_keys = ON;")
        await self._connection.commit()

        logger.info("Database terkoneksi: %s", self.database_url)

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
            logger.info("Koneksi database ditutup.")

    async def run_migrations(self, migrations_dir: str | Path) -> None:
        """
        Menjalankan semua file .sql di migrations_dir secara berurutan (nama file).
        Aman dipanggil berkali-kali karena semua statement pakai IF NOT EXISTS / OR IGNORE.
        """
        migrations_path = Path(migrations_dir)
        if not migrations_path.exists():
            logger.warning("Folder migrations tidak ditemukan: %s", migrations_path)
            return

        sql_files = sorted(migrations_path.glob("*.sql"))
        for sql_file in sql_files:
            sql_script = sql_file.read_text(encoding="utf-8")
            await self.connection.executescript(sql_script)
            await self.connection.commit()
            logger.info("Migration dijalankan: %s", sql_file.name)

    # ---------- Helper query umum ----------

    async def fetchone(self, query: str, params: tuple = ()) -> aiosqlite.Row | None:
        async with self.connection.execute(query, params) as cursor:
            return await cursor.fetchone()

    async def fetchall(self, query: str, params: tuple = ()) -> list[aiosqlite.Row]:
        async with self.connection.execute(query, params) as cursor:
            return await cursor.fetchall()

    async def execute(self, query: str, params: tuple = ()) -> None:
        await self.connection.execute(query, params)
        await self.connection.commit()
