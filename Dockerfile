# 1. استخدام صورة أحدث من Debian (Bookworm)
FROM python:3.11-slim-bookworm

WORKDIR /app

# 2. تثبيت أدوات البناء الأساسية
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 3. نسخ ملف المتطلبات وتثبيتها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. نسخ باقي ملفات المشروع
COPY . .

# 5. أمر تشغيل التطبيق
CMD ["python", "run_app.py"]