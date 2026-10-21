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
