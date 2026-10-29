"""Ephemeral, admin-only Telegram account connections.

Never store string sessions, never export them, and do not log credentials.
/logout disconnects locally without calling Telegram log_out().
"""
import asyncio
import re
from dataclasses import dataclass
from pyrogram import filters, Client
from bot import Bot
from config import ADMINS, OWNER_ID, APP_ID, API_HASH

AUTHORIZED = set(ADMINS + [OWNER_ID]) - {0}
_sessions = {}  # Telegram admin id -> (provider, connected client)
_pending = {}   # Telegram admin id -> provider


async def disconnect_all():
    for owner in list(_sessions):
        await _disconnect(owner)


async def _disconnect(owner):
    item = _sessions.pop(owner, None)
    if item:
        provider, client = item
        try:
            if provider == 'pyrogram':
                await client.stop()
            else:
                await client.disconnect()
        except Exception:
            pass


async def resolve_user_source(owner, text):
    item = _sessions.get(owner)
    if not item or not text:
        return None
    match = re.search(r'(?:https?://)?t\.me/(c/\d+|[A-Za-z][A-Za-z0-9_]{3,})/(\d+)(?:[/?#]|$)', text)
    if not match:
        return None
    ref, mid = match.group(1), int(match.group(2))
    peer = int('-100' + ref[2:]) if ref.startswith('c/') else ref
    provider, account = item
    try:
        if provider == 'pyrogram':
            chat = await account.get_chat(peer)
            # Verify the message exists and user account can read it.
            msg = await account.get_messages(chat.id, mid)
            if not msg or getattr(msg, 'empty', False):
                return None
            return chat, mid
        else:
            entity = await account.get_entity(peer)
            msg = await account.get_messages(entity, ids=mid)
            if not msg:
                return None
            from types import SimpleNamespace
            return SimpleNamespace(id=-(10**12 + entity.id), username=getattr(entity, 'username', None)), mid
    except Exception:
        return None


@Bot.on_message(filters.private & filters.user(list(AUTHORIZED)) & filters.command('connect'))
async def connect(client, message):
    owner = message.from_user.id
    if len(message.command) != 2 or message.command[1].lower() not in ('pyrogram', 'telethon'):
        await message.reply_text('Usage: /connect pyrogram OR /connect telethon')
        return
    _pending[owner] = message.command[1].lower()
    await message.reply_text('Send your own Telegram StringSession in THIS private chat. It will be deleted after reading when permissions allow. /cancel to abort. Never share sessions in groups.')


@Bot.on_message(filters.private & filters.user(list(AUTHORIZED)) & filters.command('cancel'))
async def cancel(client, message):
    _pending.pop(message.from_user.id, None)
    await message.reply_text('Connection cancelled.')


@Bot.on_message(filters.private & filters.user(list(AUTHORIZED)) & filters.command('sessionstatus'))
async def status(client, message):
    item = _sessions.get(message.from_user.id)
    await message.reply_text('Connected: ' + item[0] if item else 'No user session connected.')


@Bot.on_message(filters.private & filters.user(list(AUTHORIZED)) & filters.command('logout'))
async def logout(client, message):
    owner = message.from_user.id
    _pending.pop(owner, None)
    await _disconnect(owner)
    await message.reply_text('Disconnected from bot. Your Telegram authorization has NOT been revoked; you may reuse the original session string.')


# group=-1 ensures this is processed before the generic post copier.
@Bot.on_message(filters.private & filters.user(list(AUTHORIZED)) & filters.text, group=-1)
async def receive_session(client, message):
    owner = message.from_user.id
    provider = _pending.get(owner)
    if not provider or message.text.startswith('/'):
        return
    _pending.pop(owner, None)
    secret = message.text.strip()
    try:
        await message.delete()
    except Exception:
        pass
    if not 40 <= len(secret) <= 8192:
        await client.send_message(owner, 'Invalid session string length.')
        message.stop_propagation()
        return
    await _disconnect(owner)
    account = None
    try:
        if provider == 'pyrogram':
            from pyrogram import Client as UserClient
            account = UserClient(name=f'admin_{owner}', api_id=APP_ID, api_hash=API_HASH,
                                 session_string=secret, in_memory=True, no_updates=True)
            await account.start()
            me = await account.get_me()
        else:
            from telethon import TelegramClient
            from telethon.sessions import StringSession
            account = TelegramClient(StringSession(secret), APP_ID, API_HASH)
            await account.connect()
            if not await account.is_user_authorized():
                raise ValueError('Session is not authorized')
            me = await account.get_me()
        _sessions[owner] = (provider, account)
        await client.send_message(owner, f'✅ {provider} connected as account ID {me.id}. /logout only disconnects locally. Sessions are not persisted across restarts.')
    except Exception as exc:
        if account is not None:
            try:
                if provider == 'pyrogram':
                    await account.stop()
                else:
                    await account.disconnect()
            except Exception:
                pass
        await client.send_message(owner, f'❌ Session connection failed ({type(exc).__name__}). No session stored.')
    finally:
        message.stop_propagation()
