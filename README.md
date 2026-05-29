# Obsidian ZID Note Creator Utility

[![Version](https://img.shields.io/badge/version-v1.0.0-green)](https://github.com/voothi/20260529182202-obsidian-note-creator)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A lightweight, powerful Python command-line utility to automate the creation of standalone Zettelkasten-style notes and update active parent conversation maps (MOC) using list-prefixes or raw ZID line inputs. This replicates and improves upon Obsidian Templater Javascript workflows directly from the terminal or subagent processes.

## Table of Contents
- [Description](#description)
- [Features](#features)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Usage](#usage)
- [Obsidian Ecosystem](#obsidian-ecosystem)
- [Signature](#signature)
- [License](#license)

---

## Description
When working inside complex Obsidian vaults, quickly documenting ideas, tasks, or subtasks with unique 14-digit Zettelkasten IDs (ZIDs) is a core practice. This utility parses standard ZID lines (e.g. `20260529180346 Add to AGENTS.md...`), sanitizes task names to generate precise Obsidian slug filenames, creates the individual markdown note files with complete parent metadata and standard headers, and automatically inserts the newly structured `[[link|alias]]` Wikilinks directly into your active parent conversation log MOC.

[Return to Top](#obsidian-zid-note-creator-utility)

## Features
- **Obsidian-Aligned Sanitization**: Mimics the Obsidian JavaScript Templater code to handle German/special character mappings, remove symbols, and create consistent 4-word slugs.
- **First Sentence Splitting**: Automatically extracts the first sentence of a task input to serve as the document title/H1 header, while writing the remaining text into the note's Description body.
- **Bi-directional Wikilinks**: Automatically parses, generates, and links the new documents to their active parent conversation map (MOC) seamlessly.
- **Safe Execution Checks**: Dry-run preview capability (`--dry-run`) and automated overwrite safeguards to protect existing note contents.
- **Flexible Input Sources**: Supports processing text from CLI arguments (`--text`), input files (`--input`), or piping streams directly through `stdin`.

[Return to Top](#obsidian-zid-note-creator-utility)

## Project Structure
```text
20260529182202-obsidian-note-creator/
├── config.ini               # Active settings (vault paths, default config)
├── config.ini.template      # Settings template for clean configuration
├── .gitignore               # Excludes python caches and local configs
├── LICENSE                  # MIT License
├── README.md                # Premium documentation
├── src/                     # Source directory containing utilities
│   ├── utils.py             # Shared slug generation and configuration loading
│   └── note_creator.py      # Core ZID parser, note generator, and MOC editor
└── tests/                   # Automated unit test suite
    └── test_note_creator.py # Comprehensive test coverage for parsing, formats, and workarounds
```

[Return to Top](#obsidian-zid-note-creator-utility)

## Configuration

Configuring the utility is simple via the `config.ini` file located at the root of the project.

### Default `config.ini`
```ini
[Obsidian]
# Path to the conversations folder inside the vault where new notes are created
conversations_dir = U:\voothi.vault\kardenwort-mpv\conversations

# Default active conversation markdown file to update
active_conversation = U:\voothi.vault\kardenwort-mpv\conversations\20260529122032-conversation.md

[Parser]
# Number of words to retain in the filename slug
slug_word_count = 4

# Whether to split the first sentence as task title and the rest as description
split_description = True

# Whether to save the full original message text inside the note description (1-to-1)
one_to_one = True
```

[Return to Top](#obsidian-zid-note-creator-utility)

## Usage

### 1. Clipboard Mode (AutoHotkey Integration)
Read text directly from the Windows clipboard, batch process ZID files, update active conversation MOCs, and automatically copy formatted wikilinks back to the clipboard for pasting:
```powershell
python src/note_creator.py --clipboard
```

### 2. Process Single ZID Line
Instantly create a note and update your active conversation map with a single command line text:
```powershell
python src/note_creator.py --text "20260529180346 Add to AGENTS.md a condition not to save trial .lua scripts. This is important."
```

### 3. Batch Create from Input File
Process multiple ZID logs listed line-by-line in a text file:
```powershell
python src/note_creator.py --input path/to/input.txt
```

### 4. 1-to-1 Mapping vs Sentence Splitting
By default, `one_to_one = True` copies the entire source message exactly 1-to-1 into the note body. You can disable this to strip the title sentence from the description:
```powershell
python src/note_creator.py --no-one-to-one --text "20260529180708 Short title. The rest is standard description."
```

### 5. AutoHotkey v2 Hotkey Setup (`Ctrl+Alt+K`)
Add the following snippet to your global AHK script inside `U:\voothi\20240411110510-autohotkey` to enable high-speed note creations anywhere on your system:
```autohotkey
^!k::
{
    Send("^c")
    if !ClipWait(1.5)
        return
    RunWait("C:\\Python\\Python312\\python.exe U:\\voothi\\20260529182202-obsidian-note-creator\\src\\note_creator.py --clipboard", "U:\\voothi\\20260529182202-obsidian-note-creator", "Hide")
    Sleep(300)
    KeyWait "Alt"
    KeyWait "Control"
    Send("^v")
}
```

[Return to Top](#obsidian-zid-note-creator-utility)

## Running Tests

To run the comprehensive unit test suite and verify formatting, sanitization, and parsing workarounds, execute:
```powershell
python tests/test_note_creator.py
```

[Return to Top](#obsidian-zid-note-creator-utility)

## Obsidian Ecosystem
This utility is part of the Zettelkasten and **[Kardenwort](https://github.com/kardenwort)** productivity toolset, designed to maximize development velocity, maintain traceability, and integrate AI agent logs with Obsidian Vault note graphs.

[Return to Top](#obsidian-zid-note-creator-utility)

- **Project Anchor ZID**: `20260529182251`

[Return to Top](#obsidian-zid-note-creator-utility)

## License
MIT License. See LICENSE file for details.
