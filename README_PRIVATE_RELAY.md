# Authorized user-session relay for private `t.me/c` links

Original `/start` file delivery stays bot-based. If the source is readable by the connected account but **not** the bot, `/genlink` or `/batch` can forward the posts into the existing DB channel using the connected account, then create a link to those DB messages. This is **not** DRM/forward-protection bypassing. Content that Telegram restricts from forwarding is rejected.

Requirements:
1. Admin must `/connect telethon` or `/connect pyrogram` again after bot restart (sessions are RAM only).
2. Connected Telegram account must already have permission to read and **forward** the source message(s).
3. The same connected account must have **Post Messages** permission in the bot's DB channel. The bot must be an admin of that DB channel.
4. For a freshly imported Telethon StringSession, numeric private `t.me/c/` links need the access hash: code scans the connected account's dialogs; if chat isn't found, the account is not currently able to resolve it. Joining/appearing in the account's chats is required.
5. Set `DB_CHANNEL_USERNAME` in `.env` if the DB channel is public; no changes to `.env` are made by the patch.
6. Batch forwarding requires a complete post range (1–200) and contiguous new DB message IDs. Telegram permissions, deleted posts, rate limits or concurrent DB posts may prevent link creation.

Only `helper_func.py`, `plugins/link_generator.py`, and `plugins/user_sessions.py` are changed. Other code, bot delivery flow, and `.env` remain untouched. No TechVJ modules. Syntax and mocked session tests are performed; real Telegram operations need VPS validation.
