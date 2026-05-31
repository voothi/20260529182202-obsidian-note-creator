import os
import sys
import re
import argparse
from datetime import datetime
from utils import get_config, sanitize_name, split_first_sentence, discover_active_conversation

try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
except ImportError:
    PYPERCLIP_AVAILABLE = False

# Regex matching standard ZID lines with list prefixes
# e.g., "- 20260529180346 Add to AGENTS.md..." or "20260529180346 Add to..."
ZID_LINE_REGEX = re.compile(r'^(\s*(?:(?:[-*+]|\d+\.)(?:\s+\[[ xX]\])?\s+)?)(\d{14})\s+(.*)$')
SIMPLE_ZID_REGEX = re.compile(r'^(\d{14})\s+(.*)$', re.DOTALL)

def generate_note_content(task_name, description, parent_title, created_date):
    """
    Generates standard markdown note content with templates matching the Obsidian system.
    """
    return f"""---
aliases: 
  - {task_name}
up: "[[{parent_title}]]"
type: 
status: 
down: 
prev: 
next: 
same: 
project: 
area: 
tags: []
created: {created_date}
due: 
---

# {task_name}

## Description

{description}

## MOC.



## Notes


"""

def clean_task_name_formatting(task_name):
    """
    Cleans leading list markers, headers, and formatting markers (backticks, asterisks)
    from a task name while preserving inner hyphens and underscores.
    """
    # 1. Strip leading list markers: e.g., "- [ ] ", "- ", "* ", "+ ", "1. "
    task_name = re.sub(r'^\s*(?:[-*+]|\d+\.)(?:\s+\[[ xX]\])?\s+', '', task_name)
    # 2. Strip leading hashes: e.g., "### "
    task_name = re.sub(r'^\s*#+\s+', '', task_name)
    # 3. Strip backticks and asterisks anywhere
    task_name = task_name.replace('`', '').replace('*', '')
    
    # 3.5. Strip markdown images and links
    # Remove markdown images entirely: e.g., "![alt text](url)"
    task_name = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', task_name)
    # Strip markdown links to their text: e.g., "[Text](URL)" -> "Text"
    task_name = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', task_name)
    # Remove Obsidian image/attachment embeds entirely: e.g., "![[image.png]]"
    task_name = re.sub(r'!\[\[[^\]]+\]\]', '', task_name)
    # Strip Obsidian wikilinks with alias/display text: e.g., "[[Target|Display Text]]" -> "Display Text"
    task_name = re.sub(r'\[\[[^\]|]+\|([^\]]+)\]\]', r'\1', task_name)
    # Strip Obsidian wikilinks: e.g., "[[Target]]" -> "Target"
    task_name = re.sub(r'\[\[([^\]]+)\]\]', r'\1', task_name)
    
    # 4. Strip surrounding underscores if they format the entire task name
    while True:
        prev_name = task_name
        if task_name.startswith('__') and task_name.endswith('__'):
            task_name = task_name[2:-2].strip()
        elif task_name.startswith('_') and task_name.endswith('_'):
            task_name = task_name[1:-1].strip()
        if task_name == prev_name:
            break
            
    # 5. Collapse consecutive spaces and strip leading/trailing spaces
    task_name = re.sub(r'\s+', ' ', task_name).strip()
    return task_name

def find_existing_note_by_zid(conversations_dir, zid):
    """
    Scans conversations_dir for any markdown file starting with {zid}-.
    Returns (absolute_path, filename_without_ext, clean_title) if found, else None.
    """
    if not os.path.isdir(conversations_dir):
        return None
        
    prefix = f"{zid}-"
    for entry in os.scandir(conversations_dir):
        if entry.is_file() and entry.name.startswith(prefix) and entry.name.endswith(".md"):
            filepath = entry.path
            filename_no_ext = os.path.splitext(entry.name)[0]
            
            title = ""
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    
                # Parse title from H1 header: e.g. "# Title"
                for line in lines:
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break
                        
                # Fallback: parse title from aliases frontmatter
                if not title:
                    in_frontmatter = False
                    for line in lines:
                        if line.strip() == "---":
                            in_frontmatter = not in_frontmatter
                            continue
                        if in_frontmatter and line.strip().startswith("-"):
                            title = line.strip()[1:].strip()
                            break
            except Exception:
                pass
                
            if not title:
                slug = filename_no_ext[len(prefix):]
                title = slug.replace("-", " ").capitalize()
                
            return filepath, filename_no_ext, title
            
    return None


def process_single_message_block(text, config, parent_title, dry_run=False, force_one_to_one=None):
    """
    Parses a single multi-line chat message, extracts any ZID, and creates a 1-to-1 note.
    """
    conversations_dir = config["conversations_dir"]
    slug_word_count = config["slug_word_count"]
    split_description = config["split_description"]
    use_one_to_one = force_one_to_one if force_one_to_one is not None else config.get("one_to_one", True)
    created_date = datetime.now().strftime("%Y-%m-%d")
    # 1. Scan lines to find a ZID that acts as a prefix or header (ignoring service lines)
    # Match pattern supporting headers (###), lists (- [ ]), quotes (>), bold/italic markers
    zid_header_pattern = re.compile(r'^\s*(?:[-*+>#]|\d+\.)*(?:\s+\[[ xX]\])?\s*(?:\*\*|__|[*_])?\s*[`"\']?(\d{14})\b')
    lines = text.splitlines()
    
    # Load ignore prefixes dynamically from configuration
    service_prefixes = config.get("ignore_prefixes", [])
    
    zid = None
    zid_line_idx = -1
    for idx, line in enumerate(lines):
        trimmed = line.strip()
        if any(trimmed.startswith(p) for p in service_prefixes):
            continue
        
        match_obj = zid_header_pattern.match(line)
        if match_obj:
            zid = match_obj.group(1)
            zid_line_idx = idx
            break
            
    # 2. If no ZID header is found, generate a brand new ZID for this note
    if not zid:
        zid = datetime.now().strftime("%Y%m%d%H%M%S")
        print(f"[*] No ZID header found — generated new ZID: {zid}")
        
    # Check if a note with this ZID already exists in conversations_dir
    existing = find_existing_note_by_zid(conversations_dir, zid)
    if existing:
        existing_path, filename, clean_task_name = existing
        print(f"[*] Found existing note for ZID {zid}: {filename}.md with title '{clean_task_name}'")
        link_line = f"- [[{filename}|{clean_task_name}]]\n"
        return [link_line], 0
        
    clean_task_name = ""
    raw_task_name = ""
    task_line_idx = -1
    
    if zid_line_idx != -1:
        # Check if the ZID line itself has additional text
        zid_line = lines[zid_line_idx]
        match_obj = zid_header_pattern.match(zid_line)
        prefix_and_zid = match_obj.group(0)
        remaining_text = zid_line[len(prefix_and_zid):].strip()
        # Trim lightweight wrappers when the ZID appears as "`202...`" or '"202..."'
        remaining_text = re.sub(r'^[`"\']+|[`"\']+$', '', remaining_text).strip()
        # Strip trailing bold/italic markers if present
        remaining_text = re.sub(r'^(?:\*\*|__|[*_])|(?:\*\*|__|[*_])$', '', remaining_text).strip()
        
        # If there's remaining text on the ZID line, use it!
        if remaining_text:
            raw_task_name = remaining_text
            clean_task_name = clean_task_name_formatting(remaining_text)
            task_line_idx = zid_line_idx
        else:
            # Otherwise, scan downwards for the first non-empty line
            for idx in range(zid_line_idx + 1, len(lines)):
                line_content = lines[idx].strip()
                if line_content:
                    raw_task_name = line_content
                    clean_task_name = clean_task_name_formatting(line_content)
                    task_line_idx = idx
                    break
    else:
        # Fall back to the first non-empty line of the block (excluding service logs)
        for idx, line in enumerate(lines):
            cleaned_line = line.strip()
            if cleaned_line:
                is_service_line = any(cleaned_line.startswith(p) for p in service_prefixes)
                if is_service_line and len(lines) > 2:
                    continue
                raw_task_name = cleaned_line
                clean_task_name = clean_task_name_formatting(cleaned_line)
                task_line_idx = idx
                break
                
    if not clean_task_name:
        clean_task_name = "Untitled Note"
    else:
        # Strip any leading ZID from the front of the task name to avoid duplication in slug
        clean_task_name = re.sub(r'^[`"\']?\d{14}[`"\']?\s+', '', clean_task_name).strip()
        
    if raw_task_name:
        raw_task_name = re.sub(r'^[`"\']?\d{14}[`"\']?\s+', '', raw_task_name).strip()
        
    # Limit task name to first sentence if split is enabled
    if split_description:
        first_sentence, _ = split_first_sentence(clean_task_name, True)
        if first_sentence:
            clean_task_name = first_sentence
            
        raw_first_sentence, _ = split_first_sentence(raw_task_name, True)
        if raw_first_sentence:
            raw_task_name = raw_first_sentence
            
    safe_slug = sanitize_name(clean_task_name, slug_word_count)
    filename = f"{zid}-{safe_slug}"

    note_filepath = os.path.join(conversations_dir, f"{filename}.md")
    
    print(f"[*] Smart Mode - Found ZID: {zid} -> Slug: {safe_slug}")
    
    # Calculate the remaining description by looking at any remainder from the task line, plus subsequent lines
    _, line_desc = split_first_sentence(raw_task_name, split_description)
    subsequent_text = "\n".join(lines[task_line_idx + 1:]).strip()
    if line_desc.strip():
        if subsequent_text:
            remaining_desc = f"{line_desc.strip()}\n\n{subsequent_text}"
        else:
            remaining_desc = line_desc.strip()
    else:
        remaining_desc = subsequent_text
        
    if use_one_to_one:
        if not remaining_desc.strip():
            if clean_task_name != raw_task_name:
                note_description = text.replace(zid, "").strip()
            else:
                note_description = ""
        else:
            note_description = text.replace(zid, "").strip()
    else:
        if clean_task_name != raw_task_name:
            if remaining_desc.strip():
                note_description = f"{raw_task_name}\n\n{remaining_desc.strip()}"
            else:
                note_description = raw_task_name
        else:
            note_description = remaining_desc.strip()
    
    if not dry_run:
        # Prevent overwrite
        if os.path.exists(note_filepath):
            print(f"    [!] Note '{note_filepath}' already exists. Skipping file creation.")
        else:
            note_content = generate_note_content(clean_task_name, note_description, parent_title, created_date)
            with open(note_filepath, "w", encoding="utf-8") as f:
                f.write(note_content)
            print(f"    [+] Created Note: {note_filepath}")
            
    # Return formatted MOC link
    link_line = f"- [[{filename}|{clean_task_name}]]\n"
    return [link_line], 1

def process_zid_lines(lines, config, parent_title, dry_run=False, force_one_to_one=None):

    """
    Parses ZID lines, creates the matching markdown notes, and returns updated list lines.
    """
    conversations_dir = config["conversations_dir"]
    slug_word_count = config["slug_word_count"]
    split_description = config["split_description"]
    
    # Use override if provided, else use config value, default to True
    use_one_to_one = force_one_to_one if force_one_to_one is not None else config.get("one_to_one", True)
    
    created_date = datetime.now().strftime("%Y-%m-%d")
    
    updated_lines = []
    notes_created = 0
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            updated_lines.append(line)
            continue
        
        # Match standard ZID list line pattern
        match = ZID_LINE_REGEX.match(line)
        if match:
            prefix = match.group(1) or ""
            zid = match.group(2)
            raw_text = match.group(3)
            
            existing = find_existing_note_by_zid(conversations_dir, zid)
            if existing:
                existing_path, filename, clean_task_name = existing
                print(f"[*] Found existing note for ZID {zid}: {filename}.md with title '{clean_task_name}'")
                updated_lines.append(f"{prefix}[[{filename}|{clean_task_name}]]\n")
                continue
                
            raw_task_name, description_text = split_first_sentence(raw_text, split_description)
            clean_task_name = clean_task_name_formatting(raw_task_name)
            
            if use_one_to_one:
                if not description_text.strip():
                    if clean_task_name != raw_task_name:
                        note_description = raw_text.strip()
                    else:
                        note_description = ""
                else:
                    note_description = raw_text.strip()
            else:
                if clean_task_name != raw_task_name:
                    if description_text.strip():
                        note_description = f"{raw_task_name}\n\n{description_text.strip()}"
                    else:
                        note_description = raw_task_name
                else:
                    note_description = description_text.strip()
            
            safe_slug = sanitize_name(clean_task_name, slug_word_count)
            filename = f"{zid}-{safe_slug}"
            note_filepath = os.path.join(conversations_dir, f"{filename}.md")
            
            print(f"[*] Found ZID line: {zid} -> Slug: {safe_slug}")
            
            if not dry_run:
                # Check for existing note to prevent overwrite
                if os.path.exists(note_filepath):
                    print(f"    [!] Note '{note_filepath}' already exists. Skipping file creation.")
                else:
                    note_content = generate_note_content(clean_task_name, note_description, parent_title, created_date)
                    with open(note_filepath, "w", encoding="utf-8") as f:
                        f.write(note_content)
                    print(f"    [+] Created Note: {note_filepath}")
                    notes_created += 1
            else:
                print(f"    [Dry-run] Would create note: {filename}.md")
                notes_created += 1
                
            # Convert list line to standard Obsidian link format
            updated_lines.append(f"{prefix}[[{filename}|{clean_task_name}]]\n")
            
        else:
            # Check for simple raw ZID pattern
            simple_match = SIMPLE_ZID_REGEX.match(stripped)
            if simple_match:
                zid = simple_match.group(1)
                raw_text = simple_match.group(2)
                
                existing = find_existing_note_by_zid(conversations_dir, zid)
                if existing:
                    existing_path, filename, clean_task_name = existing
                    print(f"[*] Found existing note for ZID {zid}: {filename}.md with title '{clean_task_name}'")
                    updated_lines.append(f"[[{filename}|{clean_task_name}]]\n")
                    continue
                    
                raw_task_name, description_text = split_first_sentence(raw_text, split_description)
                clean_task_name = clean_task_name_formatting(raw_task_name)
                
                if use_one_to_one:
                    if not description_text.strip():
                        if clean_task_name != raw_task_name:
                            note_description = raw_text.strip()
                        else:
                            note_description = ""
                    else:
                        note_description = raw_text.strip()
                else:
                    if clean_task_name != raw_task_name:
                        if description_text.strip():
                            note_description = f"{raw_task_name}\n\n{description_text.strip()}"
                        else:
                            note_description = raw_task_name
                    else:
                        note_description = description_text.strip()
                
                safe_slug = sanitize_name(clean_task_name, slug_word_count)
                filename = f"{zid}-{safe_slug}"
                note_filepath = os.path.join(conversations_dir, f"{filename}.md")
                
                print(f"[*] Found raw ZID line: {zid} -> Slug: {safe_slug}")
                
                if not dry_run:
                    if os.path.exists(note_filepath):
                        print(f"    [!] Note '{note_filepath}' already exists. Skipping file creation.")
                    else:
                        note_content = generate_note_content(clean_task_name, note_description, parent_title, created_date)
                        with open(note_filepath, "w", encoding="utf-8") as f:
                            f.write(note_content)
                        print(f"    [+] Created Note: {note_filepath}")
                        notes_created += 1
                else:
                    print(f"    [Dry-run] Would create note: {filename}.md")
                    notes_created += 1
                    
                updated_lines.append(f"[[{filename}|{clean_task_name}]]\n")
            else:
                # No ZID match, preserve original line
                updated_lines.append(line)
                
    return updated_lines, notes_created

def update_conversation_moc(active_conv_path, new_moc_lines, dry_run=False):
    """
    Updates the active conversation MOC section with the newly formatted links.
    """
    if not os.path.exists(active_conv_path):
        print(f"[Error] Active conversation file '{active_conv_path}' not found.")
        return False
        
    with open(active_conv_path, "r", encoding="utf-8") as f:
        content_lines = f.readlines()
        
    # Find MOC section
    moc_start_idx = -1
    notes_section_idx = -1
    
    for i, line in enumerate(content_lines):
        if "## MOC." in line:
            moc_start_idx = i
        elif "## Notes" in line and moc_start_idx != -1:
            notes_section_idx = i
            break
            
    if moc_start_idx == -1 or notes_section_idx == -1:
        print("[Error] Could not locate '## MOC.' or '## Notes' in the conversation file.")
        return False
        
    # Extract current MOC block
    moc_block = content_lines[moc_start_idx + 1:notes_section_idx]
    
    # Filter out new lines if they already exist as links in the conversation
    filtered_new_moc_lines = []
    full_content_str = "".join(content_lines)
    for line in new_moc_lines:
        link_match = re.search(r'\[\[([^|\]]+)', line)
        if link_match:
            filename_target = link_match.group(1).strip()
            target_pattern = f"[[{filename_target}"
            if target_pattern in full_content_str:
                print(f"    [!] Link to '{filename_target}' already exists in conversation MOC. Skipping duplicate link insertion.")
                continue
        filtered_new_moc_lines.append(line)
        
    if not filtered_new_moc_lines:
        print("[*] No new links to add to the MOC (all already linked).")
        return True
        
    # We find where to append our new lines in the list of MOC items.
    # Typically, we can append them at the end of the existing list items.
    last_item_idx = -1
    for i in range(len(moc_block) - 1, -1, -1):
        if moc_block[i].strip().startswith("-") or moc_block[i].strip().startswith("*"):
            last_item_idx = i
            break
            
    if last_item_idx == -1:
        # No existing list items, insert directly after ## MOC.
        insert_position = moc_start_idx + 1
    else:
        insert_position = moc_start_idx + 1 + last_item_idx + 1
        
    # Insert new lines
    updated_content = content_lines[:insert_position] + filtered_new_moc_lines + content_lines[insert_position:]
    
    if not dry_run:
        with open(active_conv_path, "w", encoding="utf-8") as f:
            f.writelines(updated_content)
        print(f"[+] Successfully updated MOC in active conversation: {os.path.basename(active_conv_path)}")
    else:
        print(f"[Dry-run] Would update MOC in active conversation: {os.path.basename(active_conv_path)}")
        
    return True

def initialize_active_conversation(conversations_dir):
    """
    Creates a template active conversation note in conversations_dir and returns its path.
    """
    now_zid = datetime.now().strftime("%Y%m%d%H%M%S")
    new_conv_filename = f"{now_zid}-conversation.md"
    new_conv_path = os.path.join(conversations_dir, new_conv_filename)
    
    conv_content = f"""---
aliases:
  - Conversation {datetime.now().strftime("%Y-%m-%d")}
tags:
  - conversation
created: {datetime.now().strftime("%Y-%m-%d")}
---

# Conversation {datetime.now().strftime("%Y-%m-%d")}

## MOC.



## Notes

"""
    with open(new_conv_path, "w", encoding="utf-8") as f:
        f.write(conv_content)
        
    print(f"[+] Initialized active conversation file: {new_conv_filename}")
    return new_conv_path

def ensure_root_note(conversations_dir, template_path="", dry_run=False):
    """
    Ensures conversations_dir/root.md exists. Idempotent by design.
    If template_path is provided and exists, the new file is created from that template.
    """
    root_path = os.path.join(conversations_dir, "root.md")
    if os.path.exists(root_path):
        return root_path, False

    template_content = "# Root\n\n"
    if template_path and os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            template_content = f.read()

    if dry_run:
        print(f"[Dry-run] Would create root note: {root_path}")
        return root_path, True

    with open(root_path, "w", encoding="utf-8") as f:
        f.write(template_content)
    print(f"[+] Created root note: {root_path}")
    return root_path, True

def normalize_workspace_name(raw_workspace):
    """
    Normalizes workspace titles/slugs into a vault project folder name.
    """
    workspace_raw = raw_workspace.strip()
    workspace_raw = re.sub(r'^\d{14}[-_\s]*', '', workspace_raw)
    workspace_raw = re.sub(r'\s*\(Workspace\).*', '', workspace_raw).strip()
    workspace_raw = re.sub(r'\.md$', '', workspace_raw, flags=re.IGNORECASE).strip()
    return workspace_raw

def main():
    parser = argparse.ArgumentParser(
        description="Obsidian Note Creator Utility - Converts ZID text logs into standalone notes with wikilinks."
    )
    parser.add_argument("-d", "--dry-run", action="store_true", help="Preview note creations and wikilinks without writing to disk.")
    parser.add_argument("-i", "--input", type=str, help="Path to input text file containing ZID lines.")
    parser.add_argument("-c", "--config", type=str, default="config.ini", help="Path to config file.")
    parser.add_argument("-t", "--text", type=str, help="A single raw ZID line to process.")
    parser.add_argument("-cl", "--clipboard", action="store_true", help="Read input text directly from system clipboard, and write formatted wikilinks back to it.")
    parser.add_argument("--one-to-one", dest="one_to_one", action="store_true", default=None, help="Force saving exact copied message inside note description.")
    parser.add_argument("--no-one-to-one", dest="one_to_one", action="store_false", default=None, help="Disable one-to-one saving (revert to description-only).")
    parser.add_argument("-w", "--workspace", type=str, help="Active workspace name (e.g. 20260308110646-kardenwort-mpv) to dynamically discover project directories and active conversations.")
    
    args = parser.parse_args()
    config = get_config(args.config)
    
    lines_to_process = []
    
    if args.clipboard:
        if not PYPERCLIP_AVAILABLE:
            print("[Error] Pyperclip is not installed. Clipboard options are unavailable.")
            sys.exit(1)
        clipboard_content = pyperclip.paste()
        if clipboard_content:
            # Split text by newlines
            lines_to_process = clipboard_content.splitlines(keepends=True)
            print("[*] Successfully loaded text from system clipboard.")
        else:
            print("[!] Clipboard is empty.")
            sys.exit(0)
    elif args.text:
        lines_to_process = [args.text + "\n"]
    elif args.input:
        if os.path.exists(args.input):
            with open(args.input, "r", encoding="utf-8") as f:
                lines_to_process = f.readlines()
        else:
            print(f"[Error] Input file '{args.input}' not found.")
            sys.exit(1)
    else:
        # Fallback to stdin if no arguments are provided
        print("[*] No input source specified. Reading from standard input (press Ctrl+Z then Enter on Windows to finish):")
        lines_to_process = sys.stdin.readlines()
        
    if not lines_to_process:
        print("[!] No lines to process.")
        sys.exit(0)

    # 1. Prioritize focused active workspace from args.workspace first (if it exists on disk)
    project_name = None
    if args.workspace:
        vault_base = r"U:\voothi.vault"
        workspace_tokens = re.findall(r'\d{14}-[\w-]+', args.workspace)
        
        # VSCode titles often contain both file and workspace slugs:
        # "<file-zid-slug>.md - <workspace-zid-slug> - Visual Studio Code".
        # Prefer the rightmost token first, then fall back to raw input.
        candidate_tokens = list(reversed(workspace_tokens)) if workspace_tokens else []
        candidate_tokens.append(args.workspace)
        
        seen_candidates = set()
        for candidate in candidate_tokens:
            normalized = normalize_workspace_name(candidate)
            if not normalized or normalized in seen_candidates:
                continue
                
            seen_candidates.add(normalized)
            potential_dir = os.path.join(vault_base, normalized)
            if os.path.exists(potential_dir) and os.path.isdir(potential_dir):
                project_name = normalized
                print(f"[*] Workspace Focus - Selected project '{project_name}' from focused IDE window.")
                break
            
    # 2. If no valid focused workspace is resolved, fall back to Smart Discovery scanning the input text
    if not project_name:
        full_input_text = "".join(lines_to_process)
        vault_path_match = re.search(r'U:\\voothi\.vault\\([\w-]+)\\conversations\\', full_input_text, re.IGNORECASE)
        if vault_path_match:
            project_name = vault_path_match.group(1).strip()
            print(f"[*] Smart Discovery - Inferred project '{project_name}' from vault path in input text.")

    if project_name:
        vault_base = r"U:\voothi.vault"
        project_dir = os.path.join(vault_base, project_name)
        
        # If the project folder exists, OR if auto_create_project is True:
        if (os.path.exists(project_dir) and os.path.isdir(project_dir)) or config.get("auto_create_project", False):
            if not os.path.exists(project_dir):
                print(f"[+] Creating vault project directory: {project_dir} due to auto_create_project=True")
                
            conversations_dir = os.path.join(project_dir, "conversations")
            
            # Auto-create conversations directory if it's missing
            if not os.path.exists(conversations_dir):
                os.makedirs(conversations_dir, exist_ok=True)
                print(f"[+] Created conversations directory: {conversations_dir}")
                
            config["conversations_dir"] = conversations_dir
            latest_conv = discover_active_conversation(conversations_dir)
            if not latest_conv and config.get("ensure_active_conversation", True):
                latest_conv = initialize_active_conversation(conversations_dir)
                
            if latest_conv:
                config["active_conversation"] = latest_conv
                print(f"[*] Dynamic Discovery - Project: '{project_name}' -> Active Conversation: {os.path.basename(latest_conv)}")
            else:
                print("[*] Dynamic Discovery - No active conversation found and ensure_active_conversation is disabled.")
        else:
            print(f"[!] Discovered project path '{project_dir}' does not exist. Falling back to default config.")

    # Ensure fallback directories/files are valid when using default config.
    fallback_conversations = config["conversations_dir"]
    if not os.path.exists(fallback_conversations):
        os.makedirs(fallback_conversations, exist_ok=True)
        print(f"[+] Created fallback conversations directory: {fallback_conversations}")

    if config.get("ensure_root_note", True):
        ensure_root_note(
            fallback_conversations,
            config.get("root_note_template_path", ""),
            args.dry_run
        )
        
    if not os.path.exists(config["active_conversation"]) and config.get("ensure_active_conversation", True):
        latest_conv = discover_active_conversation(fallback_conversations)
        if not latest_conv:
            latest_conv = initialize_active_conversation(fallback_conversations)
        config["active_conversation"] = latest_conv
            
    parent_file = os.path.basename(config["active_conversation"])
    parent_title, _ = os.path.splitext(parent_file)
        
    # Check if this is a single message block rather than a batch ZID list
    is_batch_list = all(ZID_LINE_REGEX.match(l) or SIMPLE_ZID_REGEX.match(l.strip()) or not l.strip() for l in lines_to_process)
    
    if not is_batch_list:
        # Smart Mode: Process the entire clipboard text as a single note block
        full_text = "".join(lines_to_process)
        updated_moc_lines, notes_created = process_single_message_block(full_text, config, parent_title, args.dry_run, args.one_to_one)

    else:
        # Standard line-by-line list processing
        updated_moc_lines, notes_created = process_zid_lines(lines_to_process, config, parent_title, args.dry_run, args.one_to_one)

    
    # Extract and format only the valid list item wikilinks for MOC insertion
    moc_links_only = []
    for l in updated_moc_lines:
        if "[[" in l:
            stripped = l.strip()
            if stripped.startswith("-") or stripped.startswith("*"):
                moc_links_only.append(l)
            else:
                # Determine indentation
                indent = len(l) - len(l.lstrip())
                moc_links_only.append(" " * indent + "- " + stripped + "\n")
                
    if moc_links_only:
        if not os.path.exists(config["active_conversation"]) and not config.get("ensure_active_conversation", True):
            print("[*] Skipping MOC update because active conversation is missing and ensure_active_conversation is disabled.")
        else:
            update_conversation_moc(config["active_conversation"], moc_links_only, args.dry_run)
        
        # Combine output links for clipboard or printing
        output_links_text = "".join(moc_links_only)
        
        if args.clipboard and not args.dry_run:
            pyperclip.copy(output_links_text.strip())
            print("[*] Formatted wikilinks successfully copied back to system clipboard.")
            
        print("\n--- Output Wikilinks ---")
        for link in moc_links_only:
            print(link.strip())
        print("------------------------")
    else:
        print("[!] No notes were created. No ZID matches found in input.")

if __name__ == "__main__":
    main()
