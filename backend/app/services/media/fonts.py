from __future__ import annotations

import glob
import platform
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont


def find_japanese_font(*, bold: bool = False) -> str:
    names = ["Noto Sans CJK JP", "Noto Sans JP", "Hiragino Sans", "Yu Gothic", "Meiryo"]
    if shutil.which("fc-match"):
        for name in names:
            query = f"{name}:style={'Bold' if bold else 'Regular'}"
            try:
                result = subprocess.check_output(["fc-match", "-f", "%{file}", query], text=True).strip()
                if result and Path(result).exists():
                    return result
            except Exception:
                pass
    patterns = []
    if platform.system() == "Darwin":
        # macOS stores Japanese filenames in a decomposed Unicode form, so use
        # the stable weight suffix instead of a literal Japanese filename.
        patterns = (["/System/Library/Fonts/*W6.ttc", "/System/Library/Fonts/*W7.ttc"] if bold else ["/System/Library/Fonts/*W3.ttc", "/System/Library/Fonts/*W4.ttc"])
        patterns += ["/Library/Fonts/NotoSansJP*.ttf", "/System/Library/Fonts/Hiragino Sans GB.ttc"]
    elif platform.system() == "Windows":
        patterns = ["C:/Windows/Fonts/YuGoth*.ttc", "C:/Windows/Fonts/meiry*.ttc"]
    patterns += ["/usr/share/fonts/**/*NotoSansCJK*.ttc", "/usr/share/fonts/**/*NotoSansJP*.ttf"]
    for pattern in patterns:
        hits = glob.glob(pattern, recursive=True)
        if hits:
            return hits[0]
    raise RuntimeError("日本語フォントが見つかりません。Noto Sans JPをインストールしてください。")


@lru_cache(maxsize=8)
def font(size: int, bold: bool = False):
    return ImageFont.truetype(find_japanese_font(bold=bold), size)
