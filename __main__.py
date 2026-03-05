import asyncio
import logging

LOGGER = logging.getLogger("MusicBot")


async def main():
    from MusicBot import bot, userbot, db, call, youtube
    import MusicBot.plugins  # triggers auto-load of all plugins  # noqa: F401

    await db.connect()
    await youtube.load_cookies()
    await bot.boot()
    await userbot.boot()
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
