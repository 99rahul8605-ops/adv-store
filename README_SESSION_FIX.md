# Session/private channel handling

- `/batch` and `/genlink` use an exclusive prompt state to avoid single-post handler collisions.
- A connected user session is used to check read access when the bot cannot access a private post.
- Links are generated **only** for bot-accessible messages, because existing `/start` delivery runs as the bot. A user-only private channel cannot be served by that delivery pipeline. Add the bot to the source, or copy an authorized file to the DB channel.
- No TechVJ code. `.env` unchanged. No user session credentials persisted.
- A Telethon user account may have permission but lack a cached private peer; reconnect or open the chat with the account in a Telegram client.
