import logging
from pyrogram import Client
from pyrogram.enums import ChatMembersFilter, ChatMemberStatus
from pyrogram.errors import UserNotParticipant, ChatAdminRequired

LOGGER = logging.getLogger("MusicBot.Admins")

# In-memory cache: chat_id -> set of admin user_ids
_admin_cache: dict[int, set[int]] = {}


async def get_admins(client: Client, chat_id: int, force_refresh: bool = False) -> set[int]:
    if not force_refresh and chat_id in _admin_cache:
        return _admin_cache[chat_id]

    admins: set[int] = set()
    try:
        async for member in client.get_chat_members(chat_id, filter=ChatMembersFilter.ADMINISTRATORS):
            if not member.user.is_bot:
                admins.add(member.user.id)
    except Exception as e:
        LOGGER.warning(f"Could not fetch admins for {chat_id}: {e}")

    _admin_cache[chat_id] = admins
    return admins


def invalidate_cache(chat_id: int):
    _admin_cache.pop(chat_id, None)


async def is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    admins = await get_admins(client, chat_id)
    return user_id in admins


async def is_chat_admin(client: Client, chat_id: int, user_id: int) -> bool:
    """Check via API directly (bypasses cache)."""
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except (UserNotParticipant, ChatAdminRequired):
        return False
    except Exception:
        return False
