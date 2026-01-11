import asyncio
import time
import sys
from pathlib import Path

# Ensure repo root is on sys.path so imports like `redis_client` resolve
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from redis_client import set_bot_enabled, is_bot_enabled, get_is_bot_enabled_cached

async def test():
    print("Starting redis_client latency test")

    # measure set to False
    t0 = time.perf_counter()
    await set_bot_enabled(False)
    t1 = time.perf_counter()
    print(f"set_bot_enabled(False) took {(t1-t0)*1000:.2f} ms")

    # measure get
    t0 = time.perf_counter()
    val = await is_bot_enabled()
    t1 = time.perf_counter()
    print(f"is_bot_enabled() -> {val} took {(t1-t0)*1000:.2f} ms")

    # measure set to True
    t0 = time.perf_counter()
    await set_bot_enabled(True)
    t1 = time.perf_counter()
    print(f"set_bot_enabled(True) took {(t1-t0)*1000:.2f} ms")

    # repeated reads to exercise cache
    for i in range(5):
        t0 = time.perf_counter()
        v = await is_bot_enabled()
        t1 = time.perf_counter()
        print(f"is_bot_enabled()#{i} -> {v} {(t1-t0)*1000:.2f} ms")
        await asyncio.sleep(0.2)

    cached_val, cached_ts = get_is_bot_enabled_cached()
    print("Cached value:", cached_val, "ts:", cached_ts)

if __name__ == '__main__':
    asyncio.run(test())
