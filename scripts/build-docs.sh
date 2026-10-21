#!/usr/bin/env bash
set -euo pipefail

: "${RELEASE_TAG:?Set RELEASE_TAG to the checked-out FastLED release}"
: "${RELEASE_ID:?Set RELEASE_ID to the GitHub release ID}"
source_dir=$(realpath "${1:-fastled}")
source_sha=$(git -C "$source_dir" rev-parse --verify "refs/tags/$RELEASE_TAG^{commit}")
head_sha=$(git -C "$source_dir" rev-parse --verify HEAD)
if [ "$head_sha" != "$source_sha" ]; then
  echo "Refusing to build: HEAD $head_sha does not match release tag $RELEASE_TAG ($source_sha)" >&2
  exit 1
fi
site_dir="$(pwd)/site"
tools_dir="$(pwd)/.build/tools"
scripts_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
version=1.13.2
checksum=f2c0a349403bc5b5ade3f501301e32b49ea31b3182666954bc398452fbc0dd1c
mkdir -p "$tools_dir" "$site_dir"

curl --fail --silent --show-error --location --retry 3 \
  "https://www.doxygen.nl/files/doxygen-$version.linux.bin.tar.gz" \
  --output "$tools_dir/doxygen.tar.gz"
printf '%s  %s\n' "$checksum" "$tools_dir/doxygen.tar.gz" | sha256sum --check
tar -xzf "$tools_dir/doxygen.tar.gz" -C "$tools_dir"
doxygen="$tools_dir/doxygen-$version/bin/doxygen"
"$doxygen" --version
dot -V

# Keep the release's inputs and stylesheet; use Doxygen's matching built-in
# header/footer rather than the upstream legacy header's missing JS assets.
config="$tools_dir/Doxyfile"
cat "$source_dir/docs/Doxyfile" > "$config"
cat >> "$config" <<CONFIG

PROJECT_NUMBER = "$RELEASE_TAG"
OUTPUT_DIRECTORY = "$site_dir"
HTML_OUTPUT = .
HTML_HEADER =
HTML_FOOTER =
QUIET = YES
# Match the README's GitHub-style links to headings on the current page.
MARKDOWN_ID_STYLE = GITHUB
# Selected subdirectory READMEs are standalone guides, not directory comments.
IMPLICIT_DIR_DOCS = NO
# The release enables six workers; Doxygen 1.13.2 corrupts memory while
# generating this release in parallel. Use its default serial processing.
NUM_PROC_THREADS = 1
CONFIG
python3 "$scripts_dir/curate_inputs.py" configure "$source_dir" "$RELEASE_TAG" \
  "$tools_dir/markdown-inputs.json" >> "$config"
(
  cd "$source_dir/docs"
  "$doxygen" "$config"
)
test -s "$site_dir/index.html"
test -s "$site_dir/search/search.js"

jq --null-input --argjson id "$RELEASE_ID" --arg tag "$RELEASE_TAG" \
  --arg sha "$source_sha" --arg version "$version" \
  '{id: $id, tag_name: $tag, source_sha: $sha, doxygen_version: $version}' \
  > "$site_dir/release.json"
# Preserve the previously published landing URL while the reference lives at root.
mkdir -p "$site_dir/docs"
cat > "$site_dir/docs/index.html" <<'HTML'
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <script>window.location.replace('../' + window.location.search + window.location.hash);</script>
  <meta http-equiv="refresh" content="0; url=../">
  <title>FastLED API documentation</title>
</head>
<body><p><a href="../">Open the FastLED API documentation</a></p></body>
</html>
HTML
touch "$site_dir/.nojekyll"
echo "Built FastLED $RELEASE_TAG ($source_sha) into $site_dir"
