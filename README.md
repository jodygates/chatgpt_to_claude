# ChatGPT to Claude Migration Toolkit

A streamlined workflow to export your ChatGPT history and prepare it for Claude (via NotebookLM or direct upload to Claude Projects).

## The Goal

Moving from ChatGPT to Claude can mean leaving behind months (or years) of valuable, tailored conversations. This toolkit provides a lightweight set of Python scripts to extract your `conversations.json` from OpenAI, format it into clean Markdown, and prepare it for seamless use with Claude's Project Knowledge or Google NotebookLM.

## What's Included

| Script | Purpose |
|---|---|
| `split_by_month.py` | Split conversations into monthly Markdown files |
| `split_by_conversation.py` | Export each conversation as its own file |
| `extract_projects.py` | Extract ChatGPT Projects / Custom GPTs into separate files |
| `package_for_claude.py` | Package conversations directly for Claude Project Knowledge |
| `split_large_files.py` | Split oversized files to stay within upload limits |
| `utils.py` | Shared utilities (formatting, filtering, tree traversal) |

## Key Features

- **Correct branch handling**: Follows the active conversation path instead of merging all regenerated/discarded responses
- **Rich metadata**: Includes model info (GPT-4o, GPT-4, etc.), tool interactions, and conversation metadata
- **Flexible filtering**: Filter by date range, keyword, model, starred/archived status
- **Dual output formats**: Optimized for Claude Projects (`--format claude`, default) or NotebookLM (`--format notebooklm`)
- **UTC timestamps**: Consistent dates regardless of timezone (opt into local time with `--local-timezone`)

## Workflow Overview

1. **Request everything from ChatGPT:** Request your data export from OpenAI settings.
2. **Download your data:** You'll receive an email with a `.zip` file containing your history.
3. **Choose your path:**
   - **Direct to Claude →** Run `package_for_claude.py` to generate ready-to-upload Project Knowledge files.
   - **Via NotebookLM →** Run `split_by_month.py` and optionally `extract_projects.py`, then upload to NotebookLM.
4. **(Optional) Split large files:** If any files exceed upload limits, run `split_large_files.py`.

## Getting Started

> **For detailed, step-by-step visual instructions, open the included [guide.html](guide.html) file in your web browser.**

### Prerequisites
- Python 3.10+
- Your ChatGPT Export folder (specifically `conversations.json`)

### Quick Start

```bash
# Place conversations.json in the same directory as these scripts

# Option A: Package directly for Claude Projects
python package_for_claude.py

# Option B: One file per conversation
python split_by_conversation.py --prefix-date

# Option C: Split by month (for NotebookLM or Claude)
python split_by_month.py

# Option D: Extract ChatGPT Projects
python extract_projects.py

# Split oversized files if needed
python split_large_files.py monthly_exports
python split_large_files.py claude_projects
```

### Filtering Examples

```bash
# Only conversations from 2024
python package_for_claude.py --after 2024-01-01 --before 2025-01-01

# Only conversations using GPT-4o
python split_by_month.py --model gpt-4o

# Search for a specific topic
python package_for_claude.py --keyword "machine learning"

# One file per conversation, organised into month subfolders
python split_by_conversation.py --prefix-date --group-by-month

# Exclude archived, output in NotebookLM format
python split_by_month.py --exclude-archived --format notebooklm

# Combine filters
python package_for_claude.py --after 2024-06-01 --model gpt-4o --exclude-archived
```

### All CLI Flags

| Flag | Description |
|---|---|
| `--format claude\|notebooklm` | Output format (default: `claude`) |
| `--after YYYY-MM-DD` | Only conversations on/after this date |
| `--before YYYY-MM-DD` | Only conversations before this date |
| `--keyword TEXT` | Filter by keyword in title or messages |
| `--starred-only` | Only starred conversations |
| `--exclude-archived` | Skip archived conversations |
| `--model SLUG` | Filter by model (substring match) |
| `--no-tools` | Exclude tool messages |
| `--include-system` | Include non-empty system messages |
| `--local-timezone` | Use local timezone instead of UTC |
| `--prefix-date` | Prefix filenames with date (`split_by_conversation.py`) |
| `--group-by-month` | Create month subdirectories (`split_by_conversation.py`) |
| `--group-by-project` | Create project subdirectories (`split_by_conversation.py`) |
| `--by-month` | One knowledge file per month (`package_for_claude.py`) |
| `--max-size MB` | Max file size in MB (`split_large_files.py`, default: 25) |
| `--delete-original` | Remove original after splitting (`split_large_files.py`) |

## Suggested Prompts

Once your files are uploaded, try these prompts to get the most out of your history:

**NotebookLM** (analyzing your full history):
- *"Build a detailed profile of how I communicate: my preferred tone, vocabulary patterns, whether I'm formal or informal, and how I phrase requests."*
- *"For each distinct project or recurring topic, write a 2-3 paragraph context briefing I can hand to a new AI assistant."*
- *"Find every instance where I corrected the AI's behavior or said 'don't do X' / 'always do Y'. Compile these into a single instruction set."*
- *"Analyze how I use AI as a tool. Do I prefer step-by-step guidance, full code solutions, brainstorming, or validation?"*

**Claude** (after uploading knowledge files):
- *"Read my conversation history in your Project Knowledge. Introduce yourself matching my communication style and acknowledging my projects and preferences."*
- *"What are my active/unfinished projects? Summarize the current state and likely next steps for each."*
- *"Generate a system prompt for yourself that captures my preferred response style, formatting rules, tone, and explicit instructions I've given AI assistants."*
- *"Compare my conversations from 6+ months ago to recent ones. How have my questions, tone, and topics evolved?"*

> See [guide.html](guide.html) for the full list of suggested prompts.

## Contributing
Feel free to open issues or submit PRs if you want to improve the Python scripts or formatting!
