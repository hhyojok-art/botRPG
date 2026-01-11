import json
from pathlib import Path

P = Path(__file__).resolve().parents[1] / 'data' / 'monsters.json'
B = P.with_suffix('.json.bak')
text = P.read_text(encoding='utf-8')

# First try: simple non-greedy regex to find candidate object blocks that include a "name" key
import re
candidates = re.findall(r"\{.*?\}", text, flags=re.S)

valid_objs = []
for s in candidates:
    if '"name"' not in s:
        continue
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            valid_objs.append(obj)
    except Exception as e:
        # skip invalid candidate
        continue

if not valid_objs:
    print('No valid objects found; aborting')
else:
    # backup original (timestamped if backup exists)
    import time
    if not B.exists():
        P.replace(B)
        print(f'Original backed up to {B}')
    else:
        ts = int(time.time())
        B2 = P.with_name(P.stem + f'.bak.{ts}.json')
        P.replace(B2)
        print(f'Original backed up to {B2}')

    # write cleaned array
    out = json.dumps(valid_objs, ensure_ascii=False, indent=2)
    P.write_text(out, encoding='utf-8')
    print(f'Wrote cleaned {len(valid_objs)} objects to {P}')
