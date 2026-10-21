#!/usr/bin/env bash
set -euo pipefail

: "${GITHUB_REPOSITORY:?Set GITHUB_REPOSITORY to the documentation repository}"
: "${GITHUB_OUTPUT:?Set GITHUB_OUTPUT to the workflow output file}"
mkdir -p .build

gh api repos/FastLED/FastLED/releases/latest > .build/latest-release.json
tag=$(jq -er '.tag_name' .build/latest-release.json)
release_id=$(jq -er '.id' .build/latest-release.json)
if [[ ! "$tag" =~ ^v?[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Unsupported release tag: $tag" >&2
  exit 1
fi
pages_url=$(gh api "repos/$GITHUB_REPOSITORY/pages" --jq .html_url)
pages_url="${pages_url/http:/https:}"
status=$(curl --silent --show-error --location --retry 3 \
  --header 'Cache-Control: no-cache' \
  --output .build/deployed-release.json --write-out '%{http_code}' \
  "${pages_url%/}/release.json?run=${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}")

changed=true
case "$status" in
  200)
    # Invalid metadata fails the run instead of silently rebuilding every day.
    jq -e 'type == "object" and (.id | type == "number") and (.tag_name | type == "string")' \
      .build/deployed-release.json > /dev/null
    if jq -e --argjson id "$release_id" --arg tag "$tag" \
      '.id == $id and .tag_name == $tag' .build/deployed-release.json > /dev/null; then
      changed=false
    fi
    ;;
  404) ;; # The first deployment has no release marker yet.
  *) echo "Unable to read deployed release: HTTP $status" >&2; exit 1 ;;
esac
if [[ "${FORCE_REBUILD:-false}" == true ]]; then
  changed=true
fi
printf 'tag=%s\nrelease_id=%s\nchanged=%s\n' "$tag" "$release_id" "$changed" >> "$GITHUB_OUTPUT"
echo "Latest release: $tag; documentation update required: $changed"
