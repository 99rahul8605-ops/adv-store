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
    chat_id = chat_id if chat_id is not None else client.db_channel.id
    messages = []
    total_messages = 0
    while total_messages != len(message_ids):
        temb_ids = message_ids[total_messages:total_messages+200]
        try:
            msgs = await client.get_messages(
                chat_id=chat_id,
                message_ids=temb_ids
            )
        except FloodWait as e:
            await asyncio.sleep(getattr(e, "value", getattr(e, "x", 1)))
            msgs = await client.get_messages(
                chat_id=chat_id,
                message_ids=temb_ids
            )
        except Exception:
            raise
        total_messages += len(temb_ids)
        messages.extend(msgs)
    return messages

async def get_message_source(client, message, *, diagnose=False):
    """Resolve a source post for direct bot access or user-session DB staging.

    When diagnose=True, `session_only` means the caller must stage the post
    into the DB channel before generating a public download link.
    """
    ref = None
    mid = None
    if message.forward_from_chat and message.forward_from_message_id:
        ref = message.forward_from_chat.id
        mid = message.forward_from_message_id
    elif message.text:
        match = re.search(r"(?:https?://)?(?:www\.)?t\.me/(?:(c)/)?([A-Za-z0-9_]+)/([0-9]+)(?:[/?#]|$)", message.text.strip())
        if match:
            private, identifier, mid = match.groups()
            ref = int("-100" + identifier) if private and identifier.isdigit() else identifier
            mid = int(mid)
    if ref is None:
        return (None, "Invalid post link or forwarded message.") if diagnose else None
    chat_id = ref
    try:
        chat = await client.get_chat(ref)
        chat_id = chat.id
        post = await client.get_messages(chat.id, mid)
        if post and not getattr(post, "empty", False):
            result = (chat.id, int(mid))
            return (result, None) if diagnose else result
    except Exception:
        pass
    # A user account's access is different from a bot's delivery access.
    from plugins.user_sessions import session_read_status
    status = await session_read_status(
        message.from_user.id if message.from_user else 0, chat_id, int(mid)
    )
    if status == "available" and diagnose:
        # The caller must stage this source through the user's own session
        # into the bot's DB channel before generating any public /start link.
        return (chat_id, int(mid)), "session_only"
    if status == "not_connected":
        reason = ("The bot cannot access this post. Your user session is not connected. "
                  "Sessions are kept only in RAM, so after a bot restart use "
                  "/connect telethon or /connect pyrogram again.")
    elif status == "available":
        reason = ("Your connected user account can read this post, but the bot cannot. "
                  "This version sends files as the bot, so no working link can be made "
                  "until you add the bot to the source chat, or move an authorized copy "
                  "to the database channel.")
    elif status == "chat_not_found":
        reason = ("This private channel/group was not found in your connected account's "
                  "dialogs. Confirm that account is a member. A t.me/c link by itself "
                  "does not grant access.")
    elif status == "post_unavailable":
        reason = ("Your connected account can resolve the chat but this message is "
                  "not available to it. Check the post number and permissions.")
    else:
        reason = ("Telegram could not verify access with the connected account. "
                  "Check membership/session validity and retry. The bot still needs "
                  "access to send files using the current delivery flow.")
    return (None, reason) if diagnose else None



async def get_message_id(client, message):
    """Compatibility wrapper for the original DB-only interface."""
    source = await get_message_source(client, message)
    return source[1] if source and source[0] == client.db_channel.id else 0

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
            await asyncio.sleep(getattr(e, "value", getattr(e, "x", 1)))
            print(f"The attempt to delete the media {msg.id} was unsuccessful: {e}")

    await process.edit_text(AUTO_DEL_SUCCESS_MSG)


subscribed = filters.create(is_subscribed)
