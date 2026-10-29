#(©)Codexbotz

import base64
import re
import asyncio
import logging 
from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from config import FORCE_SUB_CHANNEL, ADMINS, AUTO_DELETE_TIME, AUTO_DEL_SUCCESS_MSG
from pyrogram.errors.exceptions.bad_request_400 import UserNotParticipant
from pyrogram.errors import FloodWait

async def is_subscribed(filter, client, update):
    if not FORCE_SUB_CHANNEL:
        return True
    user_id = update.from_user.id
    if user_id in ADMINS:
        return True
    try:
        member = await client.get_chat_member(chat_id = FORCE_SUB_CHANNEL, user_id = user_id)
    except UserNotParticipant:
        return False

    if not member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.MEMBER]:
        return False
    else:
        return True

async def encode(string):
    string_bytes = string.encode("ascii")
    base64_bytes = base64.urlsafe_b64encode(string_bytes)
    base64_string = (base64_bytes.decode("ascii")).strip("=")
    return base64_string

async def decode(base64_string):
    base64_string = base64_string.strip("=") # links generated before this commit will be having = sign, hence striping them to handle padding errors.
    base64_bytes = (base64_string + "=" * (-len(base64_string) % 4)).encode("ascii")
    string_bytes = base64.urlsafe_b64decode(base64_bytes) 
    string = string_bytes.decode("ascii")
    return string

async def get_messages(client, message_ids, chat_id=None):
    """Fetch messages from a selected channel, not just the primary DB."""
    chat_id = chat_id if chat_id is not None else client.db_channel.id
    ids = list(message_ids)
    messages = []
    for index in range(0, len(ids), 200):
        batch = ids[index:index + 200]
        try:
            result = await client.get_messages(chat_id=chat_id, message_ids=batch)
        except FloodWait as e:
            await asyncio.sleep(getattr(e, 'value', getattr(e, 'x', 1)))
            result = await client.get_messages(chat_id=chat_id, message_ids=batch)
        if not isinstance(result, list):
            result = [result]
        messages.extend(m for m in result if m and not getattr(m, 'empty', False))
    return messages


async def get_source(client, message):
    """Resolve a forwarded channel post or t.me post URL. Bot access is required."""
    forwarded_chat = getattr(message, 'forward_from_chat', None)
    forwarded_id = getattr(message, 'forward_from_message_id', None)
    if forwarded_chat and forwarded_id:
        chat = await client.get_chat(forwarded_chat.id)
        return chat, forwarded_id
    if not message.text:
        return None
    match = re.search(r'(?:https?://)?t\.me/(c/\d+|[a-zA-Z][a-zA-Z0-9_]{3,})/(\d+)(?:[/?#]|$)', message.text)
    if not match:
        return None
    ref = match.group(1)
    chat_ref = int('-100' + ref[2:]) if ref.startswith('c/') else ref
    chat = await client.get_chat(chat_ref)
    return chat, int(match.group(2))


async def get_message_id(client, message):
    result = await get_source(client, message)
    return result[1] if result else 0


async def encode_channel_link(chat_id, first, last=None):
    # Versioned payload, backward compatible with old get-encoded links.
    if last is None:
        return await encode(f'v2:{chat_id}:{first}')
    return await encode(f'v2:{chat_id}:{first}:{last}')


def get_readable_time(seconds: int) -> str:
    count = 0
    up_time = ""
    time_list = []
    time_suffix_list = ["s", "m", "h", "days"]
    while count < 4:
        count += 1
        remainder, result = divmod(seconds, 60) if count < 3 else divmod(seconds, 24)
        if seconds == 0 and remainder == 0:
            break
        time_list.append(int(result))
        seconds = int(remainder)
    hmm = len(time_list)
    for x in range(hmm):
        time_list[x] = str(time_list[x]) + time_suffix_list[x]
    if len(time_list) == 4:
        up_time += f"{time_list.pop()}, "
    time_list.reverse()
    up_time += ":".join(time_list)
    return up_time

async def delete_file(messages, client, process):
    await asyncio.sleep(AUTO_DELETE_TIME)
    for msg in messages:
        try:
            await client.delete_messages(chat_id=msg.chat.id, message_ids=[msg.id])
        except Exception as e:
            await asyncio.sleep(e.x)
            print(f"The attempt to delete the media {msg.id} was unsuccessful: {e}")

    await process.edit_text(AUTO_DEL_SUCCESS_MSG)


subscribed = filters.create(is_subscribed)
