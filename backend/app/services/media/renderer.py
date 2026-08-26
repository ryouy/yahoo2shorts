from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from ...storage.files import clean_text
from .fonts import font

TOP = (255, 92, 174)
BOTTOM = (81, 93, 244)
ACCENTS = [(255, 78, 148), (63, 195, 246), (255, 190, 47), (112, 210, 130), (166, 107, 255)]


def _background(width: int, height: int, variant: int = 0) -> Image.Image:
    top, bottom = np.array(TOP, dtype=float), np.array(BOTTOM, dtype=float)
    blend = np.linspace(0, 1, height)[:, None, None]
    pixels = np.repeat(top[None, None, :] * (1 - blend) + bottom[None, None, :] * blend, width, axis=1)
    image = Image.fromarray(pixels.astype(np.uint8), "RGB")
    draw = ImageDraw.Draw(image)
    blobs = [(-160, 250, 300, 710, (255, 255, 255)), (780, 100, 1240, 560, (255, 232, 90)), (760, 1490, 1270, 2000, (105, 237, 255))]
    shift = (variant % 3) * 230
    for x1, y1, x2, y2, color in blobs:
        yy1, yy2 = y1 + shift, y2 + shift
        if yy1 > height:
            yy1, yy2 = yy1 - height, yy2 - height
        draw.ellipse((x1, yy1 - 200, x2, yy2 + 200), fill=color)
    return image


def _wrap(draw: ImageDraw.ImageDraw, text: str, text_font, max_width: int) -> list[str]:
    lines, current = [], ""
    for char in clean_text(text).replace("\n", " "):
        candidate = current + char
        if current and draw.textbbox((0, 0), candidate, font=text_font)[2] > max_width:
            lines.append(current); current = char
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _article_header(draw, script: dict, width: int, *, intro: bool = False) -> None:
    if intro:
        box = (52, 250, width - 52, 1435)
        draw.rounded_rectangle((74, 278, width - 30, 1463), 52, fill=(69, 58, 128))
        draw.rounded_rectangle(box, 52, fill="white")
        draw.rounded_rectangle((110, 310, 222, 442), 22, fill=(255, 225, 72))
        draw.text((270, 333), clean_text(script.get("source") or "Yahoo!ニュース")[:25], font=font(28, True), fill=(100, 97, 112))
        y = 530
        for line in _wrap(draw, script["intro"]["headline"], font(70, True), width - 210)[:5]:
            draw.text((110, y), line, font=font(70, True), fill=(30, 28, 38)); y += 92
        draw.rounded_rectangle((110, y + 18, 310, y + 32), 7, fill=TOP); y += 68
        for line in _wrap(draw, script["intro"]["explainer"], font(43), width - 220)[:5]:
            draw.text((110, y), line, font=font(43), fill=(61, 58, 70)); y += 61
    else:
        draw.rounded_rectangle((45, 54, width - 35, 364), 42, fill=(62, 52, 117))
        draw.rounded_rectangle((35, 44, width - 45, 354), 42, fill="white")
        draw.rounded_rectangle((75, 80, 165, 190), 20, fill=(255, 225, 72))
        y = 72
        for line in _wrap(draw, script["intro"]["headline"], font(50, True), width - 240)[:2]:
            draw.text((200, y), line, font=font(50, True), fill=(30, 28, 38)); y += 66
        y = 220
        for line in _wrap(draw, script["intro"]["explainer"], font(34), width - 130)[:2]:
            draw.text((75, y), line, font=font(34), fill=(70, 67, 79)); y += 46


def render_frame(script: dict, output: Path, settings: dict, *, visible: int = 0, intro: bool = False, outro: bool = False) -> None:
    width, height = settings["width"], settings["height"]
    page_size = settings["comments_per_page"]
    page = max(0, (max(1, visible) - 1) // page_size)
    image = _background(width, height, page)
    draw = ImageDraw.Draw(image)
    if intro:
        _article_header(draw, script, width, intro=True)
    else:
        _article_header(draw, script, width)
        start = page * page_size
        posts = script.get("posts", [])[start:min(visible, start + page_size)]
        y = 430
        for offset, post in enumerate(posts):
            absolute = start + offset + 1
            reply = post.get("reply_to") is not None
            x = 105 if reply else 58
            card_width = width - x - 55
            text_font = font(44 if reply else (58 if len(clean_text(post["text"])) <= 15 else 47), True)
            lines = _wrap(draw, post["text"], text_font, card_width - 110)[:4]
            card_height = max(250, 135 + len(lines) * 63)
            draw.rounded_rectangle((x + 13, y + 16, width - 42, y + card_height + 16), 42, fill=(68, 56, 118))
            draw.rounded_rectangle((x, y, width - 55, y + card_height), 42, fill=(255, 255, 255))
            draw.rounded_rectangle((x, y, x + 24, y + card_height), 12, fill=ACCENTS[(absolute - 1) % len(ACCENTS)])
            name = "匿名さん" if absolute % 3 else "ネット民"
            label = f"返信 · レス{post.get('reply_to')}へ" if reply else name
            draw.text((x + 54, y + 28), label, font=font(27, True), fill=(110, 106, 124))
            ty = y + 88
            for line in lines:
                draw.text((x + 54, ty), line, font=text_font, fill=(29, 27, 36)); ty += 63
            y += card_height + 42
        total_pages = max(1, (len(script.get("posts", [])) + page_size - 1) // page_size)
        dot_y = height - 108
        for dot in range(total_pages):
            cx = width // 2 + (dot - (total_pages - 1) / 2) * 36
            draw.ellipse((cx - 8, dot_y - 8, cx + 8, dot_y + 8), fill="white" if dot == page else (190, 190, 220))
        if outro:
            draw.rounded_rectangle((90, 1480, width - 90, 1715), 48, fill="white")
            text = clean_text(script.get("outro", {}).get("text") or "あなたはどう思う？")
            lines = _wrap(draw, text, font(54, True), width - 250)[:2]
            for index, line in enumerate(lines):
                bbox = draw.textbbox((0, 0), line, font=font(54, True))
                draw.text(((width - (bbox[2] - bbox[0])) / 2, 1535 + index * 70), line, font=font(54, True), fill=(35, 31, 48))
    draw.text((45, height - 56), "Yahooニュース + YahooコメントをもとにAI再構成", font=font(22), fill="white")
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def render_thumbnail(script: dict, output: Path, settings: dict) -> None:
    width, height = settings["width"], settings["height"]
    image = _background(width, height, 1)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((55, 170, width - 55, 1335), 58, fill="white")
    draw.rounded_rectangle((95, 225, 235, 385), 26, fill=(255, 225, 72))
    draw.text((280, 260), clean_text(script.get("source") or "Yahoo!ニュース")[:24], font=font(28, True), fill=(95, 91, 106))
    y = 470
    for line in _wrap(draw, script["intro"]["headline"], font(76, True), width - 190)[:6]:
        draw.text((95, y), line, font=font(76, True), fill=(28, 26, 36)); y += 100
    short_posts = sorted(script.get("posts", []), key=lambda post: len(clean_text(post.get("text"))))[:2]
    y = 1420
    for index, post in enumerate(short_posts):
        draw.rounded_rectangle((70, y, width - 70, y + 170), 46, fill="white")
        draw.rounded_rectangle((70, y, 94, y + 170), 12, fill=ACCENTS[index + 1])
        for line_index, line in enumerate(_wrap(draw, post["text"], font(42, True), width - 230)[:2]):
            draw.text((125, y + 38 + line_index * 56), line, font=font(42, True), fill=(28, 26, 36))
        y += 200
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
