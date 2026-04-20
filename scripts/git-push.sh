#!/bin/bash
# Push all changes to git

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "Checking git status..."
git status

echo ""
read -p "Continue with commit and push? (y/n): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]
then
    echo ""
    echo "Adding files to git..."
    git add .

    echo ""
    echo "Committing changes..."
    git commit -m "chore: repository maintenance updates"

    echo ""
    echo "Pushing to remote..."
    git push origin main

    echo ""
    echo "Done. Changes pushed to GitHub."
else
    echo "Push cancelled."
fi
