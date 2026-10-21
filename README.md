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

GitHub Pages is configured to deploy from Actions. HTML is uploaded as a Pages
artifact with one-day retention; it is never committed to this repository.
The deployed `release.json` records the release ID, tag, source commit, and
Doxygen version. No personal token or cross-repository write access is needed.

For a local build on Linux x86-64, install Git, curl, jq, tar, Python 3, and Graphviz, then:

```bash
git clone --depth 1 --branch 3.10.8 https://github.com/FastLED/FastLED.git fastled
RELEASE_TAG=3.10.8 RELEASE_ID=416153555 bash scripts/build-docs.sh
```

Migration and history cleanup are tracked in
[FastLED/FastLED#4878](https://github.com/FastLED/FastLED/issues/4878).

## Schedule maintenance

GitHub can disable scheduled workflows in public repositories after 60 days
without repository activity. If the schedule is disabled, open the workflow in
Actions and choose **Enable workflow**, then run it manually. See
[GitHub's scheduled workflow documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).
