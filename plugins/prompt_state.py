from contextlib import asynccontextmanager

@asynccontextmanager
async def track_dialog(client, user_id):
    active = getattr(client, "_active_link_prompts", None)
    if active is None:
        active = set()
        client._active_link_prompts = active
    active.add(user_id)
    try:
        yield
    finally:
        active.discard(user_id)
