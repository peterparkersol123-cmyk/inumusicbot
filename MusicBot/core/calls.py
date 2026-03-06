import logging

from pytgcalls import PyTgCalls, filters as tg_filters
from pytgcalls.types import MediaStream, AudioQuality
from pytgcalls.exceptions import NotInCallError, NoActiveGroupCall
from pyrogram.errors import ChannelInvalid, ChatAdminRequired, ChatWriteForbidden
from config import Config
from MusicBot.helpers._queue import Queue, Track

LOGGER = logging.getLogger("MusicBot.Calls")


class TgCall:
    def __init__(self, userbot):
        self._userbot = userbot
        self._clients: list[PyTgCalls] = []
        self._chat_client: dict[int, PyTgCalls] = {}
        self._chat_queue: dict[int, Queue] = {}
        self._active: set[int] = set()

    def _build_clients(self):
        for ub in self._userbot.clients:
            client = PyTgCalls(ub)
            self._clients.append(client)
            self._setup_handlers(client)

    def _setup_handlers(self, client: PyTgCalls):
        @client.on_update(tg_filters.stream_end)
        async def _on_stream_end(_, update):
            chat_id = update.chat_id
            queue = self._chat_queue.get(chat_id)
            if queue is not None:
                await self._handle_stream_end(chat_id, queue)

    async def start(self):
        self._build_clients()
        for c in self._clients:
            await c.start()
        LOGGER.info(f"{len(self._clients)} PyTgCalls instance(s) started.")

    def _pick_client(self, chat_id: int) -> PyTgCalls:
        if chat_id in self._chat_client:
            return self._chat_client[chat_id]
        idx = len(self._chat_client) % len(self._clients)
        client = self._clients[idx]
        self._chat_client[chat_id] = client
        return client

    def _make_stream(self, track: Track, seek: int = 0) -> MediaStream:
        source = track.file or track.stream_url or track.url
        ffmpeg_params = f"-ss {seek}" if seek else None
        return MediaStream(
            source,
            audio_parameters=AudioQuality.MEDIUM,
            ffmpeg_parameters=ffmpeg_params,
        )

    async def play(self, chat_id: int, track: Track, queue: Queue):
        client = self._pick_client(chat_id)
        stream = self._make_stream(track)
        try:
            await client.play(chat_id, stream)
            self._active.add(chat_id)
            self._chat_queue[chat_id] = queue
        except NoActiveGroupCall:
            raise RuntimeError("❌ No active voice chat. Start one in the group first.")
        except (ChannelInvalid, KeyError):
            raise RuntimeError(
                "❌ Assistant not in this group.\n"
                "Add the assistant account as an admin with 'Manage voice chats' permission."
            )
        except ChatAdminRequired:
            raise RuntimeError(
                "❌ Assistant needs admin rights with 'Manage voice chats' permission."
            )

    async def _handle_stream_end(self, chat_id: int, queue: Queue):
        next_track = queue.next(chat_id)
        if next_track:
            await self.play(chat_id, next_track, queue)
            LOGGER.info(f"[{chat_id}] Auto-playing next: {next_track.title}")
        else:
            if Config.AUTO_END:
                await self.stop(chat_id)

    async def pause(self, chat_id: int):
        client = self._chat_client.get(chat_id)
        if client and chat_id in self._active:
            await client.pause(chat_id)

    async def resume(self, chat_id: int):
        client = self._chat_client.get(chat_id)
        if client and chat_id in self._active:
            await client.resume(chat_id)

    async def stop(self, chat_id: int):
        client = self._chat_client.get(chat_id)
        if client:
            try:
                await client.leave_call(chat_id)
            except (NotInCallError, NoActiveGroupCall):
                pass
            self._active.discard(chat_id)
            self._chat_client.pop(chat_id, None)
            self._chat_queue.pop(chat_id, None)

    async def seek(self, chat_id: int, seconds: int, track: Track):
        if track.is_live:
            raise RuntimeError("Cannot seek in a live stream.")
        client = self._pick_client(chat_id)
        stream = self._make_stream(track, seek=seconds)
        await client.play(chat_id, stream)

    def is_active(self, chat_id: int) -> bool:
        return chat_id in self._active
