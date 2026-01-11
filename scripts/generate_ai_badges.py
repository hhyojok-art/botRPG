import json
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from utils.fonts import load_font

OUT_JSON = Path(__file__).resolve().parents[1] / 'data' / 'badges.json'
ASSETS_DIR = Path(__file__).resolve().parents[1] / 'Assets' / 'badges'
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

NAMES = [
    'Pemula', 'Penakluk', 'Pengumpul', 'Pahlawan', 'Penjelajah', 'Ahli', 'Veteran', 'Pemburu', 'Collector', 'Legend'
]
ADJS = ['Berani', 'Cerdik', 'Rajin', 'Tangguh', 'Lincah', 'Kuat', 'Cepat', 'Bijak']


def make_key(name: str, idx: int) -> str:
    s = name.lower()
    s = ''.join(c if c.isalnum() else '_' for c in s).strip('_')
    return f"ai_{s}_{idx}"


def generate_icon(path: Path, label: str, color=None):
    W = 256
    img = Image.new('RGBA', (W, W), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    if color is None:
        color = tuple(random.randint(60, 220) for _ in range(3))
    # circle
    draw.ellipse((16, 16, W-16, W-16), fill=color + (255,), outline=(0,0,0,120))
    # label initials
    initials = ''.join([p[0] for p in label.split()][:2]).upper()
    try:
        font = load_font(96)
    except Exception:
        font = ImageFont.load_default()
    try:
        bbox = draw.textbbox((0, 0), initials, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
    except Exception:
        try:
            w, h = font.getsize(initials)
        except Exception:
            w, h = (len(initials) * 24, 40)
    draw.text(((W-w)/2, (W-h)/2), initials, font=font, fill=(255,255,255,255))
    img.save(path, 'PNG')


def generate_badges(count=6):
    badges = {}
    for i in range(count):
        name = random.choice(ADJS) + ' ' + random.choice(NAMES)
        key = make_key(name, i)
        desc = f"Mendapatkan badge {name} untuk prestasi tertentu dalam permainan."
        badges[key] = [name, desc]
        img_path = ASSETS_DIR / f"{key}.png"
        generate_icon(img_path, name)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUT_JSON.open('w', encoding='utf-8') as f:
        json.dump(badges, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(badges)} badges to {OUT_JSON}")


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--count', type=int, default=6)
    args = p.parse_args()
    generate_badges(args.count)
