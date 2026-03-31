FROM python:3.12-slim

WORKDIR /app

# Chromium & System‑Dependencies für Playwright
RUN apt-get update && apt-get install -y     chromium     libnss3     libatk1.0-0     libatk-bridge2.0-0     libcups2     libdrm2     libxkbcommon0     libxcomposite1     libxdamage1     libxrandr2     libgbm1     && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 1946

CMD ["uvicorn", "web.main:app", "--host", "0.0.0.0", "--port", "1946", "--proxy-headers", "--forwarded-allow-ips=*"]