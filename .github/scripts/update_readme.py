#!/usr/bin/env python3
"""Activate generated cards only after a successful, complete generation."""

from __future__ import annotations

import argparse
import html
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET


GENERATED_FILES = ("stats.svg", "languages.svg", "snake.svg", "snake-dark.svg")
SNAKE_START = "<!-- SNAKE:START -->"
SNAKE_END = "<!-- SNAKE:END -->"
SNAKE_BLOCK = """<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/generated/snake-dark.svg">
  <img alt="Animation de mon calendrier de contributions GitHub" src="assets/generated/snake.svg">
</picture>"""


def validate_images(directory: Path) -> None:
    """Reject missing or invalid SVGs before changing the README."""
    for filename in GENERATED_FILES:
        path = directory / filename
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"Image générée absente ou vide : {path}")
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as exc:
            raise ValueError(f"Image SVG invalide : {path}") from exc
        if root.tag.rsplit("}", 1)[-1] != "svg":
            raise ValueError(f"Le fichier n’est pas une image SVG : {path}")
        # An empty-language card is a legitimate result, not a reason to
        # substitute invented percentages or remove the real output.


def local_card_url(url: str) -> str:
    parsed = urlsplit(html.unescape(url))
    if parsed.scheme != "https" or parsed.netloc != "github-stats-extended.vercel.app":
        return url
    paths = {
        "/api": "assets/generated/stats.svg",
        "/api/top-langs": "assets/generated/languages.svg",
    }
    local = paths.get(parsed.path.rstrip("/"))
    if local is None:
        return url
    return local + (f"#{parsed.fragment}" if parsed.fragment else "")


def replace_card_images(markdown: str) -> str:
    """Replace image sources, preserving ordinary hyperlinks and other hosts."""
    image = re.compile(r"(!\[[^\]\n]*\]\()([^\s)]+)(\))")
    markdown = image.sub(
        lambda match: match[1] + local_card_url(match[2]) + match[3], markdown
    )
    image_tag = re.compile(r"<(?:img|source)\b[^>]*>", re.IGNORECASE)
    source_attribute = re.compile(r"(\b(?:src|srcset)\s*=\s*)([\"'])(.*?)(\2)", re.IGNORECASE)

    def replace_tag(match: re.Match[str]) -> str:
        return source_attribute.sub(
            lambda attr: attr[1] + attr[2] + local_card_url(attr[3]) + attr[4],
            match[0],
        )

    return image_tag.sub(replace_tag, markdown)


def updated_readme(markdown: str) -> str:
    if markdown.count(SNAKE_START) != 1 or markdown.count(SNAKE_END) != 1:
        raise ValueError("Le README doit contenir une seule paire de marqueurs SNAKE:START / SNAKE:END.")
    start = markdown.index(SNAKE_START) + len(SNAKE_START)
    end = markdown.index(SNAKE_END)
    if end < start:
        raise ValueError("Les marqueurs du snake sont dans le mauvais ordre.")
    markdown = markdown[:start] + "\n" + SNAKE_BLOCK + "\n" + markdown[end:]
    return replace_card_images(markdown)


def update(root: Path) -> bool:
    validate_images(root / "assets" / "generated")
    readme = root / "README.md"
    current = readme.read_text(encoding="utf-8")
    result = updated_readme(current)
    if result == current:
        return False
    # Write atomically so an interruption cannot leave a partially written README.
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=readme.parent, suffix=".tmp", delete=False
    ) as handle:
        temporary = Path(handle.name)
        handle.write(result)
    try:
        temporary.replace(readme)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    arguments = parser.parse_args()
    try:
        changed = update(arguments.root)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Mise à jour annulée : {exc}\n")
    print("README mis à jour." if changed else "README déjà à jour.")


if __name__ == "__main__":
    main()
