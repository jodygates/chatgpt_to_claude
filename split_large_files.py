import os
import argparse


def split_file(filepath, max_size_mb=25.0, delete_original=False):
    """
    Split a Markdown file into parts at conversation boundaries (``## Conversation:``
    or ``## `` headers produced by the Claude format).

    Uses incremental byte counting (O(n)) instead of re-encoding the entire
    accumulated chunk on every iteration.
    """
    max_bytes = int(max_size_mb * 1024 * 1024)
    file_size = os.path.getsize(filepath)
    if file_size <= max_bytes:
        return False

    print(f"✂️  Splitting {os.path.basename(filepath)} "
          f"({file_size / (1024*1024):.1f} MB > {max_size_mb} MB limit)...")

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Detect the header that starts each conversation.
    # Claude format uses "## Title\n\n**Date:**", legacy uses "## Conversation: Title".
    # We must NOT split on non-conversation H2s like "## Overview" or
    # "## Table of Contents" that appear in auto-generated preambles.
    lines = content.split("\n")
    boundary_indices: list[int] = []  # line indices where conversations start
    for i, line in enumerate(lines):
        if not line.startswith("## "):
            continue
        # Legacy format: "## Conversation: ..."
        if line.startswith("## Conversation:"):
            boundary_indices.append(i)
            continue
        # Claude format: "## Title" followed (within 3 lines) by "**Date:**"
        for lookahead in range(1, min(4, len(lines) - i)):
            if lines[i + lookahead].startswith("**Date:**"):
                boundary_indices.append(i)
                break

    if not boundary_indices:
        print("  ⚠️  No conversation boundaries found — cannot split.")
        return False

    # Extract the file-level header (everything before the first conversation)
    first_boundary = boundary_indices[0]
    if first_boundary == 0:
        file_header = ""  # file starts directly with a conversation heading
    else:
        file_header = "\n".join(lines[:first_boundary]) + "\n"
    # Build list of conversation text blocks
    conversations: list[str] = []
    for idx, start in enumerate(boundary_indices):
        end = boundary_indices[idx + 1] if idx + 1 < len(boundary_indices) else len(lines)
        conversations.append("\n".join(lines[start:end]) + "\n")

    base_name = os.path.splitext(filepath)[0]
    part_num = 1
    current_chunk = file_header
    current_bytes = len(file_header.encode("utf-8"))

    written_files: list[str] = []

    for conv_text in conversations:
        conv_bytes = len(conv_text.encode("utf-8"))

        if current_bytes + conv_bytes > max_bytes and current_chunk.strip():
            # Write current chunk
            out_file = f"{base_name}_part{part_num}.md"
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(current_chunk)
            written_files.append(out_file)
            print(f"  ➜ {os.path.basename(out_file)} "
                  f"({current_bytes / (1024*1024):.1f} MB)")

            part_num += 1
            # Start next chunk with the file header repeated so each part
            # is self-contained, then add this conversation
            current_chunk = file_header + conv_text
            current_bytes = len(file_header.encode("utf-8")) + conv_bytes
        else:
            current_chunk += conv_text
            current_bytes += conv_bytes

    # Write the last chunk
    if current_chunk.strip():
        out_file = f"{base_name}_part{part_num}.md"
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(current_chunk)
        written_files.append(out_file)
        print(f"  ➜ {os.path.basename(out_file)} "
              f"({current_bytes / (1024*1024):.1f} MB)")

    # Optionally remove the oversized original
    if delete_original and written_files:
        os.remove(filepath)
        print(f"  🗑️  Removed original {os.path.basename(filepath)}")

    return True


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Split large Markdown files into smaller chunks. "
            "Respects NotebookLM limits (500k words / 50 MB) and "
            "Claude Project upload limits."
        ),
    )
    parser.add_argument(
        "input_path", nargs="?", default="monthly_exports",
        help="Path to a markdown file or directory to process",
    )
    parser.add_argument(
        "--max-size", type=float, default=25.0,
        help="Maximum file size in MB (default: 25)",
    )
    parser.add_argument(
        "--delete-original", action="store_true",
        help="Delete the original file after successful splitting.",
    )
    args = parser.parse_args()

    if os.path.isdir(args.input_path):
        print(f"🔍 Scanning '{args.input_path}' for large files...")
        count = 0
        for filename in sorted(os.listdir(args.input_path)):
            if filename.endswith(".md") and "_part" not in filename:
                filepath = os.path.join(args.input_path, filename)
                if split_file(filepath, args.max_size, args.delete_original):
                    count += 1

        if count == 0:
            print("✨ All files are within size limits. No splitting needed.")
        else:
            print(f"\n🎉 Done! Split {count} file(s).")
    else:
        if not os.path.exists(args.input_path):
            print(f"❌ Error: Could not find {args.input_path}")
            return
        split_file(args.input_path, args.max_size, args.delete_original)


if __name__ == "__main__":
    main()
