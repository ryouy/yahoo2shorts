from __future__ import annotations

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
        # Clean source display without icon
        source_text = clean_text(script.get("source") or "")[:25]
        if source_text:
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
        draw.rounded_rectangle((75, 80, 165, 190), 20, fill=(255, 225, 72))
        y = 72
        for line in _wrap(draw, script["intro"]["headline"], font(50, True), width - 240)[:2]:
            draw.text((200, y), line, font=font(50, True), fill=(30, 28, 38)); y += 66
        y = 220
        for line in _wrap(draw, script["intro"]["explainer"], font(34), width - 130)[:2]:
            draw.text((75, y), line, font=font(34), fill=(70, 67, 79)); y += 46


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
    draw.text((45, height - 56), "", font=font(22), fill="white")
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def render_thumbnail(script: dict, output: Path, settings: dict, *, background_path: Path | None = None) -> None:
    width, height = settings["width"], settings["height"]
    image = _background(width, height, background_path)
    draw = ImageDraw.Draw(image)
    # Simple dark header with clean typography
    draw.rectangle((0, 0, width, 200), fill=(12, 16, 17))
    draw.text((58, 66), "NEWS", font=font(48, True), fill=LIME)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle((0, 720, width, height), fill=(0, 0, 0, 178))
    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(image)
    y = 780
    for line in _wrap(draw, script["intro"]["headline"], font(86, True), width - 110)[:5]:
        draw.text((55, y), line, font=font(86, True), fill="white", stroke_width=4, stroke_fill=(0, 0, 0)); y += 108
    # Display multiple comments for more eye-catching thumbnail
    posts = script.get("posts", [])
    comment_count = min(3, len(posts))  # Show up to 3 comments
    for idx in range(comment_count):
        post = posts[idx]
        comment_text = post.get("text", "")
        if comment_text:
            accent_color = ACCENTS[idx % len(ACCENTS)]
            comment_y = y + 45 + (idx * 180)
            if comment_y + 160 > height - 100:
                break
            # Colored card for each comment
            draw.rounded_rectangle((55, comment_y, width - 55, comment_y + 160), 24, fill=accent_color)
            for index, line in enumerate(_wrap(draw, comment_text, font(35, True), width - 150)[:2]):
                draw.text((85, comment_y + 28 + index * 48), line, font=font(35, True), fill="white", stroke_width=2, stroke_fill=(0, 0, 0))
    draw.text((58, height - 78), "yc2ys", font=font(28, True), fill=LIME)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
