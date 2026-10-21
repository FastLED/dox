#!/usr/bin/env bash
set -euo pipefail

: "${RELEASE_TAG:?Set RELEASE_TAG to the checked-out FastLED release}"
: "${RELEASE_ID:?Set RELEASE_ID to the GitHub release ID}"
source_dir=$(realpath "${1:-fastled}")
site_dir="$(pwd)/site"
tools_dir="$(pwd)/.build/tools"
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
HTML_OUTPUT = docs
HTML_HEADER =
HTML_FOOTER =
QUIET = YES
CONFIG
(
  cd "$source_dir/docs"
  "$doxygen" "$config"
)
test -s "$site_dir/docs/index.html"
test -s "$site_dir/docs/search/search.js"

source_sha=$(git -C "$source_dir" rev-parse HEAD)
jq --null-input --argjson id "$RELEASE_ID" --arg tag "$RELEASE_TAG" \
  --arg sha "$source_sha" --arg version "$version" \
  '{id: $id, tag_name: $tag, source_sha: $sha, doxygen_version: $version}' \
  > "$site_dir/release.json"
cat > "$site_dir/index.html" <<'HTML'
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="0; url=docs/">
  <title>FastLED API documentation</title>
</head>
<body><p><a href="docs/">Open the FastLED API documentation</a></p></body>
</html>
HTML
touch "$site_dir/.nojekyll"
echo "Built FastLED $RELEASE_TAG ($source_sha) into $site_dir"
