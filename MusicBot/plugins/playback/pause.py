from pyrogram import Client, filters
from pyrogram.types import Message

from MusicBot import bot, call, queue
from MusicBot.helpers._admins import is_admin
from config import Config


@bot.on_message(filters.command(["pause"]) & filters.group)
async def pause_cmd(client: Client, message: Message):
    chat_id = message.chat.id
    user = message.from_user

    if not user:
        return
    if not call.is_active(chat_id):
        return await message.reply("Nothing is playing right now.")

    is_owner = user.id == Config.OWNER_ID
    is_chat_admin = await is_admin(client, chat_id, user.id)
    from MusicBot import db
    auth_users = await db.get_auth(chat_id)
    if not (is_owner or is_chat_admin or user.id in auth_users):
        return await message.reply("Only admins or authorized users can pause.")

    await call.pause(chat_id)
    current = queue.current(chat_id)
    title = current.title if current else "the stream"
    await message.reply(f"Paused: <b>{title}</b>")
