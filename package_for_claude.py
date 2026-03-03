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

    timestamps = [t for c in conversations if (t := c.get("create_time")) is not None]
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


def _write_knowledge_files(
    conversations: list[dict],
    fmt_kwargs: dict,
    utc: bool,
    max_chars: int,
    out_dir: str,
    base_name: str = "claude_knowledge",
    part_info_prefix: str = "",
) -> int:
    """
    Format and write conversations to one-or-more knowledge files.

    Formats conversations one at a time and flushes each part to disk as
    soon as it reaches *max_chars*, keeping at most one part's worth of
    formatted text in memory at any time.

    Returns the number of files written.
    """
    part_num = 0
    current_convs: list[dict] = []
    current_texts: list[str] = []
    current_chars = 0

    def _flush() -> tuple[str, int, float] | None:
        nonlocal part_num, current_convs, current_texts, current_chars
        if not current_convs:
            return None
        part_num += 1
        if part_info_prefix:
            info = f"{part_info_prefix} (Part {part_num})"
        else:
            info = f"(Part {part_num})"
        preamble = _build_preamble(current_convs, utc=utc, part_info=info)
        filename = f"{base_name}_part{part_num}.md"
        filepath = os.path.join(out_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(preamble)
            for t in current_texts:
                f.write(t)
        size_kb = os.path.getsize(filepath) / 1024
        conv_count = len(current_convs)
        current_convs = []
        current_texts = []
        current_chars = 0
        return filename, conv_count, size_kb

    written: list[tuple[str, int, float]] = []  # (filename, conv_count, size_kb)

    for conv in conversations:
        text = format_conversation(conv, **fmt_kwargs)
        text_len = len(text)

        # Dynamically compute preamble size for the tentative part, since
        # _build_preamble scales with conversation count (table of contents).
        tentative_convs = current_convs + [conv]
        preamble_len = len(_build_preamble(tentative_convs, utc=utc))

        if current_chars + text_len + preamble_len > max_chars and current_convs:
            result = _flush()
            if result:
                written.append(result)
        current_convs.append(conv)
        current_texts.append(text)
        current_chars += text_len

    result = _flush()
    if result:
        written.append(result)

    # Single part: rename to clean filename and strip "(Part 1)" from preamble
    if part_num == 1:
        part_path = os.path.join(out_dir, f"{base_name}_part1.md")
        clean_path = os.path.join(out_dir, f"{base_name}.md")
        with open(part_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Remove the "(Part 1)" marker from the preamble heading
        if part_info_prefix:
            content = content.replace(
                f"{part_info_prefix} (Part 1)", part_info_prefix, 1
            )
        else:
            content = content.replace(" (Part 1)", "", 1)
        with open(clean_path, "w", encoding="utf-8") as f:
            f.write(content)
        if part_path != clean_path:
            os.remove(part_path)
        # Update printed filename to the clean name
        written[0] = (f"{base_name}.md", written[0][1], written[0][2])

    # Print all filenames after any renames are done
    for filename, conv_count, size_kb in written:
        print(f"  ➜ {filename} ({conv_count} conversations, {size_kb:.0f} KB)")

    return part_num


def _export_single_or_split(data, args, fmt_kwargs, utc):
    """Export all conversations into one file, splitting if over the char limit."""
    max_chars = args.max_chars

    if args.single_file:
        # Force everything into one file regardless of size limits
        print("\n📂 Writing 1 knowledge file (--single-file)...")
        preamble = _build_preamble(data, utc=utc)
        filepath = os.path.join(args.out_dir, "claude_knowledge.md")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(preamble)
            for conv in data:
                f.write(format_conversation(conv, **fmt_kwargs))
        size_kb = os.path.getsize(filepath) / 1024
        print(f"  ➜ claude_knowledge.md ({len(data)} conversations, {size_kb:.0f} KB)")
        # Warn if the single file exceeds the limit
        with open(filepath, "r", encoding="utf-8") as f:
            char_count = len(f.read())
        if char_count > max_chars:
            print(f"  ⚠️  File exceeds --max-chars ({char_count:,} > {max_chars:,} chars).")
            print("      Claude may truncate this file. Remove --single-file to auto-split.")
    else:
        print("\n📂 Writing knowledge file(s)...")
        part_count = _write_knowledge_files(
            data, fmt_kwargs, utc, max_chars, args.out_dir,
        )
        print(f"\n   {part_count} file(s) produced.")

    print(f"\n🎉 Done! Files written to '{args.out_dir}/'.")
    print("   Upload these files to a Claude Project as Knowledge sources.")


def _export_by_month(data, args, fmt_kwargs, utc):
    """Export one knowledge file per month, splitting oversized months."""
    max_chars = args.max_chars
    monthly: dict[str, list[dict]] = defaultdict(list)

    for conv in data:
        ct = conv.get("create_time")
        if not ct:
            continue
        dt = ts_to_datetime(ct, utc=utc)
        key = dt.strftime("%Y-%m")
        monthly[key].append(conv)

    sorted_months = sorted(monthly.keys(), reverse=True)

    print(f"\n📂 Writing monthly knowledge file(s)...")

    total_files = 0
    for month in sorted_months:
        convs = monthly[month]
        part_count = _write_knowledge_files(
            convs, fmt_kwargs, utc, max_chars, args.out_dir,
            base_name=f"claude_knowledge_{month}",
            part_info_prefix=f"— {month}",
        )
        total_files += part_count

    print(f"\n🎉 Done! {total_files} file(s) across {len(sorted_months)} months "
          f"written to '{args.out_dir}/'.")
    print("   Upload these files to a Claude Project as Knowledge sources.")


if __name__ == "__main__":
    main()
