#!/usr/bin/env python
"""
Wrapper script to run the FastAPI backend with proper error handling.
This ensures the Ollama connection doesn't block startup.
"""
import sys
import os

# Set working directory to project root
os.chdir(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info",
    )
