import os
import re
import glob
import configparser

def _split_delimited(raw_value, delimiter="||"):
    """
    Splits a config value by delimiter and trims each entry.
    """
    if not raw_value:
        return []
    return [entry.strip() for entry in raw_value.split(delimiter) if entry.strip()]

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
    eol = config.get("Obsidian", "eol", fallback="lf").strip().lower()
    ensure_root_note = config.getboolean("Obsidian", "ensure_root_note", fallback=True)
    ensure_active_conversation = config.getboolean("Obsidian", "ensure_active_conversation", fallback=True)
    root_note_template_path = config.get("Obsidian", "root_note_template_path", fallback="templates/root.md")
    conversation_note_template_path = config.get("Obsidian", "conversation_note_template_path", fallback="templates/conversation.md")
    moc_spacing_mode = config.get("Obsidian", "moc_spacing_mode", fallback="normalize").strip().lower()
    if root_note_template_path and not os.path.isabs(root_note_template_path):
        config_dir = os.path.dirname(os.path.abspath(config_path))
        root_note_template_path = os.path.abspath(os.path.join(config_dir, root_note_template_path))
    if conversation_note_template_path and not os.path.isabs(conversation_note_template_path):
        config_dir = os.path.dirname(os.path.abspath(config_path))
        conversation_note_template_path = os.path.abspath(os.path.join(config_dir, conversation_note_template_path))
    slug_word_count = config.getint("Parser", "slug_word_count", fallback=4)
    split_description = config.getboolean("Parser", "split_description", fallback=True)
    one_to_one = config.getboolean("Parser", "one_to_one", fallback=True)
    ignore_prefixes_raw = config.get("Parser", "ignore_prefixes", fallback="Edited ,Viewed ,Ran command:,Created At:,Completed At:,Created file ,Stdout:,Stderr:")
    ignore_prefixes = [p for p in ignore_prefixes_raw.split(",") if p]
    
    vault_base = config.get("WorkspaceDetection", "vault_base", fallback=r"U:\voothi.vault").strip()
    workspace_path_patterns_raw = config.get(
        "WorkspaceDetection",
        "workspace_path_patterns",
        fallback=r"(?:U:\\voothi\.vault\\|Private Vault[\\/])([\w\-\s]+)(?:\\|/)conversations(?:\\|/|$)||(?:U:\\voothi\.vault\\|Private Vault[\\/])([\w\-\s]+)(?:\\|/|$)"
    )
    workspace_discovery_patterns_raw = config.get(
        "WorkspaceDetection",
        "workspace_discovery_patterns",
        fallback=r"U:\\voothi\.vault\\([\w\-\s]+)\\conversations\\||Private Vault[\\/]([\w\-\s]+)[\\/]conversations[\\/]||file:///u%3A/voothi\.vault/([^/]+)/conversations/"
    )
    workspace_slug_pattern = config.get(
        "WorkspaceDetection",
        "workspace_slug_pattern",
        fallback=r"\d{14}-[\w-]+"
    ).strip()
    workspace_code_workspace_pattern = config.get(
        "WorkspaceDetection",
        "workspace_code_workspace_pattern",
        fallback=r"(\d{14}-[\w-]+)\.code-workspace"
    ).strip()
    workspace_normalization_patterns_raw = config.get(
        "WorkspaceDetection",
        "workspace_normalization_patterns",
        fallback=r"^\d{14}[-_\s]*||\s*\(Workspace\).*||\.code-workspace$||\.md$"
    )
    workspace_title_suffixes_raw = config.get(
        "WorkspaceDetection",
        "workspace_title_suffixes",
        fallback="Visual Studio Code,VS Code,VSCodium,Cursor,Antigravity,Angigravity,Code - OSS"
    )
    workspace_title_suffixes = [s.strip() for s in workspace_title_suffixes_raw.split(",") if s.strip()]
    workspace_path_patterns = _split_delimited(workspace_path_patterns_raw)
    workspace_discovery_patterns = _split_delimited(workspace_discovery_patterns_raw)
    workspace_normalization_patterns = _split_delimited(workspace_normalization_patterns_raw)

    return {
        "conversations_dir": conversations_dir,
        "active_conversation": active_conversation,
        "auto_create_project": auto_create_project,
        "eol": eol,
        "ensure_root_note": ensure_root_note,
        "ensure_active_conversation": ensure_active_conversation,
        "root_note_template_path": root_note_template_path.strip(),
        "conversation_note_template_path": conversation_note_template_path.strip(),
        "moc_spacing_mode": moc_spacing_mode,
        "slug_word_count": slug_word_count,
        "split_description": split_description,
        "one_to_one": one_to_one,
        "ignore_prefixes": ignore_prefixes,
        "vault_base": vault_base,
        "workspace_path_patterns": workspace_path_patterns,
        "workspace_discovery_patterns": workspace_discovery_patterns,
        "workspace_slug_pattern": workspace_slug_pattern,
        "workspace_code_workspace_pattern": workspace_code_workspace_pattern,
        "workspace_normalization_patterns": workspace_normalization_patterns,
        "workspace_title_suffixes": workspace_title_suffixes,
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
    final_name = re.sub(r'-+', '-', final_name)
    final_name = final_name.strip('-')
    
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
