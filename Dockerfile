FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create config.cfg from environment variables at runtime
CMD bash -c "\
mkdir -p locales/compiled && \
echo \"# -*- coding: utf-8 -*-\" > config.cfg && \
echo \"DC_BOT_TOKEN = '${DC_BOT_TOKEN}'\" >> config.cfg && \
echo \"DC_CLIENT_ID = '${DC_CLIENT_ID}'\" >> config.cfg && \
echo \"DC_OWNER_ID = '${DC_OWNER_ID}'\" >> config.cfg && \
echo \"DB_URI = '${DB_URI}'\" >> config.cfg && \
echo \"LOG_LEVEL = 'INFO'\" >> config.cfg && \
python PUBobot2.py"

