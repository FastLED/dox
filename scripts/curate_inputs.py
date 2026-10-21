#!/usr/bin/env python3
"""Select API sources and Markdown linked directly by the release README."""

import fnmatch
import json
import re
import shlex
import sys
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit


MARKDOWN = {".md", ".markdown"}
# Inline destinations and reference definitions cover the release README's links.
LINK = re.compile(
    r"(?<!!)\[[^\]\n]*\]\(\s*(?:<(?P<angle>[^>\n]+)>|(?P<inline>[^\s)]+))"
    r"|^ {0,3}\[(?P<label>[^\]\n]+)\]:\s*(?:<(?P<ref_angle>[^>\n]+)>|(?P<reference>\S+))",
    re.MULTILINE,
)
CODE = re.compile(r"^ *(```|~~~).*?^ *\1[^\n]*$|`[^`\n]*`", re.MULTILINE | re.DOTALL)
IMAGE = re.compile(r"!\[[^\]\n]*\](?:\[[^\]\n]*\]|\([^\n)]*\))?")
INLINE = re.compile(
    r"(?<!!)\[(?P<label>[^\]\n]*)\]\(\s*(?:<(?P<angle>[^>\n]+)>|"
    r'(?P<target>[^\s)]+))(?:\s+["\'][^\n]*?["\'])?\s*\)'
)
REFERENCE = re.compile(
    r"(?<!!)\[(?P<label>[^\]\n]+)\](?:\[(?P<reference>[^\]\n]*)\])?(?!\()"
)


def link_text(text: str) -> str:
    """Hide code and images while retaining source offsets for ordinary links."""
    for pattern in (CODE, IMAGE):
        text = pattern.sub(lambda match: " " * len(match[0]), text)
    return text


def destinations(text: str) -> Iterator[tuple[int, int]]:
    """Yield destination spans, ignoring code examples and images."""
    masked = link_text(text)
    body = re.sub(r"^ {0,3}\[[^\]\n]+\]:[^\n]*", "", masked, flags=re.MULTILINE)
    for match in LINK.finditer(masked):
        if match["label"] and not re.search(
            r"(?<!!)\[" + re.escape(match["label"]) + r"\]", body, re.IGNORECASE
        ):
            continue
        name = next(
            name
            for name, value in match.groupdict().items()
            if value is not None and name != "label"
        )
        yield match.span(name)


def local_path(root: Path, document: Path, target: str) -> Path | None:
    """Resolve a repository link, including missing files, without escaping root."""
    url = urlsplit(target)
    if url.scheme or url.netloc or not url.path:
        return None
    path = (document.parent / unquote(url.path)).resolve()
    if not path.is_relative_to(root):
        return None
    return path


def local_markdown(root: Path, document: Path, target: str) -> Path | None:
    path = local_path(root, document, target)
    if path is None or path.suffix.lower() not in MARKDOWN:
        return None
    return path if path.is_file() else None


def settings(config: str) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    for line in config.replace("\\\n", " ").splitlines():
        match = re.match(r"^\s*(INPUT|FILE_PATTERNS|EXCLUDE)\s*=\s*(.*)", line)
        if match:
            values[match[1]] = shlex.split(match[2], comments=True)
    return values


def select(root: Path) -> tuple[list[Path], set[Path]]:
    readme = root / "README.md"
    text = readme.read_text()
    markdown = {readme}
    for start, end in destinations(text):
        target = local_markdown(root, readme, text[start:end])
        if target is not None:
            markdown.add(target)

    config = settings((root / "docs/Doxyfile").read_text())
    excluded = [(root / "docs" / item).resolve() for item in config.get("EXCLUDE", [])]
    sources: set[Path] = set()
    for item in config["INPUT"]:
        candidate = (root / "docs" / item).resolve()
        for path in candidate.rglob("*") if candidate.is_dir() else [candidate]:
            resolved = path.resolve()
            if not resolved.is_relative_to(root) or not resolved.is_file():
                continue
            if resolved.suffix.lower() in MARKDOWN:
                continue
            if any(
                resolved == entry or resolved.is_relative_to(entry)
                for entry in excluded
            ):
                continue
            if any(
                fnmatch.fnmatch(path.name, pattern)
                for pattern in config["FILE_PATTERNS"]
            ):
                sources.add(resolved)
    return sorted(sources | markdown), markdown


def configure(root: Path, tag: str, manifest: Path) -> None:
    inputs, markdown = select(root)
    print(
        f"Selected {len(inputs) - len(markdown)} API source files and {len(markdown)} Markdown documents",
        file=sys.stderr,
    )
    manifest.write_text(
        json.dumps(
            {
                "root": str(root),
                "tag": tag,
                "markdown": [str(p) for p in sorted(markdown)],
            }
        )
    )
    # Explicit files avoid importing unrelated Markdown through recursive directories.
    print("\nINPUT =")
    for path in inputs:
        print("INPUT += " + json.dumps(str(path)))
    print("EXCLUDE =")
    command = shlex.join(
        [sys.executable, str(Path(__file__).resolve()), "filter", str(manifest)]
    )
    print(
        "FILTER_PATTERNS = "
        + " ".join(
            json.dumps(pattern + "=" + command) for pattern in ("*.md", "*.markdown")
        )
    )
    print("FILTER_SOURCE_FILES = NO")


def filter_document(manifest: Path, document: Path) -> str:
    state = json.loads(manifest.read_text())
    text = document.read_text()
    if document.suffix.lower() not in MARKDOWN:
        return text
    root = Path(state["root"])
    selected = set(state["markdown"])
    masked = link_text(text)
    edits: list[tuple[int, int, str]] = []
    missing: set[tuple[int, int]] = set()
    for start, end in destinations(text):
        target = text[start:end]
        path = local_path(root, document, target)
        if path is None:
            continue
        url = urlsplit(target)
        # Doxygen can leave file.md#section as a literal, broken relative URL.
        # Keep section links on the same tagged GitHub document.
        if str(path) in selected and not (url.query or url.fragment):
            continue
        if not path.exists():
            missing.add((start, end))
            continue
        url = urlsplit(target)
        kind = "tree" if path.is_dir() else "blob"
        external = f"https://github.com/FastLED/FastLED/{kind}/" + quote(
            state["tag"], safe=""
        )
        external += "/" + quote(path.relative_to(root).as_posix())
        if url.query:
            external += "?" + url.query
        if url.fragment:
            external += "#" + url.fragment
        edits.append((start, end, external))

    # A release can refer to documents that were never included in its tag.
    # Preserve their labels rather than publishing links that cannot resolve.
    for match in INLINE.finditer(masked):
        span = match.span("angle" if match["angle"] is not None else "target")
        if span in missing:
            edits.append(
                (
                    *match.span(),
                    text[slice(*match.span("label"))]
                    + " (not available in this release)",
                )
            )
    missing_references = set()
    for match in LINK.finditer(masked):
        if match["label"] is None:
            continue
        span = match.span(
            "ref_angle" if match["ref_angle"] is not None else "reference"
        )
        if span in missing:
            missing_references.add(" ".join(match["label"].split()).casefold())
    # Mask definitions so they cannot be mistaken for shortcut reference uses.
    body = re.sub(
        r"^ {0,3}\[[^\]\n]+\]:[^\n]*",
        lambda match: " " * len(match[0]),
        masked,
        flags=re.MULTILINE,
    )
    for match in REFERENCE.finditer(body):
        label = match["reference"] or match["label"]
        if " ".join(label.split()).casefold() in missing_references:
            edits.append(
                (
                    *match.span(),
                    text[slice(*match.span("label"))]
                    + " (not available in this release)",
                )
            )
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text


if __name__ == "__main__":
    if sys.argv[1] == "configure":
        configure(Path(sys.argv[2]).resolve(), sys.argv[3], Path(sys.argv[4]).resolve())
    elif sys.argv[1] == "filter":
        print(filter_document(Path(sys.argv[2]), Path(sys.argv[3]).resolve()), end="")
    else:
        raise SystemExit("Expected configure or filter")
