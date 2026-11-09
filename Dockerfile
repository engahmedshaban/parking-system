FROM python:3.10-slim-bullseye

WORKDIR /app

# تثبيت أدوات البناء الأساسية لتجنب مشاكل المكتبات
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# نسخ ملف المتطلبات وتثبيتها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات المشروع
COPY . .

# أمر تشغيل التطبيق
CMD ["python", "run_app.py"]