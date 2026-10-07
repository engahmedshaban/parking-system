# run_app.py — نقطة تشغيل مخصصة
import sys
import asyncio
import os

# ⭐ IMPORTANT: قبل أي استيراد لـ streamlit
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import streamlit.web.cli as stcli

if __name__ == "__main__":
    port = os.environ.get("PORT", "8501")

    # ⭐ مسار مطلق
    APP_PATH = "/app/lastv.py"
    if not os.path.exists(APP_PATH):
        # fallback لو الملف في مسار مختلف
        APP_PATH = os.path.join(os.path.dirname(__file__), "lastv.py")

    sys.argv = [
        "streamlit",
        "run",
        APP_PATH,
        f"--server.port={port}",
        "--server.address=0.0.0.0",
        "--server.headless=true",
        "--server.enableCORS=false",
        "--server.enableXsrfProtection=false"
    ]

    sys.exit(stcli.main())