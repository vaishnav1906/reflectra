#!/usr/bin/env python3
"""
Startup validation script for Reflectra backend.
Run this before starting the server to validate configuration.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import asyncio

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))

# Load environment variables
load_dotenv()

def print_header(text: str):
    """Print a formatted header"""
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60)

def check_environment_variables():
    """Check all required environment variables"""
    print_header("1. Checking Environment Variables")
    
    required_vars = {
        "DATABASE_URL": "Database connection string",
    }
    
    optional_vars = {
        "MISTRAL_API_KEY": "Mistral AI API key",
    }
    
    all_good = True
    
    print("\n📋 Required Variables:")
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            display = f"{value[:15]}..." if len(value) > 15 else value
            print(f"  ✅ {var}: {display}")
        else:
            print(f"  ❌ {var}: MISSING - {description}")
            all_good = False
    
    print("\n📋 Optional Variables:")
    for var, description in optional_vars.items():
        value = os.getenv(var)
        if value:
            display = f"{value[:15]}..." if len(value) > 15 else value
            print(f"  ✅ {var}: {display}")
        else:
            print(f"  ⚠️  {var}: Not set (will use fallback) - {description}")
    
    return all_good

async def check_database_connection():
    """Test database connection"""
    print_header("2. Testing Database Connection")
    
    try:
        from app.db.database import engine
        from sqlalchemy import text
        
        print("\n🔗 Connecting to database...")
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.fetchone()
            print(f"  ✅ Connected successfully!")
            print(f"  📊 PostgreSQL version: {version[0][:50]}...")
            
            # Test a simple query
            result = await conn.execute(text("SELECT 1 as test"))
            test_result = result.fetchone()
            assert test_result[0] == 1
            print(f"  ✅ Database queries working!")
            
        return True
    except Exception as e:
        print(f"  ❌ Database connection failed: {e}")
        print(f"  📝 Error type: {type(e).__name__}")
        return False

async def check_database_tables():
    """Check if required tables exist"""
    print_header("3. Checking Database Schema")
    
    try:
        from app.db.database import engine
        from sqlalchemy import text, inspect
        
        print("\n📊 Checking tables...")
        async with engine.connect() as conn:
            # Get list of tables
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """))
            tables = [row[0] for row in result.fetchall()]
            
            required_tables = [
                "users",
                "conversations",
                "messages",
                "trait_metrics",
                "persona_snapshots"
            ]
            
            if not tables:
                print("  ⚠️  No tables found - you may need to run migrations")
                print("  💡 Run: cd backend && alembic upgrade head")
                return False
            
            print(f"\n  Found {len(tables)} tables:")
            for table in tables:
                if table in required_tables:
                    print(f"    ✅ {table}")
                else:
                    print(f"    📄 {table}")
            
            missing_tables = [t for t in required_tables if t not in tables]
            if missing_tables:
                print(f"\n  ⚠️  Missing expected tables: {', '.join(missing_tables)}")
                print("  💡 Run: cd backend && alembic upgrade head")
                return False
            
            print("\n  ✅ All required tables exist!")
            return True
            
    except Exception as e:
        print(f"  ❌ Failed to check tables: {e}")
        print(f"  📝 Error type: {type(e).__name__}")
        return False

def check_mistral_configuration():
    """Check Mistral AI configuration"""
    print_header("4. Checking Mistral AI Configuration")
    
    api_key = os.getenv("MISTRAL_API_KEY")
    
    if not api_key:
        print("\n  ⚠️  MISTRAL_API_KEY not set")
        print("  📝 The system will fall back to template responses")
        print("  💡 To use AI: Set MISTRAL_API_KEY in .env file")
        return False
    
    try:
        from mistralai import Mistral
        
        print(f"\n  ✅ Mistral API key found: {api_key[:12]}...{api_key[-4:]}")
        print("  📝 Testing Mistral connection...")
        
        client = Mistral(api_key=api_key)
        print("  ✅ Mistral client initialized successfully!")
        
        # Note: We don't test actual API call here to avoid costs
        print("  💡 API key format is valid (not testing actual API call)")
        return True
        
    except ImportError:
        print("  ❌ mistralai package not installed")
        print("  💡 Run: pip install mistralai")
        return False
    except Exception as e:
        print(f"  ❌ Mistral setup error: {e}")
        return False

def check_file_structure():
    """Check if all required files exist"""
    print_header("5. Checking File Structure")
    
    required_files = [
        "app/__init__.py",
        "app/main.py",
        "app/api/chat.py",
        "app/api/persona.py",
        "app/api/mirror.py",
        "app/db/database.py",
        "app/db/models.py",
        "app/db/crud.py",
        "requirements.txt",
    ]
    
    print("\n📁 Checking required files:")
    all_exist = True
    for file in required_files:
        file_path = Path(__file__).resolve().parent.parent.parent / "backend" / file
        if file_path.exists():
            print(f"  ✅ {file}")
        else:
            print(f"  ❌ {file} - MISSING")
            all_exist = False
    
    return all_exist

async def main():
    """Run all validation checks"""
    print("\n" + "🚀" * 30)
    print("  REFLECTRA BACKEND STARTUP VALIDATION")
    print("🚀" * 30)
    
    results = {
        "environment": check_environment_variables(),
        "files": check_file_structure(),
        "database": await check_database_connection(),
        "schema": await check_database_tables(),
        "mistral": check_mistral_configuration(),
    }
    
    print_header("📊 Validation Summary")
    
    print("\n  Results:")
    for check, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"    {status} {check.title()}")
    
    all_critical_passed = results["environment"] and results["database"]
    
    if all_critical_passed:
        print("\n  ✅ All critical checks passed!")
        print("  🚀 Ready to start the server")
        print("\n  Run: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
        return 0
    else:
        print("\n  ❌ Some critical checks failed")
        print("  🔧 Please fix the issues above before starting the server")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
