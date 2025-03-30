FROM python:3.10-slim

# نصب وابستگی‌های مورد نیاز
RUN apt-get update && apt-get install -y \
    python3-distutils \
    wget \
    gnupg \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# نصب کروم و کروم درایور
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# نصب کروم درایور
RUN CHROME_DRIVER_VERSION=`curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE` \
    && wget -N chromedriver.storage.googleapis.com/$CHROME_DRIVER_VERSION/chromedriver_linux64.zip -P ~/ \
    && unzip ~/chromedriver_linux64.zip -d ~/ \
    && rm ~/chromedriver_linux64.zip \
    && mv -f ~/chromedriver /usr/local/bin/chromedriver \
    && chmod +x /usr/local/bin/chromedriver

# تنظیم مسیر کاری
WORKDIR /app

# کپی کردن فایل‌های پروژه
COPY . .

# نصب وابستگی‌های پایتون
RUN pip install --no-cache-dir email-validator flask flask-sqlalchemy gunicorn psycopg2-binary python-telegram-bot requests selenium undetected-chromedriver==3.5.0 webdriver-manager twilio

# تنظیم متغیرهای محیطی برای کروم
ENV CHROME_BIN=/usr/bin/google-chrome-stable
ENV CHROMEDRIVER_PATH=/usr/local/bin/chromedriver
ENV PYTHONUNBUFFERED=1

# اجرای فایل رفع مشکل distutils و سپس راه‌اندازی سرور
# اجرای برنامه با تنظیمات ساده‌تر برای ربات تلگرام
CMD python fix-distutils.py && gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 1 --threads 2 --timeout 90 --reload main:app