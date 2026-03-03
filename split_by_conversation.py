"""
Split ChatGPT conversations into individual Markdown files — one file per chat.

Supports organising output by project folders, month subfolders, or both.
"""

import os
import re
import argparse
from collections import defaultdict

from utils import (
    load_conversations, format_conversation,
    add_common_args, apply_filters, get_format_kwargs, ts_to_datetime,
)


# Windows reserved device names that cannot be used as filenames.
_WINDOWS_RESERVED = frozenset({
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(10)),
    *(f"LPT{i}" for i in range(10)),
})


def _safe_filename(title: str, max_len: int = 80) -> str:
    """Turn a conversation title into a filesystem-safe filename."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', title)
    name = name.strip('. ')
    if not name:
        name = "Untitled"
    name = name[:max_len]
    # Guard against Windows reserved device names (CON, PRN, NUL, COM1, …)
    stem = name.split('.')[0].upper()
    if stem in _WINDOWS_RESERVED:
        name = f"_{name}"
    return name


def _project_folder_name(gizmo_id: str, conversations: list[dict], index: int) -> str:
    """
    Build a human-friendly project folder name from its conversations.

    Uses the most common title words to give the folder a recognisable name,
    since ChatGPT exports don't include explicit project names.
    """
    # Collect title words
    words: dict[str, int] = {}
    stopwords = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "it", "this", "that", "was", "are",
        "be", "my", "me", "i", "how", "what", "can", "do", "new", "chat",
    }
    for conv in conversations:
        title = conv.get("title") or ""
        for w in title.split():
            cleaned = re.sub(r'[^a-zA-Z0-9äöüßÄÖÜ]', '', w)
            if cleaned and len(cleaned) > 2 and cleaned.lower() not in stopwords:
                words[cleaned.lower()] = words.get(cleaned.lower(), 0) + 1

    # Pick the top 2-3 keywords for the folder name
    top = sorted(words.items(), key=lambda x: x[1], reverse=True)[:3]
    keyword_part = "_".join(w.capitalize() for w, _ in top) if top else "Project"

    return f"Project_{index:02d}_{keyword_part}"


def main():
    parser = argparse.ArgumentParser(
        description="Export each ChatGPT conversation as its own Markdown file."
    )
    parser.add_argument(
        "input_file", nargs="?", default="conversations.json",
        help="Path to conversations.json",
    )
    parser.add_argument("--out-dir", default="conversations", help="Output directory")
    parser.add_argument(
        "--prefix-date", action="store_true",
        help="Prefix filenames with the date (YYYY-MM-DD_title.md).",
    )
    parser.add_argument(
        "--group-by-month", action="store_true",
        help="Create subdirectories per month (YYYY-MM/) for organisation.",
    )
    parser.add_argument(
        "--group-by-project", action="store_true",
        help="Create subdirectories per ChatGPT Project. "
             "Conversations without a project go into a 'No_Project/' folder.",
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

    os.makedirs(args.out_dir, exist_ok=True)
    fmt_kwargs = get_format_kwargs(args)

    # Sort oldest → newest
    data.sort(key=lambda c: c.get("create_time") or 0)

    # Build project folder mapping if grouping by project
    project_folders: dict[str | None, str] = {}
    if args.group_by_project:
        # Group conversations by gizmo_id to determine folder names
        by_gizmo: dict[str | None, list[dict]] = defaultdict(list)
        for conv in data:
            by_gizmo[conv.get("gizmo_id")].append(conv)

        # Name project folders (sorted by conversation count, most active first)
        idx = 1
        for gizmo_id, convs in sorted(by_gizmo.items(),
                                        key=lambda x: len(x[1]),
                                        reverse=True):
            if gizmo_id is None:
                project_folders[None] = "No_Project"
            else:
                project_folders[gizmo_id] = _project_folder_name(gizmo_id, convs, idx)
                idx += 1

    # Track duplicate filenames per output directory
    used_names: dict[str, int] = {}

    print(f"\n📂 Exporting {len(data)} conversations...")

    for conv in data:
        title = conv.get("title") or "Untitled"
        create_time = conv.get("create_time")

        # Build filename
        safe_title = _safe_filename(title)
        if args.prefix_date and create_time:
            dt = ts_to_datetime(create_time, utc=utc)
            date_prefix = dt.strftime("%Y-%m-%d")
            base_name = f"{date_prefix}_{safe_title}"
        else:
            base_name = safe_title

        # Determine the target directory
        target_dir = args.out_dir

        if args.group_by_project:
            gizmo_id = conv.get("gizmo_id")
            folder = project_folders.get(gizmo_id, "No_Project")
            target_dir = os.path.join(target_dir, folder)

        if args.group_by_month and create_time:
            dt = ts_to_datetime(create_time, utc=utc)
            target_dir = os.path.join(target_dir, dt.strftime("%Y-%m"))

        os.makedirs(target_dir, exist_ok=True)

        # De-duplicate within target directory
        dedup_key = os.path.join(target_dir, base_name)
        if dedup_key in used_names:
            used_names[dedup_key] += 1
            base_name = f"{base_name}_{used_names[dedup_key]}"
        else:
            used_names[dedup_key] = 0

        filepath = os.path.join(target_dir, f"{base_name}.md")

        # Write
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(format_conversation(conv, **fmt_kwargs))

    # Print folder summary when grouping by project
    if args.group_by_project:
        print("\n📁 Project folders:")
        for gizmo_id, folder in sorted(project_folders.items(),
                                         key=lambda x: x[1]):
            count = sum(1 for c in data if c.get("gizmo_id") == gizmo_id)
            print(f"  ➜ {folder}/ ({count} conversations)")

    print(f"\n🎉 Done! {len(data)} files written to '{args.out_dir}/'.")


if __name__ == "__main__":
    main()
