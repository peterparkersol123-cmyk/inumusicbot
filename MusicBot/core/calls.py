import asyncio
import logging
import os

from pytgcalls import PyTgCalls, idle
from pytgcalls.types import (
    AudioPiped,
    AudioVideoPiped,
    HighQualityAudio,
    HighQualityVideo,
)
from pytgcalls.exceptions import (
    AlreadyJoinedError,
    NoActiveGroupCall,
    NotInGroupCallError,
)
from config import Config
from MusicBot.helpers._queue import Queue, Track

LOGGER = logging.getLogger("MusicBot.Calls")

# FFmpeg input options for stable buffering
FFMPEG_INPUT = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 3"
FFMPEG_OUTPUT = "-bufsize 5M -maxrate 2M"


class TgCall:
    def __init__(self, userbot):
        self._userbot = userbot
        self._clients: list[PyTgCalls] = []
        self._chat_client: dict[int, PyTgCalls] = {}  # chat_id -> PyTgCalls instance
        self._active: set[int] = set()  # currently streaming chat ids
        self._end_events: dict[int, asyncio.Event] = {}

    def _build_clients(self):
        for ub in self._userbot.clients:
            client = PyTgCalls(ub)
            self._clients.append(client)

    async def start(self):
        self._build_clients()
        for c in self._clients:
            await c.start()
        LOGGER.info(f"{len(self._clients)} PyTgCalls instance(s) started.")

    def _pick_client(self, chat_id: int) -> PyTgCalls:
        """Pick a client for a chat, reuse if already assigned."""
        if chat_id in self._chat_client:
            return self._chat_client[chat_id]
        # round-robin across assistants
        idx = len(self._chat_client) % len(self._clients)
        client = self._clients[idx]
        self._chat_client[chat_id] = client
        return client

    # -------------------------
    # Playback
    # -------------------------
    async def play(self, chat_id: int, track: Track, queue: Queue):
        client = self._pick_client(chat_id)

        if track.is_live or not track.file:
            media_stream = AudioPiped(
                track.stream_url,
                audio_parameters=HighQualityAudio(),
                ffmpeg_parameters=FFMPEG_INPUT,
            )
        else:
            media_stream = AudioPiped(
                track.file,
                audio_parameters=HighQualityAudio(),
            )

        try:
            if chat_id in self._active:
                await client.change_stream(chat_id, media_stream)
            else:
                await client.join_group_call(chat_id, media_stream)
                self._active.add(chat_id)
                self._register_handlers(client, chat_id, queue)
        except AlreadyJoinedError:
            await client.change_stream(chat_id, media_stream)
            self._active.add(chat_id)
        except NoActiveGroupCall:
            raise RuntimeError("No active voice chat in this group. Start one first.")

    def _register_handlers(self, client: PyTgCalls, chat_id: int, queue: Queue):
        @client.on_stream_end()
        async def _on_end(_, update):
            if update.chat_id != chat_id:
                return
            await self._handle_stream_end(chat_id, queue)

    async def _handle_stream_end(self, chat_id: int, queue: Queue):
        next_track = queue.next(chat_id)
        if next_track:
            await self.play(chat_id, next_track, queue)
            # Notify the group — done via the plugin layer using bot.send_message
            LOGGER.info(f"[{chat_id}] Auto-playing next: {next_track.title}")
        else:
            if Config.AUTO_END:
                await self.stop(chat_id)

    async def pause(self, chat_id: int):
        client = self._chat_client.get(chat_id)
        if client and chat_id in self._active:
            await client.pause_stream(chat_id)

    async def resume(self, chat_id: int):
        client = self._chat_client.get(chat_id)
        if client and chat_id in self._active:
            await client.resume_stream(chat_id)

    async def stop(self, chat_id: int):
        client = self._chat_client.get(chat_id)
        if client:
            try:
                await client.leave_group_call(chat_id)
            except NotInGroupCallError:
                pass
            self._active.discard(chat_id)
            self._chat_client.pop(chat_id, None)

    async def seek(self, chat_id: int, seconds: int, track: Track):
        """Restart stream from a given offset using ffmpeg seek."""
        client = self._pick_client(chat_id)
        if track.is_live:
            raise RuntimeError("Cannot seek in a live stream.")

        media_stream = AudioPiped(
            track.file or track.stream_url,
            audio_parameters=HighQualityAudio(),
            ffmpeg_parameters=f"-ss {seconds}",
        )
        await client.change_stream(chat_id, media_stream)

    def is_active(self, chat_id: int) -> bool:
        return chat_id in self._active
