FROM python:3.11-slim

# mysqlclient derlemesi için sistem paketleri + Node.js kurulumu
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    default-libmysqlclient-dev \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Önce sadece bağımlılık dosyalarını kopyala (Docker cache için daha hızlı build)
COPY requirements.txt package.json package-lock.json* ./
RUN pip install --no-cache-dir -r requirements.txt
RUN npm install

# Şimdi projenin tamamını kopyala
COPY . .

# Build-time environment variable'lar (Coolify bunları otomatik geçiyor)
ARG SECRET_KEY
ARG DEBUG
ARG ALLOWED_HOSTS
ARG DB_NAME
ARG DB_USER
ARG DB_PASSWORD
ARG DB_HOST

ENV SECRET_KEY=$SECRET_KEY \
    DEBUG=$DEBUG \
    ALLOWED_HOSTS=$ALLOWED_HOSTS \
    DB_NAME=$DB_NAME \
    DB_USER=$DB_USER \
    DB_PASSWORD=$DB_PASSWORD \
    DB_HOST=$DB_HOST

RUN npm run build && python manage.py collectstatic --noinput

ENV PORT=8000
EXPOSE 8000

CMD ["gunicorn", "metis_admin.wsgi:application", "-c", "gunicorn.conf.py"]
