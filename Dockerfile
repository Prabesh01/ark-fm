FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    cron \
    ffmpeg \
    jq \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

COPY crontab /etc/cron.d/arkfm-cron
RUN chmod 0644 /etc/cron.d/arkfm-cron && crontab /etc/cron.d/arkfm-cron

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
