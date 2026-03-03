import os
import collections
import argparse

from utils import (
    load_conversations, format_conversation,
    add_common_args, apply_filters, get_format_kwargs,
)


def main():
    parser = argparse.ArgumentParser(
        description="Extract specific ChatGPT Projects from your data export."
    )
    parser.add_argument(
        "input_file", nargs="?", default="conversations.json",
        help="Path to conversations.json",
    )
    parser.add_argument("--out-dir", default="chatgpt_projects", help="Output directory")
    add_common_args(parser)
    args = parser.parse_args()

    # Load
    try:
        data = load_conversations(args.input_file)
    except FileNotFoundError:
        print(f"❌ Error: Could not find {args.input_file}")
        return

    print(f"✅ Loaded {len(data)} conversations.")

    # Filter
    data = apply_filters(args, data)
    if len(data) == 0:
        print("⚠️  No conversations match the given filters.")
        return
    print(f"📋 {len(data)} conversations after filtering.")

    # Group by gizmo_id (Project / Custom GPT identifier)
    projects: dict[str, list[dict]] = collections.defaultdict(list)
    for conv in data:
        gizmo_id = conv.get("gizmo_id")
        if gizmo_id:
            projects[gizmo_id].append(conv)

    if not projects:
        print("⚠️  No Projects or Custom GPTs found in this export.")
        return

    os.makedirs(args.out_dir, exist_ok=True)

    # Sort projects by conversation count (most active first)
    sorted_projects = sorted(projects.items(), key=lambda x: len(x[1]), reverse=True)

    index_content = [
        "# ChatGPT Projects Index\n",
        ("Since ChatGPT's data export doesn't include the explicit human-readable "
         "names of your Projects, this index helps you map the exported files to "
         "your Projects based on the conversation titles within them.\n"),
    ]

    fmt_kwargs = get_format_kwargs(args)

    print("\n📂 Extracting Projects...")
    count = 1
    for gizmo_id, convs in sorted_projects:
        titles = [c.get("title", "Untitled") for c in convs]

        filename = f"Project_{count:02d}_{len(convs)}_conversations.md"
        filepath = os.path.join(args.out_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# ChatGPT Project (ID: {gizmo_id})\n\n")
            f.write("## Conversations in this Project:\n")
            for t in titles:
                f.write(f"- {t}\n")
            f.write("\n---\n\n")

            for conv in convs:
                f.write(format_conversation(conv, **fmt_kwargs))

        # Index entry
        index_content.append(f"## [{filename}]({filename})")
        index_content.append(
            f"**ID:** `{gizmo_id}` | **Conversations:** {len(convs)}"
        )
        index_content.append(
            "**Sample Conversations to help you identify this Project:**"
        )
        for t in titles[:5]:
            index_content.append(f"- {t}")
        if len(titles) > 5:
            index_content.append(f"- *...and {len(titles) - 5} more.*")
        index_content.append("\n")

        print(f"  ➜ {filename} ({len(convs)} conversations)")
        count += 1

    # Write the index file
    index_file = os.path.join(args.out_dir, "Projects_Index.md")
    with open(index_file, "w", encoding="utf-8") as f:
        f.write("\n".join(index_content))

    print(
        f"\n🎉 Done! Extracted {len(sorted_projects)} Projects to '{args.out_dir}/'."
    )
    print(f"   Open '{index_file}' to see a map of all your projects.")


if __name__ == "__main__":
    main()
