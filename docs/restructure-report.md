# Repository Restructure Report

## New top-level layout
- backend/
- frontend/
- scripts/
- tests/
- docs/
- data/
- README.md
- .gitignore

## Moved and renamed files

### Moved to scripts/
- check-status.sh -> scripts/check-status.sh
- cleanup-and-push.sh -> scripts/cleanup-and-push.sh
- git-push.sh -> scripts/git-push.sh
- restart-all.sh -> scripts/restart-all.sh
- restart-backend-with-conversations.sh -> scripts/restart-backend-with-conversations.sh
- test-conversations.sh -> scripts/test-conversations.sh
- find_timetable.py -> scripts/find_timetable.py

### Moved to tests/backend/
- test_mood_detection.py -> tests/backend/test_mood_detection.py
- test_past_conversations.py -> tests/backend/test_past_conversations.py
- backend/test_confidence_tier_bounds.py -> tests/backend/test_confidence_tier_bounds.py
- backend/test_conversations.py -> tests/backend/test_conversations.py
- backend/test_mirror_confidence_updates.py -> tests/backend/test_mirror_confidence_updates.py
- backend/test_mirror_identity_mode.py -> tests/backend/test_mirror_identity_mode.py
- backend/test_mirror_mode.py -> tests/backend/test_mirror_mode.py
- backend/test_pdf.py -> tests/backend/test_pdf.py

### Consolidated into docs/
- ARCHITECTURE_FIX_COMPLETE.md -> docs/architecture-fix.md
- CONVERSATION_HISTORY_FIX.md -> docs/conversation-history.md
- PAST_CONVERSATIONS_FEATURE.md -> docs/past-conversations.md
- PERSONA_QUICKSTART.md -> docs/persona-quickstart.md
- PERSONA_SYSTEM.md -> docs/persona-system.md
- backend/ERROR_HANDLING_IMPROVEMENTS.md -> docs/error-handling-improvements.md
- frontend/BACKEND_CORS_FIX.md -> docs/backend-cors-fix.md

## Deleted redundant files
- ARCHITECTURE_FIX_SUMMARY.md
- CONVERSATION_HISTORY_IMPLEMENTATION.md
- PAST_CONVERSATIONS_IMPLEMENTATION.md
- test_output_2.pdf (generated artifact; now generated to data/ by tests/backend/test_pdf.py)

## Updated files
- README.md
- .gitignore

## Notes
- Scripts were adjusted to resolve repo root dynamically after relocation.
- Tests were updated to import backend modules from tests/backend using backend path insertion.
- PDF test output path now targets data/test_output_2.pdf.
- Existing virtual environment folders were retained in filesystem due tool execution limitations and are now ignored by .gitignore.
