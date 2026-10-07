# run_app.py — نقطة تشغيل مخصصة
import sys
import asyncio
import os
# ⭐ IMPORTANT: قبل أي استيراد لـ streamlit
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# دلوقتي نقدر نشغل streamlit
import streamlit.web.cli as stcli

if __name__ == "__main__":
    port = os.environ.get("PORT", "8501")

    sys.argv = [
        "streamlit",
        "run",
        "Lastv.py",
        f"--server.port={port}",
        "--server.address=0.0.0.0",
        "--server.headless=true"
    ]

    sys.exit(stcli.main())