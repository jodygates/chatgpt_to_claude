import os
from collections import defaultdict
import argparse

from utils import (
    load_conversations, format_conversation, filter_conversations,
    add_common_args, apply_filters, get_format_kwargs, ts_to_datetime,
)


def main():
    parser = argparse.ArgumentParser(
        description="Split ChatGPT conversations by month into Markdown files."
    )
    parser.add_argument(
        "input_file", nargs="?", default="conversations.json",
        help="Path to conversations.json",
    )
    parser.add_argument("--out-dir", default="monthly_exports", help="Output directory")
    add_common_args(parser)
    args = parser.parse_args()

    utc = not args.local_timezone

    # Load
    try:
        data = load_conversations(args.input_file)
    except FileNotFoundError:
        print(f"❌ Error: Could not find {args.input_file}")
        print("Please make sure you have extracted your ChatGPT data export "
              "and that conversations.json is in this directory.")
        return

    print(f"✅ Loaded {len(data)} conversations.")

    # Filter
    data = apply_filters(args, data)
    if len(data) == 0:
        print("⚠️  No conversations match the given filters.")
        return
    print(f"📋 {len(data)} conversations after filtering.")

    # Group by month
    monthly_data: dict[str, list[dict]] = defaultdict(list)
    skipped = 0

    for conv in data:
        create_time = conv.get("create_time")
        if not create_time:
            skipped += 1
            continue

        dt = ts_to_datetime(create_time, utc=utc)
        month_key = dt.strftime("%Y-%m")
        monthly_data[month_key].append(conv)

    if skipped:
        print(f"⚠️  Skipped {skipped} conversations with no timestamp.")

    os.makedirs(args.out_dir, exist_ok=True)

    # Sort by month (newest first)
    sorted_months = sorted(monthly_data.keys(), reverse=True)

    fmt_kwargs = get_format_kwargs(args)

    print("\n📂 Exporting to monthly Markdown files...")
    for month in sorted_months:
        convs = monthly_data[month]
        month_file = os.path.join(args.out_dir, f"chatgpt_{month}.md")
        with open(month_file, "w", encoding="utf-8") as f:
            f.write(f"# ChatGPT Conversations — {month}\n\n")
            for conv in convs:
                f.write(format_conversation(conv, **fmt_kwargs))

        size_mb = os.path.getsize(month_file) / (1024 * 1024)
        print(f"  ➜ {month_file} ({len(convs)} conversations) — {size_mb:.2f} MB")

    print(f"\n🎉 Done! {len(sorted_months)} monthly files written to '{args.out_dir}/'.")


if __name__ == "__main__":
    main()
