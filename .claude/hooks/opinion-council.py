#!/usr/bin/env python3
"""UserPromptSubmit hook: when the user asks for an opinion, remind Claude to run critical-council."""

import json
import re
import sys

PATTERNS = [
    r"что (ты )?(об этом )?(думаешь|скажешь)",
    r"как (ты )?(думаешь|считаешь|оцениваешь)",
    r"тво[её] мнение",
    r"по-твоему",
    r"стоит ли",
    r"что лучше",
    r"оцени\b",
    r"прав(а)? ли я",
    r"правильно ли",
    r"согласен\??",
    r"(хорошая|плохая) ли (это )?идея",
    r"имеет ли смысл",
    r"посоветуй",
    r"консилиум",
    r"/critical-council",
    r"what do you think",
    r"your (honest )?(opinion|take|view)",
    r"should i\b",
    r"is (this|it) a (good|bad) idea",
    r"do you agree",
    r"which is better",
    r"thoughts on",
    r"am i (right|wrong)",
]
OPT_OUT = re.compile(r"без консилиума|no council|быстро ответь", re.IGNORECASE)
MATCH = re.compile("|".join(PATTERNS), re.IGNORECASE)


def main():
    try:
        prompt = json.load(sys.stdin).get("prompt", "")
    except (ValueError, AttributeError):
        return
    if not MATCH.search(prompt) or OPT_OUT.search(prompt):
        return
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": (
                    "The user may be asking for your opinion or judgment. If so, invoke the "
                    "critical-council skill before answering (lite mode for small questions, "
                    "full for consequential ones) and follow its chairman rules. Skip it if "
                    "this is actually a factual or plain implementation request."
                ),
            }
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
