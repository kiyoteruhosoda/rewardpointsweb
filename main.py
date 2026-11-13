"""Development entry point.

In production, use ``uvicorn asgi:app`` (or Gunicorn + UvicornWorker).

To start during development::

    uv run python main.py
"""

import uvicorn
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    uvicorn.run(
        "asgi:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
