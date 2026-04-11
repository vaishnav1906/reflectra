# Error Handling & Debugging Improvements

## Summary
This document describes the comprehensive error handling and debugging improvements made to the Reflectra backend.

## Changes Made

### 1. ✅ Comprehensive Error Handling in Chat Endpoint (`app/api/chat.py`)

**Improvements:**
- Added top-level try-except wrapper around entire `/chat` endpoint
- Added UUID validation with specific error messages
- Added nested error handling for:
  - Database operations (conversation creation/retrieval)
  - LLM response generation
  - Persona service updates
  - Mirror engine calls
  - Message storage
- All exceptions are now caught and logged with:
  - Error type
  - Full stack trace (`exc_info=True`)
  - Contextual information
- Returns structured JSON error responses instead of crashing

**Error Flow:**
```
Request → Validate Mode → Validate UUIDs → Handle Conversation → Generate Response → Store Messages → Return Response
           ↓                ↓                  ↓                    ↓                  ↓             ↓
         400 Error        400 Error         404/500 Error       Fallback Templates   500 Error   JSON Response
```

### 2. ✅ Environment Variable Validation at Startup (`app/main.py`)

**New Function:** `validate_environment()`

**Features:**
- Validates all required environment variables before server starts
- Checks optional variables and warns if missing
- Displays partial values for security (first 10 characters)
- **Exits immediately** if critical variables are missing
- Provides clear instructions for fixing issues

**Validated Variables:**
- ✅ **Required:** `DATABASE_URL`
- ⚠️ **Optional:** `MISTRAL_API_KEY` (falls back to templates if missing)

### 3. ✅ Database Connection Validation (`app/main.py` + `app/db/database.py`)

**Startup Event:**
- Added `@app.on_event("startup")` handler
- Tests database connection on server start
- Executes simple query to verify connectivity
- Logs connection status

**Enhanced get_db() Dependency:**
- Added try-except-finally for session management
- Ensures sessions are properly closed even on errors
- Added debug logging for session lifecycle

**Database Engine Improvements:**
- Added logging during engine initialization
- Better error messages if engine creation fails
- Disabled SQL echo by default (set `echo=True` for debugging)

### 4. ✅ Enhanced Logging Throughout

**Added Logging:**
- Request start with mode and user_id
- Message content preview (first 50 chars)
- UUID conversion success/failure
- Database operation status
- LLM response generation
- Persona service updates
- Cache invalidation
- Error details with full stack traces

**Log Levels:**
- `INFO`: Normal operations
- `WARNING`: Recoverable issues (fallbacks)
- `ERROR`: Failures requiring attention
- `DEBUG`: Detailed session management

### 5. ✅ Startup Validation Script (`validate_startup.py`)

**New Script:** Comprehensive pre-flight checks before starting the server

**Checks:**
1. **Environment Variables**
   - Verifies required and optional variables
   - Shows partial values securely
   
2. **Database Connection**
   - Tests connection
   - Shows PostgreSQL version
   - Runs test query

3. **Database Schema**
   - Lists all tables
   - Verifies required tables exist
   - Suggests running migrations if needed

4. **Mistral AI Configuration**
   - Checks if API key is set
   - Validates mistralai package installation
   - Initializes client to verify format

5. **File Structure**
   - Verifies all critical files exist
   - Checks for missing files

**Usage:**
```bash
cd /workspaces/reflectra/backend
python validate_startup.py
```

**Output:** Clear pass/fail for each check with actionable fix suggestions

## Error Response Format

All errors now return structured JSON:

```json
{
  "detail": "Error description with context"
}
```

**Common HTTP Status Codes:**
- `400`: Bad Request (invalid UUIDs, invalid mode, mode mismatch)
- `404`: Not Found (conversation doesn't exist)
- `500`: Internal Server Error (database errors, unexpected exceptions)

## Fallback Mechanisms

The system now has multiple fallback layers:

1. **LLM Failures** → Template responses
2. **Mirror Engine Fails** → Local mirror reply function
3. **Title Generation Fails** → First 40 chars of message
4. **Persona Update Fails** → Continues without breaking chat

## Testing the Improvements

### 1. Run Validation Script
```bash
cd /workspaces/reflectra/backend
python validate_startup.py
```

### 2. Start Server
```bash
cd /workspaces/reflectra/backend
bash run.sh
```

### 3. Check Endpoints

**Health Check:**
```bash
curl http://localhost:8000/
curl http://localhost:8000/health
```

**API Docs:**  
Open: http://localhost:8000/docs

**Test Chat:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "text": "Hello, how are you?",
    "mode": "reflection"
  }'
```

## Debugging Tips

### Check Logs
The server now provides detailed logs for:
- All incoming requests
- Database operations
- LLM calls
- Error stack traces

### Common Issues and Solutions

| Issue | Likely Cause | Solution |
|-------|-------------|----------|
| `DATABASE_URL is not set` | Missing .env file | Create `.env` with `DATABASE_URL=...` |
| `Conversation not found` | Invalid conversation_id | Check UUID format and existence |
| `Invalid UUID format` | Non-UUID string passed | Use valid UUID v4 format |
| `Mode mismatch` | Conversation mode ≠ request mode | Use consistent mode for conversation |
| `Failed to store message` | Database connection issue | Check DATABASE_URL and DB status |
| `Mirror engine failed` | Persona system issue | Check logs; will fall back to templates |

### Enable SQL Query Logging

Edit `app/db/database.py`:
```python
engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=True,  # ← Enable this
)
```

### Enable Debug Logging

Edit `app/main.py`:
```python
logging.basicConfig(
    level=logging.DEBUG,  # ← Change from INFO to DEBUG
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
```

## Files Modified

1. `/workspaces/reflectra/backend/app/api/chat.py` - Comprehensive error handling
2. `/workspaces/reflectra/backend/app/main.py` - Environment validation & startup checks
3. `/workspaces/reflectra/backend/app/db/database.py` - Enhanced database session handling

## Files Created

1. `/workspaces/reflectra/backend/validate_startup.py` - Pre-flight validation script
2. `/workspaces/reflectra/backend/ERROR_HANDLING_IMPROVEMENTS.md` - This document

## Next Steps

1. ✅ Run validation script
2. ✅ Start the backend server
3. ✅ Test `/docs` endpoint
4. ✅ Test `/chat` endpoint
5. ✅ Verify frontend can communicate with backend
6. ✅ Monitor logs for any remaining issues

## Monitoring Production

**Key Metrics to Monitor:**
- Error rate in logs (search for "❌")
- Database connection failures
- LLM response fallback frequency
- Response times for `/chat` endpoint

**Alert Conditions:**
- DATABASE_URL not set (server won't start)
- DB connection failures (check pooler.supabase.com)
- High rate of 500 errors (check logs for patterns)
- MISTRAL_API_KEY missing (templates only, no AI responses)

---

**Status:** ✅ All improvements implemented and tested
**Ready for:** Production deployment
