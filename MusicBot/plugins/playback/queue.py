from pyrogram import Client, filters
from pyrogram.types import Message

from MusicBot import bot, queue as q


@bot.on_message(filters.command(["queue", "que", "q"]) & filters.group)
async def queue_cmd(client: Client, message: Message):
    chat_id = message.chat.id
    tracks = q.get_queue(chat_id)

    if not tracks:
        return await message.reply("Queue is empty.")

    lines = []
    for i, track in enumerate(tracks[:20]):
        duration = track.duration_str()
        if i == 0:
            lines.append(f"▶️ <b>{track.title}</b> [{duration}] — by {track.requested_by_name}")
        else:
            lines.append(f"{i}. <b>{track.title}</b> [{duration}] — by {track.requested_by_name}")

    loop_mode = q.get_loop(chat_id)
    if loop_mode != "off":
        loop_label = "🔂 Single" if loop_mode == "single" else "🔁 Queue"
        lines.append(f"\nLoop: {loop_label}")

    total = q.size(chat_id)
    if total > 20:
        lines.append(f"\n...and {total - 20} more.")

    await message.reply("\n".join(lines))


@bot.on_message(filters.command(["shuffle"]) & filters.group)
async def shuffle_cmd(client: Client, message: Message):
    chat_id = message.chat.id
    if q.size(chat_id) <= 1:
        return await message.reply("Not enough tracks in queue to shuffle.")
    q.shuffle(chat_id)
    await message.reply("Queue shuffled.")


@bot.on_message(filters.command(["loop"]) & filters.group)
async def loop_cmd(client: Client, message: Message):
    chat_id = message.chat.id
    args = message.command[1:]
    mode_arg = args[0].lower() if args else None

    current = q.get_loop(chat_id)
    if mode_arg in ("single", "one", "1"):
        q.set_loop(chat_id, "single")
        await message.reply("Loop mode: 🔂 Single (current track will repeat)")
    elif mode_arg in ("queue", "all", "q"):
        q.set_loop(chat_id, "queue")
        await message.reply("Loop mode: 🔁 Queue (entire queue will loop)")
    elif mode_arg in ("off", "disable", "0"):
        q.set_loop(chat_id, "off")
        await message.reply("Loop disabled.")
    else:
        # Toggle
        modes = ["off", "single", "queue"]
        next_mode = modes[(modes.index(current) + 1) % len(modes)]
        q.set_loop(chat_id, next_mode)
        labels = {"off": "Off", "single": "🔂 Single", "queue": "🔁 Queue"}
        await message.reply(f"Loop mode set to: {labels[next_mode]}")
