import asyncio
from dataclasses import dataclass, field
from typing import Optional
from config import Config


@dataclass
class Track:
    title: str
    url: str
    duration: int          # seconds (0 = unknown/live)
    thumbnail: Optional[str]
    requested_by: int      # user_id
    requested_by_name: str
    file: Optional[str] = None       # local file path after download
    stream_url: Optional[str] = None # direct stream URL (for live)
    is_live: bool = False
    loop: bool = False

    def duration_str(self) -> str:
        if not self.duration:
            return "LIVE"
        m, s = divmod(self.duration, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"


class Queue:
    """
    Per-chat queue. Each entry is a Track.
    Index 0 = currently playing.
    """

    def __init__(self):
        self._queues: dict[int, list[Track]] = {}
        self._loop_chat: dict[int, str] = {}  # "off" | "single" | "queue"
        self._lock = asyncio.Lock()

    def _q(self, chat_id: int) -> list[Track]:
        return self._queues.setdefault(chat_id, [])

    # -------------------------
    # Add / remove
    # -------------------------
    def add(self, chat_id: int, track: Track) -> int:
        """Append track. Returns position in queue (1-based, 0 = now playing)."""
        q = self._q(chat_id)
        q.append(track)
        return len(q) - 1  # 0 means it's the current track

    def add_next(self, chat_id: int, track: Track):
        """Insert track right after the currently playing one."""
        q = self._q(chat_id)
        if len(q) > 0:
            q.insert(1, track)
        else:
            q.append(track)

    def current(self, chat_id: int) -> Optional[Track]:
        q = self._q(chat_id)
        return q[0] if q else None

    def next(self, chat_id: int) -> Optional[Track]:
        """Pop current, return next track (handles loop modes)."""
        q = self._q(chat_id)
        if not q:
            return None

        mode = self._loop_chat.get(chat_id, "off")

        if mode == "single":
            return q[0]  # replay the same track

        if mode == "queue":
            rotated = q.pop(0)
            q.append(rotated)
            return q[0]

        # default: advance
        q.pop(0)
        return q[0] if q else None

    def skip(self, chat_id: int) -> Optional[Track]:
        """Force skip — always advance regardless of loop mode."""
        q = self._q(chat_id)
        if not q:
            return None
        q.pop(0)
        return q[0] if q else None

    def remove(self, chat_id: int, position: int) -> Optional[Track]:
        """Remove track at 1-based position (position 1 = currently playing)."""
        q = self._q(chat_id)
        idx = position - 1
        if 0 <= idx < len(q):
            return q.pop(idx)
        return None

    def clear(self, chat_id: int):
        self._queues.pop(chat_id, None)

    def shuffle(self, chat_id: int):
        import random
        q = self._q(chat_id)
        if len(q) > 1:
            current = q[0]
            rest = q[1:]
            random.shuffle(rest)
            self._queues[chat_id] = [current] + rest

    # -------------------------
    # Loop
    # -------------------------
    def set_loop(self, chat_id: int, mode: str):
        """mode: 'off' | 'single' | 'queue'"""
        self._loop_chat[chat_id] = mode

    def get_loop(self, chat_id: int) -> str:
        return self._loop_chat.get(chat_id, "off")

    # -------------------------
    # Info
    # -------------------------
    def get_queue(self, chat_id: int) -> list[Track]:
        return list(self._q(chat_id))

    def is_empty(self, chat_id: int) -> bool:
        return len(self._q(chat_id)) == 0

    def size(self, chat_id: int) -> int:
        return len(self._q(chat_id))

    def is_full(self, chat_id: int) -> bool:
        return self.size(chat_id) >= Config.QUEUE_LIMIT
