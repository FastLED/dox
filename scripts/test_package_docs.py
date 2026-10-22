"""Validate the public publication bundle contract using a small real site."""

import hashlib
import json
import os
import tarfile
import tempfile
import unittest
from pathlib import Path

from package_docs import package_docs


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.site = Path(self.temp.name) / "site"
        self.output = Path(self.temp.name) / "bundle"
        self.site.mkdir()
        self.release = {
            "id": 416153555,
            "tag_name": "3.10.8",
            "source_sha": "f" * 40,
            "doxygen_version": "1.13.2",
        }
        (self.site / "release.json").write_text(json.dumps(self.release))
        (self.site / "index.html").write_text("<h1>FastLED</h1>")
        (self.site / ".nojekyll").touch()
        (self.site / "search").mkdir()
        (self.site / "search" / "search.js").write_text("// search")
        (self.site / "publication.json").write_text('{"old": true}')

    def test_archive_and_manifest_describe_identical_release(self):
        manifest = package_docs(self.site, self.output, "12345-2")
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["generation"], "12345-2")
        self.assertEqual(manifest["release"], dict(self.release, generation="12345-2"))
        archive = (self.output / "docs.tar.gz").read_bytes()
        self.assertEqual(
            manifest["archive"],
            {
                "url": "https://github.com/FastLED/dox/releases/download/docs-12345-2/docs.tar.gz",
                "sha256": hashlib.sha256(archive).hexdigest(),
                "size": len(archive),
            },
        )
        self.assertEqual(
            (self.site / "publication.json").read_bytes(),
            (self.output / "manifest.json").read_bytes(),
        )
        self.assertEqual(
            json.loads((self.output / "manifest.json").read_text()), manifest
        )
        with tarfile.open(self.output / "docs.tar.gz") as bundle:
            self.assertEqual(
                set(bundle.getnames()),
                {
                    ".nojekyll",
                    "index.html",
                    "release.json",
                    "search",
                    "search/search.js",
                },
            )
            self.assertTrue(all(member.isfile() or member.isdir() for member in bundle))
            self.assertEqual(
                json.load(bundle.extractfile("release.json")), manifest["release"]
            )

    def test_rejects_unsafe_generation_before_modifying_release(self):
        original = (self.site / "release.json").read_bytes()
        for generation in ("../123", "1/2", "1-2\n", "1-2;echo", "", "1", "a-2", "0-1"):
            with self.subTest(generation=generation), self.assertRaises(ValueError):
                package_docs(self.site, self.output, generation)
        self.assertEqual((self.site / "release.json").read_bytes(), original)

    def test_rejects_symlinks_including_excluded_manifest(self):
        for name in ("linked.html", "publication.json"):
            with self.subTest(name=name):
                target = self.site / name
                if target.exists():
                    target.rename(target.with_suffix(".old"))
                target.symlink_to(self.site / "index.html")
                with self.assertRaisesRegex(ValueError, "symlink"):
                    package_docs(self.site, self.output, "12345-1")
                target.rename(target.with_suffix(".rejected"))
                # Move rejected symlinks outside the site before the next case.
                target.with_suffix(".rejected").rename(Path(self.temp.name) / name)

    def test_rejects_output_inside_site(self):
        with self.assertRaises(ValueError):
            package_docs(self.site, self.site / "bundle", "12345-1")

    def test_hardlinks_are_archived_as_regular_files(self):
        os.link(self.site / "index.html", self.site / "copy.html")
        package_docs(self.site, self.output, "12345-1")
        with tarfile.open(self.output / "docs.tar.gz") as bundle:
            self.assertTrue(bundle.getmember("index.html").isfile())
            self.assertTrue(bundle.getmember("copy.html").isfile())


if __name__ == "__main__":
    unittest.main()
