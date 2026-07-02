"""Logo loading / encoding helpers used by the page header and by agents that embed
the Aranca logo into generated reports."""

import base64
import os

from PIL import Image, ImageDraw, ImageFont


def get_base64_logo_image(path="logo.png"):
    """Return the given image file base64-encoded (for inline ``data:`` URIs)."""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def load_logo():
    """Load logo.png sitting next to the project root, or synthesize a placeholder."""
    # 1) Find the folder where the project root lives (parent of this utils package)
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # 2) Build the full path to logo.png next to it
    logo_path = os.path.join(script_dir, "logo.png")

    if os.path.isfile(logo_path):
        return Image.open(logo_path)

    # fallback dummy if not found
    img = Image.new('RGB', (200, 50), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except Exception:
        font = ImageFont.load_default()
    d.text((10, 10), "Aranca", fill=(0, 65, 106), font=font)
    return img
