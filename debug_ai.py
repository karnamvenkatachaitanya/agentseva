
import traceback
import sys
import os

# Add current directory to path so we can import backend modules
sys.path.append(os.getcwd())

try:
    print("Attempting to import backend.ai_engine...")
    from backend.ai_engine import get_ai_engine
    print("Import successful. Attempting to get instance...")
    engine = get_ai_engine()
    print("Engine loaded successfully!")
    print("Testing query...")
    res = engine.query("Hello")
    print("Query result:", res)
except Exception:
    print("CRITICAL FAILURE:")
    traceback.print_exc()
