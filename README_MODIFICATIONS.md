# Modified File Sharing Bot

## Changes
- Python 3.14 Pyrogram import event-loop compatibility workaround in `bot.py` and `main.py`.
- `.env` configuration: `APP_ID` or `API_ID`, `TG_BOT_TOKEN` or `BOT_TOKEN`, `DB_URI` or `DATABASE_URL`, `DB_NAME` or `DATABASE_NAME`.
- Optional `DB_CHANNEL_USERNAME=public_db_username` primes Pyrogram peer cache before accessing `CHANNEL_ID` by numeric ID.
- `PORT=8081` can avoid conflicts with a service using 8080.
- No `SOURCE_CHANNELS` allowlist. `/genlink` and `/batch` accept forwarded channel/group messages and Telegram post URLs from **any source the bot is authorized to read**. `/start` resolves versioned links against the correct channel, while preserving legacy DB links.
- `/connect pyrogram`, `/connect telethon`, `/sessionstatus`, `/logout`, `/cancel` in private chat, only for `OWNER_ID` and `ADMINS`. Session strings are deleted on receipt where possible, held only in memory, and disconnected locally on `/logout`; no Telegram session revocation is performed.

## Important limits and privacy
- Connected user sessions can verify links to their own accessible channels **but do not grant the bot access to those channels**. File delivery to arbitrary bot users requires that the bot itself have access to the source channel. This intentionally avoids redistributing private user-session content to people who might not be authorized.
- The connected user session is **not saved**. After bot restart, connect it again with the original string; never share a session with an untrusted operator.
- Add the bot as channel admin with appropriate permissions where it must read/post files or edit channel message buttons. The bot may not need admin status for reading every source, but must be able to access the channel.
- Do not paste credentials into issue reports or logs.

## Install (Ubuntu)
```
cd ~/File-Sharing-Bot
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python -u main.py
```

## Example .env
```
APP_ID=YOUR_NUMERIC_API_ID
API_HASH=YOUR_API_HASH
TG_BOT_TOKEN=YOUR_BOT_TOKEN
OWNER_ID=YOUR_NUMERIC_TELEGRAM_ID
ADMINS=123456789
DATABASE_URL=mongodb+srv://USER:PASS@HOST/DATABASE
DATABASE_NAME=filesharexbot
CHANNEL_ID=-1001234567890
DB_CHANNEL_USERNAME=your_public_db_username
PORT=8081
```

## Flow
1. Admin sends `/genlink` or `/batch` and then a post link / forwarded message from an accessible group or channel. No source-channel preconfiguration is needed.
2. Bot verifies the post is readable before generating the link. The existing `/start` copy-to-recipient, caption, force-subscription and auto-delete flow remains unchanged.
3. Bot automatically adds share buttons to new channel posts if it has edit rights and `DISABLE_CHANNEL_BUTTON=False`.
4. A connected user session is managed separately; it does not automatically make private content publicly downloadable through the bot. For private sources, the bot itself must be granted access.
