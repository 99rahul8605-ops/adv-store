from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot import Bot
from config import ADMINS, OWNER_ID
from helper_func import get_source, encode_channel_link

ADMIN_FILTER = filters.user(set(ADMINS + [OWNER_ID]))

async def ask_source(client, user_id, prompt):
    while True:
        try:
            msg = await client.ask(chat_id=user_id, text=prompt, timeout=90)
        except Exception:
            return None, None
        try:
            source = await get_source(client, msg)
            if source:
                chat, mid = source
                check = await client.get_messages(chat.id, mid)
                if check and not getattr(check, 'empty', False):
                    return source, msg
        except Exception:
            pass
        await msg.reply_text('❌ Bot cannot read this source. Add bot to that channel/group with access, or send a valid public message link. A user session alone does not give the bot permission to deliver private files.')

async def output_link(client, reply, chat, first, last=None):
    # The public username primes bot peer resolution on later restarts.
    ref = '@' + chat.username if getattr(chat, 'username', None) else str(chat.id)
    payload = await encode_channel_link(ref, first, last)
    url = f'https://t.me/{client.username}?start={payload}'
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton('🔁 Share URL', url=f'https://telegram.me/share/url?url={url}')]])
    await reply.reply_text(f'<b>File link:</b>\n{url}', reply_markup=keyboard, quote=True)

@Bot.on_message(filters.private & ADMIN_FILTER & filters.command('genlink'))
async def genlink(client, message):
    source, reply = await ask_source(client, message.from_user.id, 'Forward a channel post or send its t.me message link.')
    if source:
        chat, mid = source
        await output_link(client, reply, chat, mid)

@Bot.on_message(filters.private & ADMIN_FILTER & filters.command('batch'))
async def batch(client, message):
    source, reply = await ask_source(client, message.from_user.id, 'Send FIRST post link or forward it.')
    if not source:
        return
    chat, first = source
    source2, reply2 = await ask_source(client, message.from_user.id, 'Send LAST post link from the SAME channel.')
    if not source2:
        return
    chat2, last = source2
    if chat.id != chat2.id:
        await reply2.reply_text('❌ Both messages must belong to the same channel.')
        return
    if abs(last - first) > 199:
        await reply2.reply_text('❌ Maximum 200 messages per batch.')
        return
    await output_link(client, reply2, chat, first, last)
