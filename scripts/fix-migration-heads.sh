#!/bin/bash
# =============================================================================
# Fix Alembic Migration Heads
# =============================================================================
# This script fixes the "multiple migration heads" problem that occurs when
# two developers create migrations from the same base revision.
#
# What it does:
#   1. Fetches latest dev branch
#   2. Rebases your branch onto dev
#   3. Checks for multiple migration heads
#   4. If multiple heads exist, creates a merge migration
#   5. Does NOT push - you must do that manually
#
# Usage:
#   ./scripts/fix-migration-heads.sh
#
# After running:
#   git push --force-with-lease
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Print functions
print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${CYAN}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_step() {
    echo -e "${YELLOW}▶${NC} $1"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ️  $1${NC}"
}

# =============================================================================
# Pre-flight Checks
# =============================================================================
print_header "🔍 Pre-flight Checks"

# Check if we're in a git repository
if ! git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
    print_error "Not in a git repository!"
    exit 1
fi

# Get current branch name
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
print_step "Current branch: ${BOLD}$CURRENT_BRANCH${NC}"

# Check if we're on dev (shouldn't run this on dev)
if [ "$CURRENT_BRANCH" = "dev" ]; then
    print_error "You're on the dev branch. Switch to your feature branch first."
    echo "   git checkout <your-feature-branch>"
    exit 1
fi

# Check if we're on main (shouldn't run this on main)
if [ "$CURRENT_BRANCH" = "main" ]; then
    print_error "You're on the main branch. Switch to your feature branch first."
    echo "   git checkout <your-feature-branch>"
    exit 1
fi

# Check for uncommitted changes
if ! git diff-index --quiet HEAD -- 2>/dev/null; then
    print_warning "You have uncommitted changes."
    echo ""
    git status --short
    echo ""
    read -p "Continue anyway? This might cause issues during rebase. (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Aborting. Please commit or stash your changes first."
        exit 1
    fi
fi

# Check if alembic is available
if ! command -v alembic &> /dev/null; then
    print_error "Alembic is not installed or not in PATH."
    echo "   Try: pip install alembic"
    echo "   Or activate your virtual environment first."
    exit 1
fi

print_success "Pre-flight checks passed"

# =============================================================================
# Step 1: Fetch latest dev
# =============================================================================
print_header "📥 Step 1: Fetch Latest Dev"

print_step "Fetching origin/dev..."
if git fetch origin dev 2>&1; then
    print_success "Fetched latest dev"
else
    print_error "Failed to fetch dev. Check your network connection."
    exit 1
fi

# =============================================================================
# Step 2: Rebase onto dev
# =============================================================================
print_header "🔄 Step 2: Rebase onto Dev"

print_step "Rebasing $CURRENT_BRANCH onto origin/dev..."
echo ""

# Store the current commit for reference
BEFORE_REBASE=$(git rev-parse HEAD)

if git rebase origin/dev 2>&1; then
    print_success "Rebase completed successfully"
else
    print_error "Rebase failed! You have conflicts to resolve."
    echo ""
    echo -e "${YELLOW}To resolve:${NC}"
    echo "   1. Fix the conflicts in the listed files"
    echo "   2. git add <resolved-files>"
    echo "   3. git rebase --continue"
    echo "   4. Run this script again"
    echo ""
    echo -e "${YELLOW}To abort the rebase:${NC}"
    echo "   git rebase --abort"
    exit 1
fi

# =============================================================================
# Step 3: Check for multiple heads
# =============================================================================
print_header "🔎 Step 3: Check Migration Heads"

print_step "Running alembic heads..."
echo ""

# Capture alembic heads output
HEADS_OUTPUT=$(alembic heads 2>&1) || true
HEAD_COUNT=$(echo "$HEADS_OUTPUT" | grep -c "^[a-f0-9]" || echo "0")

echo "$HEADS_OUTPUT"
echo ""

if [ "$HEAD_COUNT" -le 1 ]; then
    print_header "✅ Result: No Multiple Heads Detected"
    echo ""
    print_success "Your migrations are clean!"
    echo ""
    
    # Check if rebase made any changes
    AFTER_REBASE=$(git rev-parse HEAD)
    if [ "$BEFORE_REBASE" != "$AFTER_REBASE" ]; then
        print_info "Your branch was rebased onto the latest dev."
        echo ""
        echo -e "${YELLOW}Next steps:${NC}"
        echo "   git push --force-with-lease"
    else
        print_info "No changes were needed."
    fi
    
    exit 0
fi

# =============================================================================
# Step 4: Merge the heads
# =============================================================================
print_header "🔧 Step 4: Merging Migration Heads"

print_warning "Multiple migration heads detected ($HEAD_COUNT heads)"
echo ""
print_step "Creating merge migration..."
echo ""

# Generate a descriptive merge message
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
MERGE_MESSAGE="merge_heads_${TIMESTAMP}"

if alembic merge heads -m "$MERGE_MESSAGE" 2>&1; then
    print_success "Merge migration created!"
    echo ""
    
    # Find the new merge migration file
    NEW_MIGRATION=$(ls -t alembic/versions/*.py | head -1)
    print_info "New migration file: $NEW_MIGRATION"
else
    print_error "Failed to create merge migration!"
    echo ""
    echo "This might happen if:"
    echo "   - The heads have conflicting dependencies"
    echo "   - There's an issue with the migration files"
    echo ""
    echo "Try manually running:"
    echo "   alembic merge heads -m \"merge_migrations\""
    exit 1
fi

# =============================================================================
# Step 5: Verify the fix
# =============================================================================
print_header "✔️  Step 5: Verify Fix"

print_step "Checking heads again..."
echo ""

HEADS_AFTER=$(alembic heads 2>&1) || true
HEAD_COUNT_AFTER=$(echo "$HEADS_AFTER" | grep -c "^[a-f0-9]" || echo "0")

echo "$HEADS_AFTER"
echo ""

if [ "$HEAD_COUNT_AFTER" -eq 1 ]; then
    print_success "Migration heads successfully merged!"
else
    print_error "Still have multiple heads. Manual intervention required."
    exit 1
fi

# =============================================================================
# Summary and Next Steps
# =============================================================================
print_header "📋 Summary"

echo ""
print_success "Migration heads fixed!"
echo ""
echo -e "${CYAN}Changes made:${NC}"
echo "   1. Rebased your branch onto latest dev"
echo "   2. Created merge migration: $MERGE_MESSAGE"
echo ""

# Check git status
STAGED=$(git diff --cached --name-only | wc -l | tr -d ' ')
UNSTAGED=$(git diff --name-only | wc -l | tr -d ' ')

if [ "$UNSTAGED" -gt 0 ]; then
    echo -e "${YELLOW}Unstaged changes detected:${NC}"
    git status --short
    echo ""
fi

print_header "🚀 Next Steps"

echo ""
echo -e "${BOLD}1. Review the changes:${NC}"
echo "   git status"
echo "   git diff alembic/versions/"
echo ""
echo -e "${BOLD}2. Stage and commit the merge migration:${NC}"
echo "   git add alembic/versions/"
echo "   git commit -m \"Merge migration heads\""
echo ""
echo -e "${BOLD}3. Push your changes:${NC}"
echo "   git push --force-with-lease"
echo ""
echo -e "${YELLOW}⚠️  Note: Force push is required because we rebased.${NC}"
echo -e "${YELLOW}   Always use --force-with-lease for safety.${NC}"
echo ""

