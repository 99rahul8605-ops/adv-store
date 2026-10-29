# Clean original File-Sharing-Bot changes

- `/genlink` accepts forwarded posts or `t.me/name/id` and `t.me/c/id/id` links from channels/groups the **bot can read**. No `SOURCE_CHANNELS` needed.
- `/batch` supports one channel/group per batch, max 200 posts.
- Original DB-channel auto-copy / auto-button flow retained, as are old `get-*` start links.
- Admin-only `/connect pyrogram`, `/connect telethon`, `/sessionstatus`, `/logout`, `/cancel` manage in-memory user accounts. Logout only disconnects, does not revoke the Telegram session. Restart loses the connection.
- User sessions do not authorize arbitrary file distribution. The delivery bot must have access to the source.
- `CHANNEL_ID` is still needed for the original DB copy workflow and old links; it is NOT a source allowlist. `DB_CHANNEL_USERNAME` optional for bot peer cache.
- `.env` is never included in ZIP.

## Deployment and testing

Run `bash start.sh` from the project directory. It creates a local `venv`, installs requirements and starts `main.py`; no system-wide pip or Git operations are performed. Existing `.env` is never modified.

The Telegram bot must be able to read each source message when generating and delivering a link. Public posts may still require source access, and private `t.me/c` links require channel membership plus resolvable peer cache. User session login only manages user authorization, not file access or public file delivery.

Testing performed in the packaging environment: compile all Python modules, static config/import audits, link parser smoke tests with stub client, URL-safe payload compatibility, ZIP integrity. Real Telegram and MongoDB connections must be tested on the deployment VPS.
