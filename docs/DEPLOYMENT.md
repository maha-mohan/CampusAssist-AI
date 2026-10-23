# Deployment guide (Ubuntu VPS)

A single server with **4 vCPU / 8 GB RAM / 80 GB SSD** comfortably handles a college's traffic. Any provider works (AWS Lightsail/EC2, Azure, GCP, DigitalOcean, or an Indian region host for data residency).

## 1. Server setup

```bash
sudo apt update && sudo apt upgrade -y
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER   # log out and back in

sudo ufw allow OpenSSH && sudo ufw allow 80 && sudo ufw allow 443 && sudo ufw enable
```

## 2. Get the code and configure

```bash
sudo mkdir -p /opt && cd /opt
sudo git clone <your-repo-url> college-ai-helpdesk && sudo chown -R $USER college-ai-helpdesk
cd college-ai-helpdesk
cp backend/.env.example backend/.env
nano backend/.env
```

Set at least:

| Variable | Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `SECRET_KEY` | output of `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `COLLEGE_NAME` | your college's name |
| `CORS_ORIGINS` | `https://www.yourcollege.edu,https://yourcollege.edu` |
| `OPENAI_API_KEY` | your key |
| `FIRST_ADMIN_EMAIL` / `FIRST_ADMIN_PASSWORD` | the first super admin |
| `SMTP_*` | for ticket emails (college Google Workspace / Microsoft 365 SMTP works) |

Also create a root `.env` next to `docker-compose.yml` with a strong database password:

```bash
echo "POSTGRES_PASSWORD=$(openssl rand -hex 16)" > .env
```

## 3. Start

```bash
docker compose up -d --build
docker compose exec api python -m app.scripts.seed          # departments + first admin (+ --samples for demo docs)
docker compose ps                                            # all services "running"/"healthy"
curl http://localhost:8080/api/health
```

## 4. Domain and HTTPS

Point a DNS A record such as `helpdesk.yourcollege.edu` to the server IP. Then put a TLS-terminating Nginx (or Caddy) on the host in front of the stack:

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
sudo tee /etc/nginx/sites-available/helpdesk >/dev/null <<'EOF'
server {
    server_name helpdesk.yourcollege.edu;
    client_max_body_size 30m;
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_read_timeout 120s;
    }
}
EOF
sudo ln -s /etc/nginx/sites-available/helpdesk /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d helpdesk.yourcollege.edu
```

`proxy_buffering off` matters: without it, streamed answers arrive all at once.

## 5. Backups

```bash
crontab -e
# daily at 02:30
30 2 * * * /opt/college-ai-helpdesk/infra/scripts/backup.sh >> /var/log/helpdesk-backup.log 2>&1
```

Copy `backups/` off the server regularly (e.g. `rclone` to Google Drive or S3). Uploaded files live in the `uploads` Docker volume; back it up too:
`docker run --rm -v college-ai-helpdesk_uploads:/u -v $PWD/backups:/b alpine tar czf /b/uploads.tgz -C /u .`

Restore a database backup: `gunzip -c backups/helpdesk_XXXX.sql.gz | docker compose exec -T postgres psql -U helpdesk helpdesk`

## 6. Updating

```bash
cd /opt/college-ai-helpdesk
git pull
docker compose up -d --build     # migrations run automatically when the api container starts
```

## 7. Monitoring

- `docker compose logs -f api worker` for live logs
- Set `SENTRY_DSN` to receive error alerts
- Use an uptime monitor (UptimeRobot, Better Stack) on `https://helpdesk.yourcollege.edu/api/health`
- Watch AI cost on the admin Overview and set a monthly budget alert in the OpenAI dashboard

## Data protection notes (India, DPDP Act 2023)

- Visitors are anonymous; only a hashed IP and browser user agent are stored with chats.
- Names, emails and phone numbers are collected only when someone raises a ticket. The widget form says who will contact them.
- Chats older than `CHAT_RETENTION_DAYS` (default 365) are deleted nightly by the worker.
- Publish a short privacy notice on the college website describing this, and name a contact for data requests.
- Prefer a hosting region in India if the college's policy requires data residency. Messages are sent to OpenAI for answering; review your provider's data-use terms.
