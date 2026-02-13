"""
Check System Audit Imports
"""
try:
    from app.api.system import router
    print("✅ system_router imported successfully")
except Exception as e:
    import traceback
    print(f"❌ system_router import failed: {e}")
    traceback.print_exc()
