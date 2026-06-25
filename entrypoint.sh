#!/bin/bash
set -e

printenv | grep -v "no_proxy" >> /etc/environment
cron

cd app/ && gunicorn --bind 0.0.0.0:5000 --workers 1 --worker-class geventwebsocket.gunicorn.workers.GeventWebSocketWorker main:app
