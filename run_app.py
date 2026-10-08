import sys
import asyncio
import os

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import streamlit.web.cli as stcli


if __name__ == "__main__":
    port = os.environ.get("PORT", "8501")

    # مجلد المشروع الحالي
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # ابحث عن الملف محليًا أو على Railway
    candidates = [
        os.path.join(base_dir, "lastv.py"),
        os.path.join(base_dir, "Lastv.py"),
        "/app/lastv.py",
        "/app/Lastv.py",
    ]

    app_path = None

    for candidate in candidates:
        if os.path.isfile(candidate):
            app_path = candidate
            break

    if not app_path:
        print("❌ لم يتم العثور على lastv.py أو Lastv.py")
        print("📁 الملفات الموجودة في:", base_dir)
        print(os.listdir(base_dir))
        sys.exit(1)

    print(f"✅ Starting Streamlit app: {app_path}")

    sys.argv = [
        "streamlit",
        "run",
        app_path,
        f"--server.port={port}",
        "--server.address=0.0.0.0",
        "--server.headless=true",
        "--server.enableCORS=false",
        "--server.enableXsrfProtection=false",
    ]

    sys.exit(stcli.main())