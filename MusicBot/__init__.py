import logging
import logging.handlers
import time

for lib in ("pyrogram", "httpx", "pymongo", "motor"):
    logging.getLogger(lib).setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(
            "musicbot.log", maxBytes=5_000_000, backupCount=2
        ),
    ],
)

LOGGER = logging.getLogger("MusicBot")
VERSION = "1.0.0"
boot_time = time.time()
background_tasks: list = []

from config import Config  # noqa: E402

Config.check()

from MusicBot.core.bot import Bot  # noqa: E402
from MusicBot.core.userbot import Userbot  # noqa: E402
from MusicBot.core.mongo import MongoDB  # noqa: E402
from MusicBot.core.youtube import YouTube  # noqa: E402
from MusicBot.helpers._queue import Queue  # noqa: E402
from MusicBot.core.calls import TgCall  # noqa: E402

bot = Bot()
userbot = Userbot()
db = MongoDB()
youtube = YouTube()
queue = Queue()
call = TgCall(userbot)


async def stop():
    LOGGER.info("Shutting down...")
    import asyncio
    for task in background_tasks:
        task.cancel()
    await asyncio.gather(*background_tasks, return_exceptions=True)
    await bot.exit()
    await userbot.exit()
    await db.close()
    LOGGER.info("Shutdown complete.")
