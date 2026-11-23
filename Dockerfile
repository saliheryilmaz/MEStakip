FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# mysqlclient/psycopg2 derlemesi için sistem paketleri + Node.js kurulumu
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    default-libmysqlclient-dev \
    libpq-dev \
    pkg-config \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Önce sadece bağımlılık dosyalarını kopyala (Docker cache için daha hızlı build)
COPY requirements.txt package.json package-lock.json* ./
RUN pip install --no-cache-dir -r requirements.txt
RUN npm ci

# Şimdi projenin tamamını kopyala
COPY . .

ENV SECRET_KEY=build-time-only-not-for-runtime \
    DEBUG=False \
    ALLOWED_HOSTS=localhost

RUN npm run build && python manage.py collectstatic --noinput
RUN sed -i 's/\r$//' /app/docker/entrypoint.sh && chmod +x /app/docker/entrypoint.sh

ENV PORT=8000
EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["web"]
