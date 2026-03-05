from pyrogram import Client, filters
from pyrogram.types import Message

from MusicBot import bot, call, queue
from MusicBot.helpers._admins import is_admin
from config import Config


@bot.on_message(filters.command(["stop", "end"]) & filters.group)
async def stop_cmd(client: Client, message: Message):
    chat_id = message.chat.id
    user = message.from_user

    if not user:
        return
    if not call.is_active(chat_id):
        return await message.reply("Nothing is playing right now.")

    is_owner = user.id == Config.OWNER_ID
    is_chat_admin = await is_admin(client, chat_id, user.id)
    if not (is_owner or is_chat_admin):
        return await message.reply("Only admins can stop the player.")

    queue.clear(chat_id)
    await call.stop(chat_id)
    await message.reply("Stopped playback and cleared the queue.")
