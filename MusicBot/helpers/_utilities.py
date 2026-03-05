import time
import psutil
import os
from pyrogram.types import Message
from pyrogram.errors import FloodWait, MessageNotModified
import asyncio
import logging

LOGGER = logging.getLogger("MusicBot.Utils")


async def safe_edit(message: Message, text: str, **kwargs):
    try:
        return await message.edit(text, **kwargs)
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await safe_edit(message, text, **kwargs)
    except MessageNotModified:
        pass
    except Exception:
        pass


async def safe_delete(message: Message):
    try:
        await message.delete()
    except Exception:
        pass


def format_duration(seconds: int) -> str:
    if not seconds:
        return "LIVE"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def get_system_stats() -> dict:
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return {
        "cpu": f"{cpu:.1f}%",
        "ram_used": f"{ram.used / 1024**3:.2f} GB",
        "ram_total": f"{ram.total / 1024**3:.2f} GB",
        "ram_percent": f"{ram.percent:.1f}%",
        "disk_used": f"{disk.used / 1024**3:.1f} GB",
        "disk_total": f"{disk.total / 1024**3:.1f} GB",
    }


def uptime_str(boot_time: float) -> str:
    seconds = int(time.time() - boot_time)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)


def clean_downloads(directory: str = "downloads", max_files: int = 50):
    """Remove oldest files from download cache if it grows too large."""
    try:
        files = [
            os.path.join(directory, f)
            for f in os.listdir(directory)
            if os.path.isfile(os.path.join(directory, f))
        ]
        if len(files) > max_files:
            files.sort(key=os.path.getmtime)
            for f in files[: len(files) - max_files]:
                try:
                    os.remove(f)
                except Exception:
                    pass
    except Exception as e:
        LOGGER.warning(f"Download cleanup failed: {e}")
