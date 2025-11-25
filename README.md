# Betwatch Python SDK

[![PyPI - Version](https://img.shields.io/pypi/v/betwatch.svg)](https://pypi.org/project/betwatch)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/betwatch.svg)](https://pypi.org/project/betwatch)

-----
The Betwatch Python SDK allows you to interact with the [Betwatch.com](https://www.betwatch.com) API to integrate up to date racing price data into your Python applications.

### Disclaimer
This library is provided on a best-effort basis in order to lower the barrier of entry for accessing the Betwatch API. No guarantees are made for the reliability of this library and development will be ongoing.

## Installation

```console
pip install betwatch
```

## Usage
See [examples](https://github.com/betwatch/betwatch-sdk-python/tree/main/examples)

A Betwatch API key is required. Please contact [api@betwatch.com](mailto:api@betwatch.com) for more information.

## Development

### Setup

Install dependencies using `uv`:
```console
uv sync
```

Install pre-commit hooks:
```console
pre-commit install --hook-type commit-msg
```

### Commit Convention

This project follows [Conventional Commits](https://www.conventionalcommits.org/) for automatic changelog generation. All commit messages must follow this format:

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

**Types:**
- `feat`: A new feature (triggers minor version bump)
- `fix`: A bug fix (triggers patch version bump)
- `docs`: Documentation only changes
- `style`: Changes that don't affect code meaning (white-space, formatting)
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `perf`: Performance improvement
- `test`: Adding missing tests
- `chore`: Changes to build process or auxiliary tools

**Breaking Changes:**
Add `!` after the type or `BREAKING CHANGE:` in the footer to trigger a major version bump.

**Examples:**
```bash
feat: add support for new market types
fix: resolve race condition in async client
docs: update API examples
feat!: change API endpoint structure
```

The pre-commit hook will validate your commit messages automatically.

### Running Tests

```console
uv run pytest
```

### Linting and Type Checking

```console
uv run ruff check .
uv run basedpyright
```

### Generating Changelog Locally

To see what the changelog would look like:
```console
git-cliff --unreleased
```

## Releasing

This project uses GitHub Actions for automated releases and publishing to PyPI.

### Release Process

1. Go to the [Actions tab](https://github.com/betwatch/betwatch-sdk-python/actions/workflows/release.yml) in GitHub
2. Click "Run workflow"
3. Enter the new version number (e.g., `1.8.0`)
4. Select the release type (`major`, `minor`, or `patch`)
5. Click "Run workflow"

This will:
- Create a release branch with the version bump
- Generate a changelog from recent commits
- Create a Pull Request for the release
- Auto-merge the PR (if CI passes)
- Create a GitHub release with the changelog
- Trigger the publish workflow to upload to PyPI

### Manual Release

If you need to create a release manually:

1. Update the version in `pyproject.toml`
2. Commit the change: `git commit -am "chore: bump version to X.Y.Z"`
3. Create a tag: `git tag vX.Y.Z`
4. Push the tag: `git push origin vX.Y.Z`
5. Create a GitHub release from the tag

The publish workflow will automatically upload to PyPI when a GitHub release is published.
