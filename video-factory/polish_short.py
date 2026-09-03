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


def build_hook(path: Path, font_path: Path, message: str) -> None:
    image = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    box = (92, 160, 988, 470)
    draw.rounded_rectangle(box, radius=38, fill=(255, 255, 255, 244))
    draw.text((140, 195), "CLIENT", font=_font(font_path, 34), fill=(70, 85, 120, 255))
    _centered_multiline(
        draw,
        (120, 235, 960, 440),
        message,
        _font(font_path, 58),
        (20, 25, 35, 255),
    )
    image.save(path)


def build_cta(path: Path, font_path: Path) -> None:
    image = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    box = (90, 720, 990, 1190)
    draw.rounded_rectangle(box, radius=48, fill=(18, 23, 35, 238))
    _centered_multiline(
        draw,
        (130, 765, 950, 860),
        "FIRST TIME RECEIVING STABLECOIN?",
        _font(font_path, 38),
        (190, 205, 235, 255),
    )
    _centered_multiline(
        draw,
        (130, 865, 950, 1090),
        "Beginner guide\nin profile",
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
    parser.add_argument("--cta-start", type=float, default=23.0)
    parser.add_argument("--cta-end", type=float, default=27.0)
    args = parser.parse_args()

    input_video = Path(args.input).resolve()
    output_video = Path(args.output).resolve()
    font_path = Path(args.font).resolve()
    output_video.parent.mkdir(parents=True, exist_ok=True)

    work = output_video.parent / ".polish"
    work.mkdir(parents=True, exist_ok=True)
    hook_png = work / "hook.png"
    cta_png = work / "cta.png"
    build_hook(hook_png, font_path, args.hook)
    build_cta(cta_png, font_path)

    filter_complex = (
        f"[0:v][1:v]overlay=0:0:enable='between(t,0,{args.hook_end})'[v1];"
        f"[v1][2:v]overlay=0:0:enable='between(t,{args.cta_start},{args.cta_end})'[vout]"
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
