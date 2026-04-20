#!/bin/bash
# Clean up redundant files and prepare for git push

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "Cleaning up redundant files..."

rm -f COMPLETE_FIX.md CONNECTION_FIXED.md MISTRAL_SETUP.md SETUP_COMPLETE.md QUICKSTART.md
rm -f test-mistral.sh test_connection.sh
rm -f restart-backend.sh restart.sh start-all.sh
rm -f backend/test_api_key.py backend/test_import.py

echo "Cleanup complete"
echo ""
echo "Removed:"
echo "  - Redundant documentation files"
echo "  - Duplicate restart scripts"
echo "  - Legacy test helper files"
echo ""
echo "Current git status:"
git status --short

echo ""
read -p "Stage all changes and commit? (y/n): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]
then
    echo ""
    echo "Staging changes..."
    git add -A

    echo ""
    echo "Committing..."
    git commit -m "chore: repository cleanup and structure normalization"

    echo ""
    read -p "Push to remote? (y/n): " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]
    then
        echo ""
        echo "Pushing to GitHub..."
        git push origin main
        echo ""
        echo "Done. Changes pushed successfully."
    else
        echo "Changes committed but not pushed."
        echo "Run 'git push origin main' when ready."
    fi
else
    echo "No changes committed."
fi
