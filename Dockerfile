FROM python:3.12-slim

# Mencegah Python membuat file .pyc dan memastikan log langsung tampil (unbuffered)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Instal dependensi sistem minimal untuk kompilasi/libpq bila diperlukan
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

# Salin definisi dependensi terlebih dahulu untuk memanfaatkan Docker layer cache
COPY pyproject.toml requirements.txt ./

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Salin kode aplikasi, migrasi database, dan skrip utilitas
COPY app ./app
COPY db ./db
COPY scripts ./scripts

# Buat user non-root untuk keamanan runtime
RUN useradd --create-home --shell /bin/bash wmsuser \
    && chown -R wmsuser:wmsuser /app

USER wmsuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

