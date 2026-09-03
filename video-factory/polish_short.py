from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def _centered_multiline(draw: ImageDraw.ImageDraw, box, text: str, font, fill, spacing: int = 8) -> None:
    x0, y0, x1, y1 = box
    bbox = draw.multiline_textbbox((0, 0), text, font=font, spacing=spacing, align="center")
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.multiline_text(
        ((x0 + x1 - tw) / 2, (y0 + y1 - th) / 2),
        text,
        font=font,
        fill=fill,
        spacing=spacing,
        align="center",
    )


def _wrap_to_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> str:
    words = text.split()
    if not words:
        return text
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return "\n".join(lines)


def _fit_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: Path,
    max_width: int,
    max_height: int,
    max_lines: int = 3,
) -> tuple[str, ImageFont.FreeTypeFont]:
    for size in range(58, 39, -2):
        font = _font(font_path, size)
        wrapped = _wrap_to_width(draw, text, font, max_width)
        lines = wrapped.splitlines()
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=8, align="center")
        if len(lines) <= max_lines and (bbox[3] - bbox[1]) <= max_height:
            return wrapped, font
    font = _font(font_path, 40)
    return _wrap_to_width(draw, text, font, max_width), font


def _video_duration(path: Path) -> float:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(proc.stdout.strip())


def build_hook(path: Path, font_path: Path, message: str) -> None:
    image = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    box = (92, 160, 988, 500)
    draw.rounded_rectangle(box, radius=38, fill=(255, 255, 255, 244))
    draw.text((140, 195), "CLIENT", font=_font(font_path, 34), fill=(70, 85, 120, 255))
    text_box = (132, 245, 948, 465)
    wrapped, font = _fit_wrapped_text(
        draw,
        message,
        font_path,
        max_width=text_box[2] - text_box[0],
        max_height=text_box[3] - text_box[1],
        max_lines=3,
    )
    _centered_multiline(
        draw,
        text_box,
        wrapped,
        font,
        (20, 25, 35, 255),
    )
    image.save(path)


def build_cta(path: Path, font_path: Path, headline: str, action: str) -> None:
    image = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    box = (90, 720, 990, 1190)
    draw.rounded_rectangle(box, radius=48, fill=(18, 23, 35, 238))
    _centered_multiline(
        draw,
        (130, 765, 950, 860),
        headline,
        _font(font_path, 38),
        (190, 205, 235, 255),
    )
    _centered_multiline(
        draw,
        (130, 865, 950, 1090),
        action,
        _font(font_path, 64),
        (255, 255, 255, 255),
        spacing=12,
    )
    image.save(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--font", required=True)
    parser.add_argument("--hook", default="Can I pay you in USDT?")
    parser.add_argument("--hook-end", type=float, default=3.8)
    parser.add_argument("--cta-start", type=float)
    parser.add_argument("--cta-end", type=float)
    parser.add_argument("--cta-headline", default="FIRST TIME RECEIVING STABLECOIN?")
    parser.add_argument("--cta-action", default="Beginner guide\nin profile")
    args = parser.parse_args()

    input_video = Path(args.input).resolve()
    output_video = Path(args.output).resolve()
    font_path = Path(args.font).resolve()
    output_video.parent.mkdir(parents=True, exist_ok=True)

    duration = _video_duration(input_video)
    hook_end = min(max(0.1, args.hook_end), duration)
    cta_end = args.cta_end if args.cta_end is not None else max(0.1, duration - 0.05)
    cta_end = min(max(0.1, cta_end), duration)
    cta_start = args.cta_start if args.cta_start is not None else max(hook_end + 0.2, cta_end - 4.0)
    cta_start = min(max(0.0, cta_start), cta_end)

    work = output_video.parent / ".polish"
    work.mkdir(parents=True, exist_ok=True)
    hook_png = work / "hook.png"
    cta_png = work / "cta.png"
    build_hook(hook_png, font_path, args.hook)
    build_cta(cta_png, font_path, args.cta_headline, args.cta_action)

    filter_complex = (
        f"[0:v][1:v]overlay=0:0:enable='between(t,0,{hook_end})'[v1];"
        f"[v1][2:v]overlay=0:0:enable='between(t,{cta_start},{cta_end})'[vout]"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(input_video),
            "-i",
            str(hook_png),
            "-i",
            str(cta_png),
            "-filter_complex",
            filter_complex,
            "-map",
            "[vout]",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            "-shortest",
            str(output_video),
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
