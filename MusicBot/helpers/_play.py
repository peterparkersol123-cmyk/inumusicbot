"""
checkUB decorator — validates play commands before execution.
"""
import functools
import logging
from pyrogram.types import Message
from pyrogram.enums import ChatType
from pyrogram.errors import ChatWriteForbidden

from config import Config
from MusicBot.helpers._admins import is_admin

LOGGER = logging.getLogger("MusicBot.Play")


def checkUB(func):
    """
    Validates that:
    - The command is in a supergroup
    - There is a query or a replied audio/document
    - The queue is not full
    - The user has permission (admin or auth'd)
    """
    @functools.wraps(func)
    async def wrapper(client, message: Message, *args, **kwargs):
        from MusicBot import queue, db

        chat_id = message.chat.id
        user = message.from_user

        # Must be a supergroup
        if message.chat.type not in (ChatType.SUPERGROUP, ChatType.GROUP):
            return await _safe_reply(message, "This command only works in groups.")

        # Anonymous admins are not supported
        if not user:
            return await _safe_reply(message, "Anonymous admins cannot use this command.")

        user_id = user.id

        # Needs a query or replied media
        query = " ".join(message.command[1:]).strip() if len(message.command) > 1 else ""
        reply = message.reply_to_message
        has_media = reply and (reply.audio or reply.document or reply.video)

        if not query and not has_media:
            return await _safe_reply(
                message,
                "Please provide a song name, YouTube link, or reply to an audio file."
            )

        # Queue limit check
        if queue.is_full(chat_id):
            return await _safe_reply(
                message,
                f"Queue is full ({Config.QUEUE_LIMIT} tracks max). Skip or stop something first."
            )

        # Duration limit check (URL case checked later after info fetch)

        # Permission: owner, sudo, or admin or auth'd user
        is_owner = user_id == Config.OWNER_ID
        is_chat_admin = await is_admin(client, chat_id, user_id)
        auth_users = await db.get_auth(chat_id)
        is_authorized = user_id in auth_users

        if not (is_owner or is_chat_admin or is_authorized):
            # Check if play mode is locked to admins
            play_mode = await db.get_setting(chat_id, "play_mode", "all")
            if play_mode == "admin":
                return await _safe_reply(message, "Only admins can use play commands in this group.")

        return await func(client, message, query=query, *args, **kwargs)

    return wrapper


async def _safe_reply(message: Message, text: str):
    try:
        return await message.reply(text)
    except ChatWriteForbidden:
        return None
