from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from ...storage.files import clean_text
from .fonts import font

ACCENTS = [(188, 255, 66), (255, 193, 63), (88, 210, 178), (178, 145, 255), (255, 121, 152)]
INK = (22, 25, 29)
LIME = (188, 255, 66)


def _background(width: int, height: int, background_path: Path | int | None = None) -> Image.Image:
    """Use the article's key visual while keeping foreground copy readable."""
    if isinstance(background_path, Path) and background_path.is_file():
        try:
            with Image.open(background_path) as source:
                image = ImageOps.fit(source.convert("RGB"), (width, height), method=Image.Resampling.LANCZOS, centering=(.5, .42))
            image = image.filter(ImageFilter.GaussianBlur(3))
            return Image.blend(image, Image.new("RGB", (width, height), (10, 14, 16)), .50)
        except OSError:
            pass
    image = Image.new("RGB", (width, height), (19, 24, 25))
    draw = ImageDraw.Draw(image)
    for y in range(0, height, 94):
        draw.rectangle((0, y, width, y + 1), fill=(35, 43, 42))
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
        # Clean source display without icon (hide if contains "yahoo")
        source_text = clean_text(script.get("source") or "")[:25]
        if source_text and "yahoo" not in source_text.lower():
            draw.text((110, 333), source_text, font=font(32, True), fill=(100, 97, 112))
        y = 530
        for line in _wrap(draw, script["intro"]["headline"], font(70, True), width - 210)[:5]:
            draw.text((110, y), line, font=font(70, True), fill=(30, 28, 38)); y += 92
        draw.rounded_rectangle((110, y + 18, 310, y + 32), 7, fill=LIME); y += 68
        for line in _wrap(draw, script["intro"]["explainer"], font(43), width - 220)[:5]:
            draw.text((110, y), line, font=font(43), fill=(61, 58, 70)); y += 61
    else:
        draw.rounded_rectangle((45, 54, width - 35, 364), 42, fill=(62, 52, 117))
        draw.rounded_rectangle((35, 44, width - 45, 354), 42, fill="white")
        y = 72
        for line in _wrap(draw, script["intro"]["headline"], font(50, True), width - 150)[:2]:
            draw.text((75, y), line, font=font(50, True), fill=(30, 28, 38)); y += 66
        y = 220
        for line in _wrap(draw, script["intro"]["explainer"], font(34), width - 130)[:2]:
            draw.text((75, y), line, font=font(34), fill=(70, 67, 79)); y += 46


def render_summary_frame(script: dict, page_text: str, page_index: int, total_pages: int, output: Path, settings: dict, *, background_path: Path | None = None) -> None:
    """One page of the multi-page body-explanation deck (see paginate_summary_text).
    The card is sized to the actual text so a short page doesn't leave a big empty card."""
    width, height = settings["width"], settings["height"]
    image = _background(width, height, background_path)
    draw = ImageDraw.Draw(image)
    text_width = width - 260
    line_height = 50
    headline_lines = _wrap(draw, script["intro"]["headline"], font(38, True), text_width)[:2]
    body_lines = _wrap(draw, page_text, font(36), text_width)[:12]
    dots_height = 76 if total_pages > 1 else 20
    content_height = 56 + len(headline_lines) * line_height + 22 + len(body_lines) * line_height + dots_height
    card_height = max(560, min(content_height, height - 300))
    card_top = (height - card_height) // 2
    card_bottom = card_top + card_height
    box = (75, card_top, width - 75, card_bottom)
    draw.rounded_rectangle((95, card_top + 24, width - 55, card_bottom + 20), 44, fill=(69, 58, 128))
    draw.rounded_rectangle(box, 44, fill="white")
    y = card_top + 56
    for line in headline_lines:
        draw.text((130, y), line, font=font(38, True), fill=(30, 28, 38)); y += line_height
    y += 22
    for line in body_lines:
        draw.text((130, y), line, font=font(36), fill=(61, 58, 70)); y += line_height
    if total_pages > 1:
        dot_y = card_bottom - 55
        for dot in range(total_pages):
            cx = width // 2 + (dot - (total_pages - 1) / 2) * 34
            draw.ellipse((cx - 7, dot_y - 7, cx + 7, dot_y + 7), fill=(69, 58, 128) if dot == page_index else (215, 213, 227))
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def paginate_summary_text(text: str, *, chars_per_page: int = 130) -> list[str]:
    """Split the body-explanation narration into card-sized pages at sentence
    boundaries so each page reads as a complete thought."""
    value = clean_text(text)
    if not value:
        return [""]
    sentences = re.split(r"(?<=[。！？])", value)
    sentences = [s for s in (part.strip() for part in sentences) if s]
    pages: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = current + sentence
        if current and len(candidate) > chars_per_page:
            pages.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        pages.append(current)
    return pages or [value]


def render_frame(script: dict, output: Path, settings: dict, *, visible: int = 0, intro: bool = False, outro: bool = False, background_path: Path | None = None) -> None:
    width, height = settings["width"], settings["height"]
    page_size = settings["comments_per_page"]
    page = max(0, (max(1, visible) - 1) // page_size)
    image = _background(width, height, background_path)
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
            if reply:
                draw.text((x + 54, y + 28), "返信", font=font(27, True), fill=(110, 106, 124))
            ty = y + (88 if reply else 42)
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
    # Credit text removed for cleaner design
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def render_thumbnail(script: dict, output: Path, settings: dict, *, background_path: Path | None = None) -> None:
    width, height = settings["width"], settings["height"]
    image = _background(width, height, background_path)
    draw = ImageDraw.Draw(image)
    # Premium header with gradient-like effect
    draw.rectangle((0, 0, width, 240), fill=(8, 12, 14))
    draw.rectangle((0, 0, width, 12), fill=(188, 255, 66))
    header_label = clean_text(settings.get("channel_name") or "")[:14] or "TOPIC"
    draw.text((58, 76), header_label, font=font(52, True), fill=(188, 255, 66))

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle((0, 560, width, height), fill=(0, 0, 0, 200))
    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(image)

    # Headline with better positioning
    y = 300
    headline_lines = _wrap(draw, script["intro"]["headline"], font(78, True), width - 110)[:3]
    for line in headline_lines:
        draw.text((55, y), line, font=font(78, True), fill="white", stroke_width=5, stroke_fill=(0, 0, 0))
        y += 98

    # Display multiple comments for eye-catching layout
    posts = script.get("posts", [])
    comment_count = min(3, len(posts))
    for idx in range(comment_count):
        post = posts[idx]
        comment_text = post.get("text", "")
        if comment_text:
            accent_color = ACCENTS[idx % len(ACCENTS)]
            text_length = len(clean_text(comment_text))

            # Adaptive sizing — kept large even for long comments
            if text_length > 35:
                font_size = 36
                max_lines = 3
                line_height = 50
                card_height = 170
            elif text_length > 20:
                font_size = 42
                max_lines = 2
                line_height = 58
                card_height = 150
            else:
                font_size = 50
                max_lines = 2
                line_height = 66
                card_height = 160

            comment_y = y + 30 + (idx * (card_height + 22))
            if comment_y + card_height > height - 110:
                break

            # Eye-catching card with shadow effect
            draw.rounded_rectangle((40, comment_y + 8, width - 40, comment_y + card_height + 8), 24, fill=(0, 0, 0))
            draw.rounded_rectangle((35, comment_y, width - 35, comment_y + card_height), 24, fill=accent_color)

            # Comment text with better spacing
            text_y = comment_y + (card_height - min(max_lines, len(_wrap(draw, comment_text, font(font_size, True), width - 140))) * line_height) // 2
            for line in _wrap(draw, comment_text, font(font_size, True), width - 140)[:max_lines]:
                draw.text((70, text_y), line, font=font(font_size, True), fill="white", stroke_width=4, stroke_fill=(0, 0, 0))
                text_y += line_height

    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
