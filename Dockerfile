FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    nmap \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .

VOLUME /data
ENV WIFINDER_CONFIG=/data/config.yaml
ENV WIFINDER_DB=/data/wifinder.db

EXPOSE 8080

CMD ["wifinder", "serve", "--host", "0.0.0.0"]
