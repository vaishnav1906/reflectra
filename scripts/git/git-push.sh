#!/bin/bash
# Push all changes to git

echo "🔍 Checking git status..."
git status

echo ""
read -p "Continue with commit and push? (y/n): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]
then
    echo ""
    echo "📦 Adding files to git..."
    git add .
    
    echo ""
    echo "📝 Committing changes..."
    git commit -m "feat: Add Mistral AI integration and clean up project structure

- Integrate Mistral AI for chat responses
- Update gitignore files for better security
- Clean up redundant documentation
- Add comprehensive setup instructions
- Improve error handling and logging"
    
    echo ""
    echo "🚀 Pushing to remote..."
    git push origin main
    
    echo ""
    echo "✅ Done! Changes pushed to GitHub."
else
    echo "❌ Push cancelled."
fi
