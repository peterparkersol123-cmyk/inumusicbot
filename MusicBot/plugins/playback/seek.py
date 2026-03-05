from pyrogram import Client, filters
from pyrogram.types import Message

from MusicBot import bot, call, queue
from MusicBot.helpers._admins import is_admin
from config import Config


@bot.on_message(filters.command(["seek"]) & filters.group)
async def seek_cmd(client: Client, message: Message):
    chat_id = message.chat.id
    user = message.from_user

    if not user:
        return
    if not call.is_active(chat_id):
        return await message.reply("Nothing is playing.")

    is_owner = user.id == Config.OWNER_ID
    is_chat_admin = await is_admin(client, chat_id, user.id)
    from MusicBot import db
    auth_users = await db.get_auth(chat_id)
    if not (is_owner or is_chat_admin or user.id in auth_users):
        return await message.reply("Only admins or authorized users can seek.")

    args = message.command[1:]
    if not args:
        return await message.reply("Usage: /seek <seconds>  e.g. /seek 90")

    try:
        seconds = int(args[0])
    except ValueError:
        return await message.reply("Please provide a valid number of seconds.")

    current = queue.current(chat_id)
    if not current:
        return await message.reply("Nothing is in the queue.")
    if current.is_live:
        return await message.reply("Cannot seek in a live stream.")

    try:
        await call.seek(chat_id, seconds, current)
        from MusicBot.helpers._utilities import format_duration
        await message.reply(f"Seeked to {format_duration(seconds)}")
    except Exception as e:
        await message.reply(f"Seek failed: {e}")
