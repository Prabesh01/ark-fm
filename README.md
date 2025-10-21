- `cd app/ && nohup gunicorn --bind 127.0.0.1:5000 main:app &`

- `ln -s /etc/nginx/sites-available/ark.conf /etc/nginx/sites-enabled/`

- `* * * * * radio.sh &`
