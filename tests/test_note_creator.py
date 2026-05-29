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

if __name__ == '__main__':
    unittest.main()
