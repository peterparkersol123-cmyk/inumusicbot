from pyrogram import Client, filters
from pyrogram.types import Message

from MusicBot import bot, queue, call
from MusicBot.helpers._admins import is_admin
from MusicBot.helpers._utilities import safe_edit
from config import Config


@bot.on_message(filters.command(["skip", "s"]) & filters.group)
async def skip_cmd(client: Client, message: Message):
    chat_id = message.chat.id
    user = message.from_user

    if not user:
        return

    if not call.is_active(chat_id):
        return await message.reply("Nothing is playing right now.")

    # Only admins/auth'd users can skip
    is_owner = user.id == Config.OWNER_ID
    is_chat_admin = await is_admin(client, chat_id, user.id)
    from MusicBot import db
    auth_users = await db.get_auth(chat_id)
    if not (is_owner or is_chat_admin or user.id in auth_users):
        return await message.reply("Only admins or authorized users can skip.")

    current = queue.current(chat_id)
    if not current:
        return await message.reply("Queue is empty.")

    next_track = queue.skip(chat_id)

    if next_track:
        from MusicBot.plugins.playback.play import _start_playing
        msg = await message.reply(f"Skipped. Now playing: <b>{next_track.title}</b>")
        await _start_playing(chat_id, msg)
    else:
        await call.stop(chat_id)
        await message.reply(f"Skipped <b>{current.title}</b>. Queue is now empty.")
