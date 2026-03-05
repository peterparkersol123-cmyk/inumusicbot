from pyrogram import Client, filters
from pyrogram.types import Message

from MusicBot import bot, db
from config import Config


def _owner_only():
    async def _check(_, client, message: Message) -> bool:
        return message.from_user and message.from_user.id == Config.OWNER_ID
    return filters.create(_check)


@bot.on_message(filters.command(["addsudo"]) & _owner_only())
async def addsudo_cmd(client: Client, message: Message):
    user = await _get_user(client, message)
    if not user:
        return
    await db.add_sudo(user.id)
    await message.reply(f"{user.mention} added as sudo user.")


@bot.on_message(filters.command(["delsudo"]) & _owner_only())
async def delsudo_cmd(client: Client, message: Message):
    user = await _get_user(client, message)
    if not user:
        return
    await db.remove_sudo(user.id)
    await message.reply(f"{user.mention} removed from sudo users.")


@bot.on_message(filters.command(["sudolist"]) & _owner_only())
async def sudolist_cmd(client: Client, message: Message):
    sudoers = await db.get_sudoers()
    if not sudoers:
        return await message.reply("No sudo users.")
    lines = ["<b>Sudo users:</b>"]
    for uid in sudoers:
        try:
            user = await client.get_users(uid)
            lines.append(f"• {user.mention}")
        except Exception:
            lines.append(f"• <code>{uid}</code>")
    await message.reply("\n".join(lines))


async def _get_user(client: Client, message: Message):
    reply = message.reply_to_message
    if reply and reply.from_user:
        return reply.from_user
    args = message.command[1:]
    if args:
        try:
            return await client.get_users(int(args[0]))
        except Exception:
            pass
    await message.reply("Reply to a user or provide their ID.")
    return None
