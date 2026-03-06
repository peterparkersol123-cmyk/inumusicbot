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

VIDEO_ID_REGEX = re.compile(r"(?:v=|youtu\.be/|shorts/)([a-zA-Z0-9_-]{11})")

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

_semaphore = asyncio.Semaphore(5)

# Public Invidious instances — tried in order, first success wins
INVIDIOUS_INSTANCES = [
    "https://inv.nadeko.net",
    "https://yewtu.be",
    "https://invidious.flokinet.to",
    "https://invidious.privacydev.net",
    "https://yt.artemislena.eu",
    "https://invidious.lunar.icu",
]


class YouTube:
    def __init__(self):
        self._cookies_file: str | None = None
        self._proxy: str | None = os.getenv("YTDLP_PROXY", "").strip() or None
        self._search_cache: dict[str, tuple[list, float]] = {}
        self._CACHE_TTL = 600  # 10 minutes

    # -------------------------
    # Cookie management
    # -------------------------
    async def load_cookies(self):
        if self._proxy:
            LOGGER.info(f"yt-dlp proxy configured: {self._proxy}")
        path = os.path.join(DOWNLOAD_DIR, "cookies.txt")

        # Option 1: base64-encoded cookies pasted directly as env var
        cookies_b64 = os.getenv("COOKIES_B64", "").strip()
        if cookies_b64:
            try:
                import base64
                content = base64.b64decode(cookies_b64).decode("utf-8")
                with open(path, "w") as f:
                    f.write(content)
                self._cookies_file = path
                LOGGER.info("YouTube cookies loaded from COOKIES_B64.")
                return
            except Exception as e:
                LOGGER.warning(f"Failed to load cookies from COOKIES_B64: {e}")

        # Option 2: download from URL
        if not Config.COOKIE_URL:
            return
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(Config.COOKIE_URL, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        with open(path, "w") as f:
                            f.write(await resp.text())
                        self._cookies_file = path
                        LOGGER.info("YouTube cookies loaded from COOKIE_URL.")
        except Exception as e:
            LOGGER.warning(f"Failed to load cookies from COOKIE_URL: {e}")

    # -------------------------
    # URL helpers
    # -------------------------
    def is_url(self, query: str) -> bool:
        return bool(YOUTUBE_REGEX.match(query.strip()))

    def is_playlist(self, query: str) -> bool:
        return "playlist?list=" in query or "&list=" in query

    def _extract_video_id(self, url: str) -> str | None:
        m = VIDEO_ID_REGEX.search(url)
        return m.group(1) if m else None

    # -------------------------
    # Invidious fallback
    # -------------------------
    async def _get_stream_invidious(self, video_id: str) -> dict | None:
        """Get direct audio stream URL via Invidious public API (no bot-detection)."""
        fields = "title,lengthSeconds,videoThumbnails,adaptiveFormats,formatStreams"
        for instance in INVIDIOUS_INSTANCES:
            try:
                url = f"{instance}/api/v1/videos/{video_id}?fields={fields}"
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        url, timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        if resp.status != 200:
                            continue
                        data = await resp.json()

                # Prefer audio-only adaptive formats (opus/webm or aac/mp4)
                best_audio = None
                for fmt in data.get("adaptiveFormats", []):
                    if not fmt.get("type", "").startswith("audio/"):
                        continue
                    if not fmt.get("url"):
                        continue
                    bitrate = int(fmt.get("bitrate", 0))
                    if best_audio is None or bitrate > int(best_audio.get("bitrate", 0)):
                        best_audio = fmt

                # Fall back to combined format streams
                if not best_audio:
                    streams = data.get("formatStreams", [])
                    best_audio = streams[-1] if streams else None

                if not best_audio or not best_audio.get("url"):
                    continue

                thumbs = data.get("videoThumbnails", [])
                thumbnail = thumbs[0]["url"] if thumbs else None

                LOGGER.info(f"Invidious stream resolved via {instance} for {video_id}")
                return {
                    "title": data.get("title", "Unknown"),
                    "duration": int(data.get("lengthSeconds", 0)),
                    "thumbnail": thumbnail,
                    "url": f"https://youtube.com/watch?v={video_id}",
                    "stream_url": best_audio["url"],
                    "file": None,
                    "is_live": False,
                }
            except Exception as e:
                LOGGER.warning(f"Invidious {instance} failed: {type(e).__name__}: {e}")
                continue

        LOGGER.error(f"All Invidious instances failed for {video_id}")
        return None

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
    # oEmbed — title/thumbnail without auth (works from any IP)
    # -------------------------
    async def get_oembed_info(self, url: str) -> dict | None:
        """Fetch title and thumbnail via YouTube oEmbed (no API key, no proxy needed)."""
        try:
            oembed_url = (
                "https://www.youtube.com/oembed"
                f"?url={url}&format=json"
            )
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    oembed_url, timeout=aiohttp.ClientTimeout(total=8)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {
                            "title": data.get("title", "Unknown"),
                            "thumbnail": data.get("thumbnail_url"),
                            "duration": 0,
                            "url": url,
                            "is_live": False,
                        }
        except Exception as e:
            LOGGER.debug(f"oEmbed failed for {url}: {e}")
        return None

    # -------------------------
    # SoundCloud fallback (no bot-detection on datacenter IPs)
    # -------------------------
    async def download_soundcloud(self, query: str) -> dict | None:
        """Search and download from SoundCloud — works on any IP without proxy."""
        async with _semaphore:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._sc_download_sync, query)

    def _sc_download_sync(self, query: str) -> dict | None:
        opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "playlist_items": "1",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "opus",
                    "preferredquality": "0",
                }
            ],
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"scsearch1:{query}", download=True)
                if not info:
                    return None
                # scsearch returns a playlist wrapper
                entries = info.get("entries", [info])
                if not entries:
                    return None
                entry = entries[0]

                file_path = ydl.prepare_filename(entry)
                base = os.path.splitext(file_path)[0]
                for ext in (".opus", ".ogg", ".m4a", ".webm", ".mp3"):
                    candidate = base + ext
                    if os.path.exists(candidate):
                        file_path = candidate
                        break

                return {
                    "title": entry.get("title", query),
                    "duration": int(entry.get("duration", 0)),
                    "thumbnail": entry.get("thumbnail"),
                    "url": entry.get("webpage_url", query),
                    "file": file_path,
                    "stream_url": None,
                    "is_live": False,
                    "source": "soundcloud",
                }
        except Exception as e:
            LOGGER.error(f"SoundCloud download error for '{query}': {e}")
            return None

    # -------------------------
    # Download (with Invidious fallback)
    # -------------------------
    async def download(self, url: str, video: bool = False) -> dict | None:
        async with _semaphore:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._download_sync, url, video)
            if result:
                return result

            # yt-dlp failed — try Invidious for audio streams
            if not video:
                video_id = self._extract_video_id(url)
                if video_id:
                    LOGGER.info(f"yt-dlp failed, falling back to Invidious for {video_id}")
                    return await self._get_stream_invidious(video_id)

            return None

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
            "extractor_args": {"youtube": {"player_client": ["ios", "web"]}},
        }
        if self._proxy:
            opts["proxy"] = self._proxy
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
                    "stream_url": None,
                    "is_live": info.get("is_live", False),
                }
        except yt_dlp.utils.DownloadError as e:
            LOGGER.error(f"yt-dlp download error: {e}")
            return None

    async def get_info(self, url: str) -> dict | None:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._get_info_sync, url)
        if result:
            return result

        # yt-dlp info fetch failed — try Invidious for metadata
        video_id = self._extract_video_id(url)
        if video_id:
            LOGGER.info(f"yt-dlp info failed, trying Invidious for {video_id}")
            return await self._get_stream_invidious(video_id)

        return None

    def _get_info_sync(self, url: str) -> dict | None:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
            "extractor_args": {"youtube": {"player_client": ["ios", "web"]}},
        }
        if self._proxy:
            opts["proxy"] = self._proxy
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
