"""Optional admin-only user session connections. Does not alter delivery logic."""
import asyncio
from pyrogram import filters, StopPropagation
from pyrogram.types import Message
from bot import Bot
from config import ADMINS, APP_ID, API_HASH

_sessions = {}
_pending = {}

@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("connect"), group=-10)
async def connect_session(bot, msg: Message):
    if len(msg.command) != 2 or msg.command[1].lower() not in ("pyrogram", "telethon"):
        await msg.reply("Use /connect pyrogram or /connect telethon")
        raise StopPropagation
    _pending[msg.from_user.id] = msg.command[1].lower()
    await msg.reply("Send your OWN StringSession here in this private chat. It will be deleted after processing. /cancel to abort. Treat it as a password.")
    raise StopPropagation

@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("cancel"), group=-10)
async def cancel_session(bot, msg):
    _pending.pop(msg.from_user.id, None)
    await msg.reply("Connection cancelled.")
    raise StopPropagation

@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("sessionstatus"), group=-10)
async def session_status(bot, msg):
    state = _sessions.get(msg.from_user.id)
    await msg.reply(f"Connected: {state[0]}" if state else "No user session connected.")
    raise StopPropagation

@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("logout"), group=-10)
async def disconnect_session(bot, msg):
    _pending.pop(msg.from_user.id, None)
    state = _sessions.pop(msg.from_user.id, None)
    if state:
        kind, client = state
        try:
            await (client.stop() if kind == "pyrogram" else client.disconnect())
        except Exception:
            pass
    await msg.reply("Disconnected from this bot only. Telegram authorization was NOT revoked. Keep your session string to reconnect.")
    raise StopPropagation

@Bot.on_message(filters.private & filters.user(ADMINS) & filters.text & ~filters.command(["connect", "cancel", "logout", "sessionstatus"]), group=-20)
async def receive_session(bot, msg):
    kind = _pending.pop(msg.from_user.id, None)
    if not kind:
        return
    string = msg.text.strip()
    try:
        await msg.delete()
    except Exception:
        pass
    old = _sessions.pop(msg.from_user.id, None)
    if old:
        try:
            await (old[1].stop() if old[0] == "pyrogram" else old[1].disconnect())
        except Exception:
            pass
    client = None
    try:
        if kind == "pyrogram":
            from pyrogram import Client
            client = Client(f"user_{msg.from_user.id}", api_id=APP_ID, api_hash=API_HASH, session_string=string, in_memory=True, no_updates=True)
            await client.start()
            me = await client.get_me()
        else:
            from telethon import TelegramClient
            from telethon.sessions import StringSession
            client = TelegramClient(StringSession(string), APP_ID, API_HASH)
            await client.connect()
            if not await client.is_user_authorized():
                raise ValueError("Unauthorized session")
            me = await client.get_me()
        _sessions[msg.from_user.id] = (kind, client)
        await bot.send_message(msg.chat.id, f"Connected ({kind}) as ID {me.id}. Session is kept in RAM and is not used for file delivery.")
    except Exception as e:
        if client:
            try:
                await (client.stop() if kind == "pyrogram" else client.disconnect())
            except Exception:
                pass
        await bot.send_message(msg.chat.id, f"Connection failed: {type(e).__name__}. Check string, API credentials and session validity.")
    raise StopPropagation


async def session_can_read(owner_id: int, chat_id: int, message_id: int) -> bool:
    """Check account access to a post. Never return credentials or expose file content."""
    state = _sessions.get(owner_id)
    if state is None:
        return False
    kind, client = state
    try:
        if kind == "pyrogram":
            result = await client.get_messages(chat_id, message_id)
            return bool(result and not getattr(result, "empty", False))
        # Telethon uses signed -100 channel IDs but needs peer resolution
        entity = await client.get_input_entity(chat_id)
        result = await client.get_messages(entity, ids=message_id)
        return result is not None
    except Exception:
        return False
