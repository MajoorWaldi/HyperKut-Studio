"""The colors of the pictures of a job, for the planner: an accent, a light and a dark color, and the colors most present. Pillow only.

Texts, shapes and effects in colors taken from the pictures belong to the film; a fixed default color looks pasted on."""
import colorsys
from collections import Counter

from PIL import Image

SIZE = 96


def _hex(rgb) -> str:
    return '#' + ''.join(f'{max(0, min(255, int(round(v)))):02x}' for v in rgb)


def picture_palette(paths) -> dict | None:
    """{"accent", "light", "dark", "colors"} of the pictures, or None without a readable picture. The accent is the most present hue family
    among the vivid pixels only (a red jacket, a neon sign), even when they cover little of the frame."""
    pixels = []
    for path in paths:
        try:
            with Image.open(path) as image:
                pixels += list(image.convert('RGB').resize((SIZE, SIZE)).getdata())
        except OSError:
            continue
    if not pixels:
        return None
    mixed = Image.new('RGB', (len(pixels), 1))
    mixed.putdata(pixels)
    quantized = mixed.quantize(colors=6, method=Image.Quantize.MEDIANCUT)
    table = quantized.getpalette()[:18]
    counts = Counter(quantized.getdata())
    colors = [tuple(table[3 * i:3 * i + 3]) for i, _ in counts.most_common() if 3 * i + 2 < len(table)]
    vivid = [(rgb, colorsys.rgb_to_hsv(*(v / 255 for v in rgb))) for rgb in pixels]
    vivid = [(rgb, hsv) for rgb, hsv in vivid if hsv[1] >= .3 and hsv[2] >= .35]
    accent = None
    if len(vivid) >= max(30, .005 * len(pixels)):
        family = Counter(int(hsv[0] * 12) % 12 for _, hsv in vivid).most_common(1)[0][0]
        members = sorted((hsv for _, hsv in vivid if int(hsv[0] * 12) % 12 == family), key=lambda hsv: hsv[2])
        h, s, v = members[len(members) // 2]
        accent = _hex(v * 255 for v in colorsys.hsv_to_rgb(h, max(s, .55), max(v, .8)))  # lifted a little, so it reads over the picture
    luma = lambda rgb: .299 * rgb[0] + .587 * rgb[1] + .114 * rgb[2]
    light, dark = max(colors, key=luma), min(colors, key=luma)
    return {'accent': accent, 'light': _hex(light) if luma(light) >= 200 else '#ffffff', 'dark': _hex(dark) if luma(dark) <= 50 else '#000000',
            'colors': [_hex(rgb) for rgb in colors]}


def palette_direction(found: dict | None) -> str:
    """The palette as a line of the planning instructions; empty without one."""
    if not found:
        return ''
    accent = f"accent {found['accent']}, " if found['accent'] else ''
    return (f"Palette of the supplied pictures: {accent}light {found['light']}, dark {found['dark']}, present colors {', '.join(found['colors'][:5])}. "
            'Unless the brief names colors, take the colors of texts, shapes and effects from it: the accent for what must be seen, light or dark text on top of it.')
