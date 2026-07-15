"""Convenience launcher for the Fire & Smoke Detection web POC.

    python run_web.py            # serve on http://localhost:8080
    PORT=9000 python run_web.py  # custom port

Equivalent to `python -m server.main`.
"""

import os

import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    print(f"Fire POC → http://localhost:{port}")
    uvicorn.run("server.main:app", host="0.0.0.0", port=port)
