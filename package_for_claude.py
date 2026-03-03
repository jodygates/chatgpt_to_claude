"""
Package ChatGPT conversations into Claude Project Knowledge files.

Generates a structured summary + conversation content optimized for
Claude's Project Knowledge feature, with automatic splitting if the
output exceeds Claude's context limits.
"""

import os
import argparse
from collections import Counter, defaultdict

from utils import (
    load_conversations, format_conversation, ts_to_datetime, ts_to_str,
    add_common_args, apply_filters, get_format_kwargs,
    CLAUDE_PROJECT_LIMIT_CHARS,
)


def _top_keywords(conversations: list[dict], n: int = 15) -> list[str]:
    """Extract the most common meaningful words from conversation titles."""
    stopwords = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "it", "this", "that", "was", "are",
        "be", "as", "not", "my", "me", "i", "how", "what", "can", "do", "does",
        "about", "into", "its", "your", "you", "we", "he", "she", "they",
        "will", "would", "could", "should", "has", "have", "had", "been",
        "being", "more", "some", "all", "no", "up", "out", "so", "if", "just",
        "-", "—", "–", "&", "vs", "vs.", "etc", "using", "use", "based",
    }
    counter: Counter[str] = Counter()
    for conv in conversations:
        title = conv.get("title") or ""
        for word in title.lower().split():
            cleaned = word.strip(".,!?:;\"'()[]{}#")
            if cleaned and len(cleaned) > 2 and cleaned not in stopwords:
                counter[cleaned] += 1
    return [word for word, _ in counter.most_common(n)]


def _build_preamble(
    conversations: list[dict],
    *,
    utc: bool = True,
    part_info: str = "",
) -> str:
    """Build an auto-generated summary preamble for the knowledge file."""
    total = len(conversations)
    if total == 0:
        return "# ChatGPT Conversation History\n\nNo conversations.\n\n"

    timestamps = [c.get("create_time") for c in conversations if c.get("create_time")]
    earliest = min(timestamps) if timestamps else None
    latest = max(timestamps) if timestamps else None

    # Model distribution
    models: Counter[str] = Counter()
    for c in conversations:
        slug = c.get("default_model_slug", "unknown") or "unknown"
        models[slug] += 1

    # Top keywords from titles
    keywords = _top_keywords(conversations)

    lines = [
        "# ChatGPT Conversation History" + (f" {part_info}" if part_info else ""),
        "",
        "This file contains conversations exported from ChatGPT, formatted for "
        "use as Claude Project Knowledge.",
        "",
        "## Overview",
        f"- **Total conversations:** {total}",
        f"- **Date range:** {ts_to_str(earliest, utc=utc)} → {ts_to_str(latest, utc=utc)}",
        f"- **Models used:** {', '.join(f'{slug} ({cnt})' for slug, cnt in models.most_common(5))}",
    ]

    if keywords:
        lines.append(f"- **Top topics:** {', '.join(keywords)}")

    lines.append("")
    lines.append("## Table of Contents\n")

    for i, conv in enumerate(conversations, 1):
        title = conv.get("title", "Untitled")
        date = ts_to_str(conv.get("create_time"), utc=utc)
        lines.append(f"{i}. {title} ({date})")

    lines.append("\n---\n")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Package ChatGPT conversations into Claude Project Knowledge files. "
            "Generates a structured summary + rich conversation content, "
            "automatically splitting if output exceeds Claude's limits."
        ),
    )
    parser.add_argument(
        "input_file", nargs="?", default="conversations.json",
        help="Path to conversations.json",
    )
    parser.add_argument(
        "--out-dir", default="claude_projects",
        help="Output directory (default: claude_projects)",
    )
    parser.add_argument(
        "--max-chars", type=int, default=CLAUDE_PROJECT_LIMIT_CHARS,
        help=f"Max characters per output file (default: {CLAUDE_PROJECT_LIMIT_CHARS:,})",
    )
    parser.add_argument(
        "--single-file", action="store_true",
        help="Try to produce a single output file (split only if over limit).",
    )
    parser.add_argument(
        "--by-month", action="store_true",
        help="Create one knowledge file per month instead of one big file.",
    )
    add_common_args(parser)
    args = parser.parse_args()

    utc = not args.local_timezone

    # Load & filter
    try:
        data = load_conversations(args.input_file)
    except FileNotFoundError:
        print(f"❌ Error: Could not find {args.input_file}")
        return

    print(f"✅ Loaded {len(data)} conversations.")
    data = apply_filters(args, data)
    if not data:
        print("⚠️  No conversations match the given filters.")
        return
    print(f"📋 {len(data)} conversations after filtering.")

    # Sort chronologically (oldest first for reading order)
    data.sort(key=lambda c: c.get("create_time") or 0)

    os.makedirs(args.out_dir, exist_ok=True)
    fmt_kwargs = get_format_kwargs(args)
    fmt_kwargs["fmt"] = "claude"  # always Claude format for this script

    if args.by_month:
        _export_by_month(data, args, fmt_kwargs, utc)
    else:
        _export_single_or_split(data, args, fmt_kwargs, utc)


def _export_single_or_split(data, args, fmt_kwargs, utc):
    """Export all conversations into one file, splitting if over the char limit."""
    max_chars = args.max_chars

    # Pre-format all conversations
    formatted = []
    for conv in data:
        text = format_conversation(conv, **fmt_kwargs)
        formatted.append((conv, text))

    # Try to fit into a single file, otherwise split
    parts: list[list[tuple[dict, str]]] = []
    current_part: list[tuple[dict, str]] = []
    current_chars = 0

    # Reserve space for preamble (estimate ~3K chars)
    preamble_reserve = 5000

    for conv, text in formatted:
        text_len = len(text)
        if current_chars + text_len + preamble_reserve > max_chars and current_part:
            parts.append(current_part)
            current_part = []
            current_chars = 0
        current_part.append((conv, text))
        current_chars += text_len

    if current_part:
        parts.append(current_part)

    print(f"\n📂 Writing {len(parts)} knowledge file(s)...")

    for i, part_convs in enumerate(parts, 1):
        part_info = f"(Part {i}/{len(parts)})" if len(parts) > 1 else ""
        convs_only = [c for c, _ in part_convs]

        preamble = _build_preamble(convs_only, utc=utc, part_info=part_info)
        body = "".join(text for _, text in part_convs)

        if len(parts) > 1:
            filename = f"claude_knowledge_part{i}.md"
        else:
            filename = "claude_knowledge.md"

        filepath = os.path.join(args.out_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(preamble)
            f.write(body)

        size_kb = os.path.getsize(filepath) / 1024
        print(f"  ➜ {filename} ({len(convs_only)} conversations, {size_kb:.0f} KB)")

    print(f"\n🎉 Done! Files written to '{args.out_dir}/'.")
    print("   Upload these files to a Claude Project as Knowledge sources.")


def _export_by_month(data, args, fmt_kwargs, utc):
    """Export one knowledge file per month."""
    monthly: dict[str, list[dict]] = defaultdict(list)

    for conv in data:
        ct = conv.get("create_time")
        if not ct:
            continue
        dt = ts_to_datetime(ct, utc=utc)
        key = dt.strftime("%Y-%m")
        monthly[key].append(conv)

    sorted_months = sorted(monthly.keys(), reverse=True)

    print(f"\n📂 Writing {len(sorted_months)} monthly knowledge file(s)...")

    for month in sorted_months:
        convs = monthly[month]
        preamble = _build_preamble(convs, utc=utc, part_info=f"— {month}")
        body = "".join(format_conversation(c, **fmt_kwargs) for c in convs)

        filename = f"claude_knowledge_{month}.md"
        filepath = os.path.join(args.out_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(preamble)
            f.write(body)

        size_kb = os.path.getsize(filepath) / 1024
        print(f"  ➜ {filename} ({len(convs)} conversations, {size_kb:.0f} KB)")

    print(f"\n🎉 Done! {len(sorted_months)} monthly files written to '{args.out_dir}/'.")
    print("   Upload these files to a Claude Project as Knowledge sources.")


if __name__ == "__main__":
    main()
