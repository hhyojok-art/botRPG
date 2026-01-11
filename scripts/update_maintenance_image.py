from PIL import Image, ImageDraw, ImageFont, ImageFilter
from utils.fonts import load_font
from pathlib import Path
import textwrap
import os
import math

BASE = Path(__file__).resolve().parents[1]
IMG_PATH = BASE / 'Assets' / 'background' / 'maintenance.png'
FONT_PATH = BASE / 'Assets' / 'fonts' / 'undertale.ttf'


def _parse_color(s, default):
    if not s:
        return default
    s = s.strip()
    try:
        if s.startswith('#'):
            s = s[1:]
        if ',' in s:
            parts = [int(x) for x in s.split(',')]
            return tuple(parts)
        if len(s) in (6, 3):
            if len(s) == 3:
                s = ''.join([c*2 for c in s])
            r = int(s[0:2], 16)
            g = int(s[2:4], 16)
            b = int(s[4:6], 16)
            return (r, g, b)
    except Exception:
        pass
    return default


def main():
    if not IMG_PATH.exists():
        print('Maintenance image not found at', IMG_PATH)
        return

    # theme selection via env
    theme = os.getenv('MAINT_THEME', '').lower()

    # default values
    title_color = (255, 215, 64)
    subtitle_color = (235, 235, 235)
    title_scale = 0.12
    subtitle_scale = 0.06

    if theme == 'mario':
        # Mario theme: red title with white stroke, blue subtitle
        title_color = (223, 15, 20)  # Mario red
        subtitle_color = (66, 133, 244)  # Mario blue
        title_scale = 0.16
        subtitle_scale = 0.06

    img = Image.open(IMG_PATH).convert('RGBA')
    w, h = img.size

    # Create overlay for text
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Load fonts
    try:
        font_large = load_font(int(h * title_scale))
        font_small = load_font(int(h * subtitle_scale))
    except Exception:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Text lines
    lines = [
        "BOT SEDANG MAINTENANCE",
        "",
        "TERIMA KASIH TELAH MENGGUNAKAN BOT KAMI",
        "SILAKAN TUNGGU SEBENTAR"
    ]

    # Prepare wrapped text
    wrapped = []
    for line in lines:
        if line.strip() == '':
            wrapped.append('')
            continue
        wrapped.extend(textwrap.wrap(line, 36))

    # Calculate sizes
    spacing = int(h * 0.02)
    total_h = 0
    sizes = []
    for i, line in enumerate(wrapped):
        font = font_large if i == 0 else font_small
        try:
            bbox = draw.textbbox((0, 0), line, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
        except Exception:
            try:
                tw, th = font.getsize(line)
            except Exception:
                tw, th = (0, 0)
        sizes.append((tw, th, font))
        total_h += th + spacing

    y = (h - total_h) // 2

    # Draw cheerful background behind text (rounded rectangle)
    try:
        def _parse_color(s, default):
            if not s:
                return default
            s = s.strip()
            try:
                if s.startswith('#'):
                    s = s[1:]
                if ',' in s:
                    parts = [int(x) for x in s.split(',')]
                    return tuple(parts)
                if len(s) in (6, 3):
                    if len(s) == 3:
                        s = ''.join([c*2 for c in s])
                    r = int(s[0:2], 16)
                    g = int(s[2:4], 16)
                    b = int(s[4:6], 16)
                    return (r, g, b)
            except Exception:
                pass
            return default

        bg_default = (255, 238, 173) if theme == 'mario' else (255, 245, 238)
        bg_color = _parse_color(os.getenv('MAINT_BG_COLOR'), bg_default)
        rect_w = int(w * 0.88)
        rect_h = int(total_h + spacing * 2)
        rect_x = (w - rect_w) // 2
        rect_y = (h - rect_h) // 2 - 10
        radius = max(8, int(h * 0.03))
        # draw rounded rectangle on overlay
        rect_fill = tuple(list(bg_color) + [220])
        try:
            draw.rounded_rectangle([rect_x, rect_y, rect_x + rect_w, rect_y + rect_h], radius=radius, fill=rect_fill)
        except Exception:
            # fallback: draw normal rectangle
            draw.rectangle([rect_x, rect_y, rect_x + rect_w, rect_y + rect_h], fill=rect_fill)
    except Exception:
        pass

    # If mario theme, draw a cheery red stripe and some pixel blocks to mimic Mario aesthetic
    if theme == 'mario':
        stripe_h = int(h * 0.22)
        stripe = Image.new('RGBA', (w, stripe_h), (240, 64, 64, 220))
        img.paste(stripe, (0, 0), stripe)
        # small bricks on bottom of stripe
        block_w = 24
        block_h = 12
        bw = block_w
        bh = block_h
        bcol = (180, 40, 40, 255)
        bimg = Image.new('RGBA', (bw, bh), bcol)
        for bx in range(0, w, bw + 6):
            img.paste(bimg, (bx, stripe_h - bh - 4), bimg)

        # Try to find an icon file to overlay; look in Assets/icons or background
        icon_paths = [
            BASE / 'Assets' / 'icons' / 'mario.png',
            BASE / 'Assets' / 'background' / 'mario_icon.png',
            BASE / 'Assets' / 'background' / 'mushroom.png',
        ]
        icon_img = None
        for p in icon_paths:
            try:
                if p.exists():
                    icon_img = Image.open(p).convert('RGBA')
                    break
            except Exception:
                icon_img = None

        # If no icon file, generate a simple Mario cap icon (red circle with white M)
        if icon_img is None:
            icw = int(h * 0.18)
            icon_img = Image.new('RGBA', (icw, icw), (0, 0, 0, 0))
            idraw = ImageDraw.Draw(icon_img)
            # cap circle
            idraw.ellipse((0, 0, icw - 1, icw - 1), fill=(220, 20, 20, 255))
            # white circle inner
            idraw.ellipse((icw * 0.15, icw * 0.25, icw * 0.85, icw * 0.75), fill=(255, 255, 255, 255))
            # draw M using available font
            try:
                mfont = load_font(int(icw * 0.5))
            except Exception:
                mfont = ImageFont.load_default()
            mtext = 'M'
            try:
                mbbox = idraw.textbbox((0, 0), mtext, font=mfont)
                mw = mbbox[2] - mbbox[0]
                mh = mbbox[3] - mbbox[1]
            except Exception:
                mw, mh = mfont.getsize(mtext)
            mx = (icw - mw) // 2
            my = int(icw * 0.25 - mh // 2)
            idraw.text((mx, my), mtext, font=mfont, fill=(200, 30, 30, 255))

        # Paste icon onto img at top-left inside stripe with margin
        try:
            icon_size = int(h * 0.18)
            icon_resized = icon_img.resize((icon_size, icon_size), resample=Image.LANCZOS)
            margin = int(h * 0.03)
            img.paste(icon_resized, (margin, margin), icon_resized)
        except Exception:
            pass

    # Draw text with stroke and shadow; title uses title_color, others use subtitle_color
    for (tw, th, font), line in zip(sizes, wrapped):
        x = (w - tw) // 2
        line_y = y
        # shadow
        draw.text((x + 4, line_y + 4), line, font=font, fill=(0, 0, 0, 180))
        # stroke
        stroke = (255, 255, 255) if theme == 'mario' else (30, 30, 30)
        for ox, oy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
            draw.text((x + ox, line_y + oy), line, font=font, fill=stroke + (255,) if isinstance(stroke, tuple) and len(stroke) == 3 else (255, 255, 255, 255))
        # main color
        main_col = title_color if font == font_large else subtitle_color
        draw.text((x, line_y), line, font=font, fill=tuple(list(main_col) + [255]))
        y += th + spacing

    result = Image.alpha_composite(img, overlay)

    if theme == 'mario':
        # Mario bright gradient (left: red -> orange -> yellow : right)
        grad = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(grad)
        for x in range(w):
            t = x / max(1, w - 1)
            if t < 0.5:
                # red -> orange
                tt = t / 0.5
                r = int((1 - tt) * 223 + tt * 255)
                g = int((1 - tt) * 15 + tt * 140)
                b = int((1 - tt) * 20 + tt * 0)
            else:
                # orange -> yellow
                tt = (t - 0.5) / 0.5
                r = int((1 - tt) * 255 + tt * 255)
                g = int((1 - tt) * 140 + tt * 215)
                b = int((1 - tt) * 0 + tt * 64)
            a = 160
            gdraw.line([(x, 0), (x, h)], fill=(r, g, b, a))
        # light blur to blend
        grad = grad.filter(ImageFilter.GaussianBlur(radius=6))
        result = Image.alpha_composite(grad, result)
    else:
        # subtle vignette for non-mario themes
        vignette = Image.new('L', (w, h), 0)
        vp = vignette.load()
        cx, cy = w / 2.0, h / 2.0
        maxd = math.hypot(cx, cy)
        for yy in range(h):
            for xx in range(w):
                d = math.hypot(xx - cx, yy - cy)
                a = int(180 * ((d / maxd) ** 1.6))
                if a > 255:
                    a = 255
                vp[xx, yy] = a
        vignette = vignette.filter(ImageFilter.GaussianBlur(radius=18))
        black = Image.new('RGBA', (w, h), (0, 0, 0, 120))
        result = Image.alpha_composite(result, black)
        result.paste(black, (0, 0), mask=vignette)

    # Save (backup original if not already backed up)
    backup = IMG_PATH.with_suffix('.bak.png')
    try:
        if not backup.exists():
            IMG_PATH.rename(backup)
    except Exception:
        pass

    result.convert('RGB').save(IMG_PATH, format='PNG')
    print('Updated maintenance image at', IMG_PATH)


if __name__ == '__main__':
    main()
