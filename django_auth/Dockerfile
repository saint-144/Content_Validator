FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    default-mysql-client \
    build-essential \
    pkg-config \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x entrypoint.sh

EXPOSE 8001

ENTRYPOINT ["./entrypoint.sh"]
