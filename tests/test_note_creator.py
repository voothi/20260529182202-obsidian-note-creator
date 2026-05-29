import os
import sys
import unittest
import re
from datetime import datetime

# Add src folder to import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from note_creator import clean_task_name_formatting, process_single_message_block, process_zid_lines
from utils import sanitize_name, split_first_sentence

class TestNoteCreator(unittest.TestCase):
    
    def test_clean_task_name_formatting(self):
        """
        Verify that formatting markers, leading hashes, and list prefixes are removed
        while preserving inner hyphens and underscores.
        """
        # Leading list prefixes
        self.assertEqual(clean_task_name_formatting("- [ ] My Task"), "My Task")
        self.assertEqual(clean_task_name_formatting("- My Task"), "My Task")
        self.assertEqual(clean_task_name_formatting("* My Task"), "My Task")
        self.assertEqual(clean_task_name_formatting("+ My Task"), "My Task")
        self.assertEqual(clean_task_name_formatting("1. [x] My Task"), "My Task")
        
        # Leading headers
        self.assertEqual(clean_task_name_formatting("### My Header"), "My Header")
        self.assertEqual(clean_task_name_formatting("# Header"), "Header")
        
        # Surrounding formatting
        self.assertEqual(clean_task_name_formatting("`my-inline-code`"), "my-inline-code")
        self.assertEqual(clean_task_name_formatting("**bold-task**"), "bold-task")
        self.assertEqual(clean_task_name_formatting("__bold-task__"), "bold-task")
        self.assertEqual(clean_task_name_formatting("*italic-task*"), "italic-task")
        self.assertEqual(clean_task_name_formatting("`**nested**`"), "nested")
        
        # Inner hyphens/underscores (double hyphen parity)
        self.assertEqual(clean_task_name_formatting("and--open"), "and--open")
        self.assertEqual(clean_task_name_formatting("U:\\path\\to\\_template.md"), "U:\\path\\to\\_template.md")
        
        # Markdown links stripping
        self.assertEqual(clean_task_name_formatting("Updated [AGENTS.md](file:///path/to/AGENTS.md) here."), "Updated AGENTS.md here.")

    def test_sanitize_name(self):
        """
        Verify that sanitize_name creates correct slugs, matching Obsidian Templater.
        """
        self.assertEqual(sanitize_name("Ran command: openspec update", 4), "ran-command--openspec-update")
        self.assertEqual(sanitize_name("Check the original logic and--open", 4), "check-the-original-logic")
        self.assertEqual(sanitize_name("My cool task name", 2), "my-cool")

    def test_split_first_sentence(self):
        """
        Verify split_first_sentence function splits correctly on sentence boundary.
        """
        title, desc = split_first_sentence("First sentence here. Second sentence starts here.")
        self.assertEqual(title, "First sentence here.")
        self.assertEqual(desc, "Second sentence starts here.")
        
        title, desc = split_first_sentence("Only one sentence.")
        self.assertEqual(title, "Only one sentence.")
        self.assertEqual(desc, "")

    def test_process_single_message_block_workaround(self):
        """
        Verify process_single_message_block extracts the latest ZID and ignores
        preceding Antigravity service logs to build a clean note slug and task name.
        """
        text = """Edited 20260529122032-conversation.md
Viewed note_creator.py:60-95
Ran command: `python U:\\voothi\\20241116203211-zid\\zid.py --no-clipboard`

20260529193509

I have identified exactly why the ZID duplication occurred and have successfully resolved it!
"""
        config = {
            "conversations_dir": ".",
            "active_conversation": "test-conversation.md",
            "slug_word_count": 4,
            "split_description": True,
            "one_to_one": True
        }
        
        # Dry-run execution
        links, count = process_single_message_block(
            text, config, parent_title="test-conversation", dry_run=True
        )
        
        self.assertEqual(count, 1)
        self.assertEqual(
            links[0], 
            "- [[20260529193509-i-have-identified-exactly|I have identified exactly why the ZID duplication occurred and have successfully resolved it!]]\n"
        )

    def test_process_single_message_block_no_preceding_logs(self):
        """
        Verify processing works correctly when there are no prepended service logs.
        """
        text = """20260529192802 Check the original logic again `and--open`

- Some description details.
"""
        config = {
            "conversations_dir": ".",
            "active_conversation": "test-conversation.md",
            "slug_word_count": 4,
            "split_description": True,
            "one_to_one": True
        }
        
        links, count = process_single_message_block(
            text, config, parent_title="test-conversation", dry_run=True
        )
        
        self.assertEqual(count, 1)
        self.assertEqual(
            links[0],
            "- [[20260529192802-check-the-original-logic|Check the original logic again and--open]]\n"
        )

    def test_moc_duplication_prevention(self):
        """
        Verify that update_conversation_moc filters out links that are already
        present in the conversation file.
        """
        from note_creator import update_conversation_moc
        
        mock_conv_path = "mock_conversation.md"
        with open(mock_conv_path, "w", encoding="utf-8") as f:
            f.write("""# Active Conversation
## MOC.
- [[20260529193509-i-have-identified-exactly|I have identified exactly]]
## Notes
""")
            
        try:
            new_moc_lines = ["- [[20260529193509-i-have-identified-exactly|I have identified exactly]]\n"]
            update_conversation_moc(mock_conv_path, new_moc_lines, dry_run=False)
            
            with open(mock_conv_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            self.assertEqual(content.count("20260529193509-i-have-identified-exactly"), 1)
            
        finally:
            if os.path.exists(mock_conv_path):
                os.remove(mock_conv_path)

    def test_discover_active_conversation(self):
        """
        Verify that discover_active_conversation correctly detects the chronologically
        latest conversation file in a directory.
        """
        from utils import discover_active_conversation
        
        mock_dir = "mock_conversations_dir"
        os.makedirs(mock_dir, exist_ok=True)
        
        file1 = os.path.join(mock_dir, "20260529120000-conversation.md")
        file2 = os.path.join(mock_dir, "20260529130000-conversation.md")
        file3 = os.path.join(mock_dir, "20260529110000-conversation.md")
        
        for fpath in [file1, file2, file3]:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write("# Mock Conversation")
                
        try:
            latest = discover_active_conversation(mock_dir)
            self.assertEqual(os.path.abspath(latest), os.path.abspath(file2))
        finally:
            for fpath in [file1, file2, file3]:
                if os.path.exists(fpath):
                    os.remove(fpath)
            if os.path.exists(mock_dir):
                os.rmdir(mock_dir)

    def test_existing_zid_note_resolution(self):
        """
        Verify that processing a ZID line or block when a note with that ZID already
        exists in the conversations directory (even with a different slug) successfully
        reuses the existing file name and cleanest title.
        """
        mock_dir = "mock_conv_dir"
        os.makedirs(mock_dir, exist_ok=True)
        
        # Create an existing note with a custom slug and H1 title
        existing_note_path = os.path.join(mock_dir, "20260529180506-updated-agents-md-with-lua.md")
        with open(existing_note_path, "w", encoding="utf-8") as f:
            f.write("""---
aliases:
  - Updated AGENTS.md with Lua guidelines
---

# Updated AGENTS.md with Lua guidelines.

## Description
Some description here.
""")
            
        config = {
            "conversations_dir": mock_dir,
            "active_conversation": "test-conversation.md",
            "slug_word_count": 4,
            "split_description": True,
            "one_to_one": True
        }
        
        try:
            # Parse a block text representing a verbose status, but sharing the same ZID
            text = """20260529180506
I have successfully updated AGENTS.md to add a rule preventing agents from saving trial or temporary .lua scripts in the workspace.
"""
            links, count = process_single_message_block(
                text, config, parent_title="test-conversation", dry_run=True
            )
            
            # Should have count = 0 (since it was skipped as already existing)
            self.assertEqual(count, 0)
            # Should reuse the existing slug '20260529180506-updated-agents-md-with-lua' and its H1 title!
            self.assertEqual(
                links[0],
                "- [[20260529180506-updated-agents-md-with-lua|Updated AGENTS.md with Lua guidelines.]]\n"
            )
            
        finally:
            if os.path.exists(existing_note_path):
                os.remove(existing_note_path)
            if os.path.exists(mock_dir):
                os.rmdir(mock_dir)

if __name__ == '__main__':
    unittest.main()
