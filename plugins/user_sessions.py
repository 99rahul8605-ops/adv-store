"""Optional admin-only user session connections. Does not alter delivery logic."""
import asyncio
from pyrogram import filters, StopPropagation
from pyrogram.types import Message
from bot import Bot
from config import ADMINS, APP_ID, API_HASH

_sessions = {}
_pending = {}
_stage_locks = {}

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
    _stage_locks.pop(msg.from_user.id, None)
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
    _stage_locks.pop(msg.from_user.id, None)
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




async def _telethon_input_peer(client, ref):
    """Resolve a peer only from this logged-in user's accessible dialogs."""
    try:
        return await client.get_input_entity(ref)
    except (ValueError, TypeError):
        from telethon import utils
        async for dialog in client.iter_dialogs():
            if utils.get_peer_id(dialog.entity) == ref:
                return dialog.input_entity
        return None


async def _pyrogram_accessible_chat(client, ref):
    """Prime a user session's chat cache via its dialogs if necessary."""
    try:
        await client.get_chat(ref)
        return True
    except Exception:
        async for dialog in client.get_dialogs():
            if getattr(dialog.chat, "id", None) == ref:
                return True
        return False

async def session_read_status(owner_id: int, chat_id, message_id: int) -> str:
    """Check a post using the already connected user account, without copying it.

    Status values: not_connected, available, chat_not_found, post_unavailable,
    access_error. No access hashes or message data are exposed to the bot user.
    """
    state = _sessions.get(owner_id)
    if state is None:
        return "not_connected"

    kind, client = state
    try:
        if kind == "telethon":
            # A raw t.me/c chat ID doesn't contain the access hash needed by
            # Telethon. A freshly imported StringSession may have no peer cache.
            entity = await _telethon_input_peer(client, chat_id)
            if entity is None:
                return "chat_not_found"
            post = await client.get_messages(entity, ids=message_id)
        elif kind == "pyrogram":
            try:
                post = await client.get_messages(chat_id, message_id)
            except (ValueError, KeyError) as exc:
                # Populate Pyrogram's per-session peer cache by walking the
                # logged-in account's own dialogs, then retry the lookup.
                found = False
                async for dialog in client.get_dialogs():
                    if getattr(dialog.chat, "id", None) == chat_id:
                        found = True
                        break
                if not found:
                    return "chat_not_found"
                post = await client.get_messages(chat_id, message_id)
            except Exception as exc:
                # Pyrogram can also raise its own PEER_ID_INVALID exception.
                if "PEER_ID_INVALID" not in str(exc).upper() and "PEERIDINVALID" not in type(exc).__name__.upper():
                    raise
                found = False
                async for dialog in client.get_dialogs():
                    if getattr(dialog.chat, "id", None) == chat_id:
                        found = True
                        break
                if not found:
                    return "chat_not_found"
                post = await client.get_messages(chat_id, message_id)
        else:
            return "access_error"
        return "available" if post and not getattr(post, "empty", False) else "post_unavailable"
    except Exception:
        return "access_error"


async def session_can_read(owner_id: int, chat_id, message_id: int) -> bool:
    """Backwards-compatible boolean check; does not change file delivery."""
    return await session_read_status(owner_id, chat_id, message_id) == "available"


async def stage_to_db_channel(owner_id: int, source_chat: int, first_id: int,
                              last_id: int, db_chat: int, db_username: str = ""):
    """Forward authorized source posts using a connected account into the bot DB.

    Returns ((first_db_id, last_db_id), None) on success, otherwise
    (None, user-facing error). The existing bot /start copy flow is unchanged.
    Telegram forward protection is respected; media is never downloaded to disk.
    """
    state = _sessions.get(owner_id)
    if not state:
        return None, "Session disconnected. Use /connect telethon or /connect pyrogram again."
    if source_chat == db_chat:
        return (first_id, last_id), None
    if abs(last_id - first_id) > 199 or min(first_id, last_id) < 1:
        return None, "Batch must contain 1 to 200 posts."
    kind, user_client = state
    lock = _stage_locks.setdefault(owner_id, asyncio.Lock())
    async with lock:
        ids = list(range(first_id, last_id + (1 if last_id >= first_id else -1),
                         1 if last_id >= first_id else -1))
        try:
            if kind == "telethon":
                src = await _telethon_input_peer(user_client, source_chat)
                if src is None:
                    return None, "Source channel is not accessible to your connected account."
                # Use DB username if provided (it can resolve a fresh account's cache).
                dest = await _telethon_input_peer(user_client, db_username or db_chat)
                if dest is None:
                    return None, "Connected account cannot find the DB channel. Add it there as an admin with Post Messages permission."
                posts = await user_client.get_messages(src, ids=ids)
                if not isinstance(posts, (list, tuple)):
                    posts = [posts]
                if len(posts) != len(ids) or any(p is None or not getattr(p, "id", 0) for p in posts):
                    return None, "One or more posts in that range are missing or inaccessible. Nothing was forwarded."
                if any(getattr(p, "noforwards", False) for p in posts):
                    return None, "Source content has forwarding protection. It cannot be relayed."
                sent = await user_client.forward_messages(dest, ids, from_peer=src, silent=True)
            elif kind == "pyrogram":
                if not await _pyrogram_accessible_chat(user_client, source_chat):
                    return None, "Source channel is not accessible to your connected Pyrogram account."
                dest = db_username or db_chat
                if not await _pyrogram_accessible_chat(user_client, dest):
                    return None, "Connected account cannot access the DB channel. Add it there as an admin with Post Messages permission."
                posts = await user_client.get_messages(source_chat, ids)
                if not isinstance(posts, (list, tuple)):
                    posts = [posts]
                if len(posts) != len(ids) or any(p is None or getattr(p, "empty", False) for p in posts):
                    return None, "One or more posts in that range are missing or inaccessible. Nothing was forwarded."
                if any(getattr(p, "has_protected_content", False) for p in posts):
                    return None, "Source content has forwarding protection. It cannot be relayed."
                sent = await user_client.forward_messages(
                    chat_id=dest, from_chat_id=source_chat,
                    message_ids=ids, disable_notification=True
                )
            else:
                return None, "Unknown session type; reconnect."
        except Exception as exc:
            name = type(exc).__name__
            if "FloodWait" in name:
                return None, "Telegram rate limit reached. Retry later."
            if "Protected" in name or "ForwardsRestricted" in name:
                return None, "This channel restricts forwarding. Content was not relayed."
            if "Admin" in name or "WriteForbidden" in name or "ChatWrite" in name:
                return None, "Your connected account needs Post Messages permission in the DB channel."
            return None, ("Telegram could not forward the post(s) to the DB channel (" + name + "). "
                          "Confirm your account can post there and is authorized to share this content.")
        if not isinstance(sent, (list, tuple)):
            sent = [sent]
        forwarded_ids = [getattr(x, "id", None) for x in sent]
        if (len(forwarded_ids) != len(ids) or any(x is None for x in forwarded_ids)
            or len(set(forwarded_ids)) != len(ids)
            or sorted(forwarded_ids) != list(range(min(forwarded_ids), max(forwarded_ids) + 1))):
            return None, ("Telegram forwarded only part of the range, or another post "
                          "interrupted the DB sequence. No link was created. Check your DB channel.")
        return (forwarded_ids[0], forwarded_ids[-1]), None
