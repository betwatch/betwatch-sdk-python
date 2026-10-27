#!/usr/bin/env bash
# Cut a release commit and tag: bump the version, prepend the changelog from
# conventional commits, and run every gate. Pushing the tag publishes it.
#
#   tools/release.sh 2.0.0b4
#   git push origin HEAD v2.0.0b4
set -euo pipefail
cd "$(dirname "$0")/.."

version=${1:?usage: tools/release.sh <version, e.g. 2.0.0b4>}
tag="v$version"

[[ -z $(git status --porcelain) ]] || { echo "worktree not clean" >&2; exit 1; }
git rev-parse -q --verify "refs/tags/$tag" >/dev/null && { echo "$tag already exists" >&2; exit 1; }

printf '__version__ = "%s"\n' "$version" > src/betwatch/__about__.py
uv run git-cliff --unreleased --tag "$tag" --prepend CHANGELOG.md
bash tools/check.sh

git add src/betwatch/__about__.py CHANGELOG.md
git commit -q -m "chore(release): $tag"
git tag -a "$tag" -m "$tag"
echo "tagged $tag; publish with: git push origin HEAD $tag"
