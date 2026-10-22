# FastLED Doxygen

Release-based API documentation for [FastLED](https://github.com/FastLED/FastLED).

The daily GitHub Actions workflow checks the latest stable FastLED release and
publishes its Doxygen documentation to GitHub Pages when a new release appears.

**API reference:** https://fastled.github.io/dox/

This repository publishes the FastLED library's Doxygen reference directly at
the site root. The previous `/dox/docs/` landing URL redirects to `/dox/`.
Other FastLED projects keep their own documentation sites; this is not a shared
documentation hub. If that scope changes, repository names should identify the
individual references, such as `/dox/fastled/` and `/dox/fbuild/`.

## Updates

The check runs daily at **09:17 UTC**. It compares GitHub's latest stable
`FastLED/FastLED` release against the `release.json` marker on the published site.
When the release matches, the build and deployment are skipped. Failed builds
leave the published marker unchanged, so the next run retries automatically.

To publish immediately, use **Actions → Publish release documentation → Run
workflow**. Enable **force** to rebuild the current release after changing the
pipeline. Drafts and prereleases are excluded by GitHub's latest-release API.

## Build and hosting

The workflow checks out the exact `refs/tags/<release>` with depth 1, never a
subsequent commit on `master`. Before downloading tools or generating documentation,
the build verifies that `HEAD` equals the release tag's commit and fails on a
mismatch. The verified commit is recorded in `release.json`. It uses that release's
Doxyfile, source, examples, and stylesheet with SHA256-verified Doxygen 1.13.2
and Graphviz. Doxygen's built-in header/footer avoid missing assets referenced
by the upstream legacy header. The generated pages include the release number.

The reference includes the release's API source files, root README, and local
Markdown documents linked directly from that README. Other Markdown files are
excluded from the navigation. Links from included documents to further Markdown
documents open their source on GitHub at the same release tag.

For documents or examples absent from the exact release tag, the published
reference retains the link label with “not available in this release” instead
of a broken hyperlink. Existing source and directory links point to that same
tag on GitHub.

GitHub Pages is configured to deploy from Actions. HTML is uploaded as a Pages
artifact with one-day retention; it is never committed to this repository.
The deployed `release.json` records the release ID, tag, source commit, and
Doxygen version. No personal token or cross-repository write access is needed.

## Durable documentation downloads

The active site's [publication.json](https://fastled.github.io/dox/publication.json)
identifies a public, versioned download of that exact publication. Mirrors should
discover downloads through this manifest rather than GitHub's latest-release API.
Its `schema_version` is `1`; `generation` is the GitHub run ID and attempt joined
with a hyphen. The `release` object contains `id`, `tag_name`, `source_sha`,
`doxygen_version`, and the same `generation`. The `archive` object contains the
public `url`, hexadecimal `sha256`, and byte `size` of `docs.tar.gz`.

Each build creates a `docs-<generation>` documentation prerelease containing
`docs.tar.gz` and `manifest.json`. These assets are uploaded before Pages deploys;
the public site selects the generation only after deployment succeeds. Failed
deployments therefore leave the previous publication selected. Consumers should
verify the archive's size and SHA256 before extracting its files and directories.
The archive includes `release.json` with the matching generation and excludes
`publication.json` to avoid a self-referential checksum. The standalone
`manifest.json` and deployed `publication.json` are identical.

Publication assets remain available beyond the Actions artifact retention period.
Generated HTML and archives are never committed to Git. A forced rebuild of the
same FastLED tag creates a new generation; an unchanged daily check still skips
building and publishing. The publish job uses repository write permission to
create its documentation release; the release check retains read permission.

For a local build on Linux x86-64, install Git, curl, jq, tar, Python 3, and Graphviz, then:

```bash
git clone --depth 1 --branch 3.10.8 https://github.com/FastLED/FastLED.git fastled
RELEASE_TAG=3.10.8 RELEASE_ID=416153555 bash scripts/build-docs.sh
```

Migration and history cleanup are tracked in
[FastLED/FastLED#4878](https://github.com/FastLED/FastLED/issues/4878).

Section links to other Markdown documents open the same release tag on GitHub;
local heading links use GitHub-style IDs. This avoids Doxygen leaving literal
`file.md#section` URLs in the generated HTML.

Selected subdirectory READMEs render as standalone guides. The input filter
normalizes Setext or missing page titles for Doxygen filename linking and
resolves selected document paths explicitly. Release source files stay unchanged.

## Schedule maintenance

The successful daily check records a small status snapshot on
`automation/release-checks` at most once every 30 days. This provides repository
activity before GitHub's 60-day inactivity limit. The audit history contains
only JSON and never triggers a documentation build or deployment. The audit job
has repository write permission, as does the separate publish job for its public
download release. Release checking retains read permission.

If GitHub disables the schedule after a prolonged outage, open the workflow in
Actions and choose **Enable workflow**, then run it manually. See
[GitHub's scheduled workflow documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).
