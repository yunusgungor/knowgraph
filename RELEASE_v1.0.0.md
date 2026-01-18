# Quick Release Guide for v1.0.0

This document provides step-by-step instructions for creating the v1.0.0 release.

## Prerequisites

- You have write access to the repository
- You are on the `main` or `master` branch
- All changes for v1.0.0 are merged
- CI is passing
- Version in `pyproject.toml` is set to `1.0.0` ✅
- `CHANGELOG.md` has an entry for `[1.0.0]` dated `2026-01-18` ✅

## Option 1: Using the Automated Script (Recommended)

```bash
# Navigate to the repository
cd /path/to/knowgraph

# Make sure you're on main and up to date
git checkout main
git pull origin main

# Run the release script
./scripts/release.sh
```

The script will:
- Check prerequisites
- Verify you're on the correct branch
- Ensure working directory is clean
- Pull latest changes
- Display current version from `pyproject.toml`
- Prompt for confirmation
- Create the annotated tag `v1.0.0`
- Push the tag to GitHub
- Trigger the automated release workflow

## Option 2: Manual Release

```bash
# Navigate to the repository
cd /path/to/knowgraph

# Make sure you're on main and up to date
git checkout main
git pull origin main

# Verify everything is ready
git status  # Should be clean
grep "version = " pyproject.toml  # Should show "1.0.0"

# Create the annotated tag
git tag -a v1.0.0 -m "Release v1.0.0"

# Push the tag to GitHub
git push origin v1.0.0
```

## What Happens After Pushing the Tag

Once the tag `v1.0.0` is pushed to GitHub:

1. **GitHub Actions Triggered**: The `.github/workflows/release.yml` workflow is automatically triggered
2. **Package Build**: Python package (wheel and source distribution) is built
3. **Release Notes Extraction**: Release notes are extracted from `CHANGELOG.md`
4. **GitHub Release Created**: A new release is created on GitHub with:
   - Release title: `v1.0.0`
   - Release notes from the changelog
   - Built packages as downloadable assets
5. **PyPI Publication** (if configured): Package is uploaded to PyPI

## Monitoring the Release

After pushing the tag:

1. **Check GitHub Actions**:
   - Go to: https://github.com/yunusgungor/knowgraph/actions
   - Look for the "Release" workflow run
   - Monitor progress and check for any errors

2. **Verify GitHub Release**:
   - Go to: https://github.com/yunusgungor/knowgraph/releases
   - Confirm that v1.0.0 release is created
   - Check that release notes are correct
   - Verify that package files are attached

3. **Verify PyPI** (if published):
   - Go to: https://pypi.org/project/knowgraph/
   - Confirm version 1.0.0 is available
   - Test installation: `pip install knowgraph==1.0.0`

## Troubleshooting

### If the tag push fails

```bash
# Check if tag already exists
git tag -l | grep v1.0.0

# If it exists locally, delete it
git tag -d v1.0.0

# If it exists remotely, delete it (careful!)
git push origin :refs/tags/v1.0.0

# Then recreate and push
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

### If the workflow fails

1. Check the Actions tab for error details
2. Common issues:
   - **Build errors**: Check package dependencies
   - **CHANGELOG format**: Ensure version section exists and is properly formatted
   - **PyPI upload**: Verify `PYPI_API_TOKEN` secret is set (optional)

3. If needed, you can manually create the release:
   - Go to https://github.com/yunusgungor/knowgraph/releases/new
   - Select tag `v1.0.0`
   - Copy release notes from CHANGELOG.md
   - Upload built packages from `dist/` directory

## Post-Release Tasks

After successful release:

1. **Announce the release** (if applicable):
   - Social media
   - Project documentation
   - User mailing lists

2. **Update documentation links** to point to v1.0.0 if needed

3. **Start planning for the next release**:
   - Create a new section in CHANGELOG.md for the next version
   - Update version in pyproject.toml to the next planned version (e.g., 1.1.0-dev)

## Notes

- The automated workflow is configured in `.github/workflows/release.yml`
- Release notes are automatically extracted from `CHANGELOG.md`
- The workflow expects CHANGELOG entries in the format: `## [VERSION] - DATE`
- PyPI upload requires the `PYPI_API_TOKEN` secret to be configured in GitHub

## Support

For questions or issues:
- Open an issue: https://github.com/yunusgungor/knowgraph/issues
- Contact: mail@yunusgungor.com
