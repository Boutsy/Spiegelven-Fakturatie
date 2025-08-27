FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
  && rm -rf /var/lib/apt/lists/*

RUN curl -sL -o /usr/local/bin/tailwindcss \
  https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.10/tailwindcss-linux-x64 \
  && chmod +x /usr/local/bin/tailwindcss

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
