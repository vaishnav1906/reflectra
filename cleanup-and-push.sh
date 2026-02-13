#!/bin/bash
# Clean up redundant files and prepare for git push

echo "🧹 Cleaning up redundant files..."

# Remove redundant documentation files
rm -f COMPLETE_FIX.md CONNECTION_FIXED.md MISTRAL_SETUP.md SETUP_COMPLETE.md QUICKSTART.md

# Remove test connection scripts (keep check-status.sh)
rm -f test-mistral.sh test_connection.sh

# Remove redundant restart scripts (keep restart-all.sh)
rm -f restart-backend.sh restart.sh start-all.sh

# Remove backend test files
rm -f backend/test_api_key.py backend/test_import.py

echo "✅ Cleanup complete!"
echo ""
echo "📦 Removed:"
echo "  - Redundant documentation files"
echo "  - Duplicate restart scripts"
echo "  - Test files"
echo ""
echo "📂 Keeping:"
echo "  - README.md (main documentation)"
echo "  - check-status.sh (status checker)"
echo "  - restart-all.sh (service launcher)"
echo ""

# Show git status
echo "🔍 Current git status:"
git status --short

echo ""
read -p "Stage all changes and commit? (y/n): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]
then
    echo ""
    echo "📦 Staging changes..."
    git add -A
    
    echo ""
    echo "📝 Committing..."
    git commit -m "feat: Add Mistral AI integration and clean up project

- Integrate Mistral AI for chat responses
- Simplify backend to use only Mistral (removed OpenAI/Anthropic)  
- Update gitignore files for better security
- Clean up redundant documentation and scripts
- Add comprehensive README with setup instructions
- Improve error handling and logging
- Fix .env loading and API key validation"
    
    echo ""
    read -p "Push to remote? (y/n): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]
    then
        echo ""
        echo "🚀 Pushing to GitHub..."
        git push origin main
        echo ""
        echo "✅ Done! Changes pushed successfully."
    else
        echo "⏸️  Changes committed but not pushed."
        echo "   Run 'git push origin main' when ready."
    fi
else
    echo "❌ No changes committed."
fi
