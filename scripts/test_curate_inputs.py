"""Focused checks using real release-shaped files and Markdown links."""

import json
import tempfile
import unittest
from pathlib import Path

from curate_inputs import filter_document, select


class CuratedInputsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "release"
        self.root.mkdir()
        self.write(
            "docs/Doxyfile",
            """
INPUT = ../src \\
        ../examples ../README.md ../PORTING.md
FILE_PATTERNS = *.h *.cpp *.ino *.md *.markdown
EXCLUDE = ../src/platforms
""",
        )
        self.write(
            "README.md",
            """# Release
[Guide](<guide%20one.md?view=1#topic>)
[Platform](src/platforms/guide.md)
[Reference][port]
[port]: PORTING.md
[unused]: unused.md
![Image](image.md)
[Remote](https://example.org/remote.md)
[Escape](../outside.md)
[Encoded escape](%2e%2e/outside.md)
[Symlink](escape.md)
`[Code](unused.md)`
```
[Example](unused.md)
```
""",
        )
        self.write(
            "guide one.md", "[Nested](src/nested.md?plain=1#details) [Root](README.md)"
        )
        self.write("src/platforms/guide.md", "# Linked platform guide")
        self.write("src/nested.md", "# Not directly linked")
        self.write("src/journal.markdown", "# Unlinked journal")
        self.write("src/api.h", "/** API. */ class Api {};")
        self.write("src/platforms/private.h", "class Excluded {};")
        self.write("examples/Blink/Blink.ino", "void setup() {}")
        for name in ("PORTING.md", "unused.md", "image.md"):
            self.write(name, "# Other")
        outside = self.root.parent / "outside.md"
        outside.write_text("# Outside")
        (self.root / "escape.md").symlink_to(outside)

    def write(self, name: str, text: str):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def render(self, document="README.md"):
        _, markdown = select(self.root)
        manifest = self.root / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "root": str(self.root),
                    "tag": "3.10.8",
                    "markdown": [str(p) for p in markdown],
                }
            )
        )
        return filter_document(manifest, self.root / document)

    def test_missing_release_documents_keep_labels_without_broken_links(self):
        self.write(
            "README.md",
            """[FX library](src/fx/README.md)
[LCD migration](<src/platforms/esp/32/drivers/lcd_cam/LCD_I80_vs_RGB_MIGRATION_GUIDE.md> "Guide")
[Release notes][lcd]
[lcd]: missing%20notes.md#status
[lcd][] and [lcd]
![Image][lcd]
![Image](missing.md)
`[Code](missing.md)`
```
[Code][lcd]
```
""",
        )
        rendered = self.render()
        self.assertIn("FX library (not available in this release)", rendered)
        self.assertIn("LCD migration (not available in this release)", rendered)
        self.assertIn("Release notes (not available in this release)", rendered)
        self.assertIn(
            "lcd (not available in this release) and lcd (not available in this release)",
            rendered,
        )
        self.assertIn("![Image][lcd]", rendered)
        self.assertIn("![Image](missing.md)", rendered)
        self.assertIn("`[Code](missing.md)`", rendered)
        self.assertIn("[Code][lcd]", rendered)
        self.assertNotIn("[FX library]", rendered)

    def test_sources_directories_and_encoded_links_use_existing_tagged_paths(self):
        self.write(
            "README.md",
            """[API](src/api.h?plain=1#L1)
[Examples](examples/)
[Missing](missing%20guide.md?plain=1#topic)
[External](https://example.org/missing.md)
[Escape](../outside.md)
[Symlink](escape.md)
""",
        )
        rendered = self.render()
        self.assertIn(
            "https://github.com/FastLED/FastLED/blob/3.10.8/src/api.h?plain=1#L1",
            rendered,
        )
        self.assertIn(
            "https://github.com/FastLED/FastLED/tree/3.10.8/examples", rendered
        )
        self.assertIn("Missing (not available in this release)", rendered)
        self.assertIn("[External](https://example.org/missing.md)", rendered)
        self.assertIn("[Escape](../outside.md)", rendered)
        self.assertIn("[Symlink](escape.md)", rendered)

    def test_selected_markdown_section_links_use_the_exact_tag(self):
        rendered = self.render()
        self.assertIn(
            "https://github.com/FastLED/FastLED/blob/3.10.8/guide%20one.md?view=1#topic",
            rendered,
        )

    def test_missing_links_preserve_inline_code_labels(self):
        self.write(
            "README.md",
            "[`missing.h`](missing.h) and [`Guide`][gone]\n[gone]: absent.md\n",
        )
        rendered = self.render()
        self.assertIn("`missing.h` (not available in this release)", rendered)
        self.assertIn("`Guide` (not available in this release)", rendered)

    def test_exact_readme_selection_preserves_api_and_excludes_junk(self):
        inputs, markdown = select(self.root)
        self.assertEqual(
            {path.relative_to(self.root).as_posix() for path in markdown},
            {"README.md", "guide one.md", "PORTING.md", "src/platforms/guide.md"},
        )
        self.assertEqual(
            set(inputs) - markdown,
            {
                self.root / "src/api.h",
                self.root / "examples/Blink/Blink.ino",
            },
        )

    def test_nested_links_use_tagged_github_and_keep_selected_links(self):
        _, markdown = select(self.root)
        manifest = self.root / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "root": str(self.root),
                    "tag": "release/1",
                    "markdown": [str(p) for p in markdown],
                }
            )
        )
        rendered = filter_document(manifest, self.root / "guide one.md")
        self.assertIn(
            "https://github.com/FastLED/FastLED/blob/release%2F1/src/nested.md?plain=1#details",
            rendered,
        )
        self.assertIn("[Root](README.md)", rendered)
        self.assertNotIn("[Nested](src/nested.md", rendered)


if __name__ == "__main__":
    unittest.main()
