# run_app.py — نقطة تشغيل مخصصة
import sys
import asyncio

# ⭐ IMPORTANT: قبل أي استيراد لـ streamlit
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# دلوقتي نقدر نشغل streamlit
import streamlit.web.cli as stcli

if __name__ == "__main__":
    sys.argv = ["streamlit", "run", "lastv.py",
                "--server.port=8501",
                "--server.headless=true"]
    sys.exit(stcli.main())