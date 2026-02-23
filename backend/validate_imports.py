#!/usr/bin/env python3
"""Validate that all persona system imports work correctly."""

import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

print("Testing imports...")

try:
    print("  ✓ Importing constants...")
    from app.constants import TRAIT_LIST, TRAIT_GROUPS
    
    print("  ✓ Importing models...")
    from app.db.models import UserPersonaMetric, PersonaSnapshot
    
    print("  ✓ Importing repository...")
    from app.repository.persona_repository import PersonaRepository
    
    print("  ✓ Importing trait extraction service...")
    from app.services.trait_extraction_service import extract_traits
    
    print("  ✓ Importing persona update service...")
    from app.services.persona_update_service import update_traits
    
    print("  ✓ Importing snapshot service...")
    from app.services.snapshot_service import generate_persona_snapshot
    
    print("  ✓ Importing mirror engine...")
    from app.services.mirror_engine import generate_mirror_response
    
    print("  ✓ Importing persona API routes...")
    from app.api.persona import router as persona_router
    
    print("  ✓ Importing mirror API routes...")
    from app.api.mirror import router as mirror_router
    
    print("\n✅ All imports successful!")
    print(f"\nTrait taxonomy: {len(TRAIT_LIST)} traits")
    print(f"Trait groups: {len(TRAIT_GROUPS)} groups")
    
except ImportError as e:
    print(f"\n❌ Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
