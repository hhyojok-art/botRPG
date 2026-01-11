import os
from PIL import ImageFont

FONT_PATH = os.path.join('Assets', 'fonts', 'undertale.ttf')


def load_font(size: int):
    """Return a PIL ImageFont instance preferring the Undertale font if available."""
    try:
        if os.path.exists(FONT_PATH):
            return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        pass
    # try common fallbacks
    for name in ('arial.ttf', 'DejaVuSans.ttf', 'FreeSans.ttf'):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()
