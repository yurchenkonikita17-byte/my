#!/usr/bin/env python3
"""Claude Code status line: shows how much of the context window is left, in percent.

Claude Code pipes session JSON to this script on stdin and prints whatever
it writes to stdout under the input box. Example output:

    Opus 5.5 · ██████░░░░ 62% tokens left
"""
import json
import sys

BAR_WIDTH = 10
DEFAULT_WINDOW = 200_000

GREEN, YELLOW, RED, DIM, RESET = "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[0m"


def used_tokens(usage):
    """Tokens that occupy the context window, from an API usage object."""
    if not isinstance(usage, dict):
        return None
    keys = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    return sum(int(usage.get(k) or 0) for k in keys)


def usage_from_transcript(path):
    """Usage of the latest assistant message in the transcript (older Claude Code)."""
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except (OSError, TypeError):
        return None
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        message = entry.get("message") if isinstance(entry, dict) else None
        if isinstance(message, dict) and message.get("usage") and not entry.get("isSidechain"):
            return message["usage"]
    return None


def remaining_percent(data):
    ctx = data.get("context_window") or {}

    # Newer Claude Code versions report the percentage directly.
    if ctx.get("remaining_percentage") is not None:
        return float(ctx["remaining_percentage"])
    if ctx.get("used_percentage") is not None:
        return 100.0 - float(ctx["used_percentage"])

    size = ctx.get("context_window_size") or DEFAULT_WINDOW
    used = used_tokens(ctx.get("current_usage"))
    if used is None:
        used = used_tokens(usage_from_transcript(data.get("transcript_path")))
    if used is None:
        return 100.0  # nothing sent yet
    return 100.0 * (1 - used / size)


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        data = {}

    pct = max(0.0, min(100.0, remaining_percent(data)))
    color = GREEN if pct > 50 else YELLOW if pct > 20 else RED
    filled = round(pct / 100 * BAR_WIDTH)
    bar = "█" * filled + "░" * (BAR_WIDTH - filled)

    model = (data.get("model") or {}).get("display_name") or ""
    prefix = f"{DIM}{model} · {RESET}" if model else ""
    print(f"{prefix}{color}{bar} {pct:.0f}%{RESET} tokens left")


if __name__ == "__main__":
    main()
