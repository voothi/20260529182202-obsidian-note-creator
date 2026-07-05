import os
import sys
import unittest
import re
from datetime import datetime

# Add src folder to import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from note_creator import clean_task_name_formatting, process_single_message_block, process_zid_lines, ensure_root_note, initialize_active_conversation, ensure_root_moc_contains_conversation, resolve_conversation_up_parents_from_root, normalize_workspace_name
from utils import sanitize_name, split_first_sentence
from utils import get_config

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
        
        # Wikilinks and image embeds stripping
        self.assertEqual(clean_task_name_formatting("Task with [[Some Note]] here."), "Task with Some Note here.")
        self.assertEqual(clean_task_name_formatting("Task with [[Some Note|custom display]] here."), "Task with custom display here.")
        self.assertEqual(clean_task_name_formatting("Task with ![[pasted-image.png]] here."), "Task with here.")
        self.assertEqual(clean_task_name_formatting("Task with ![alt text](http://example.com/image.png) here."), "Task with here.")

    def test_sanitize_name(self):
        """
        Verify that sanitize_name creates correct slugs, matching Obsidian Templater.
        """
        self.assertEqual(sanitize_name("Ran command: openspec update", 4), "ran-command-openspec-update")
        self.assertEqual(sanitize_name("Check the original logic and--open", 4), "check-the-original-logic")
        self.assertEqual(sanitize_name("My cool task name", 2), "my-cool")
        
        # Test ZID exclusion (second ZID)
        self.assertEqual(sanitize_name("/opsx-archive 20260701133515-staged-progressive-loading", 4), "opsx-archive-staged-progressive")
        self.assertEqual(sanitize_name("zid-20260623000219", 4), "zid")
        
        # Test correct word counting with hyphens and underscores
        self.assertEqual(sanitize_name("def test_config_case_sensitive_diffquiz_env", 4), "def-test-config-case")


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

    def test_update_conversation_moc_keeps_blank_line_boundaries(self):
        """
        Verify one empty line exists after '## MOC.' and before '## Notes' after insertion.
        """
        from note_creator import update_conversation_moc

        mock_conv_path = "mock_conversation_spacing.md"
        with open(mock_conv_path, "w", encoding="utf-8") as f:
            f.write("# Active Conversation\n## MOC.\n## Notes\n")

        try:
            new_moc_lines = ["- [[20260601104007-write-readme|Write README]]\n"]
            changed = update_conversation_moc(mock_conv_path, new_moc_lines, dry_run=False)
            self.assertTrue(changed)

            with open(mock_conv_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            moc_idx = next(i for i, l in enumerate(lines) if l.strip() == "## MOC.")
            notes_idx = next(i for i, l in enumerate(lines) if l.strip() == "## Notes")
            self.assertEqual(lines[moc_idx + 1].strip(), "")
            self.assertEqual(lines[notes_idx - 1].strip(), "")
            self.assertEqual(lines[moc_idx + 2].strip(), "- [[20260601104007-write-readme|Write README]]")
        finally:
            if os.path.exists(mock_conv_path):
                os.remove(mock_conv_path)

    def test_update_conversation_moc_normalizes_spacing_when_link_exists(self):
        """
        Verify spacing is normalized even when all incoming links are duplicates.
        """
        from note_creator import update_conversation_moc

        mock_conv_path = "mock_conversation_spacing_existing.md"
        with open(mock_conv_path, "w", encoding="utf-8") as f:
            f.write(
                "# Active Conversation\n"
                "## MOC.\n"
                "- [[20260601104007-write-readme|Write README]]\n"
                "## Notes\n"
            )

        try:
            new_moc_lines = ["- [[20260601104007-write-readme|Write README]]\n"]
            changed = update_conversation_moc(mock_conv_path, new_moc_lines, dry_run=False)
            self.assertTrue(changed)

            with open(mock_conv_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            moc_idx = next(i for i, l in enumerate(lines) if l.strip() == "## MOC.")
            notes_idx = next(i for i, l in enumerate(lines) if l.strip() == "## Notes")
            self.assertEqual(lines[moc_idx + 1].strip(), "")
            self.assertEqual(lines[notes_idx - 1].strip(), "")
            self.assertEqual("".join(lines).count("[[20260601104007-write-readme|Write README]]"), 1)
        finally:
            if os.path.exists(mock_conv_path):
                os.remove(mock_conv_path)

    def test_update_conversation_moc_normalizes_crlf_input_lines(self):
        """
        Verify CRLF input lines do not produce doubled blank lines on Windows.
        """
        from note_creator import update_conversation_moc

        mock_conv_path = "mock_conversation_crlf.md"
        with open(mock_conv_path, "w", encoding="utf-8", newline="\n") as f:
            f.write("# Active Conversation\n## MOC.\n## Notes\n")

        try:
            new_moc_lines = ["- [[20260601112154-check-auto-create|Check auto_create_project]]\r\n"]
            changed = update_conversation_moc(mock_conv_path, new_moc_lines, dry_run=False)
            self.assertTrue(changed)

            with open(mock_conv_path, "rb") as f:
                raw = f.read()
            self.assertNotIn(b"\r\r\n", raw)

            with open(mock_conv_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            moc_idx = next(i for i, l in enumerate(lines) if l.strip() == "## MOC.")
            notes_idx = next(i for i, l in enumerate(lines) if l.strip() == "## Notes")
            self.assertEqual(lines[moc_idx + 1].strip(), "")
            self.assertEqual(lines[notes_idx - 1].strip(), "")
            self.assertEqual(lines[moc_idx + 2].strip(), "- [[20260601112154-check-auto-create|Check auto_create_project]]")
        finally:
            if os.path.exists(mock_conv_path):
                os.remove(mock_conv_path)

    def test_update_conversation_moc_ignores_inline_moc_text_in_link_titles(self):
        """
        Verify MOC header detection uses exact section headers, not '## MOC.' text inside links.
        """
        from note_creator import update_conversation_moc

        mock_conv_path = "mock_conversation_inline_moc_text.md"
        with open(mock_conv_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(
                "# Active Conversation\n"
                "## MOC.\n"
                "- [[20260601105049-lets-see-how-the|Contains ## MOC. in title]]\n"
                "- [[20260601111135-check-that-this-works|Second item]]\n"
                "## Notes\n"
            )

        try:
            changed = update_conversation_moc(
                mock_conv_path,
                ["- [[20260601114003-double-check-why-in-the|Third item]]\n"],
                dry_run=False
            )
            self.assertTrue(changed)

            with open(mock_conv_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            moc_idx = next(i for i, l in enumerate(lines) if l.strip() == "## MOC.")
            notes_idx = next(i for i, l in enumerate(lines) if l.strip() == "## Notes")
            self.assertEqual(lines[moc_idx + 1].strip(), "")
            self.assertEqual(lines[notes_idx - 1].strip(), "")
            self.assertEqual("".join(lines).count("[[20260601114003-double-check-why-in-the|Third item]]"), 1)
            self.assertEqual(
                lines[moc_idx + 2].strip(),
                "- [[20260601105049-lets-see-how-the|Contains ## MOC. in title]]"
            )
        finally:
            if os.path.exists(mock_conv_path):
                os.remove(mock_conv_path)

    def test_update_conversation_moc_preserve_mode_keeps_existing_spacing(self):
        """
        Verify preserve mode appends links without collapsing existing blank lines.
        """
        from note_creator import update_conversation_moc

        mock_conv_path = "mock_conversation_preserve_mode.md"
        with open(mock_conv_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(
                "# Active Conversation\n"
                "## MOC.\n"
                "\n"
                "- [[20260601111135-check-that-this-works|First]]\n"
                "\n"
                "\n"
                "## Notes\n"
            )

        try:
            changed = update_conversation_moc(
                mock_conv_path,
                ["- [[20260601114706-relaxed-moc-spacing|Second]]\n"],
                dry_run=False,
                moc_spacing_mode="preserve"
            )
            self.assertTrue(changed)

            with open(mock_conv_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("\n\n\n## Notes\n", content)
            self.assertIn("- [[20260601114706-relaxed-moc-spacing|Second]]", content)
        finally:
            if os.path.exists(mock_conv_path):
                os.remove(mock_conv_path)

    def test_update_conversation_moc_smart_mode_centers_first_entry(self):
        """
        Verify smart mode centers first insertion in an empty/new MOC section.
        """
        from note_creator import update_conversation_moc

        mock_conv_path = "mock_conversation_smart_mode_first_insert.md"
        with open(mock_conv_path, "w", encoding="utf-8", newline="\n") as f:
            f.write("# Active Conversation\n## MOC.\n\n\n\n## Notes\n")

        try:
            changed = update_conversation_moc(
                mock_conv_path,
                ["- [[20260601114706-relaxed-moc-spacing|First]]\n"],
                dry_run=False,
                moc_spacing_mode="smart"
            )
            self.assertTrue(changed)

            with open(mock_conv_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            moc_idx = next(i for i, l in enumerate(lines) if l.strip() == "## MOC.")
            notes_idx = next(i for i, l in enumerate(lines) if l.strip() == "## Notes")
            self.assertEqual(lines[moc_idx + 1].strip(), "")
            self.assertEqual(lines[moc_idx + 2].strip(), "- [[20260601114706-relaxed-moc-spacing|First]]")
            self.assertEqual(lines[notes_idx - 1].strip(), "")
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
        file4 = os.path.join(mock_dir, "20260529140000-some-task-ending-with-conversation.md")
        
        for fpath in [file1, file2, file3, file4]:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write("# Mock Conversation")
                
        try:
            latest = discover_active_conversation(mock_dir)
            self.assertEqual(os.path.abspath(latest), os.path.abspath(file2))
        finally:
            for fpath in [file1, file2, file3, file4]:
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

    def test_description_preserves_uncleaned_link_when_title_differs(self):
        """
        Verify that if the title differs from the alias/cleaned title (due to link stripping),
        the original uncleaned version containing the link is written in the Description.
        """
        mock_dir = "mock_test_desc_dir"
        os.makedirs(mock_dir, exist_ok=True)
        
        config = {
            "conversations_dir": mock_dir,
            "active_conversation": "test-conversation.md",
            "slug_word_count": 10,
            "split_description": True,
            "one_to_one": True,
            "ignore_prefixes": []
        }
        
        try:
            # Case 1: Smart Mode (single message block) with a link
            text = """20260531165012 Check command ![[20260531165230-pasted-image.png]]"""
            links, count = process_single_message_block(
                text, config, parent_title="test-conversation", dry_run=False
            )
            
            # The file should have been created with slug-ified filename
            filename = "20260531165012-check-command.md"
            filepath = os.path.join(mock_dir, filename)
            self.assertTrue(os.path.exists(filepath))
            
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                
            # Verify alias and title are cleaned (no link)
            self.assertIn("aliases: \n  - Check command\n", content)
            self.assertIn("# Check command\n", content)
            # Verify description has the original text with link
            self.assertIn("## Description\n\nCheck command ![[20260531165230-pasted-image.png]]", content)
            
            # Case 2: Batch list lines with a link
            os.remove(filepath)
            lines = ["- 20260531165012 Check command ![[20260531165230-pasted-image.png]]\n"]
            updated_lines, notes_created = process_zid_lines(
                lines, config, parent_title="test-conversation", dry_run=False
            )
            
            self.assertTrue(os.path.exists(filepath))
            with open(filepath, "r", encoding="utf-8") as f:
                content_batch = f.read()
                
            self.assertIn("aliases: \n  - Check command\n", content_batch)
            self.assertIn("# Check command\n", content_batch)
            self.assertIn("## Description\n\nCheck command ![[20260531165230-pasted-image.png]]", content_batch)
            
        finally:
            # Clean up
            if os.path.exists(mock_dir):
                for entry in os.scandir(mock_dir):
                    if entry.is_file():
                        os.remove(entry.path)
                os.rmdir(mock_dir)

    def test_multi_line_no_punctuation_description_retention(self):
        """
        Verify that a multi-line message block without standard sentence punctuation
        in the first line correctly treats the first line as the task name, and
        correctly saves the subsequent lines in the description (rather than discarding them).
        """
        mock_dir = "mock_test_multiline_dir"
        os.makedirs(mock_dir, exist_ok=True)
        
        config = {
            "conversations_dir": mock_dir,
            "active_conversation": "test-conversation.md",
            "slug_word_count": 10,
            "split_description": True,
            "one_to_one": False,
            "ignore_prefixes": []
        }
        
        text = """20260531165721 Title line with no punctuation
Second line of content that is very important
Third line of content that is also important"""
        
        try:
            links, count = process_single_message_block(
                text, config, parent_title="test-conversation", dry_run=False
            )
            
            filename = "20260531165721-title-line-with-no-punctuation.md"
            filepath = os.path.join(mock_dir, filename)
            self.assertTrue(os.path.exists(filepath))
            
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                
            self.assertIn("aliases: \n  - Title line with no punctuation\n", content)
            self.assertIn("# Title line with no punctuation\n", content)
            self.assertIn("## Description\n\nSecond line of content that is very important\nThird line of content that is also important", content)
            
        finally:
            if os.path.exists(mock_dir):
                for entry in os.scandir(mock_dir):
                    if entry.is_file():
                        os.remove(entry.path)
                os.rmdir(mock_dir)

    def test_process_single_message_block_backticked_zid_header(self):
        """
        Verify a backticked ZID header is recognized as the source ZID instead of generating a new one.
        """
        config = {
            "conversations_dir": ".",
            "active_conversation": "test-conversation.md",
            "slug_word_count": 4,
            "split_description": True,
            "one_to_one": True,
            "ignore_prefixes": []
        }

        text = """`20260531210151`

Reviewed `c68c990d91197abe7ce73f62683db0adb7a1dc2e`.
"""
        links, count = process_single_message_block(
            text, config, parent_title="test-conversation", dry_run=True
        )

        self.assertEqual(count, 1)
        self.assertTrue(links[0].startswith("- [[20260531210151-"))

    def test_process_single_message_block_quoted_zid_header(self):
        """
        Verify quoted ZID headers (single/double quotes) are recognized.
        """
        config = {
            "conversations_dir": ".",
            "active_conversation": "test-conversation.md",
            "slug_word_count": 4,
            "split_description": True,
            "one_to_one": True,
            "ignore_prefixes": []
        }

        for quote in ["'", '"']:
            text = f"""{quote}20260531210151{quote}

Reviewed commit id.
"""
            links, count = process_single_message_block(
                text, config, parent_title="test-conversation", dry_run=True
            )
            self.assertEqual(count, 1)
            self.assertTrue(links[0].startswith("- [[20260531210151-"))

    def test_process_single_message_block_labeled_zid_header(self):
        """
        Verify a "ZID: 202..." header uses the numeric ZID and does not put
        the label into the generated file name.
        """
        config = {
            "conversations_dir": ".",
            "active_conversation": "test-conversation.md",
            "slug_word_count": 4,
            "split_description": True,
            "one_to_one": True,
            "ignore_prefixes": []
        }

        text = """ZID: 20260607224326

**Findings**
Medium: [scripts/kardenwort/main.lua](u:/voothi/project/main.lua:6710) noisy logging.
"""
        links, count = process_single_message_block(
            text, config, parent_title="test-conversation", dry_run=True
        )

        self.assertEqual(count, 1)
        self.assertEqual(
            links[0],
            "- [[20260607224326-findings|Findings]]\n"
        )

    def test_ensure_root_note_idempotent_with_template(self):
        """
        Verify root.md is created once from template and then left unchanged on repeat calls.
        """
        mock_dir = "mock_root_dir"
        os.makedirs(mock_dir, exist_ok=True)
        template_path = os.path.join(mock_dir, "root-template.md")
        with open(template_path, "w", encoding="utf-8") as f:
            f.write("# Root Template\n\nSeed content.\n")

        try:
            root_path, created = ensure_root_note(mock_dir, template_path=template_path, dry_run=False)
            self.assertTrue(created)
            self.assertTrue(os.path.exists(root_path))
            with open(root_path, "r", encoding="utf-8") as f:
                first_content = f.read()
            self.assertEqual(first_content, "# Root Template\n\nSeed content.\n")

            with open(root_path, "w", encoding="utf-8") as f:
                f.write("manual content")

            root_path_again, created_again = ensure_root_note(mock_dir, template_path=template_path, dry_run=False)
            self.assertFalse(created_again)
            with open(root_path_again, "r", encoding="utf-8") as f:
                second_content = f.read()
            self.assertEqual(second_content, "manual content")
        finally:
            if os.path.exists(mock_dir):
                for entry in os.scandir(mock_dir):
                    if entry.is_file():
                        os.remove(entry.path)
                os.rmdir(mock_dir)

    def test_ensure_root_note_replaces_created_date_placeholder(self):
        """
        Verify {CREATED_DATE} placeholder is rendered in root template.
        """
        mock_dir = "mock_root_date_dir"
        os.makedirs(mock_dir, exist_ok=True)
        template_path = os.path.join(mock_dir, "root-template.md")
        with open(template_path, "w", encoding="utf-8") as f:
            f.write("created: {CREATED_DATE}\n")
        try:
            root_path, created = ensure_root_note(mock_dir, template_path=template_path, dry_run=False)
            self.assertTrue(created)
            with open(root_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertNotIn("{CREATED_DATE}", content)
            self.assertRegex(content, r"created: \d{4}-\d{2}-\d{2}")
        finally:
            if os.path.exists(mock_dir):
                for entry in os.scandir(mock_dir):
                    if entry.is_file():
                        os.remove(entry.path)
                os.rmdir(mock_dir)

    def test_get_config_supports_utf8_bom(self):
        """
        Verify config files with UTF-8 BOM are parsed correctly.
        """
        cfg_path = "mock_bom_config.ini"
        try:
            with open(cfg_path, "w", encoding="utf-8-sig") as f:
                f.write("[Obsidian]\nconversations_dir = U:\\voothi.vault\\kardenwort-mpv\\conversations\n")
            cfg = get_config(cfg_path)
            self.assertIn("conversations_dir", cfg)
            self.assertEqual(cfg["conversations_dir"], r"U:\voothi.vault\kardenwort-mpv\conversations")
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)

    def test_get_config_parses_ensure_active_conversation(self):
        """
        Verify the ensure_active_conversation flag is parsed from config.
        """
        cfg_path = "mock_ensure_active_config.ini"
        try:
            with open(cfg_path, "w", encoding="utf-8") as f:
                f.write("[Obsidian]\nensure_active_conversation = false\n")
            cfg = get_config(cfg_path)
            self.assertIn("ensure_active_conversation", cfg)
            self.assertFalse(cfg["ensure_active_conversation"])
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)

    def test_get_config_resolves_relative_root_template_path(self):
        """
        Verify relative root_note_template_path is resolved against config directory.
        """
        cfg_dir = "mock_cfg_dir"
        cfg_path = os.path.join(cfg_dir, "config.ini")
        os.makedirs(cfg_dir, exist_ok=True)
        try:
            with open(cfg_path, "w", encoding="utf-8") as f:
                f.write("[Obsidian]\nroot_note_template_path = templates/root.md\n")
            cfg = get_config(cfg_path)
            self.assertTrue(cfg["root_note_template_path"].endswith(os.path.join("templates", "root.md")))
            self.assertTrue(os.path.isabs(cfg["root_note_template_path"]))
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)
            if os.path.exists(cfg_dir):
                os.rmdir(cfg_dir)

    def test_get_config_parses_eol_mode(self):
        """
        Verify the EOL mode is parsed from config.
        """
        cfg_path = "mock_eol_config.ini"
        try:
            with open(cfg_path, "w", encoding="utf-8") as f:
                f.write("[Obsidian]\neol = crlf\n")
            cfg = get_config(cfg_path)
            self.assertIn("eol", cfg)
            self.assertEqual(cfg["eol"], "crlf")
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)

    def test_get_config_parses_moc_spacing_mode(self):
        """
        Verify MOC spacing mode is parsed from config.
        """
        cfg_path = "mock_moc_spacing_config.ini"
        try:
            with open(cfg_path, "w", encoding="utf-8") as f:
                f.write("[Obsidian]\nmoc_spacing_mode = preserve\n")
            cfg = get_config(cfg_path)
            self.assertIn("moc_spacing_mode", cfg)
            self.assertEqual(cfg["moc_spacing_mode"], "preserve")
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)

    def test_initialize_active_conversation_uses_template_placeholders(self):
        """
        Verify conversation template placeholders {ZID}/{CREATED_DATE} are rendered.
        """
        mock_dir = "mock_conv_template_dir"
        os.makedirs(mock_dir, exist_ok=True)
        template_path = os.path.join(mock_dir, "conversation-template.md")
        with open(template_path, "w", encoding="utf-8") as f:
            f.write("file: {ZID}-conversation.md\ncreated: {CREATED_DATE}\n")

        try:
            conv_path = initialize_active_conversation(mock_dir, template_path=template_path)
            self.assertTrue(os.path.exists(conv_path))
            with open(conv_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertNotIn("{ZID}", content)
            self.assertNotIn("{CREATED_DATE}", content)
            self.assertRegex(content, r"file: \d{14}-conversation\.md")
            self.assertRegex(content, r"created: \d{4}-\d{2}-\d{2}")
        finally:
            if os.path.exists(mock_dir):
                for entry in os.scandir(mock_dir):
                    if entry.is_file():
                        os.remove(entry.path)
                os.rmdir(mock_dir)

    def test_ensure_root_moc_contains_conversation_idempotent(self):
        """
        Verify root MOC receives one conversation link and does not duplicate it.
        """
        mock_dir = "mock_root_moc_dir"
        os.makedirs(mock_dir, exist_ok=True)
        root_path = os.path.join(mock_dir, "root.md")
        conv_path = os.path.join(mock_dir, "20260531222451-conversation.md")
        try:
            with open(root_path, "w", encoding="utf-8") as f:
                f.write("# root\n\n## MOC.\n\n## Notes\n")
            with open(conv_path, "w", encoding="utf-8") as f:
                f.write("# Conversation\n")

            changed_first = ensure_root_moc_contains_conversation(root_path, conv_path, dry_run=False)
            changed_second = ensure_root_moc_contains_conversation(root_path, conv_path, dry_run=False)
            self.assertTrue(changed_first)
            self.assertTrue(changed_second)

            with open(root_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertEqual(content.count("[[20260531222451-conversation|Conversation]]"), 1)
        finally:
            if os.path.exists(mock_dir):
                for entry in os.scandir(mock_dir):
                    if entry.is_file():
                        os.remove(entry.path)
                os.rmdir(mock_dir)

    def test_ensure_root_moc_detects_non_list_wikilink_in_moc_section(self):
        """
        Verify any wikilink line inside MOC section counts as existing.
        """
        mock_dir = "mock_root_moc_nonlist_dir"
        os.makedirs(mock_dir, exist_ok=True)
        root_path = os.path.join(mock_dir, "root.md")
        conv_path = os.path.join(mock_dir, "20260531222451-conversation.md")
        try:
            with open(root_path, "w", encoding="utf-8") as f:
                f.write("# root\n\n## MOC.\n\nReference [[20260531222451-conversation|Conversation]]\n\n## Notes\n")
            with open(conv_path, "w", encoding="utf-8") as f:
                f.write("# Conversation\n")

            changed = ensure_root_moc_contains_conversation(root_path, conv_path, dry_run=False)
            self.assertTrue(changed)
            with open(root_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertEqual(content.count("[[20260531222451-conversation|Conversation]]"), 1)
        finally:
            if os.path.exists(mock_dir):
                for entry in os.scandir(mock_dir):
                    if entry.is_file():
                        os.remove(entry.path)
                os.rmdir(mock_dir)

    def test_ensure_root_moc_detects_nested_list_wikilink(self):
        """
        Verify nested/indented list-item wikilink counts as existing entry.
        """
        mock_dir = "mock_root_moc_nested_dir"
        os.makedirs(mock_dir, exist_ok=True)
        root_path = os.path.join(mock_dir, "root.md")
        conv_path = os.path.join(mock_dir, "20260531222451-conversation.md")
        try:
            with open(root_path, "w", encoding="utf-8") as f:
                f.write("# root\n\n## MOC.\n\n    - [[20260531222451-conversation|Conversation]]\n\n## Notes\n")
            with open(conv_path, "w", encoding="utf-8") as f:
                f.write("# Conversation\n")

            changed = ensure_root_moc_contains_conversation(root_path, conv_path, dry_run=False)
            self.assertTrue(changed)
            with open(root_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertEqual(content.count("[[20260531222451-conversation|Conversation]]"), 1)
        finally:
            if os.path.exists(mock_dir):
                for entry in os.scandir(mock_dir):
                    if entry.is_file():
                        os.remove(entry.path)
                os.rmdir(mock_dir)

    def test_ensure_root_moc_ignores_wikilink_outside_moc_section(self):
        """
        Verify wikilink outside MOC section does not block insertion into MOC.
        """
        mock_dir = "mock_root_moc_outside_dir"
        os.makedirs(mock_dir, exist_ok=True)
        root_path = os.path.join(mock_dir, "root.md")
        conv_path = os.path.join(mock_dir, "20260531222451-conversation.md")
        try:
            with open(root_path, "w", encoding="utf-8") as f:
                f.write("# root\n\n## MOC.\n\n## Notes\nReference [[20260531222451-conversation|Conversation]]\n")
            with open(conv_path, "w", encoding="utf-8") as f:
                f.write("# Conversation\n")

            changed = ensure_root_moc_contains_conversation(root_path, conv_path, dry_run=False)
            self.assertTrue(changed)
            with open(root_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertEqual(content.count("[[20260531222451-conversation|Conversation]]"), 2)
        finally:
            if os.path.exists(mock_dir):
                for entry in os.scandir(mock_dir):
                    if entry.is_file():
                        os.remove(entry.path)
                os.rmdir(mock_dir)

    def test_resolve_conversation_up_parents_uses_root_parent_context(self):
        """
        Verify parent resolution for a new conversation reuses root's latest conversation parent branch.
        """
        mock_dir = "mock_root_parent_ctx_dir"
        os.makedirs(mock_dir, exist_ok=True)
        root_path = os.path.join(mock_dir, "root.md")
        try:
            with open(root_path, "w", encoding="utf-8") as f:
                f.write(
                    "## MOC.\n"
                    "- [[20260529150158-archive|Archive.]]\n"
                    "    - [[20260529011639-conversation|Conversation]]\n"
                    "- [[20260529150201-active|Active.]]\n"
                    "    - [[20260529122032-conversation|Conversation]]\n"
                    "## Notes\n"
                )

            parents = resolve_conversation_up_parents_from_root(root_path, "20260531235959-conversation")
            self.assertEqual(parents, ["20260529150201-active"])
        finally:
            if os.path.exists(mock_dir):
                for entry in os.scandir(mock_dir):
                    if entry.is_file():
                        os.remove(entry.path)
                os.rmdir(mock_dir)

    def test_initialize_active_conversation_uses_root_parent_for_up_field(self):
        """
        Verify conversation creation injects dynamic up links from root parent context.
        """
        mock_dir = "mock_conv_root_up_dir"
        os.makedirs(mock_dir, exist_ok=True)
        root_path = os.path.join(mock_dir, "root.md")
        template_path = os.path.join(mock_dir, "conversation-template.md")
        try:
            with open(root_path, "w", encoding="utf-8") as f:
                f.write(
                    "## MOC.\n"
                    "- [[20260529150158-archive|Archive.]]\n"
                    "    - [[20260529011639-conversation|Conversation]]\n"
                    "- [[20260529150201-active|Active.]]\n"
                    "    - [[20260529122032-conversation|Conversation]]\n"
                    "## Notes\n"
                )
            with open(template_path, "w", encoding="utf-8") as f:
                f.write("---\nup:\n{UP_LINES}\ncreated: {CREATED_DATE}\n---\n")

            conv_path = initialize_active_conversation(mock_dir, template_path=template_path, root_path=root_path)
            with open(conv_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn('  - "[[20260529150201-active]]"', content)
            self.assertNotIn("{UP_LINES}", content)
        finally:
            if os.path.exists(mock_dir):
                for entry in os.scandir(mock_dir):
                    if entry.is_file():
                        os.remove(entry.path)
                os.rmdir(mock_dir)

    def test_ensure_root_moc_inserts_under_preferred_parent(self):
        """
        Verify root MOC insertion can place new conversation under a preferred parent branch.
        """
        mock_dir = "mock_root_preferred_insert_dir"
        os.makedirs(mock_dir, exist_ok=True)
        root_path = os.path.join(mock_dir, "root.md")
        conv_path = os.path.join(mock_dir, "20260531235959-conversation.md")
        try:
            with open(root_path, "w", encoding="utf-8") as f:
                f.write(
                    "# root\n\n"
                    "## MOC.\n"
                    "- [[20260529150201-active|Active.]]\n"
                    "    - [[20260529122032-conversation|Conversation]]\n"
                    "## Notes\n"
                )
            with open(conv_path, "w", encoding="utf-8") as f:
                f.write("# Conversation\n")

            changed = ensure_root_moc_contains_conversation(
                root_path,
                conv_path,
                dry_run=False,
                preferred_parent="20260529150201-active"
            )
            self.assertTrue(changed)

            with open(root_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("    - [[20260531235959-conversation|Conversation]]", content)
        finally:
            if os.path.exists(mock_dir):
                for entry in os.scandir(mock_dir):
                    if entry.is_file():
                        os.remove(entry.path)
                os.rmdir(mock_dir)

    def test_ensure_root_moc_keeps_blank_line_boundaries(self):
        """
        Verify one empty line exists after '## MOC.' and before '## Notes' after insertion.
        """
        mock_dir = "mock_root_spacing_dir"
        os.makedirs(mock_dir, exist_ok=True)
        root_path = os.path.join(mock_dir, "root.md")
        conv_path = os.path.join(mock_dir, "20260530001202-conversation.md")
        try:
            with open(root_path, "w", encoding="utf-8") as f:
                f.write("# root\n\n## MOC.\n## Notes\n")
            with open(conv_path, "w", encoding="utf-8") as f:
                f.write("# Conversation\n")

            changed = ensure_root_moc_contains_conversation(root_path, conv_path, dry_run=False)
            self.assertTrue(changed)

            with open(root_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            moc_idx = next(i for i, l in enumerate(lines) if l.strip() == "## MOC.")
            notes_idx = next(i for i, l in enumerate(lines) if l.strip() == "## Notes")
            self.assertEqual(lines[moc_idx + 1].strip(), "")
            self.assertEqual(lines[notes_idx - 1].strip(), "")
        finally:
            if os.path.exists(mock_dir):
                for entry in os.scandir(mock_dir):
                    if entry.is_file():
                        os.remove(entry.path)
                os.rmdir(mock_dir)

    def test_ensure_root_moc_normalizes_spacing_when_link_already_exists(self):
        """
        Verify spacing is normalized even if the conversation link already exists.
        """
        mock_dir = "mock_root_spacing_existing_dir"
        os.makedirs(mock_dir, exist_ok=True)
        root_path = os.path.join(mock_dir, "root.md")
        conv_path = os.path.join(mock_dir, "20260530001202-conversation.md")
        try:
            with open(root_path, "w", encoding="utf-8") as f:
                f.write("# root\n\n## MOC.\n- [[20260530001202-conversation|Conversation]]\n## Notes\n")
            with open(conv_path, "w", encoding="utf-8") as f:
                f.write("# Conversation\n")

            changed = ensure_root_moc_contains_conversation(root_path, conv_path, dry_run=False)
            self.assertTrue(changed)

            with open(root_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            moc_idx = next(i for i, l in enumerate(lines) if l.strip() == "## MOC.")
            notes_idx = next(i for i, l in enumerate(lines) if l.strip() == "## Notes")
            self.assertEqual(lines[moc_idx + 1].strip(), "")
            self.assertEqual(lines[notes_idx - 1].strip(), "")
            self.assertNotEqual(lines[moc_idx + 2].strip(), "")
            self.assertEqual("".join(lines).count("[[20260530001202-conversation|Conversation]]"), 1)
        finally:
            if os.path.exists(mock_dir):
                for entry in os.scandir(mock_dir):
                    if entry.is_file():
                        os.remove(entry.path)
                os.rmdir(mock_dir)

    def test_normalize_workspace_name_robust(self):
        """
        Verify that normalize_workspace_name strips suffixes anywhere in the title,
        supporting both VS Code and Antigravity IDE title formats.
        """
        suffixes = ["Visual Studio Code", "VS Code", "VSCodium", "Cursor", "Antigravity", "Angigravity", "Code - OSS"]
        
        # Test 1: Antigravity IDE format (suffix in middle)
        title1 = "20260529182202-obsidian-note-creator - Antigravity IDE - config.ini"
        self.assertEqual(
            normalize_workspace_name(title1, title_suffixes=suffixes),
            "obsidian-note-creator"
        )
        
        # Test 2: VS Code format (suffix at end)
        title2 = "20260531191028-conversation.md - 20240411110510-autohotkey - Visual Studio Code"
        self.assertEqual(
            normalize_workspace_name(title2, title_suffixes=suffixes),
            "conversation.md - 20240411110510-autohotkey"
        )

    def test_normalize_workspace_name_without_workspace_tag(self):
        """
        Verify that normalize_workspace_name strips suffix from Antigravity format
        even without a (Workspace) indicator in the title.
        """
        suffixes = ["Visual Studio Code", "VS Code", "VSCodium", "Cursor", "Antigravity", "Angigravity", "Code - OSS"]
        title = "20260529182202-obsidian-note-creator - Antigravity IDE - config.ini"
        self.assertEqual(
            normalize_workspace_name(title, title_suffixes=suffixes),
            "obsidian-note-creator"
        )

    def test_workspace_parsing_candidates(self):
        """
        Verify that splitting the title by ' - ' and filtering suffixes/files
        correctly extracts clean workspace candidates.
        """
        suffixes = ["Visual Studio Code", "VS Code", "VSCodium", "Cursor", "Antigravity", "Angigravity", "Code - OSS"]
        
        # Test Case 1: Antigravity IDE format
        title1 = "20260529182202-obsidian-note-creator (Workspace) - Antigravity IDE - config.ini"
        parts1 = [p.strip() for p in title1.split(' - ') if p.strip()]
        clean_parts1 = []
        for p in parts1:
            if any(s.lower() in p.lower() for s in suffixes):
                continue
            if re.search(r'\.[a-zA-Z0-9]+$', p):
                continue
            clean_parts1.append(p)
        self.assertEqual(clean_parts1, ["20260529182202-obsidian-note-creator (Workspace)"])

        # Test Case 2: VS Code format
        title2 = "20260531191028-conversation.md - 20240411110510-autohotkey (Workspace) - Visual Studio Code"
        parts2 = [p.strip() for p in title2.split(' - ') if p.strip()]
        clean_parts2 = []
        for p in parts2:
            if any(s.lower() in p.lower() for s in suffixes):
                continue
            if re.search(r'\.[a-zA-Z0-9]+$', p):
                continue
            clean_parts2.append(p)
        self.assertEqual(clean_parts2, ["20240411110510-autohotkey (Workspace)"])

        # Test Case 3: Obsidian format
        title3 = "20260608122139-conversation - voothi.vault - Obsidian v1.8.4"
        parts3 = [p.strip() for p in title3.split(' - ') if p.strip()]
        is_obsidian = "obsidian" in title3.lower()
        suffixes_with_obs = suffixes + ["Obsidian"]
        clean_parts3 = []
        for idx, p in enumerate(parts3):
            if is_obsidian and idx == 0:
                continue
            if p.lower() == "voothi.vault":
                continue
            if any(s.lower() in p.lower() for s in suffixes_with_obs):
                continue
            if re.search(r'\.[a-zA-Z0-9]+$', p):
                continue
    def test_git_working_tree_and_two_pass_resolution(self):
        # Simulate note_creator's main workspace resolution logic
        vault_base = "U:\\voothi.vault"
        workspace_normalization_patterns = [r'^\d{14}[-_\s]*', r'\s*\(Workspace\).*', r'\.code-workspace$', r'\.md$']
        workspace_title_suffixes = ["Visual Studio Code", "VS Code", "VSCodium", "Cursor", "Antigravity", "Angigravity", "Code - OSS"]
        
        # Test 1: Active workspace has obsidian in name, but is NOT Obsidian app window
        title = "note_creator.py (Working Tree) (note_creator.py) - 20260529182202-obsidian-note-creator (Workspace) - Antigravity IDE"
        
        parts = [p.strip() for p in title.split(' - ') if p.strip()]
        is_obsidian = bool(re.search(r'\s+-\s+Obsidian\b', title, re.IGNORECASE))
        self.assertFalse(is_obsidian)
        
        workspace_tokens = re.findall(r"\d{14}-[\w-]+", title)
        
        clean_parts = []
        for idx, p in enumerate(parts):
            is_suffix = False
            for suffix in workspace_title_suffixes:
                if suffix.lower() in p.lower():
                    is_suffix = True
                    break
            if is_suffix:
                continue
            if re.search(r'\.[a-zA-Z0-9]+$', p):
                continue
            clean_parts.append(p)

        candidate_tokens = list(reversed(workspace_tokens)) if workspace_tokens else []
        for p in reversed(clean_parts):
            if p not in candidate_tokens:
                candidate_tokens.append(p)
        if not is_obsidian:
            candidate_tokens.append(title)
            
        seen_candidates = set()
        candidate_norms = []
        for candidate in candidate_tokens:
            normalized = normalize_workspace_name(
                candidate,
                workspace_normalization_patterns,
                workspace_title_suffixes,
            )
            if not normalized or normalized in seen_candidates:
                continue
            seen_candidates.add(normalized)
            
            has_extension = bool(re.search(r'\.[a-zA-Z0-9\-]+(?:\b|$)', candidate))
            is_file = has_extension or bool(re.search(re.escape(candidate) + r'\.[a-zA-Z0-9]+', title, re.IGNORECASE))
            is_git_temp = any(token in candidate for token in ["(Working Tree)", "(Revision)", "(Git", "(Index)", "(HEAD)"])
            candidate_norms.append((candidate, normalized, is_file or is_git_temp))

        # Pass 1: Check existing folder
        project_name = None
        # Mocking check: assume "obsidian-note-creator" exists in vault
        for candidate, normalized, is_file in candidate_norms:
            if normalized == "obsidian-note-creator":
                project_name = normalized
                break
                
        self.assertEqual(project_name, "obsidian-note-creator")
        
        # Test 2: If we are in a file and there is no workspace, we should avoid auto-creating it
        title_no_ws = "main.py - Antigravity IDE"
        parts_no_ws = [p.strip() for p in title_no_ws.split(' - ') if p.strip()]
        clean_parts_no_ws = []
        for idx, p in enumerate(parts_no_ws):
            is_suffix = False
            for suffix in workspace_title_suffixes:
                if suffix.lower() in p.lower():
                    is_suffix = True
                    break
            if is_suffix:
                continue
            if re.search(r'\.[a-zA-Z0-9]+$', p):
                continue
            clean_parts_no_ws.append(p)
            
        candidate_tokens_no_ws = [title_no_ws]
        candidate_norms_no_ws = []
        seen_candidates_no_ws = set()
        for candidate in candidate_tokens_no_ws:
            normalized = normalize_workspace_name(
                candidate,
                workspace_normalization_patterns,
                workspace_title_suffixes,
            )
            if not normalized or normalized in seen_candidates_no_ws:
                continue
            seen_candidates_no_ws.add(normalized)
            has_extension = bool(re.search(r'\.[a-zA-Z0-9\-]+(?:\b|$)', candidate))
            is_file = has_extension or bool(re.search(re.escape(candidate) + r'\.[a-zA-Z0-9]+', title_no_ws, re.IGNORECASE))
            is_git_temp = any(token in candidate for token in ["(Working Tree)", "(Revision)", "(Git", "(Index)", "(HEAD)"])
            candidate_norms_no_ws.append((candidate, normalized, is_file or is_git_temp))
            
        # Verify it is flagged as file so Pass 2 auto-creation will skip it
        self.assertTrue(candidate_norms_no_ws[0][2])

    def test_update_conversation_moc_hierarchy_disabled(self):
        """
        Verify update_conversation_moc preserves original behavior when hierarchy_indent=-1.
        """
        from note_creator import update_conversation_moc
        mock_conv_path = "mock_hierarchy_disabled.md"
        with open(mock_conv_path, "w", encoding="utf-8", newline="\n") as f:
            f.write("# Active Conversation\n## MOC.\n- [[20260601111135-first|First]]\n## Notes\n")
        try:
            new_moc_lines = ["- [[20260601114706-second|Second]]\n"]
            update_conversation_moc(mock_conv_path, new_moc_lines, dry_run=False, hierarchy_indent=-1)
            with open(mock_conv_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("\n- [[20260601114706-second|Second]]\n", content)
        finally:
            if os.path.exists(mock_conv_path):
                os.remove(mock_conv_path)

    def test_update_conversation_moc_hierarchy_enabled_empty_moc(self):
        """
        Verify update_conversation_moc indents sequentially when hierarchy_indent > 0 on an empty MOC.
        """
        from note_creator import update_conversation_moc
        mock_conv_path = "mock_hierarchy_empty.md"
        with open(mock_conv_path, "w", encoding="utf-8", newline="\n") as f:
            f.write("# Active Conversation\n## MOC.\n## Notes\n")
        try:
            new_moc_lines = [
                "- [[20260601111135-first|First]]\n",
                "- [[20260601114706-second|Second]]\n",
                "- [[20260601115000-third|Third]]\n"
            ]
            update_conversation_moc(mock_conv_path, new_moc_lines, dry_run=False, hierarchy_indent=4)
            with open(mock_conv_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            # MOC index
            moc_idx = next(i for i, l in enumerate(lines) if l.strip() == "## MOC.")
            self.assertEqual(lines[moc_idx + 2], "- [[20260601111135-first|First]]\n")
            self.assertEqual(lines[moc_idx + 3], "    - [[20260601114706-second|Second]]\n")
            self.assertEqual(lines[moc_idx + 4], "        - [[20260601115000-third|Third]]\n")
        finally:
            if os.path.exists(mock_conv_path):
                os.remove(mock_conv_path)

    def test_update_conversation_moc_hierarchy_enabled_non_empty_moc(self):
        """
        Verify update_conversation_moc indents relative to last item's indentation when hierarchy_indent > 0.
        """
        from note_creator import update_conversation_moc
        mock_conv_path = "mock_hierarchy_non_empty.md"
        with open(mock_conv_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(
                "# Active Conversation\n"
                "## MOC.\n"
                "    - [[20260601111135-first|First]]\n"
                "## Notes\n"
            )
        try:
            new_moc_lines = [
                "- [[20260601114706-second|Second]]\n",
                "- [[20260601115000-third|Third]]\n"
            ]
            update_conversation_moc(mock_conv_path, new_moc_lines, dry_run=False, hierarchy_indent=4)
            with open(mock_conv_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            moc_idx = next(i for i, l in enumerate(lines) if l.strip() == "## MOC.")
            self.assertEqual(lines[moc_idx + 2], "    - [[20260601111135-first|First]]\n")
            self.assertEqual(lines[moc_idx + 3], "        - [[20260601114706-second|Second]]\n")
            self.assertEqual(lines[moc_idx + 4], "            - [[20260601115000-third|Third]]\n")
        finally:
            if os.path.exists(mock_conv_path):
                os.remove(mock_conv_path)

    def test_update_conversation_moc_hierarchy_zero_indent(self):
        """
        Verify update_conversation_moc inserts at same level as last item when hierarchy_indent=0.
        """
        from note_creator import update_conversation_moc
        mock_conv_path = "mock_hierarchy_zero.md"
        with open(mock_conv_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(
                "# Active Conversation\n"
                "## MOC.\n"
                "    - [[20260601111135-first|First]]\n"
                "## Notes\n"
            )
        try:
            new_moc_lines = [
                "- [[20260601114706-second|Second]]\n",
                "- [[20260601115000-third|Third]]\n"
            ]
            update_conversation_moc(mock_conv_path, new_moc_lines, dry_run=False, hierarchy_indent=0)
            with open(mock_conv_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            moc_idx = next(i for i, l in enumerate(lines) if l.strip() == "## MOC.")
            self.assertEqual(lines[moc_idx + 2], "    - [[20260601111135-first|First]]\n")
            self.assertEqual(lines[moc_idx + 3], "    - [[20260601114706-second|Second]]\n")
            self.assertEqual(lines[moc_idx + 4], "    - [[20260601115000-third|Third]]\n")
        finally:
            if os.path.exists(mock_conv_path):
                os.remove(mock_conv_path)

if __name__ == '__main__':
    unittest.main()
