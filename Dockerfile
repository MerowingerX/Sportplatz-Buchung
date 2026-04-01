FROM python:3.12-slim

WORKDIR /app

# Chromium & System‑Dependencies für Playwright
RUN apt-get update && apt-get install -y     chromium     libnss3     libatk1.0-0     libatk-bridge2.0-0     libcups2     libdrm2     libxkbcommon0     libxcomposite1     libxdamage1     libxrandr2     libgbm1     && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Git-Infos als Build-Args einbacken (werden zur Laufzeit als ENV gesetzt)
ARG GIT_COMMIT=unknown
ARG GIT_BRANCH=unknown
ARG GIT_DATE=unknown
ENV GIT_COMMIT=${GIT_COMMIT} GIT_BRANCH=${GIT_BRANCH} GIT_DATE=${GIT_DATE}

EXPOSE 1946

CMD ["uvicorn", "web.main:app", "--host", "0.0.0.0", "--port", "1946", "--proxy-headers", "--forwarded-allow-ips=*"]