"""SYLION AEIS server runner."""
import uvicorn
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

if __name__ == "__main__":
    uvicorn.run(
        "sylion.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
