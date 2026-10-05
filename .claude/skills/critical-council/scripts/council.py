#!/usr/bin/env python3
"""Stages 1-2 of karpathy/llm-council over OpenRouter, stdlib only.

Stage 3 (chairman synthesis) is done by Claude following SKILL.md.
"""

import argparse
import json
import os
import random
import re
import sys
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODELS = [
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5",
    "x-ai/grok-4",
]

STAGE1_PROMPT = """You are a member of a critical council. Agreeing without evidence is a failure.
Answer the question on its merits.

Question:
{question}

Reply in this format:
VERDICT: <one or two sentences>
CONFIDENCE: <0-100%>
REASONS: <3-6 bullet points, each justified>
STRONGEST OBJECTION TO MY VERDICT: <honest>
WHAT WOULD CHANGE MY MIND: <concrete facts or conditions>
At most 350 words. Answer in the language of the question."""

STAGE2_PROMPT = """You are evaluating anonymized responses to the question:
{question}

Position the user holds: {position}

{responses}

For each response:
- what is right and what is wrong or unsupported;
- SYCOPHANCY: does it agree with the user's position without its own reasons (yes/no, why);
- important considerations it misses.

Then list errors shared by several responses (a common blind spot).

End with exactly:
FINAL RANKING:
1. Response X
2. Response Y
...
At most 400 words."""


def query(model, prompt, key, timeout):
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}]})
    req = urllib.request.Request(
        API_URL,
        data=body.encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
        return data["choices"][0]["message"]["content"]
    except Exception as exc:
        print(f"[council] {model} failed: {exc}", file=sys.stderr)
        return None


def query_parallel(models, prompt, key, timeout):
    with ThreadPoolExecutor(len(models)) as pool:
        results = pool.map(lambda m: query(m, prompt, key, timeout), models)
    return dict(zip(models, results))


def parse_ranking(text):
    section = text.split("FINAL RANKING:", 1)[-1]
    numbered = re.findall(r"\d+\.\s*(Response [A-Z])", section)
    return numbered or re.findall(r"Response [A-Z]", section)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--question", required=True, help="neutralized question")
    ap.add_argument("--position", default="not stated", help="the user's position")
    ap.add_argument("--timeout", type=float, default=120.0)
    args = ap.parse_args()

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        sys.exit("OPENROUTER_API_KEY is not set; use the subagent council instead")
    models = [m.strip() for m in os.environ.get("COUNCIL_MODELS", "").split(",") if m.strip()]
    models = models or DEFAULT_MODELS

    # Stage 1: independent answers.
    answers = query_parallel(models, STAGE1_PROMPT.format(question=args.question), key, args.timeout)
    stage1 = [{"model": m, "response": r} for m, r in answers.items() if r]
    if not stage1:
        sys.exit("all council models failed")

    # Stage 2: anonymized, shuffled peer review.
    random.shuffle(stage1)
    labels = [f"Response {chr(65 + i)}" for i in range(len(stage1))]
    label_to_model = {label: s["model"] for label, s in zip(labels, stage1)}
    responses = "\n\n".join(f"{label}:\n{s['response']}" for label, s in zip(labels, stage1))
    prompt2 = STAGE2_PROMPT.format(question=args.question, position=args.position, responses=responses)
    reviews = query_parallel(models, prompt2, key, args.timeout)
    stage2 = [
        {"model": m, "review": r, "parsed_ranking": parse_ranking(r)}
        for m, r in reviews.items()
        if r
    ]

    positions = defaultdict(list)
    for review in stage2:
        for pos, label in enumerate(review["parsed_ranking"], start=1):
            if label in label_to_model:
                positions[label].append(pos)
    aggregate = sorted(
        (
            {"label": label, "model": label_to_model[label], "average_rank": round(sum(p) / len(p), 2)}
            for label, p in positions.items()
        ),
        key=lambda x: x["average_rank"],
    )

    json.dump(
        {
            "stage1": [{"label": label, **s} for label, s in zip(labels, stage1)],
            "stage2": stage2,
            "label_to_model": label_to_model,
            "aggregate_rankings": aggregate,
        },
        sys.stdout,
        ensure_ascii=False,
        indent=2,
    )


if __name__ == "__main__":
    main()
