import os
import sys
import re
import argparse
from datetime import datetime
from utils import get_config, sanitize_name, split_first_sentence

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

def process_single_message_block(text, config, parent_title, dry_run=False, force_one_to_one=None):
    """
    Parses a single multi-line chat message, extracts any ZID, and creates a 1-to-1 note.
    """
    conversations_dir = config["conversations_dir"]
    slug_word_count = config["slug_word_count"]
    split_description = config["split_description"]
    use_one_to_one = force_one_to_one if force_one_to_one is not None else config.get("one_to_one", True)
    created_date = datetime.now().strftime("%Y-%m-%d")
    
    # 1. Find all ZIDs in the text and select the chronologically latest (maximum value)
    zids = re.findall(r'\b(\d{14})\b', text)
    if not zids:
        print("[!] No ZID found in the input block.")
        return [], 0
        
    zid = max(zids, key=int)

    
    # 2. Extract clean task name: first non-empty line that isn't just the ZID or command
    lines = text.splitlines()
    clean_task_name = ""
    for line in lines:
        cleaned_line = line.strip()
        if cleaned_line and cleaned_line != zid:
            # Strip markdown formatting for the title
            clean_task_name = re.sub(r'[`*_#\-]', '', cleaned_line).strip()
            # If it's a "Ran command" line, clean it up slightly or use it
            break
            
    if not clean_task_name:
        clean_task_name = "Untitled Note"
    else:
        # Strip any leading ZID from the front of the task name to avoid duplication in slug
        clean_task_name = re.sub(r'^\d{14}\s+', '', clean_task_name).strip()
        
    # Limit task name to first sentence if split is enabled
    if split_description:
        first_sentence, _ = split_first_sentence(clean_task_name, True)
        if first_sentence:
            clean_task_name = first_sentence
            
    safe_slug = sanitize_name(clean_task_name, slug_word_count)
    filename = f"{zid}-{safe_slug}"

    note_filepath = os.path.join(conversations_dir, f"{filename}.md")
    
    print(f"[*] Smart Mode - Found ZID: {zid} -> Slug: {safe_slug}")
    
    note_description = text.strip() if use_one_to_one else text.replace(zid, "").strip()
    
    if not dry_run:
        # Prevent overwrite
        if os.path.exists(note_filepath):
            print(f"    [!] Note '{filename}.md' already exists. Skipping file creation.")
        else:
            note_content = generate_note_content(clean_task_name, note_description, parent_title, created_date)
            with open(note_filepath, "w", encoding="utf-8") as f:
                f.write(note_content)
            print(f"    [+] Created Note: {filename}.md")
            
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
            
            clean_task_name, description_text = split_first_sentence(raw_text, split_description)
            note_description = raw_text.strip() if use_one_to_one else description_text
            
            safe_slug = sanitize_name(clean_task_name, slug_word_count)
            filename = f"{zid}-{safe_slug}"
            note_filepath = os.path.join(conversations_dir, f"{filename}.md")
            
            print(f"[*] Found ZID line: {zid} -> Slug: {safe_slug}")
            
            if not dry_run:
                # Check for existing note to prevent overwrite
                if os.path.exists(note_filepath):
                    print(f"    [!] Note '{filename}.md' already exists. Skipping file creation.")
                else:
                    note_content = generate_note_content(clean_task_name, note_description, parent_title, created_date)
                    with open(note_filepath, "w", encoding="utf-8") as f:
                        f.write(note_content)
                    print(f"    [+] Created Note: {filename}.md")
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
                
                clean_task_name, description_text = split_first_sentence(raw_text, split_description)
                note_description = raw_text.strip() if use_one_to_one else description_text
                
                safe_slug = sanitize_name(clean_task_name, slug_word_count)
                filename = f"{zid}-{safe_slug}"
                note_filepath = os.path.join(conversations_dir, f"{filename}.md")
                
                print(f"[*] Found raw ZID line: {zid} -> Slug: {safe_slug}")
                
                if not dry_run:
                    if os.path.exists(note_filepath):
                        print(f"    [!] Note '{filename}.md' already exists. Skipping file creation.")
                    else:
                        note_content = generate_note_content(clean_task_name, note_description, parent_title, created_date)
                        with open(note_filepath, "w", encoding="utf-8") as f:
                            f.write(note_content)
                        print(f"    [+] Created Note: {filename}.md")
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
    updated_content = content_lines[:insert_position] + new_moc_lines + content_lines[insert_position:]
    
    if not dry_run:
        with open(active_conv_path, "w", encoding="utf-8") as f:
            f.writelines(updated_content)
        print(f"[+] Successfully updated MOC in active conversation: {os.path.basename(active_conv_path)}")
    else:
        print(f"[Dry-run] Would update MOC in active conversation: {os.path.basename(active_conv_path)}")
        
    return True

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
    
    args = parser.parse_args()
    config = get_config(args.config)
    
    parent_file = os.path.basename(config["active_conversation"])
    parent_title, _ = os.path.splitext(parent_file)
    
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
        
    # Check if this is a single message block rather than a batch ZID list
    is_batch_list = all(ZID_LINE_REGEX.match(l) or SIMPLE_ZID_REGEX.match(l.strip()) or not l.strip() for l in lines_to_process)
    
    if not is_batch_list:
        # Smart Mode: Process the entire clipboard text as a single note block
        full_text = "".join(lines_to_process)
        updated_moc_lines, notes_created = process_single_message_block(full_text, config, parent_title, args.dry_run, args.one_to_one)

    else:
        # Standard line-by-line list processing
        updated_moc_lines, notes_created = process_zid_lines(lines_to_process, config, parent_title, args.dry_run, args.one_to_one)

    
    if notes_created > 0:
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

