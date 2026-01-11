import redis
import asyncio
import time
import json
from pathlib import Path
import socket

# Redis client with short network timeouts to avoid long blocking
# If you use a remote Redis, consider setting host/port from env.
# Use decode_responses so Redis returns str instead of bytes when available.
# Keep short timeouts to avoid blocking on network ops.
r = redis.Redis(host='localhost', port=6379, db=0, socket_connect_timeout=0.5, socket_timeout=0.5, decode_responses=True)

# Simple in-memory cache to avoid hitting Redis on every command check.
# Cached value expires after `CACHE_TTL` seconds.
_CACHE = {
    'value': True,
    'ts': 0.0
}
# Increase cache TTL to reduce fallback disk reads when Redis is down.
# This keeps the in-memory flag stable for a short period.
CACHE_TTL = 5.0  # seconds

# Local fallback file when Redis is unavailable
_LOCAL_STATE_FILE = Path(__file__).resolve().parents[0] / 'bot_state.json'


def _read_local_flag():
    try:
        if _LOCAL_STATE_FILE.exists():
            with _LOCAL_STATE_FILE.open('r', encoding='utf-8') as f:
                data = json.load(f)
            return bool(data.get('bot_enabled', True))
    except Exception:
        pass
    return True


def _write_local_flag(value: bool):
    try:
        with _LOCAL_STATE_FILE.open('w', encoding='utf-8') as f:
            json.dump({'bot_enabled': bool(value)}, f)
        return True
    except Exception:
        return False


def _ensure_parent_dir():
    try:
        _LOCAL_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


_pending_write = None

def _schedule_local_write(value: bool):
    """Schedule a background write to disk (non-blocking). Coalesce multiple writes."""
    global _pending_write
    loop = None
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    def _write():
        try:
            _ensure_parent_dir()
            with _LOCAL_STATE_FILE.open('w', encoding='utf-8') as f:
                json.dump({'bot_enabled': bool(value)}, f)
            return True
        except Exception:
            return False

    if loop:
        # cancel previous pending write to coalesce rapid updates
        try:
            if _pending_write and not _pending_write.done():
                _pending_write.cancel()
        except Exception:
            pass
        _pending_write = loop.run_in_executor(None, _write)
    else:
        # fallback synchronous write
        _write()


def _debug_print(msg: str):
    try:
        print(f"[redis_client DEBUG] {msg}")
    except Exception:
        pass


def get_is_bot_enabled_cached():
    return _CACHE['value'], _CACHE['ts']


async def is_bot_enabled():
    """Async wrapper that checks whether the bot is enabled from Redis.
    Uses a short in-memory cache to avoid calling Redis on every command.
    Returns True if enabled, False otherwise. Falls back to local file when Redis unavailable.
    """
    now = time.time()
    if now - _CACHE['ts'] < CACHE_TTL:
        return _CACHE['value']

    loop = asyncio.get_running_loop()
    try:
        enabled = await loop.run_in_executor(None, r.get, 'bot_enabled')
    except Exception:
        # If Redis is unavailable or slow, fallback to local file flag (if present)
        # read local flag in executor to avoid blocking event loop
        try:
            val = await loop.run_in_executor(None, _read_local_flag)
        except Exception:
            val = _read_local_flag()
        _CACHE['value'] = val
        _CACHE['ts'] = now
        return val

    if enabled is None:
        val = True
    else:
        # redis-py may return bytes or str depending on decode_responses
        if isinstance(enabled, bytes):
            val = (enabled.lower() == b'true')
        else:
            val = (str(enabled).lower() == 'true')

    _CACHE['value'] = val
    _CACHE['ts'] = now
    return val


async def set_bot_enabled(value: bool):
    """Set bot enabled flag in Redis and update local cache. Best-effort.
    Accepts True/False.
    """
    loop = asyncio.get_running_loop()
    val = 'true' if value else 'false'
    # Quick TCP probe to avoid blocking a threadpool task for long if Redis is down
    host = r.connection_pool.connection_kwargs.get('host', 'localhost')
    port = r.connection_pool.connection_kwargs.get('port', 6379)
    can_connect = False
    try:
        sock = socket.create_connection((host, port), timeout=0.2)
        sock.close()
        can_connect = True
    except Exception:
        can_connect = False

    if can_connect:
        try:
            await loop.run_in_executor(None, r.set, 'bot_enabled', val)
        except Exception:
            try:
                _schedule_local_write(value)
            except Exception:
                _write_local_flag(value)
    else:
        # Redis not reachable quickly — schedule local write immediately
        try:
            _schedule_local_write(value)
        except Exception:
            _write_local_flag(value)

    # update local cache immediately
    _CACHE['value'] = value
    _CACHE['ts'] = time.time()
    return True
