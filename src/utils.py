import os
import re
import glob
import configparser

def get_config(config_path="config.ini"):
    """
    Loads configuration settings from config.ini, falling back to defaults if not found.
    """
    config = configparser.ConfigParser(interpolation=None)
    if os.path.exists(config_path):
        # Support UTF-8 config files with or without BOM.
        with open(config_path, "r", encoding="utf-8-sig") as f:
            config.read_file(f)
    
    # Defaults
    conversations_dir = config.get("Obsidian", "conversations_dir", fallback=r"U:\voothi.vault\kardenwort-mpv\conversations")
    active_conversation = config.get("Obsidian", "active_conversation", fallback=r"U:\voothi.vault\kardenwort-mpv\conversations\20260529122032-conversation.md")
    auto_create_project = config.getboolean("Obsidian", "auto_create_project", fallback=False)
    ensure_root_note = config.getboolean("Obsidian", "ensure_root_note", fallback=True)
    root_note_template_path = config.get("Obsidian", "root_note_template_path", fallback="")
    slug_word_count = config.getint("Parser", "slug_word_count", fallback=4)
    split_description = config.getboolean("Parser", "split_description", fallback=True)
    one_to_one = config.getboolean("Parser", "one_to_one", fallback=True)
    ignore_prefixes_raw = config.get("Parser", "ignore_prefixes", fallback="Edited ,Viewed ,Ran command:,Created At:,Completed At:,Created file ,Stdout:,Stderr:")
    ignore_prefixes = [p for p in ignore_prefixes_raw.split(",") if p]

    return {
        "conversations_dir": conversations_dir,
        "active_conversation": active_conversation,
        "auto_create_project": auto_create_project,
        "ensure_root_note": ensure_root_note,
        "root_note_template_path": root_note_template_path.strip(),
        "slug_word_count": slug_word_count,
        "split_description": split_description,
        "one_to_one": one_to_one,
        "ignore_prefixes": ignore_prefixes
    }


def sanitize_name(input_string, slug_word_count=4):
    """
    Sanitizes title string to create a safe, slugified filename.
    Matches the Obsidian Templater logic exactly.
    """
    replacements = {
        'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss',
        'Ä': 'ae', 'Ö': 'oe', 'Ü': 'ue', 
        '_': '-', ':': '-', '. ': '-', '.': '-'
    }
    
    processed_string = input_string
    for char, rep in replacements.items():
        processed_string = processed_string.replace(char, rep)
    
    # Remove characters that are not letters, numbers, spaces, or hyphens.
    # Matches /[^a-zA-Zа-яА-ЯёЁ0-9\s-]/g in JavaScript exactly.
    cleaned_for_splitting = re.sub(r'[^a-zA-Zа-яА-ЯёЁ0-9\s-]', '', processed_string)
    
    # Split by spaces and get the first N words
    words = cleaned_for_splitting.strip().split()
    first_words = words[:slug_word_count]
    
    final_name = '-'.join(first_words)
    final_name = re.sub(r'-+$', '', final_name)
    
    return final_name.lower()

def split_first_sentence(text, split_enabled=True):
    """
    Splits the first sentence of the text as the task name, 
    and returns the rest as the description.
    """
    if not split_enabled:
        return text.strip(), ""
        
    # Regex matching the first sentence ending with . ? or !
    split_match = re.match(r'^(.*?[.?!])(?:\s+|$)(.*)$', text, re.DOTALL)
    if split_match:
        clean_task_name = split_match.group(1).strip()
        description_text = split_match.group(2).strip() if split_match.group(2) else ""
        return clean_task_name, description_text
    
    return text.strip(), ""

def discover_active_conversation(conversations_dir):
    """
    Finds the latest conversation file in the conversations directory
    by sorting files matching '*conversation.md' or '*log.md' chronologically.
    """
    if not os.path.exists(conversations_dir):
        return None
        
    pattern = os.path.join(conversations_dir, "*conversation.md")
    files = glob.glob(pattern)
    if not files:
        pattern_log = os.path.join(conversations_dir, "*log.md")
        files = glob.glob(pattern_log)
        
    if not files:
        return None
        
    def extract_zid_key(filepath):
        basename = os.path.basename(filepath)
        match = re.match(r'^(\d{14})', basename)
        if match:
            return int(match.group(1))
        return os.path.getmtime(filepath)
        
    files.sort(key=extract_zid_key)
    return files[-1]
