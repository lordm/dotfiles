"""Turn agent responses into text worth listening to.

Every function here is pure. The daemon does the talking; this module only
decides what words come out. Ordering of the transforms matters: code fences
are consumed before inline code so a fence body is never mistaken for inline
spans, and paths are reduced before whitespace collapse so line-number
suffixes stay attached.
"""

from __future__ import annotations

import re

DEFAULT_WPM = 160
DEFAULT_MAX_SECONDS = 45.0
_TRUNCATION_NOTICE = "continues on screen."

_FENCE = re.compile(r"```[^\n]*\n(.*?)(?:```|\Z)", re.DOTALL)
_INLINE = re.compile(r"`([^`\n]+)`")
_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_BARE_URL = re.compile(r"https?://\S+")
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEP = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+")
_LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+")
_EMPHASIS = re.compile(
    r"\*\*(?:[^ *][^*]*[^ *]|[^ *])\*\*"
    r"|__(?:[^ _][^_]*[^ _]|[^ _])__"
    r"|\*(?:[^ *][^*]*[^ *]|[^ *])\*"
    r"|(?<!\w)_(?:[^ _][^_]*[^ _]|[^ _])_(?!\w)"
)
_PATH = re.compile(
    r"(?<![\w/])"
    r"((?:"
    r"/[\w.-]+/[\w./-]*"
    r"|/[\w.-]*\.[a-zA-Z]\w*"
    r"|\.[\w./-]*"
    r"|[\w.-]+(?:/[\w.-]+)+\.[a-zA-Z]\w*"
    r"))"
    r"(?::(\d+))?"
)
_SENTENCE = re.compile(r"\S.*?[.!?](?=\s|$)|\S.+$", re.DOTALL)


def _fence_to_summary(match: re.Match[str]) -> str:
    body = match.group(1)
    lines = [ln for ln in body.split("\n") if ln.strip()]
    n = max(len(lines), 1)
    return f" code block, {n} line{'s' if n != 1 else ''}. "


def _inline_to_speech(match: re.Match[str]) -> str:
    content = match.group(1).strip()
    return content if len(content.split()) <= 3 else "snippet"


def _path_to_speech(match: re.Match[str]) -> str:
    basename = match.group(1).rstrip("/").split("/")[-1]
    line_no = match.group(2)
    return f"{basename} line {line_no}" if line_no else basename


def _emphasis_replacement(match: re.Match[str]) -> str:
    """Extract content from paired emphasis markers, leaving the content."""
    full = match.group(0)
    if full.startswith("**") and full.endswith("**"):
        return full[2:-2]
    elif full.startswith("__") and full.endswith("__"):
        return full[2:-2]
    elif full.startswith("*") and full.endswith("*"):
        return full[1:-1]
    elif full.startswith("_") and full.endswith("_"):
        return full[1:-1]
    return full


def _strip_tables(text: str) -> str:
    out: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        if not buffer:
            return
        rows = [r for r in buffer if not _TABLE_SEP.match(r)]
        # The header row labels the table rather than being data.
        n = max(len(rows) - 1, 0)
        out.append(f"a table with {n} row{'s' if n != 1 else ''}.")
        buffer.clear()

    for line in text.split("\n"):
        if _TABLE_ROW.match(line):
            buffer.append(line)
        else:
            flush()
            out.append(line)
    flush()
    return "\n".join(out)


def _terminate_structural_lines(text: str) -> str:
    """Give headings and list items a full stop so they are not run together.

    Only these earn a terminator. Terminating every line would drop a period
    into the middle of any prose paragraph that happens to wrap.
    """
    out: list[str] = []
    for line in text.split("\n"):
        if not line.strip():
            out.append("")
            continue
        structural = bool(_HEADING.match(line) or _LIST_ITEM.match(line))
        stripped = _LIST_ITEM.sub("", _HEADING.sub("", line)).strip()
        if structural and stripped and not stripped.endswith((".", "!", "?", ":")):
            stripped += "."
        out.append(stripped)
    return "\n".join(out)


def clean_for_speech(text: str) -> str:
    """Reduce markdown-heavy agent output to plain speakable prose."""
    if not text or not text.strip():
        return ""

    text = _FENCE.sub(_fence_to_summary, text)
    text = _INLINE.sub(_inline_to_speech, text)
    text = _MD_LINK.sub(r"\1", text)
    text = _BARE_URL.sub("a link", text)
    text = _strip_tables(text)
    text = _terminate_structural_lines(text)
    text = _PATH.sub(_path_to_speech, text)
    text = _EMPHASIS.sub(_emphasis_replacement, text)

    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\.\s*\.(\s|$)", r".\1", text)
    return text.strip()


def estimate_seconds(text: str, wpm: int = DEFAULT_WPM) -> float:
    """Estimate spoken duration by word count. No trial synthesis."""
    return len(text.split()) / wpm * 60.0


def split_sentences(text: str) -> list[str]:
    """Split into synthesis chunks so playback can start on the first sentence."""
    if not text.strip():
        return []
    return [m.group(0).strip() for m in _SENTENCE.finditer(text) if m.group(0).strip()]


def cap_to_duration(
    text: str,
    max_seconds: float = DEFAULT_MAX_SECONDS,
    wpm: int = DEFAULT_WPM,
) -> str:
    """Truncate at a sentence boundary once the estimate exceeds max_seconds."""
    if estimate_seconds(text, wpm) <= max_seconds:
        return text

    kept: list[str] = []
    for sentence in split_sentences(text):
        candidate = kept + [sentence]
        if kept and estimate_seconds(" ".join(candidate), wpm) > max_seconds:
            break
        kept.append(sentence)

    # A single over-long sentence is spoken anyway; silence would be worse.
    return " ".join(kept) + " " + _TRUNCATION_NOTICE


def prepare(
    text: str,
    max_seconds: float = DEFAULT_MAX_SECONDS,
    wpm: int = DEFAULT_WPM,
) -> str:
    """Full pipeline: clean, then cap."""
    return cap_to_duration(clean_for_speech(text), max_seconds, wpm)
