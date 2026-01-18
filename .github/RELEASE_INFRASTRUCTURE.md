# Release Infrastructure Summary

This document summarizes the release infrastructure added to the KnowGraph project.

## Overview

The project now has a complete, automated release infrastructure that allows maintainers to create releases by simply pushing a git tag.

## Files Added

### 1. `.github/workflows/release.yml`
**Purpose**: GitHub Actions workflow for automated releases

**Triggers**: When a tag matching `v*.*.*` is pushed

**Actions**:
- Builds Python package (wheel and source distribution)
- Extracts release notes from `CHANGELOG.md`
- Creates GitHub Release with notes and package files
- Publishes to PyPI (if `PYPI_API_TOKEN` is configured)

**Configuration**:
```yaml
on:
  push:
    tags:
      - 'v*.*.*'
```

### 2. `RELEASE.md`
**Purpose**: Comprehensive release process documentation

**Contents**:
- Release workflow overview
- Step-by-step instructions for creating releases
- Version numbering guidelines (Semantic Versioning)
- Changelog format requirements
- PyPI configuration instructions
- Manual release fallback procedures
- Troubleshooting guide
- Release checklist

### 3. `scripts/release.sh`
**Purpose**: Automated bash script to streamline the release process

**Features**:
- Validates prerequisites (git, python)
- Checks current branch (warns if not on main/master)
- Ensures working directory is clean
- Pulls latest changes
- Reads current version from `pyproject.toml`
- Checks for existing tags
- Creates annotated git tag
- Pushes tag to trigger automated workflow
- Provides visual feedback with colors

**Usage**:
```bash
./scripts/release.sh
```

### 4. `.github/RELEASE_TEMPLATE.md`
**Purpose**: Template for GitHub release descriptions

**Contents**:
- Highlights section
- Changelog section
- Installation instructions
- Setup guides
- Documentation links
- Contributors acknowledgment

### 5. `RELEASE_v1.0.0.md`
**Purpose**: Quick reference guide specifically for v1.0.0 release

**Contents**:
- Prerequisites checklist
- Two release options (automated script vs manual)
- What happens after pushing the tag
- Monitoring instructions
- Troubleshooting guide
- Post-release tasks

### 6. `CONTRIBUTING.md` (Updated)
**Purpose**: Added release process section for maintainers

**Addition**:
- Brief release process overview
- Links to detailed documentation

## Release Workflow

### For Maintainers

1. **Prepare Release**:
   - Update version in `pyproject.toml`
   - Update `CHANGELOG.md` with release notes
   - Commit and push to main branch
   - Wait for CI to pass

2. **Create Release**:
   - Option A: Run `./scripts/release.sh`
   - Option B: Manually create and push tag

3. **Monitor**:
   - Check GitHub Actions for workflow status
   - Verify GitHub Release creation
   - Verify PyPI publication (if configured)

### Automated Steps (After Tag Push)

1. GitHub Actions workflow triggers
2. Package is built
3. Release notes extracted from CHANGELOG
4. GitHub Release created with:
   - Title: version tag
   - Body: extracted release notes
   - Assets: built packages
5. Package published to PyPI (optional)

## Configuration Requirements

### Required
- Version must be in `pyproject.toml`: `version = "X.Y.Z"`
- CHANGELOG entry must exist: `## [X.Y.Z] - YYYY-MM-DD`
- Git tag must follow pattern: `vX.Y.Z`

### Optional
- `PYPI_API_TOKEN` GitHub secret for PyPI publishing

## Testing

All components have been validated:
- ✅ YAML syntax: `.github/workflows/release.yml`
- ✅ Bash syntax: `scripts/release.sh`
- ✅ Release notes extraction: Works with current CHANGELOG format
- ✅ Script is executable: `chmod +x` applied

## Current Status

For v1.0.0 release:
- ✅ Version set to `1.0.0` in `pyproject.toml`
- ✅ CHANGELOG has entry for `[1.0.0] - 2026-01-18`
- ✅ Automated workflow configured
- ✅ Documentation complete
- ✅ Release script ready

**Ready to release**: Run `./scripts/release.sh` or manually push tag `v1.0.0`

## Benefits

1. **Consistency**: Every release follows the same process
2. **Automation**: Minimal manual steps required
3. **Documentation**: Clear instructions for all scenarios
4. **Safety**: Validation checks prevent common mistakes
5. **Traceability**: Git tags link releases to code state
6. **Distribution**: Automatic PyPI publishing

## Future Improvements

Potential enhancements:
- Add pre-release support (alpha, beta, rc)
- Automated version bumping
- Changelog generation from commits
- Release notes preview before publishing
- Integration tests for workflow
- Docker image publishing
- Documentation site deployment

## References

- [Semantic Versioning](https://semver.org/)
- [Keep a Changelog](https://keepachangelog.com/)
- [GitHub Actions - Publishing packages](https://docs.github.com/en/actions/publishing-packages)
- [softprops/action-gh-release](https://github.com/softprops/action-gh-release)
