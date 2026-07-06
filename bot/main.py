"""
Entry point JOY UNIVERSE.

Jalankan dengan: python -m bot.main
"""

from __future__ import annotations

import asyncio
import logging

from bot.core.bot import JoyUniverse
from bot.core.config import config
from bot.utils.logger import setup_logging

logger = logging.getLogger("joyuniverse.main")


async def main() -> None:
    setup_logging()
    bot = JoyUniverse()

    try:
        async with bot:
            await bot.start(config.token)
    except KeyboardInterrupt:
        logger.info("Bot dihentikan manual (KeyboardInterrupt).")
    except Exception:
        logger.exception("Bot berhenti karena error fatal.")


if __name__ == "__main__":
    asyncio.run(main())
