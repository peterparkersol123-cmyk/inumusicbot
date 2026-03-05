import logging
from pyrogram import Client
from config import Config

LOGGER = logging.getLogger("MusicBot.Userbot")


class Userbot:
    def __init__(self):
        self.clients: list[Client] = []

        sessions = [
            ("MusicBotUB1", Config.STRING_SESSION),
            ("MusicBotUB2", Config.STRING_SESSION2),
            ("MusicBotUB3", Config.STRING_SESSION3),
        ]

        for name, session in sessions:
            if session:
                client = Client(
                    name=name,
                    api_id=Config.API_ID,
                    api_hash=Config.API_HASH,
                    session_string=session,
                    no_updates=True,
                )
                setattr(self, name, client)
                self.clients.append(client)

    async def _boot_client(self, client: Client):
        try:
            await client.start()
            me = await client.get_me()
            LOGGER.info(f"Assistant started: {me.first_name} (@{me.username})")
            return client
        except Exception as e:
            LOGGER.warning(f"Failed to start assistant {client.name}: {e}")
            self.clients.remove(client)
            return None

    async def boot(self):
        if not self.clients:
            LOGGER.error("No assistant session strings configured.")
            raise SystemExit(1)

        import asyncio
        await asyncio.gather(*[self._boot_client(c) for c in self.clients[:]])
        LOGGER.info(f"{len(self.clients)} assistant(s) running.")

    async def exit(self):
        for client in self.clients:
            try:
                await client.stop()
            except Exception:
                pass
        LOGGER.info("All assistants stopped.")

    def get_client(self, index: int = 0) -> Client | None:
        """Return a specific assistant client by index."""
        if self.clients and index < len(self.clients):
            return self.clients[index]
        return None
