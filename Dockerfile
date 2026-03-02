FROM python:3.12-slim

WORKDIR /app

# Abhängigkeiten zuerst – Layer wird gecacht solange requirements.txt unverändert
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Anwendungscode
COPY . .

# Laufzeit-Verzeichnisse anlegen (werden via Volume vom Host überschrieben)
RUN mkdir -p logs backup Platzbelegung

EXPOSE 1946

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "web.main:app", "--host", "0.0.0.0", "--port", "1946"]
