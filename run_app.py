import sys
import asyncio
import os

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import streamlit.web.cli as stcli

if __name__ == "__main__":
    port = os.environ.get("PORT", "8501")

    # ⭐ يدور على الحالتين
    APP_PATH = None
    for cand in ["/app/lastv.py", "/app/Lastv.py"]:
        if os.path.exists(cand):
            APP_PATH = cand
            break

    if not APP_PATH:
        print("❌ lastv.py مش موجود في /app!")
        sys.exit(1)

    print(f"✅ Starting: {APP_PATH}")

    sys.argv = [
        "streamlit", "run", APP_PATH,
        f"--server.port={port}",
        "--server.address=0.0.0.0",
        "--server.headless=true",
        "--server.enableCORS=false",
        "--server.enableXsrfProtection=false"
    ]
    sys.exit(stcli.main())