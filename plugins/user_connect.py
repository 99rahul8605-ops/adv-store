"""Owner-only session pairing via private DM; never echoes or stores session strings."""
from pyrogram import Client, filters
from config import ADMINS
from TechVJ.bot.user_sessions import connect, connected, detach

# Temporary pending connection prompts, keyed by Telegram user ID.
_pending: dict[int, str] = {}


def _admin(message):
    return (message.chat.type.value == 'private' and message.from_user is not None
            and message.from_user.id in ADMINS)


@Client.on_message(filters.command('connect') & filters.private)
async def connect_prompt(_, message):
    if not _admin(message):
        return await message.reply_text('This command is restricted to bot administrators.')
    if connected(message.from_user.id):
        return await message.reply_text('Already connected. Use /logout to disconnect first.')
    if len(message.command) != 2 or message.command[1].lower() not in ('pyrogram', 'telethon'):
        return await message.reply_text('Usage: /connect pyrogram  OR  /connect telethon')
    lib = message.command[1].lower()
    _pending[message.from_user.id] = lib
    await message.reply_text(
        f'Send your {lib.title()} StringSession as the next private message. '
        'Only use this with a bot you control. The bot will try to delete your message. '
        'Use /cancel to exit. Do not send OTPs or passwords.'
    )


@Client.on_message(filters.command('cancel') & filters.private)
async def cancel_prompt(_, message):
    if not _admin(message):
        return
    _pending.pop(message.from_user.id, None)
    await message.reply_text('Connection request cancelled.')


@Client.on_message(filters.command('sessionstatus') & filters.private)
async def status(_, message):
    if not _admin(message):
        return
    account = connected(message.from_user.id)
    if not account:
        return await message.reply_text('No user session connected.')
    await message.reply_text(
        f'Connected via {account.library.title()} to account ID {account.user_id} '
        f'(name: {account.name}).'
    )


@Client.on_message(filters.command('logout') & filters.private)
async def logout(_, message):
    if not _admin(message):
        return
    _pending.pop(message.from_user.id, None)
    disconnected = await detach(message.from_user.id)
    await message.reply_text(
        'Disconnected from this bot. Telegram authorization was NOT revoked; '
        'you can reconnect with the same string later.' if disconnected
        else 'No connected user session. Telegram authorization was not changed.'
    )


@Client.on_message(filters.private & filters.text & ~filters.command([
    'connect', 'cancel', 'sessionstatus', 'logout'
]), group=-2)
async def accept_session(bot, message):
    if not _admin(message):
        return
    owner_id = message.from_user.id
    lib = _pending.pop(owner_id, None)
    if lib is None:
        return
    session = message.text.strip()
    # Never print/log/reply with session; remove sensitive message before network calls.
    try:
        await message.delete()
    except Exception:
        await bot.send_message(owner_id, 'Could not delete your session message; please delete it manually.')
    if len(session) < 40 or len(session) > 10000 or any(ch.isspace() for ch in session):
        return await bot.send_message(owner_id, 'Invalid session string format. Use /connect to try again.')
    notice = await bot.send_message(owner_id, f'Checking {lib.title()} session...')
    try:
        user = await connect(owner_id, lib, session)
        await notice.edit_text(
            f'Connected successfully to Telegram account ID {user.user_id} via '
            f'{lib.title()}. Use /sessionstatus or /logout. No link was generated.'
        )
    except Exception:
        # Avoid leaking exception text: upstream exceptions may contain credential fragments.
        await notice.edit_text('Connection failed. Check that the session is valid and matches API_ID/API_HASH.')
