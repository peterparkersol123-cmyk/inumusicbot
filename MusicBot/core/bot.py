import logging
from pyrogram import Client, filters
from config import Config

LOGGER = logging.getLogger("MusicBot.Bot")


class Bot(Client):
    def __init__(self):
        super().__init__(
            name="MusicBot",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            parse_mode="html",
            max_concurrent_transmissions=5,
            no_updates=False,
        )
        self.owner_id: int = Config.OWNER_ID
        self.logger_id: int = Config.LOGGER_ID

        # Populated after boot
        self.id: int = 0
        self.name: str = ""
        self.username: str = ""
        self.mention: str = ""

        self.sudo_filter = filters.user(Config.OWNER_ID)

    async def boot(self):
        await self.start()
        me = await self.get_me()
        self.id = me.id
        self.name = me.first_name
        self.username = f"@{me.username}" if me.username else str(me.id)
        self.mention = me.mention

        LOGGER.info(f"Bot started: {self.name} ({self.username})")

        if self.logger_id:
            try:
                await self.send_message(
                    self.logger_id,
                    f"<b>{self.mention} started.</b>\nVersion: {__import__('MusicBot').VERSION}",
                )
                LOGGER.info("Logger group notified.")
            except Exception as e:
                LOGGER.warning(f"Could not send to logger group: {e}")

    async def exit(self):
        if self.logger_id:
            try:
                await self.send_message(self.logger_id, "<b>Bot is shutting down...</b>")
            except Exception:
                pass
        await self.stop()
        LOGGER.info("Bot stopped.")
