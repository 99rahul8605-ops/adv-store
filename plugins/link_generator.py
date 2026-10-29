from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from bot import Bot
from config import ADMINS
from helper_func import encode, get_message_source
from plugins.prompt_state import track_dialog

async def ask_source(client, user_id, text):
    while True:
        try:
            reply = await client.ask(chat_id=user_id, text=text,
                filters=filters.forwarded | (filters.text & ~filters.forwarded), timeout=90)
        except Exception:
            return None
        source, reason = await get_message_source(client, reply, diagnose=True)
        if source:
            return source, reply
        await reply.reply_text("❌ " + (reason or "Unable to access this post."))
        # user may send a corrected link, continue until timeout of ask

async def send_link(client, reply, payload):
    value = await encode(payload)
    link = f"https://t.me/{client.username}?start={value}"
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Share URL", url=f"https://telegram.me/share/url?url={link}")]])
    await reply.reply_text(f"<b>Here is your link</b>\n\n{link}", reply_markup=markup)

@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("batch"))
async def batch(client: Client, message: Message):
    async with track_dialog(client, message.from_user.id):
        first = await ask_source(client, message.from_user.id,
            "Forward the first message from an accessible channel/group, or send its post link")
        if not first:
            return
        last = await ask_source(client, message.from_user.id,
            "Forward the last message from the SAME channel/group, or send its post link")
        if not last:
            return
        if first[0][0] != last[0][0]:
            await last[1].reply_text("❌ The posts must belong to the same channel/group. Run /batch again.")
            return
        a, b = first[0][1], last[0][1]
        if abs(a-b)>199:
            await last[1].reply_text("❌ Maximum 200 messages per batch.")
            return
        await send_link(client, last[1], f"src:{first[0][0]}:{a}:{b}")

@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("genlink"))
async def link_generator(client: Client, message: Message):
    async with track_dialog(client, message.from_user.id):
        result = await ask_source(client, message.from_user.id,
            "Forward a message from an accessible channel/group or send its post link")
        if result:
            await send_link(client, result[1], f"src:{result[0][0]}:{result[0][1]}")
