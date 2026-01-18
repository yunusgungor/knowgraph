# Release Process

This document describes the release process for KnowGraph.

## Overview

KnowGraph follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html) and uses GitHub Actions for automated releases.

## Release Workflow

### 1. Prepare the Release

Before creating a release, ensure:

- [ ] All changes are committed and pushed to `main` branch
- [ ] Version is updated in `pyproject.toml`
- [ ] `CHANGELOG.md` is updated with the new version and release date
- [ ] All tests pass in CI
- [ ] Documentation is up to date

### 2. Create and Push a Tag

Once everything is ready on the `main` branch:

```bash
# Make sure you're on the main branch and it's up to date
git checkout main
git pull origin main

# Create an annotated tag (replace X.Y.Z with the version number)
git tag -a vX.Y.Z -m "Release vX.Y.Z"

# Push the tag to GitHub
git push origin vX.Y.Z
```

**Example for version 1.0.0:**

```bash
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

### 3. Automated Release Process

Once the tag is pushed, the GitHub Actions workflow (`.github/workflows/release.yml`) will automatically:

1. **Extract version** from the tag name
2. **Build Python package** (wheel and source distribution)
3. **Extract release notes** from `CHANGELOG.md`
4. **Create GitHub Release** with:
   - Release notes from the changelog
   - Built packages as release assets
5. **Publish to PyPI** (if `PYPI_API_TOKEN` secret is configured)

### 4. Verify the Release

After the workflow completes:

1. Visit [GitHub Releases](https://github.com/yunusgungor/knowgraph/releases) to verify the release
2. Check that the package is available on [PyPI](https://pypi.org/project/knowgraph/)
3. Test installation: `pip install knowgraph==X.Y.Z`

## Version Numbering

KnowGraph follows semantic versioning:

- **MAJOR** (X.0.0): Incompatible API changes
- **MINOR** (0.Y.0): New features (backward-compatible)
- **PATCH** (0.0.Z): Bug fixes (backward-compatible)

## Changelog Format

The `CHANGELOG.md` follows [Keep a Changelog](https://keepachangelog.com/) format:

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- New features

### Changed
- Changes to existing features

### Deprecated
- Soon-to-be removed features

### Removed
- Removed features

### Fixed
- Bug fixes

### Security
- Security fixes
```

## PyPI Configuration

To enable automatic PyPI publishing:

1. Create a PyPI API token at https://pypi.org/manage/account/token/
2. Add it as a GitHub secret named `PYPI_API_TOKEN` in the repository settings

## Manual Release (Fallback)

If the automated workflow fails, you can create a release manually:

### Build the Package

```bash
python -m pip install build twine
python -m build
```

### Create GitHub Release

1. Go to https://github.com/yunusgungor/knowgraph/releases/new
2. Select the tag you created
3. Add release title: `v{version}`
4. Copy release notes from `CHANGELOG.md`
5. Upload `dist/*.whl` and `dist/*.tar.gz` files
6. Click "Publish release"

### Publish to PyPI

```bash
twine upload dist/*
```

## Pre-release Versions

For alpha, beta, or release candidate versions:

```bash
# Examples:
git tag -a v1.0.0-alpha.1 -m "Release v1.0.0-alpha.1"
git tag -a v1.0.0-beta.1 -m "Release v1.0.0-beta.1"
git tag -a v1.0.0-rc.1 -m "Release v1.0.0-rc.1"
```

Mark these as "pre-release" when creating the GitHub release.

## Troubleshooting

### Tag Already Exists

If you need to recreate a tag:

```bash
# Delete local tag
git tag -d vX.Y.Z

# Delete remote tag
git push origin :refs/tags/vX.Y.Z

# Create new tag
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

### Workflow Fails

Check the [Actions tab](https://github.com/yunusgungor/knowgraph/actions) for error details. Common issues:

- **Build failure**: Ensure all dependencies are correctly specified
- **PyPI upload failure**: Check that `PYPI_API_TOKEN` is set correctly
- **Missing release notes**: Ensure `CHANGELOG.md` has an entry for the version

## Release Checklist

Use this checklist when preparing a release:

- [ ] Update version in `pyproject.toml`
- [ ] Update `CHANGELOG.md` with new version and date
- [ ] Commit changes: `git commit -m "chore: Release vX.Y.Z"`
- [ ] Push to main: `git push origin main`
- [ ] Wait for CI to pass
- [ ] Create and push tag: `git tag -a vX.Y.Z -m "Release vX.Y.Z" && git push origin vX.Y.Z`
- [ ] Monitor GitHub Actions workflow
- [ ] Verify GitHub release
- [ ] Verify PyPI publication
- [ ] Test installation: `pip install knowgraph==X.Y.Z`
- [ ] Announce release (if applicable)

## Contact

For questions about the release process, please open an issue or contact the maintainers.
