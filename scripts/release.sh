#!/bin/bash

# KnowGraph Release Script
# This script helps automate the release process for KnowGraph

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_info() {
    echo -e "${GREEN}ℹ${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
check_prerequisites() {
    print_info "Checking prerequisites..."
    
    local missing_deps=()
    
    if ! command_exists git; then
        missing_deps+=("git")
    fi
    
    if ! command_exists python; then
        missing_deps+=("python")
    fi
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        print_error "Missing required dependencies: ${missing_deps[*]}"
        exit 1
    fi
    
    print_success "All prerequisites met"
}

# Check if we're on main branch
check_branch() {
    local current_branch=$(git rev-parse --abbrev-ref HEAD)
    
    if [ "$current_branch" != "main" ] && [ "$current_branch" != "master" ]; then
        print_warning "You are not on main/master branch (current: $current_branch)"
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        print_success "On $current_branch branch"
    fi
}

# Check if working directory is clean
check_clean() {
    if ! git diff-index --quiet HEAD --; then
        print_error "Working directory is not clean. Please commit or stash changes."
        exit 1
    fi
    print_success "Working directory is clean"
}

# Pull latest changes
pull_latest() {
    print_info "Pulling latest changes..."
    git pull origin $(git rev-parse --abbrev-ref HEAD)
    print_success "Pulled latest changes"
}

# Get version from pyproject.toml
get_current_version() {
    grep -E '^version = ' pyproject.toml | sed -E 's/version = "(.*)"/\1/'
}

# Check if tag already exists
check_tag_exists() {
    local tag=$1
    if git rev-parse "$tag" >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Main release function
create_release() {
    local version=$(get_current_version)
    local tag="v$version"
    
    print_info "Current version in pyproject.toml: $version"
    
    # Check if tag already exists
    if check_tag_exists "$tag"; then
        print_error "Tag $tag already exists!"
        print_info "If you want to recreate it, run:"
        print_info "  git tag -d $tag"
        print_info "  git push origin :refs/tags/$tag"
        exit 1
    fi
    
    # Confirm release
    echo
    print_warning "This will create and push tag: $tag"
    read -p "Continue? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Release cancelled"
        exit 0
    fi
    
    # Create annotated tag
    print_info "Creating annotated tag $tag..."
    git tag -a "$tag" -m "Release $tag"
    print_success "Tag created: $tag"
    
    # Push tag
    print_info "Pushing tag to origin..."
    git push origin "$tag"
    print_success "Tag pushed: $tag"
    
    echo
    print_success "Release process initiated!"
    print_info "GitHub Actions will now:"
    print_info "  1. Build the package"
    print_info "  2. Create a GitHub release"
    print_info "  3. Publish to PyPI (if configured)"
    echo
    print_info "Monitor the workflow at:"
    print_info "  https://github.com/yunusgungor/knowgraph/actions"
    echo
}

# Main script
main() {
    echo "================================"
    echo "  KnowGraph Release Script"
    echo "================================"
    echo
    
    check_prerequisites
    check_branch
    check_clean
    pull_latest
    
    echo
    create_release
}

# Run main function
main
