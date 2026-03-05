from pyrogram import Client, filters
from pyrogram.types import Message

from MusicBot import bot


@bot.on_message(filters.command(["start"]))
async def start_cmd(client: Client, message: Message):
    me = await client.get_me()
    await message.reply(
        f"Hi! I'm <b>{me.first_name}</b>, a music bot for Telegram group voice chats.\n\n"
        "Add me to a group and start a voice chat, then use:\n"
        "<code>/play &lt;song name or YouTube URL&gt;</code> to play music.\n\n"
        "<b>Commands:</b>\n"
        "/play — Play a song\n"
        "/skip — Skip current song\n"
        "/pause — Pause\n"
        "/resume — Resume\n"
        "/stop — Stop and clear queue\n"
        "/queue — View queue\n"
        "/loop — Toggle loop mode\n"
        "/shuffle — Shuffle queue\n"
        "/seek — Seek to position\n"
        "/ping — Check bot latency\n"
    )
