import asyncio
import logging

LOGGER = logging.getLogger("MusicBot")


async def main():
    from MusicBot import bot, userbot, db, call, youtube
    import MusicBot.plugins  # triggers auto-load of all plugins  # noqa: F401

    await db.connect()
    await youtube.load_cookies()

    # Retry boot on FloodWait (Telegram rate-limits rapid re-auth from redeploys)
    from pyrogram.errors import FloodWait
    for attempt in range(5):
        try:
            await bot.boot()
            break
        except FloodWait as e:
            LOGGER.warning(f"FloodWait on bot boot: waiting {e.value}s (attempt {attempt + 1}/5)")
            await asyncio.sleep(e.value + 5)
    else:
        raise RuntimeError("Bot failed to start after 5 FloodWait retries")

    for attempt in range(5):
        try:
            await userbot.boot()
            break
        except FloodWait as e:
            LOGGER.warning(f"FloodWait on userbot boot: waiting {e.value}s (attempt {attempt + 1}/5)")
            await asyncio.sleep(e.value + 5)
    await call.start()

    LOGGER.info("All systems up. Bot is running.")

    try:
        from pytgcalls import idle
        await idle()
    except KeyboardInterrupt:
        pass
    finally:
        from MusicBot import stop
        await stop()


if __name__ == "__main__":
    asyncio.run(main())
