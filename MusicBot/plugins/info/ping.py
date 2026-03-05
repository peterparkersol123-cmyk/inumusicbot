import time
from pyrogram import Client, filters
from pyrogram.types import Message

from MusicBot import bot, boot_time
from MusicBot.helpers._utilities import get_system_stats, uptime_str


@bot.on_message(filters.command(["ping", "alive"]))
async def ping_cmd(client: Client, message: Message):
    start = time.monotonic()
    msg = await message.reply("Pong!")
    elapsed = (time.monotonic() - start) * 1000

    stats = get_system_stats()
    up = uptime_str(boot_time)

    await msg.edit(
        f"<b>Pong!</b> <code>{elapsed:.1f}ms</code>\n\n"
        f"<b>Uptime:</b> {up}\n"
        f"<b>CPU:</b> {stats['cpu']}\n"
        f"<b>RAM:</b> {stats['ram_used']} / {stats['ram_total']} ({stats['ram_percent']})\n"
        f"<b>Disk:</b> {stats['disk_used']} / {stats['disk_total']}"
    )


@bot.on_message(filters.command(["stats"]))
async def stats_cmd(client: Client, message: Message):
    stats = get_system_stats()
    up = uptime_str(boot_time)
    from MusicBot import VERSION
    await message.reply(
        f"<b>Bot Stats</b>\n"
        f"Version: <code>{VERSION}</code>\n"
        f"Uptime: {up}\n"
        f"CPU: {stats['cpu']}\n"
        f"RAM: {stats['ram_used']} / {stats['ram_total']}\n"
        f"Disk: {stats['disk_used']} / {stats['disk_total']}"
    )
