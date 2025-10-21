- `0 * * * * cd app/ && nohup gunicorn --bind 127.0.0.1:5000 --workers 1 --worker-class eventlet main:app`

- `ln -s /etc/nginx/sites-available/ark.conf /etc/nginx/sites-enabled/`

- `sudo apt-get install jq`

- `* * * * * radio.sh &`
