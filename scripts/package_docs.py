"""Package a release site for durable downloads and independent mirrors."""

import argparse
import hashlib
import json
import re
import tarfile
from pathlib import Path


def package_docs(site, output_dir, generation):
    if not re.fullmatch(r"[1-9][0-9]*-[1-9][0-9]*", generation):
        raise ValueError(
            "generation must be a GitHub run ID and attempt: <id>-<attempt>"
        )
    site = Path(site)
    output_dir = Path(output_dir)
    if site.is_symlink():
        raise ValueError("site must not be a symlink")
    site = site.resolve(strict=True)
    output_dir = output_dir.resolve()
    if output_dir == site or site in output_dir.parents:
        raise ValueError("output directory must be outside the site")
    paths = sorted(site.rglob("*"))
    for path in paths:
        if path.is_symlink():
            raise ValueError(f"site contains a symlink: {path.relative_to(site)}")
        if not (path.is_file() or path.is_dir()):
            raise ValueError(
                f"site contains a non-file entry: {path.relative_to(site)}"
            )

    release = json.loads((site / "release.json").read_text())
    for key in ("id", "tag_name", "source_sha", "doxygen_version"):
        if key not in release:
            raise ValueError(f"release.json is missing {key}")
    release["generation"] = generation
    (site / "release.json").write_text(json.dumps(release, indent=2) + "\n")
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / "docs.tar.gz"
    # Symlinks were rejected above; dereference hard links into regular files.
    with tarfile.open(archive_path, "w:gz", dereference=True) as archive:
        for path in paths:
            if path != site / "publication.json":
                archive.add(path, arcname=path.relative_to(site), recursive=False)
    digest = hashlib.sha256()
    with archive_path.open("rb") as archive:
        for chunk in iter(lambda: archive.read(1024 * 1024), b""):
            digest.update(chunk)
    manifest = {
        "schema_version": 1,
        "generation": generation,
        "release": release,
        "archive": {
            "url": f"https://github.com/FastLED/dox/releases/download/docs-{generation}/docs.tar.gz",
            "sha256": digest.hexdigest(),
            "size": archive_path.stat().st_size,
        },
    }
    content = json.dumps(manifest, indent=2) + "\n"
    (output_dir / "manifest.json").write_text(content)
    (site / "publication.json").write_text(content)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--generation", required=True)
    args = parser.parse_args()
    package_docs(args.site, args.output_dir, args.generation)


if __name__ == "__main__":
    main()
