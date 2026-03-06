import logging
from pyrogram import Client, filters
from pyrogram.types import Message

from MusicBot import bot, queue, call, youtube, db
from MusicBot.helpers._play import checkUB
from MusicBot.helpers._queue import Track
from MusicBot.helpers._utilities import safe_edit, format_duration
from config import Config

LOGGER = logging.getLogger("MusicBot.Plugin.Play")


@bot.on_message(filters.command(["play", "p"]) & filters.group)
@checkUB
async def play_cmd(client: Client, message: Message, query: str = ""):
    await _play_handler(client, message, query, force=False)


@bot.on_message(filters.command(["playforce", "pf"]) & filters.group)
@checkUB
async def playforce_cmd(client: Client, message: Message, query: str = ""):
    await _play_handler(client, message, query, force=True)


async def _play_handler(client: Client, message: Message, query: str, force: bool):
    chat_id = message.chat.id
    user = message.from_user

    # --- Handle replied audio/document ---
    reply = message.reply_to_message
    if not query and reply and (reply.audio or reply.document or reply.video):
        await _play_telegram_file(client, message, reply, force)
        return

    status_msg = await message.reply("<i>Searching...</i>")

    # --- YouTube playlist ---
    if youtube.is_url(query) and youtube.is_playlist(query):
        await safe_edit(status_msg, "<i>Fetching playlist...</i>")
        tracks = await youtube.get_playlist(query, limit=Config.QUEUE_LIMIT)
        if not tracks:
            return await safe_edit(status_msg, "Could not fetch playlist. Try a direct link.")

        added = 0
        for t in tracks:
            if queue.is_full(chat_id):
                break
            track = Track(
                title=t["title"],
                url=t["url"],
                duration=t.get("duration", 0),
                thumbnail=None,
                requested_by=user.id,
                requested_by_name=user.first_name,
            )
            queue.add(chat_id, track)
            added += 1

        await safe_edit(status_msg, f"Added <b>{added}</b> tracks from playlist to queue.")
        if not call.is_active(chat_id):
            await _start_playing(chat_id, status_msg)
        return

    # --- Single YouTube URL or search query ---
    if youtube.is_url(query):
        # Use oEmbed for fast title/thumbnail lookup — no yt-dlp, no bot-detection issues.
        # SoundCloud will be used for the actual audio download.
        info = await youtube.get_oembed_info(query)
        if not info:
            return await safe_edit(status_msg, "❌ Could not fetch song info. The video may be private or unavailable.")
    else:
        results = await youtube.search(query, limit=1)
        if not results:
            return await safe_edit(status_msg, "No results found. Try a different query.")
        info = {
            "title": results[0].get("title", "Unknown"),
            "url": results[0].get("link", results[0].get("url", "")),
            "duration": _parse_duration(results[0].get("duration", "0:00")),
            "thumbnail": results[0].get("thumbnails", [{}])[0].get("url"),
        }

    if not info:
        return await safe_edit(status_msg, "No results found. Try a different query.")

    # Duration limit
    if info.get("duration", 0) > Config.DURATION_LIMIT and not info.get("is_live"):
        return await safe_edit(
            status_msg,
            f"Song exceeds duration limit ({Config.DURATION_LIMIT // 60} min)."
        )

    track = Track(
        title=info["title"],
        url=info["url"],
        duration=info.get("duration", 0),
        thumbnail=info.get("thumbnail"),
        requested_by=user.id,
        requested_by_name=user.first_name,
        is_live=info.get("is_live", False),
    )

    if force and call.is_active(chat_id):
        queue.add_next(chat_id, track)
        await safe_edit(status_msg, f"Force playing: <b>{track.title}</b>")
        await _skip_to_next(chat_id)
        return

    pos = queue.add(chat_id, track)

    if pos == 0 or not call.is_active(chat_id):
        # First track or bot not yet in VC — start playing
        await safe_edit(status_msg, f"Playing: <b>{track.title}</b> [{track.duration_str()}]")
        await _start_playing(chat_id, status_msg)
    else:
        await safe_edit(
            status_msg,
            f"Added to queue at position <b>#{pos}</b>: <b>{track.title}</b> [{track.duration_str()}]"
        )


async def _play_telegram_file(client: Client, message: Message, reply: Message, force: bool):
    chat_id = message.chat.id
    user = message.from_user
    media = reply.audio or reply.document or reply.video

    status_msg = await message.reply("<i>Downloading file...</i>")
    file_path = await reply.download()

    title = getattr(media, "file_name", None) or getattr(media, "title", None) or "Audio File"
    duration = getattr(media, "duration", 0) or 0

    track = Track(
        title=title,
        url="",
        duration=duration,
        thumbnail=None,
        requested_by=user.id,
        requested_by_name=user.first_name,
        file=file_path,
    )

    if force and call.is_active(chat_id):
        queue.add_next(chat_id, track)
        await safe_edit(status_msg, f"Force playing: <b>{title}</b>")
        await _skip_to_next(chat_id)
        return

    pos = queue.add(chat_id, track)
    if pos == 0 or not call.is_active(chat_id):
        await safe_edit(status_msg, f"Playing: <b>{title}</b>")
        await _start_playing(chat_id, status_msg)
    else:
        await safe_edit(status_msg, f"Added to queue at position <b>#{pos}</b>: <b>{title}</b>")


async def _start_playing(chat_id: int, status_msg=None):
    current = queue.current(chat_id)
    if not current:
        return

    if not current.file and not current.stream_url and not current.is_live:
        info = None

        # --- Resolve title if needed (oEmbed is fast and works from any IP) ---
        if not current.title or current.title == "Unknown":
            if current.url and youtube.is_url(current.url):
                oembed = await youtube.get_oembed_info(current.url)
                if oembed and oembed.get("title"):
                    current.title = oembed["title"]

        search_title = current.title
        if not search_title or search_title == "Unknown":
            if status_msg:
                await safe_edit(status_msg, "❌ Could not resolve song title.")
            queue.skip(chat_id)
            return

        if status_msg:
            await safe_edit(status_msg, f"<i>Searching SoundCloud for</i> <b>{search_title}</b>...")
        info = await youtube.download_soundcloud(search_title)

        if not info:
            if status_msg:
                await safe_edit(status_msg, "❌ Could not fetch audio from SoundCloud.")
            queue.skip(chat_id)
            await _start_playing(chat_id, status_msg)
            return

        current.file = info.get("file")
        current.stream_url = info.get("stream_url")
        if info.get("title") and info["title"] != "Unknown":
            current.title = info["title"]

    try:
        await call.play(chat_id, current, queue)
    except RuntimeError as e:
        err = str(e)
        # Auto-invite the assistant if it's not in the group yet
        if "Assistant not in this group" in err:
            try:
                from MusicBot import bot, userbot
                assistant_ids = []
                for ub in userbot.clients:
                    me = await ub.get_me()
                    assistant_ids.append(me.id)
                if assistant_ids:
                    await bot.add_chat_members(chat_id, assistant_ids)
                    # Retry after adding
                    await call.play(chat_id, current, queue)
                    return
            except Exception as invite_err:
                err = (
                    f"❌ Couldn't auto-add assistant ({invite_err}).\n"
                    "Please add the assistant account manually as an admin "
                    "with 'Manage voice chats' permission."
                )
        if status_msg:
            await safe_edit(status_msg, err)


async def _skip_to_next(chat_id: int):
    next_track = queue.skip(chat_id)
    if next_track:
        await _start_playing(chat_id, None)


def _parse_duration(duration_str: str) -> int:
    """Parse 'HH:MM:SS' or 'MM:SS' string to seconds."""
    try:
        parts = [int(x) for x in str(duration_str).split(":")]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        elif len(parts) == 2:
            return parts[0] * 60 + parts[1]
        return int(parts[0])
    except Exception:
        return 0
