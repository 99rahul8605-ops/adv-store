"""Volatile user-session connections. Disconnect does not revoke Telegram authorization."""
import asyncio
from dataclasses import dataclass
from typing import Any

from config import API_HASH, API_ID


@dataclass
class ConnectedUser:
    library: str
    client: Any
    user_id: int
    name: str


_connections: dict[int, ConnectedUser] = {}
_locks: dict[int, asyncio.Lock] = {}


def connected(owner_id: int) -> ConnectedUser | None:
    return _connections.get(owner_id)


async def connect(owner_id: int, library: str, session: str) -> ConnectedUser:
    """Check the supplied session by signing in; don't persist it or write it to logs."""
    lock = _locks.setdefault(owner_id, asyncio.Lock())
    async with lock:
        if owner_id in _connections:
            raise ValueError("Already connected. Use /logout before changing accounts.")
        client = None
        try:
            if library == 'pyrogram':
                from pyrogram import Client
                client = Client(
                    name=f'user_{owner_id}', api_id=API_ID, api_hash=API_HASH,
                    session_string=session, in_memory=True, no_updates=True
                )
                await client.start()
                me = await client.get_me()
                if me.is_bot:
                    raise ValueError('A Telegram user session is required, not a bot session.')
                display = me.first_name or str(me.id)
            elif library == 'telethon':
                from telethon import TelegramClient
                from telethon.sessions import StringSession
                client = TelegramClient(StringSession(session), API_ID, API_HASH)
                await client.connect()
                if not await client.is_user_authorized():
                    raise ValueError('The Telethon session is not authorized.')
                me = await client.get_me()
                if getattr(me, 'bot', False):
                    raise ValueError('A Telegram user session is required, not a bot session.')
                display = me.first_name or str(me.id)
            else:
                raise ValueError('Choose pyrogram or telethon.')
            result = ConnectedUser(library, client, me.id, display)
            _connections[owner_id] = result
            return result
        except Exception:
            if client is not None:
                await _disconnect_client(library, client)
            raise


async def _disconnect_client(library: str, client: Any) -> None:
    # IMPORTANT: use stop()/disconnect(), never log_out()/log_out.
    try:
        if library == 'pyrogram':
            await client.stop()
        else:
            await client.disconnect()
    except Exception:
        pass


async def detach(owner_id: int) -> bool:
    lock = _locks.setdefault(owner_id, asyncio.Lock())
    async with lock:
        session = _connections.pop(owner_id, None)
        if session is None:
            return False
        await _disconnect_client(session.library, session.client)
        return True


async def detach_all() -> None:
    for owner_id in list(_connections):
        await detach(owner_id)
