from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from bot import Bot
from config import ADMINS, DB_CHANNEL_USERNAME
from helper_func import encode, get_message_source
from plugins.prompt_state import track_dialog
from plugins.user_sessions import stage_to_db_channel

async def ask_source(client, user_id, text):
    while True:
        try:
            reply = await client.ask(chat_id=user_id, text=text,
                filters=filters.forwarded | (filters.text & ~filters.forwarded), timeout=90)
        except Exception:
            return None
        source, reason = await get_message_source(client, reply, diagnose=True)
        if source:
            return source, reason, reply
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
            await last[2].reply_text("❌ The posts must belong to the same channel/group. Run /batch again.")
            return
        source_chat = first[0][0]
        a, b = first[0][1], last[0][1]
        if abs(a-b)>199:
            await last[2].reply_text("❌ Maximum 200 messages per batch.")
            return
        if first[1] == "session_only" or last[1] == "session_only":
            await last[2].reply_text("Your account can read this private chat. Forwarding permitted posts to the bot's DB channel for normal delivery...")
            staged, error = await stage_to_db_channel(
                message.from_user.id, source_chat, a, b,
                client.db_channel.id, DB_CHANNEL_USERNAME
            )
            if error:
                await last[2].reply_text("❌ " + error)
                return
            a, b = staged
            source_chat = client.db_channel.id
        await send_link(client, last[2], f"src:{source_chat}:{a}:{b}")

@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command("genlink"))
async def link_generator(client: Client, message: Message):
    async with track_dialog(client, message.from_user.id):
        result = await ask_source(client, message.from_user.id,
            "Forward a message from an accessible channel/group or send its post link")
        if result:
            source_chat, mid = result[0]
            if result[1] == "session_only":
                await result[2].reply_text("Forwarding the permitted post to the bot's DB channel for normal delivery...")
                staged, error = await stage_to_db_channel(
                    message.from_user.id, source_chat, mid, mid,
                    client.db_channel.id, DB_CHANNEL_USERNAME
                )
                if error:
                    await result[2].reply_text("❌ " + error)
                    return
                source_chat, mid = client.db_channel.id, staged[0]
            await send_link(client, result[2], f"src:{source_chat}:{mid}")
