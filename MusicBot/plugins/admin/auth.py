from pyrogram import Client, filters
from pyrogram.types import Message

from MusicBot import bot, db
from MusicBot.helpers._admins import is_admin
from config import Config


def _is_owner_or_admin():
    async def _check(_, client: Client, message: Message) -> bool:
        if not message.from_user:
            return False
        if message.from_user.id == Config.OWNER_ID:
            return True
        return await is_admin(client, message.chat.id, message.from_user.id)
    return filters.create(_check)


@bot.on_message(filters.command(["auth"]) & filters.group & _is_owner_or_admin())
async def auth_cmd(client: Client, message: Message):
    target = await _get_target(client, message)
    if not target:
        return
    await db.add_auth(message.chat.id, target.id)
    await message.reply(f"{target.mention} is now authorized to control playback.")


@bot.on_message(filters.command(["unauth"]) & filters.group & _is_owner_or_admin())
async def unauth_cmd(client: Client, message: Message):
    target = await _get_target(client, message)
    if not target:
        return
    await db.remove_auth(message.chat.id, target.id)
    await message.reply(f"{target.mention} has been unauthorized.")


@bot.on_message(filters.command(["authlist"]) & filters.group)
async def authlist_cmd(client: Client, message: Message):
    auth_users = await db.get_auth(message.chat.id)
    if not auth_users:
        return await message.reply("No authorized users in this group.")
    lines = ["<b>Authorized users:</b>"]
    for uid in auth_users:
        try:
            user = await client.get_users(uid)
            lines.append(f"• {user.mention} (<code>{uid}</code>)")
        except Exception:
            lines.append(f"• <code>{uid}</code>")
    await message.reply("\n".join(lines))


async def _get_target(client: Client, message: Message):
    reply = message.reply_to_message
    if reply and reply.from_user:
        return reply.from_user
    args = message.command[1:]
    if args:
        try:
            return await client.get_users(int(args[0]))
        except Exception:
            try:
                return await client.get_users(args[0])
            except Exception:
                pass
    await message.reply("Reply to a user or provide their username/ID.")
    return None
