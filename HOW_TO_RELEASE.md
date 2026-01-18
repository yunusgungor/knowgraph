# 🚀 How to Create the v1.0.0 Release

## TL;DR (Too Long; Didn't Read)

Once this PR is merged to main, run:

```bash
git checkout main
git pull
./scripts/release.sh
```

That's it! The automated workflow will handle the rest.

---

## What This PR Adds

This PR adds complete release infrastructure to automate the creation of GitHub releases and PyPI packages. Here's what was added:

### 📁 Files Added

1. **`.github/workflows/release.yml`** - Automated release workflow
2. **`RELEASE.md`** - Comprehensive release documentation
3. **`RELEASE_v1.0.0.md`** - Quick guide for this specific release
4. **`scripts/release.sh`** - Automated release script
5. **`.github/RELEASE_TEMPLATE.md`** - Template for release notes
6. **`.github/RELEASE_INFRASTRUCTURE.md`** - Infrastructure overview
7. **`CONTRIBUTING.md`** - Updated with release process

### ✅ Pre-requisites (Already Done)

- ✅ Version is `1.0.0` in `pyproject.toml`
- ✅ CHANGELOG.md has entry for `[1.0.0] - 2026-01-18`
- ✅ All files validated and tested

---

## Step-by-Step Release Instructions

### Step 1: Merge This PR

Merge this PR to the `main` branch.

### Step 2: Update Your Local Repository

```bash
git checkout main
git pull origin main
```

### Step 3: Create the Release

#### Option A: Automated Script (Recommended)

```bash
./scripts/release.sh
```

This script will:
- ✅ Check prerequisites
- ✅ Verify you're on the main branch
- ✅ Ensure working directory is clean
- ✅ Show current version (1.0.0)
- ✅ Create annotated tag `v1.0.0`
- ✅ Push tag to GitHub
- ✅ Trigger automated release workflow

#### Option B: Manual

```bash
# Create the tag
git tag -a v1.0.0 -m "Release v1.0.0"

# Push the tag
git push origin v1.0.0
```

### Step 4: Monitor the Release

After pushing the tag:

1. **GitHub Actions**: https://github.com/yunusgungor/knowgraph/actions
   - Look for the "Release" workflow
   - It should complete in ~2-5 minutes

2. **GitHub Release**: https://github.com/yunusgungor/knowgraph/releases
   - A new release `v1.0.0` will be created automatically
   - Release notes will be extracted from CHANGELOG.md
   - Package files (.whl and .tar.gz) will be attached

3. **PyPI** (Optional): https://pypi.org/project/knowgraph/
   - If `PYPI_API_TOKEN` secret is configured, package will be published
   - Otherwise, this step is skipped (can be done manually later)

### Step 5: Verify the Release

```bash
# Test installation from PyPI
pip install knowgraph==1.0.0

# Verify version
python -c "import knowgraph; print(knowgraph.__version__)"
```

---

## What Happens Automatically

Once you push the tag `v1.0.0`, the GitHub Actions workflow will:

1. ✅ Checkout the repository
2. ✅ Set up Python 3.11
3. ✅ Install build dependencies
4. ✅ Build the package (wheel + source distribution)
5. ✅ Extract release notes from CHANGELOG.md
6. ✅ Create GitHub Release with:
   - Title: `v1.0.0`
   - Body: Release notes from CHANGELOG
   - Assets: Built packages
7. ✅ Publish to PyPI (if token is configured)

---

## Troubleshooting

### If the tag already exists

```bash
# Delete local tag
git tag -d v1.0.0

# Delete remote tag (if needed)
git push origin :refs/tags/v1.0.0

# Recreate and push
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

### If the workflow fails

1. Check the Actions tab for error details
2. Most common issues:
   - **Build error**: Check dependencies in pyproject.toml
   - **CHANGELOG format**: Verify the format matches `## [1.0.0] - 2026-01-18`
   - **PyPI upload**: Verify `PYPI_API_TOKEN` secret (optional)

3. You can always create the release manually:
   - Go to https://github.com/yunusgungor/knowgraph/releases/new
   - Select tag `v1.0.0`
   - Copy content from CHANGELOG.md
   - Upload files from `dist/` directory

---

## PyPI Configuration (Optional)

To enable automatic PyPI publishing:

1. Create a PyPI API token at https://pypi.org/manage/account/token/
2. Add it as a GitHub secret:
   - Go to: Repository Settings → Secrets and variables → Actions
   - Name: `PYPI_API_TOKEN`
   - Value: Your PyPI token

If the token is not configured, the workflow will skip PyPI publishing (not a failure).

---

## Future Releases

For future releases, the process is even simpler:

1. Update version in `pyproject.toml`
2. Add entry to `CHANGELOG.md`
3. Commit and push to main
4. Run `./scripts/release.sh`

That's it!

---

## Documentation

For more details:
- **RELEASE.md** - Full release process documentation
- **RELEASE_v1.0.0.md** - Quick guide for this release
- **.github/RELEASE_INFRASTRUCTURE.md** - Infrastructure overview

---

## Questions?

If you have any questions about the release process:
- Check the documentation files
- Open an issue
- Review the workflow file: `.github/workflows/release.yml`

---

## Summary

✅ All infrastructure is in place and tested
✅ Version 1.0.0 is ready to release
✅ CHANGELOG is up to date
✅ Automated workflow is configured

**Next step**: Merge this PR, then run `./scripts/release.sh` to create the release!

---

**Happy releasing! 🎉**
