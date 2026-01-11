import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / 'data' / 'monsters.json'

def normalize(threshold=120, target_hp=100):
    p = DATA
    if not p.exists():
        print('monsters.json not found at', p)
        return
    bak = p.with_suffix('.json.bak')
    p.rename(bak)
    with bak.open('r', encoding='utf-8') as f:
        mobs = json.load(f)

    changed = 0
    for m in mobs:
        hp = m.get('hp', 0)
        if hp > threshold:
            factor = target_hp / hp
            m['hp'] = int(target_hp)
            # scale other numeric stats
            for key in ('atk', 'def', 'xp', 'gold'):
                if key in m:
                    newv = max(1, round(m[key] * factor))
                    m[key] = newv
            changed += 1

    with p.open('w', encoding='utf-8') as f:
        json.dump(mobs, f, ensure_ascii=False, indent=2)

    print(f'Normalized {changed} mobs. Backup saved to {bak.name}')

if __name__ == '__main__':
    normalize()
