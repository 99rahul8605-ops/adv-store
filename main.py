import asyncio
# Needed by Pyrogram 2.x on Python 3.14 before importing bot.
asyncio.set_event_loop(asyncio.new_event_loop())
from bot import Bot

Bot().run()
