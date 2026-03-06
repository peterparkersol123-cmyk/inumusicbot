import asyncio
import logging
import os
import re
import time
from functools import lru_cache

import aiohttp
import yt_dlp
from config import Config

LOGGER = logging.getLogger("MusicBot.YouTube")

YOUTUBE_REGEX = re.compile(
    r"(https?://)?(www\.)?"
    r"(youtube\.com/(watch\?v=|shorts/|playlist\?list=)|youtu\.be/)"
    r"[a-zA-Z0-9_-]+"
)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

_semaphore = asyncio.Semaphore(5)


class YouTube:
    def __init__(self):
        self._cookies_file: str | None = None
        self._search_cache: dict[str, tuple[list, float]] = {}
        self._CACHE_TTL = 600  # 10 minutes

    # -------------------------
    # Cookie management
    # -------------------------
    async def load_cookies(self):
        if not Config.COOKIE_URL:
            return
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(Config.COOKIE_URL, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        path = os.path.join(DOWNLOAD_DIR, "cookies.txt")
                        with open(path, "w") as f:
                            f.write(await resp.text())
                        self._cookies_file = path
                        LOGGER.info("YouTube cookies loaded.")
        except Exception as e:
            LOGGER.warning(f"Failed to load cookies: {e}")

    # -------------------------
    # URL helpers
    # -------------------------
    def is_url(self, query: str) -> bool:
        return bool(YOUTUBE_REGEX.match(query.strip()))

    def is_playlist(self, query: str) -> bool:
        return "playlist?list=" in query or "&list=" in query

    # -------------------------
    # Search
    # -------------------------
    async def search(self, query: str, limit: int = 5) -> list[dict]:
        now = time.time()
        cached = self._search_cache.get(query)
        if cached and now - cached[1] < self._CACHE_TTL:
            return cached[0]

        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, self._search_sync, query, limit)

        if len(self._search_cache) >= 100:
            oldest = min(self._search_cache, key=lambda k: self._search_cache[k][1])
            del self._search_cache[oldest]
        self._search_cache[query] = (results, now)
        return results

    def _search_sync(self, query: str, limit: int) -> list[dict]:
        try:
            from py_yt import VideosSearch  # type: ignore
            result = VideosSearch(query, limit=limit).result()
            return result.get("result", [])
        except Exception as e:
            LOGGER.error(f"YouTube search error: {e}")
            return []

    # -------------------------
    # Download
    # -------------------------
    async def download(self, url: str, video: bool = False) -> dict | None:
        async with _semaphore:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._download_sync, url, video)

    def _download_sync(self, url: str, video: bool) -> dict | None:
        opts = {
            "format": "bestvideo+bestaudio/best" if video else "bestaudio/best",
            "outtmpl": os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "concurrent_fragment_downloads": 4,
            "http_chunk_size": 512 * 1024,
            "socket_timeout": 30,
            "retries": 3,
            "noplaylist": True,
            "extractor_args": {"youtube": {"player_client": ["web", "tv_embedded"]}},
        }
        if self._cookies_file and os.path.exists(self._cookies_file):
            opts["cookiefile"] = self._cookies_file

        if video:
            opts["postprocessors"] = []
        else:
            opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "opus",
                    "preferredquality": "0",
                }
            ]

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    return None

                file_path = ydl.prepare_filename(info)
                if not video:
                    # yt-dlp renames to .opus after post-processing
                    base = os.path.splitext(file_path)[0]
                    for ext in (".opus", ".ogg", ".m4a", ".webm", ".mp3"):
                        candidate = base + ext
                        if os.path.exists(candidate):
                            file_path = candidate
                            break

                return {
                    "title": info.get("title", "Unknown"),
                    "duration": info.get("duration", 0),
                    "thumbnail": info.get("thumbnail"),
                    "url": url,
                    "file": file_path,
                    "is_live": info.get("is_live", False),
                }
        except yt_dlp.utils.DownloadError as e:
            LOGGER.error(f"yt-dlp download error: {e}")
            return None

    async def get_info(self, url: str) -> dict | None:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_info_sync, url)

    def _get_info_sync(self, url: str) -> dict | None:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
            "extractor_args": {"youtube": {"player_client": ["web", "tv_embedded"]}},
        }
        if self._cookies_file and os.path.exists(self._cookies_file):
            opts["cookiefile"] = self._cookies_file
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    return None
                return {
                    "title": info.get("title", "Unknown"),
                    "duration": info.get("duration", 0),
                    "thumbnail": info.get("thumbnail"),
                    "url": url,
                    "is_live": info.get("is_live", False),
                }
        except Exception as e:
            LOGGER.error(f"yt-dlp info error: {e}")
            return None

    async def get_playlist(self, url: str, limit: int = 20) -> list[dict]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_playlist_sync, url, limit)

    def _get_playlist_sync(self, url: str, limit: int) -> list[dict]:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": True,
            "playlist_items": f"1:{limit}",
        }
        if self._cookies_file and os.path.exists(self._cookies_file):
            opts["cookiefile"] = self._cookies_file
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    return []
                entries = info.get("entries", [])
                return [
                    {
                        "title": e.get("title", "Unknown"),
                        "url": f"https://youtube.com/watch?v={e['id']}",
                        "duration": e.get("duration", 0),
                    }
                    for e in entries
                    if e.get("id")
                ]
        except Exception as e:
            LOGGER.error(f"Playlist fetch error: {e}")
            return []
