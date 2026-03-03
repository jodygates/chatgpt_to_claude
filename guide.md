# ChatGPT to Claude Migration Guide

The definitive workflow to migrate your context, instructions, and history over to Claude — directly or via Google's NotebookLM.

## 1. Request everything from ChatGPT
Your first step is to get your data out of OpenAI. Head over to ChatGPT on your web browser.
Navigate to **Settings** > **Data Controls** > **Export Data** and request an export. It may take a few minutes for them to compile it.

## 2. Download when it's ready
Check your email. OpenAI will send you a secure link to download a `.zip` file containing your data. Download it and extract the folder to your computer.
Inside, find the file named `conversations.json`. Move this file into the same directory as the Python scripts provided in this repository.

## 3. Choose your export path
You have several ways to structure your export. Pick the one that fits your workflow:

### Path A: Package directly for Claude Projects (Recommended)
The fastest way to get your history into Claude. This generates ready-to-upload Project Knowledge files with an auto-generated summary, table of contents, and optimised formatting.
```bash
python package_for_claude.py
```
This creates a `claude_projects/` folder with one or more knowledge files, automatically split to stay within Claude's limits.

You can also split by month:
```bash
python package_for_claude.py --by-month
```

### Path B: One file per conversation
Export each chat as its own Markdown file — great for browsing or selective upload.
```bash
python split_by_conversation.py --prefix-date
```
This creates a `conversations/` folder with files like `2024-10-04_My Chat Title.md`.

Organise into project folders and month subfolders:
```bash
python split_by_conversation.py --prefix-date --group-by-project --group-by-month
```
This produces a nested structure like `conversations/Project_01_Name/2024-10/2024-10-04_Title.md`.

### Path C: Split by month
Group all conversations into monthly Markdown files.
```bash
python split_by_month.py
```
This generates a `monthly_exports/` folder with files like `chatgpt_2024-10.md`.

### Path D: Extract by ChatGPT Project
If you're a Plus or Team user, you likely used ChatGPT's **Projects** feature. ChatGPT stores these as "gizmos" internally without human-readable names.
```bash
python extract_projects.py
```
This creates a `chatgpt_projects/` folder with a Markdown file per Project, plus a `Projects_Index.md` map that helps you identify which file belongs to which project based on conversation titles.

## 4. Filter your export (Optional)
All scripts support powerful filtering flags. Combine them freely:
```bash
# Only conversations from 2024
python package_for_claude.py --after 2024-01-01 --before 2025-01-01

# Only conversations using GPT-4o
python split_by_month.py --model gpt-4o

# Search for a specific topic
python split_by_conversation.py --keyword "machine learning" --prefix-date

# Exclude archived conversations
python package_for_claude.py --exclude-archived

# Combine multiple filters
python package_for_claude.py --after 2024-06-01 --model gpt-4o --exclude-archived
```

Available filters: `--after`, `--before`, `--keyword`, `--model`, `--starred-only`, `--exclude-archived`.

## 5. Choose your output format (Optional)
All scripts default to `--format claude`, which is concise and optimised for Claude's Project Knowledge. If you plan to use NotebookLM, switch to the verbose format:
```bash
python split_by_month.py --format notebooklm
```

Other useful flags:
- `--no-tools` — Exclude tool messages (memory updates, code interpreter output, etc.)
- `--include-system` — Include non-empty system messages (custom instructions that were active)
- `--local-timezone` — Use your local timezone instead of UTC

## 6. Split large files (Optional)
If any files exceed upload limits (NotebookLM: 500,000 words / 50 MB, Claude: varies by plan), split them automatically:
```bash
python split_large_files.py monthly_exports
python split_large_files.py claude_projects
```
Files are split at conversation boundaries so no single chat is broken across files. Each part repeats the file header so it's self-contained.

## 7. Upload to Claude or NotebookLM

### Direct to Claude
Go to [claude.ai](https://claude.ai), create a new **Project**, and upload your generated Markdown files as **Project Knowledge** sources. Claude will have full context of your conversation history.

### Via NotebookLM (Optional)
Head over to [Google NotebookLM](https://notebooklm.google.com) and create a new notebook. Drag and drop your Markdown files into the Sources panel.

Try prompting NotebookLM with the following:
- *"Analyze these conversations and write a comprehensive 'Custom Instructions' guide that captures my communication style and preferences."*
- *"Summarize my ongoing projects and their current context based on my chat history over the last 3 months."*
- *"What are the most common formatting requirements I ask the AI to adhere to?"*

Copy NotebookLM's output, and paste it straight into Claude's **Project Knowledge** to hit the ground running!

## 8. Suggested Prompts

Once your conversations are uploaded, use these prompts to extract maximum value from your history.

### NotebookLM Prompts (analyzing your full history)

**Personality & Communication Style**
- *"Build a detailed profile of how I communicate: my preferred tone, vocabulary patterns, whether I'm formal or informal, how I phrase requests, and how I handle disagreements or pushback from the AI."*
- *"What recurring phrases, idioms, or verbal habits do I use? List them with examples."*

**Working Patterns**
- *"Analyze how I use AI as a tool. Do I prefer step-by-step guidance, full code solutions, brainstorming, or validation of my own ideas? Summarize my working style."*
- *"What times of day and days of the week am I most active? Are there patterns in what topics I discuss at different times?"*

**Project Context Extraction**
- *"For each distinct project or recurring topic in my history, write a 2-3 paragraph context briefing that I can hand to a new AI assistant so they can pick up where ChatGPT left off."*
- *"List every technical stack, framework, language, and tool I've mentioned using. Group them by project."*

**Preferences & Corrections**
- *"Find every instance where I corrected the AI's behavior, asked it to change format, or said something like 'don't do X' or 'always do Y'. Compile these into a single instruction set."*
- *"What formatting preferences do I have? (markdown style, code block usage, response length, bullet points vs prose, etc.)"*

**Knowledge Gaps & Learning**
- *"What topics have I repeatedly asked about in different ways, suggesting I'm still learning or uncertain? Summarize these as areas where I'd benefit from a structured explanation."*

### Claude Prompts (after uploading knowledge files)

**Onboarding Claude**
- *"Read through my conversation history in your Project Knowledge. Based on what you learn, introduce yourself to me the way I'd want an AI assistant to talk to me — matching my communication style and acknowledging what you know about my projects and preferences."*

**Continuing Projects**
- *"Based on my conversation history, what are my active/unfinished projects? For each one, summarize the current state, what decisions were already made, and what the likely next steps are."*

**Custom Instructions Generation**
- *"From my conversation history, generate a system prompt for yourself that captures: my preferred response style, formatting rules, tone, recurring topics, and any explicit instructions I've given to AI assistants."*

**Decision Patterns**
- *"Analyze how I make decisions based on my conversations. Do I tend to overthink, act impulsively, seek validation, or weigh pros and cons methodically? Give me an honest assessment with examples."*

**Periodic Review**
- *"Compare my conversations from 6+ months ago to my most recent ones. How have my questions, tone, and topics evolved? What does this suggest about my growth or changing priorities?"*
