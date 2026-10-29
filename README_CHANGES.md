# Clean original File-Sharing-Bot changes

- `/genlink` accepts forwarded posts or `t.me/name/id` and `t.me/c/id/id` links from channels/groups the **bot can read**. No `SOURCE_CHANNELS` needed.
- `/batch` supports one channel/group per batch, max 200 posts.
- Original DB-channel auto-copy / auto-button flow retained, as are old `get-*` start links.
- Admin-only `/connect pyrogram`, `/connect telethon`, `/sessionstatus`, `/logout`, `/cancel` manage in-memory user accounts. Logout only disconnects, does not revoke the Telegram session. Restart loses the connection.
- User sessions do not authorize arbitrary file distribution. The delivery bot must have access to the source.
- `CHANNEL_ID` is still needed for the original DB copy workflow and old links; it is NOT a source allowlist. `DB_CHANNEL_USERNAME` optional for bot peer cache.
- `.env` is never included in ZIP.
