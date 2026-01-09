# Production Deployment Guide

## 🚀 Deploying to Production

Complete guide for deploying LearnSwift Academia to production servers.

---

## 📋 Pre-Deployment Checklist

### Code & Configuration
- [ ] All tests passing: `python manage.py test`
- [ ] No migration conflicts: `python manage.py makemigrations --check`
- [ ] Static files collected: `python manage.py collectstatic`
- [ ] Security settings reviewed
- [ ] Environment variables configured
- [ ] Database backups configured
- [ ] Error tracking enabled (Sentry)

### Settings Review
- [ ] `DEBUG = False` in production
- [ ] `SECRET_KEY` from environment variable (not hardcoded)
- [ ] `ALLOWED_HOSTS` configured with production domain
- [ ] `CSRF_TRUSTED_ORIGINS` includes production URL
- [ ] Database credentials secured
- [ ] SSL/HTTPS enabled
- [ ] Media file serving configured

---

## 🔧 Environment Variables

Create `.env` file in production (or use platform environment variables):

```env
# Django Core
SECRET_KEY=your-production-secret-key-here
DEBUG=False
DJANGO_ALLOWED_HOSTS=learnswift.icu,www.learnswift.icu

# Database
DATABASE_URL=postgresql://user:password@host:5432/dbname

# Security
CSRF_TRUSTED_ORIGINS=https://learnswift.icu,https://www.learnswift.icu
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_PRELOAD=True
SECURE_HSTS_INCLUDE_SUBDOMAINS=True

# Session
SESSION_EXPIRE_AT_BROWSER_CLOSE=False

# Email (Optional - for password resets)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# Error Tracking (Optional)
SENTRY_DSN=https://your-sentry-dsn

# API Keys
GEMINI_API_KEY=your-gemini-api-key
```

**Generate SECRET_KEY:**
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

## 🐳 Docker Deployment

### Dockerfile
Already configured at project root. Build and run:

```bash
# Build image
docker build -t lsaapp:latest .

# Run container
docker run -d \
  -p 8000:8000 \
  -e DATABASE_URL=postgresql://... \
  -e SECRET_KEY=... \
  -v /path/to/media:/app/media \
  --name lsaapp \
  lsaapp:latest
```

### Docker Compose
Use `compose.yaml`:

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

**Production compose.yaml:**
```yaml
version: '3.8'

services:
  web:
    build: .
    command: gunicorn lsaapp.wsgi:application --bind 0.0.0.0:8000 --workers 4
    volumes:
      - ./media:/app/media
      - ./staticfiles:/app/staticfiles
    env_file:
      - .env
    depends_on:
      - db
    restart: unless-stopped

  db:
    image: postgres:14
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=lsaapp
      - POSTGRES_USER=lsaapp_user
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./staticfiles:/staticfiles
      - ./media:/media
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - web
    restart: unless-stopped

volumes:
  postgres_data:
```

---

## 🌐 Traditional VPS Deployment

### 1. Server Setup (Ubuntu 22.04)

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3.11 python3.11-venv python3-pip postgresql postgresql-contrib nginx git

# Create application user
sudo useradd -m -s /bin/bash lsaapp
sudo usermod -aG sudo lsaapp
```

### 2. PostgreSQL Setup

```bash
# Switch to postgres user
sudo -u postgres psql

# Create database and user
CREATE DATABASE lsaapp;
CREATE USER lsaapp_user WITH PASSWORD 'your-secure-password';
ALTER ROLE lsaapp_user SET client_encoding TO 'utf8';
ALTER ROLE lsaapp_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE lsaapp_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE lsaapp TO lsaapp_user;
\q
```

### 3. Application Setup

```bash
# Switch to app user
sudo su - lsaapp

# Clone repository
git clone https://github.com/your-org/LSAApp.git
cd LSAApp

# Create virtual environment
python3.11 -m venv lsa_env
source lsa_env/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Create .env file
nano .env
# (Add environment variables from above)

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput

# Create media directory
mkdir -p media
chmod 755 media
```

### 4. Gunicorn Setup

```bash
# Install gunicorn
pip install gunicorn

# Test gunicorn
gunicorn --bind 0.0.0.0:8000 lsaapp.wsgi:application

# Create systemd service
sudo nano /etc/systemd/system/lsaapp.service
```

**lsaapp.service:**
```ini
[Unit]
Description=LSA App Gunicorn Service
After=network.target

[Service]
User=lsaapp
Group=www-data
WorkingDirectory=/home/lsaapp/LSAApp
Environment="PATH=/home/lsaapp/LSAApp/lsa_env/bin"
EnvironmentFile=/home/lsaapp/LSAApp/.env
ExecStart=/home/lsaapp/LSAApp/lsa_env/bin/gunicorn \
          --workers 4 \
          --bind unix:/home/lsaapp/LSAApp/lsaapp.sock \
          --timeout 120 \
          --access-logfile /var/log/lsaapp/access.log \
          --error-logfile /var/log/lsaapp/error.log \
          lsaapp.wsgi:application

[Install]
WantedBy=multi-user.target
```

```bash
# Create log directory
sudo mkdir -p /var/log/lsaapp
sudo chown lsaapp:www-data /var/log/lsaapp

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable lsaapp
sudo systemctl start lsaapp
sudo systemctl status lsaapp
```

### 5. Nginx Configuration

```bash
sudo nano /etc/nginx/sites-available/lsaapp
```

**Nginx config:**
```nginx
upstream lsaapp {
    server unix:/home/lsaapp/LSAApp/lsaapp.sock fail_timeout=0;
}

server {
    listen 80;
    server_name learnswift.icu www.learnswift.icu;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name learnswift.icu www.learnswift.icu;

    # SSL certificates (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/learnswift.icu/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/learnswift.icu/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    client_max_body_size 10M;

    # Static files
    location /static/ {
        alias /home/lsaapp/LSAApp/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files
    location /media/ {
        alias /home/lsaapp/LSAApp/media/;
        expires 7d;
        add_header Cache-Control "public";
    }

    # Django application
    location / {
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Host $http_host;
        proxy_redirect off;
        proxy_pass http://lsaapp;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/lsaapp /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 6. SSL Certificate (Let's Encrypt)

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d learnswift.icu -d www.learnswift.icu

# Auto-renewal test
sudo certbot renew --dry-run
```

---

## ☁️ Platform as a Service (PaaS) Deployment

### Render.com

1. **Create Web Service**
   - Connect GitHub repository
   - Select Python environment
   - Build command: `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
   - Start command: `gunicorn lsaapp.wsgi:application`

2. **Environment Variables**
   - Add all variables from .env template
   - Set `DATABASE_URL` from Render PostgreSQL

3. **Create PostgreSQL Database**
   - Create new PostgreSQL instance
   - Copy internal database URL to `DATABASE_URL`

4. **Custom Domain**
   - Add custom domain in dashboard
   - Update DNS records
   - Add domain to `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`

### Heroku

```bash
# Install Heroku CLI
# Login
heroku login

# Create app
heroku create learnswift-academia

# Add PostgreSQL
heroku addons:create heroku-postgresql:hobby-dev

# Set environment variables
heroku config:set SECRET_KEY=your-secret-key
heroku config:set DEBUG=False
heroku config:set ALLOWED_HOSTS=learnswift-academia.herokuapp.com

# Deploy
git push heroku main

# Run migrations
heroku run python manage.py migrate

# Create superuser
heroku run python manage.py createsuperuser

# Collect static files
heroku run python manage.py collectstatic --noinput
```

**Procfile:**
```
web: gunicorn lsaapp.wsgi:application --log-file -
release: python manage.py migrate
```

---

## 🔄 Continuous Deployment

### GitHub Actions

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Production

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.11
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    
    - name: Run tests
      run: |
        python manage.py test
    
    - name: Deploy to server
      uses: appleboy/ssh-action@master
      with:
        host: ${{ secrets.SERVER_HOST }}
        username: ${{ secrets.SERVER_USER }}
        key: ${{ secrets.SSH_PRIVATE_KEY }}
        script: |
          cd /home/lsaapp/LSAApp
          git pull origin main
          source lsa_env/bin/activate
          pip install -r requirements.txt
          python manage.py migrate
          python manage.py collectstatic --noinput
          sudo systemctl restart lsaapp
```

---

## 📊 Monitoring & Logging

### Application Monitoring (Sentry)

Already configured in settings.py. Just add to .env:
```env
SENTRY_DSN=https://your-sentry-dsn-here
```

### Server Monitoring

```bash
# Install monitoring tools
sudo apt install -y htop nethogs iotop

# View logs
sudo journalctl -u lsaapp -f
tail -f /var/log/lsaapp/error.log
tail -f /var/log/nginx/error.log
```

### Django Logging

Already configured to log errors to `/tmp/logs/error.log`

---

## 🔐 Security Hardening

### Firewall (UFW)
```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

### Fail2Ban
```bash
sudo apt install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### Regular Updates
```bash
# Create update script
sudo nano /usr/local/bin/update-system.sh
```

```bash
#!/bin/bash
apt update && apt upgrade -y
apt autoremove -y
systemctl restart lsaapp
systemctl restart nginx
```

```bash
sudo chmod +x /usr/local/bin/update-system.sh

# Add to crontab (weekly updates)
sudo crontab -e
0 2 * * 0 /usr/local/bin/update-system.sh
```

---

## 🆘 Troubleshooting

### Application won't start
```bash
# Check logs
sudo journalctl -u lsaapp -n 50
tail -f /var/log/lsaapp/error.log

# Check socket file
ls -la /home/lsaapp/LSAApp/lsaapp.sock

# Test gunicorn manually
cd /home/lsaapp/LSAApp
source lsa_env/bin/activate
gunicorn --bind 0.0.0.0:8000 lsaapp.wsgi:application
```

### 502 Bad Gateway
```bash
# Check if gunicorn is running
sudo systemctl status lsaapp

# Check Nginx configuration
sudo nginx -t

# Check Nginx logs
tail -f /var/log/nginx/error.log
```

### Static files not loading
```bash
# Re-collect static files
python manage.py collectstatic --noinput

# Check permissions
ls -la /home/lsaapp/LSAApp/staticfiles
sudo chown -R lsaapp:www-data staticfiles
```

### Database connection errors
```bash
# Test database connection
sudo -u postgres psql -d lsaapp

# Check DATABASE_URL in .env
cat .env | grep DATABASE_URL

# Test from Django shell
python manage.py shell
>>> from django.db import connection
>>> connection.ensure_connection()
```

---

## 📝 Post-Deployment Tasks

- [ ] Test all major features
- [ ] Upload test media files
- [ ] Configure backups (see below)
- [ ] Set up monitoring alerts
- [ ] Document deployment process
- [ ] Share admin credentials securely
- [ ] Test email functionality
- [ ] Verify SSL certificate
- [ ] Test file uploads
- [ ] Check mobile responsiveness

---

## 💾 Backup Strategy

### Database Backups

```bash
# Create backup script
nano /home/lsaapp/backup-db.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/home/lsaapp/backups/db"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

pg_dump -U lsaapp_user lsaapp | gzip > $BACKUP_DIR/lsaapp_$DATE.sql.gz

# Keep only last 7 days
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete
```

```bash
chmod +x /home/lsaapp/backup-db.sh

# Add to crontab (daily at 2 AM)
crontab -e
0 2 * * * /home/lsaapp/backup-db.sh
```

### Media Files Backup

```bash
# Sync to remote storage (example: rsync)
rsync -avz /home/lsaapp/LSAApp/media/ user@backup-server:/backups/lsaapp/media/

# Or use cloud storage (rclone)
rclone sync /home/lsaapp/LSAApp/media/ remote:lsaapp-media-backup
```

---

## 📞 Support Resources

- [Django Deployment Checklist](https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/)
- [Gunicorn Documentation](https://docs.gunicorn.org/)
- [Nginx Documentation](https://nginx.org/en/docs/)
- [Let's Encrypt](https://letsencrypt.org/)
- [Sentry Docs](https://docs.sentry.io/)

---

**Last Updated:** January 9, 2026  
**Status:** Production-ready configuration
