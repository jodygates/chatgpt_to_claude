"""
Shared utilities for ChatGPT-to-Claude migration toolkit.

Provides conversation loading, active-branch tree traversal, rich formatting,
and filtering capabilities used by all export scripts.
"""

import json
import os
from datetime import datetime, timezone
from collections import defaultdict


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CLAUDE_PROJECT_LIMIT_CHARS = 500_000   # ~200K tokens
NOTEBOOKLM_LIMIT_MB = 50
DEFAULT_SPLIT_MB = 25.0

ROLE_LABELS = {
    "user": "User",
    "assistant": "Assistant",
    "system": "System",
    "tool": "Tool",
}


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_conversations(path: str) -> list[dict]:
    """Load and validate conversations.json, returning the list of conversation dicts."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Could not find {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Expected a JSON array of conversation objects.")

    return data


# ---------------------------------------------------------------------------
# Tree Traversal – active branch only
# ---------------------------------------------------------------------------

def _walk_active_branch(mapping: dict, current_node: str | None) -> list[dict]:
    """
    Walk the conversation tree from *current_node* up to the root via parent
    pointers, then reverse to get chronological order.  Returns the ordered
    list of message dicts (only nodes that actually carry a message).

    Falls back to iterating all mapping nodes sorted by create_time when
    *current_node* is missing or not found in the mapping.
    """
    if current_node and current_node in mapping:
        # Walk up from the active leaf to the root
        path_ids: list[str] = []
        node_id = current_node
        while node_id is not None:
            path_ids.append(node_id)
            node = mapping.get(node_id)
            if node is None:
                break
            node_id = node.get("parent")
        path_ids.reverse()

        messages = []
        for nid in path_ids:
            node = mapping.get(nid, {})
            msg = node.get("message")
            if msg:
                messages.append(msg)
        return messages

    # Fallback: no current_node – collect all messages and sort by time
    messages = []
    for node in mapping.values():
        msg = node.get("message")
        if msg:
            messages.append(msg)
    messages.sort(key=lambda m: m.get("create_time") or 0)
    return messages


# ---------------------------------------------------------------------------
# Message extraction helpers
# ---------------------------------------------------------------------------

def _extract_text(content: dict) -> str:
    """Extract plain text from a message content dict, handling text and multimodal_text."""
    content_type = content.get("content_type", "")
    parts = content.get("parts", [])

    if content_type in ("text", "multimodal_text"):
        text_parts = []
        for part in parts:
            if isinstance(part, str):
                text_parts.append(part)
            elif isinstance(part, dict):
                # Image / file attachment placeholder
                asset_type = part.get("asset_pointer", "") or ""
                if "image" in asset_type or part.get("content_type", "") == "image_asset_pointer":
                    text_parts.append("[Image]")
                elif part.get("name"):
                    text_parts.append(f"[File: {part['name']}]")
                else:
                    text_parts.append("[Attachment]")
        return "".join(text_parts)

    # Other content types (e.g. execution_output, tether_browsing_display, etc.)
    if parts:
        return "".join(str(p) for p in parts if isinstance(p, str))
    return ""


def _model_badge(conv: dict, message: dict | None = None) -> str:
    """Return a short model identifier like 'GPT-4o' for display."""
    slug = None
    if message:
        slug = message.get("metadata", {}).get("model_slug")
    if not slug:
        slug = conv.get("default_model_slug", "")
    if not slug:
        return ""
    # Prettify common slugs
    pretty = {
        "gpt-4o": "GPT-4o",
        "gpt-4o-mini": "GPT-4o mini",
        "gpt-4": "GPT-4",
        "gpt-4-turbo": "GPT-4 Turbo",
        "gpt-3.5-turbo": "GPT-3.5",
        "o1-preview": "o1-preview",
        "o1-mini": "o1-mini",
        "o3-mini": "o3-mini",
    }
    return pretty.get(slug, slug.upper())


# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------

def ts_to_datetime(ts, *, utc: bool = True) -> datetime:
    """Convert a Unix timestamp to a datetime object."""
    if ts is None:
        return datetime.min.replace(tzinfo=timezone.utc) if utc else datetime.min
    if utc:
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    return datetime.fromtimestamp(ts)


def ts_to_str(ts, *, utc: bool = True) -> str:
    """Convert a Unix timestamp to a human-readable date string."""
    if ts is None:
        return "Unknown Date"
    dt = ts_to_datetime(ts, utc=utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S") + (" UTC" if utc else "")


# ---------------------------------------------------------------------------
# Conversation Formatter
# ---------------------------------------------------------------------------

def format_conversation(
    conv: dict,
    *,
    fmt: str = "claude",
    include_tools: bool = True,
    include_system: bool = False,
    utc: bool = True,
) -> str:
    """
    Format a single conversation dict into Markdown.

    Parameters
    ----------
    conv : dict
        A raw conversation object from conversations.json.
    fmt : str
        'claude' for Claude-optimized output, 'notebooklm' for verbose/legacy.
    include_tools : bool
        Include tool role messages (memory updates, code interpreter, etc.).
    include_system : bool
        Include system role messages (usually empty rebase bookmarks).
    utc : bool
        Use UTC timestamps (True) or local timezone (False).
    """
    title = conv.get("title", "Unknown Title")
    create_time = conv.get("create_time")
    date_str = ts_to_str(create_time, utc=utc)
    model = _model_badge(conv)
    is_archived = conv.get("is_archived", False)

    mapping = conv.get("mapping", {})
    current_node = conv.get("current_node")

    # --- header ---
    output: list[str] = []

    if fmt == "claude":
        meta_parts = [f"**Date:** {date_str}"]
        if model:
            meta_parts.append(f"**Model:** {model}")
        if is_archived:
            meta_parts.append("**Archived**")
        output.append(f"## {title}")
        output.append(" | ".join(meta_parts) + "\n")
    else:
        # notebooklm / legacy format
        output.append(f"## Conversation: {title}")
        meta_line = f"**Date:** {date_str}"
        if model:
            meta_line += f" | **Model:** {model}"
        output.append(meta_line + "\n")

    # --- walk active branch ---
    ordered_messages = _walk_active_branch(mapping, current_node)

    for msg in ordered_messages:
        weight = msg.get("weight", 1.0)
        if weight == 0.0:
            continue  # skip hidden / superseded messages

        author_role = msg.get("author", {}).get("role", "unknown")
        author_name = msg.get("author", {}).get("name")
        recipient = msg.get("recipient", "all")
        content = msg.get("content", {})

        # Decide which roles to include
        if author_role == "system":
            if not include_system:
                continue
            # Even with flag on, skip truly empty system bookmarks
            text = _extract_text(content)
            if not text.strip():
                continue
        elif author_role == "tool":
            if not include_tools:
                continue
        elif author_role not in ("user", "assistant"):
            continue

        text = _extract_text(content)
        if not text.strip():
            continue

        # Build role label
        if author_role == "user":
            label = "User"
        elif author_role == "assistant":
            if recipient != "all" and recipient:
                label = f"Assistant → {recipient}"
            else:
                label = "Assistant"
        elif author_role == "tool":
            tool_name = author_name or "unknown"
            label = f"Tool ({tool_name})"
        elif author_role == "system":
            label = "System"
        else:
            label = author_role.capitalize()

        # Per-message model info (only if different from conversation default)
        msg_model = _model_badge(conv, msg)
        if fmt == "claude" and msg_model and msg_model != model and author_role == "assistant":
            label += f" [{msg_model}]"

        output.append(f"### {label}:\n{text}\n")

    output.append("---\n")
    return "\n".join(output)


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def filter_conversations(
    data: list[dict],
    *,
    after: str | None = None,
    before: str | None = None,
    keyword: str | None = None,
    starred_only: bool = False,
    exclude_archived: bool = False,
    model_filter: str | None = None,
    utc: bool = True,
) -> list[dict]:
    """
    Filter a list of conversation dicts by various criteria.

    Parameters
    ----------
    after : str   – Only include conversations created on/after this date (YYYY-MM-DD).
    before : str  – Only include conversations created before this date (YYYY-MM-DD).
    keyword : str – Only include conversations whose title or messages contain this text (case-insensitive).
    starred_only : bool – Only include starred conversations.
    exclude_archived : bool – Exclude archived conversations.
    model_filter : str – Only include conversations using this model slug (substring match).
    utc : bool – Parse timestamps as UTC.
    """
    filtered = data

    # Date filters
    if after:
        after_dt = datetime.strptime(after, "%Y-%m-%d").replace(tzinfo=timezone.utc if utc else None)
        after_ts = after_dt.timestamp()
        filtered = [c for c in filtered if (c.get("create_time") or 0) >= after_ts]

    if before:
        before_dt = datetime.strptime(before, "%Y-%m-%d").replace(tzinfo=timezone.utc if utc else None)
        before_ts = before_dt.timestamp()
        filtered = [c for c in filtered if (c.get("create_time") or 0) < before_ts]

    # Starred
    if starred_only:
        filtered = [c for c in filtered if c.get("is_starred") is True]

    # Archived
    if exclude_archived:
        filtered = [c for c in filtered if not c.get("is_archived")]

    # Model
    if model_filter:
        model_lower = model_filter.lower()
        filtered = [
            c for c in filtered
            if model_lower in (c.get("default_model_slug") or "").lower()
        ]

    # Keyword (search in title + message text)
    if keyword:
        kw_lower = keyword.lower()
        result = []
        for c in filtered:
            # Quick check: title
            if kw_lower in (c.get("title") or "").lower():
                result.append(c)
                continue
            # Deeper check: message text
            found = False
            for node in c.get("mapping", {}).values():
                msg = node.get("message")
                if not msg:
                    continue
                text = _extract_text(msg.get("content", {}))
                if kw_lower in text.lower():
                    found = True
                    break
            if found:
                result.append(c)
        filtered = result

    return filtered


# ---------------------------------------------------------------------------
# CLI helpers – common argument setup
# ---------------------------------------------------------------------------

def add_common_args(parser):
    """Add filter and format flags shared across all export scripts."""
    parser.add_argument(
        "--format", choices=["claude", "notebooklm"], default="claude",
        help="Output format: 'claude' (default, optimized for Claude Projects) or 'notebooklm' (verbose legacy)."
    )
    parser.add_argument(
        "--after", metavar="YYYY-MM-DD", default=None,
        help="Only include conversations created on or after this date."
    )
    parser.add_argument(
        "--before", metavar="YYYY-MM-DD", default=None,
        help="Only include conversations created before this date."
    )
    parser.add_argument(
        "--keyword", default=None,
        help="Only include conversations containing this keyword (searches title and messages)."
    )
    parser.add_argument(
        "--starred-only", action="store_true",
        help="Only include starred conversations."
    )
    parser.add_argument(
        "--exclude-archived", action="store_true",
        help="Exclude archived conversations."
    )
    parser.add_argument(
        "--model", default=None,
        help="Only include conversations using this model (substring match, e.g. 'gpt-4o')."
    )
    parser.add_argument(
        "--no-tools", action="store_true",
        help="Exclude tool messages (memory updates, code interpreter output, etc.)."
    )
    parser.add_argument(
        "--include-system", action="store_true",
        help="Include non-empty system messages."
    )
    parser.add_argument(
        "--local-timezone", action="store_true",
        help="Use local timezone instead of UTC for date display and grouping."
    )
    return parser


def apply_filters(args, data: list[dict]) -> list[dict]:
    """Apply CLI filter arguments to a list of conversations."""
    utc = not getattr(args, "local_timezone", False)
    return filter_conversations(
        data,
        after=args.after,
        before=args.before,
        keyword=args.keyword,
        starred_only=args.starred_only,
        exclude_archived=args.exclude_archived,
        model_filter=args.model,
        utc=utc,
    )


def get_format_kwargs(args) -> dict:
    """Build keyword arguments for format_conversation from CLI args."""
    return {
        "fmt": args.format,
        "include_tools": not getattr(args, "no_tools", False),
        "include_system": getattr(args, "include_system", False),
        "utc": not getattr(args, "local_timezone", False),
    }
