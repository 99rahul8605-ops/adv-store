#(©)Codexbotz

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from bot import Bot
from config import ADMINS
from helper_func import encode, get_message_source

@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command('batch'))
async def batch(client: Client, message: Message):
    while True:
        try:
            first_message = await client.ask(text = "Forward the first message from an accessible channel/group, or send its post link", chat_id = message.from_user.id, filters=(filters.forwarded | (filters.text & ~filters.forwarded)), timeout=60)
        except:
            return
        first_source = await get_message_source(client, first_message)
        if first_source:
            break
        else:
            await first_message.reply("❌ Error\n\nCould not access this post, or the two posts are from different chats", quote = True)
            continue

    while True:
        try:
            second_message = await client.ask(text = "Forward the last message from the SAME channel/group, or send its post link", chat_id = message.from_user.id, filters=(filters.forwarded | (filters.text & ~filters.forwarded)), timeout=60)
        except:
            return
        last_source = await get_message_source(client, second_message)
        if last_source and last_source[0] == first_source[0]:
            break
        else:
            await second_message.reply("❌ Error\n\nCould not access this post, or the two posts are from different chats", quote = True)
            continue


    string = f"src:{first_source[0]}:{first_source[1]}:{last_source[1]}"
    base64_string = await encode(string)
    link = f"https://t.me/{client.username}?start={base64_string}"
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Share URL", url=f'https://telegram.me/share/url?url={link}')]])
    await second_message.reply_text(f"<b>Here is your link</b>\n\n{link}", quote=True, reply_markup=reply_markup)


@Bot.on_message(filters.private & filters.user(ADMINS) & filters.command('genlink'))
async def link_generator(client: Client, message: Message):
    while True:
        try:
            channel_message = await client.ask(text = "Forward a message from an accessible channel/group or send its post link", chat_id = message.from_user.id, filters=(filters.forwarded | (filters.text & ~filters.forwarded)), timeout=60)
        except:
            return
        source = await get_message_source(client, channel_message)
        if source:
            break
        else:
            await channel_message.reply("❌ Error\n\nBot cannot access that channel/group post", quote = True)
            continue

    base64_string = await encode(f"src:{source[0]}:{source[1]}")
    link = f"https://t.me/{client.username}?start={base64_string}"
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Share URL", url=f'https://telegram.me/share/url?url={link}')]])
    await channel_message.reply_text(f"<b>Here is your link</b>\n\n{link}", quote=True, reply_markup=reply_markup)
