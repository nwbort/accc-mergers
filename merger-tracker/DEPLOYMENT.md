# Deployment Guide

This guide covers deployment options for the ACCC Merger Tracker application.

## Table of Contents
1. [Docker Deployment](#docker-deployment)
2. [DigitalOcean Deployment](#digitalocean-deployment)
3. [AWS EC2 Deployment](#aws-ec2-deployment)
4. [Production Considerations](#production-considerations)

## Docker Deployment

The easiest way to deploy is using Docker Compose.

### Prerequisites
- Docker
- Docker Compose

### Steps

1. Create a `docker-compose.yml` file (see example in repository)
2. Build and start containers:
```bash
docker-compose up -d
```

3. Sync initial data:
```bash
docker-compose exec backend python sync_data.py
```

The application will be available at `http://localhost` (configured port).

## DigitalOcean Deployment

### Option 1: DigitalOcean App Platform

1. **Create a new App**
   - Go to DigitalOcean App Platform
   - Click "Create App"
   - Connect your GitHub repository

2. **Configure Backend Service**
   - Type: Web Service
   - Source Directory: `merger-tracker/backend`
   - Build Command: `pip install -r requirements.txt`
   - Run Command: `uvicorn main:app --host 0.0.0.0 --port 8080`
   - Environment Variables:
     - `PORT=8080`
     - `ALLOWED_ORIGINS=https://your-frontend-domain.ondigitalocean.app`

3. **Configure Frontend Service**
   - Type: Static Site
   - Source Directory: `merger-tracker/frontend`
   - Build Command: `npm install && npm run build`
   - Output Directory: `dist`
   - Environment Variables:
     - `VITE_API_URL=https://your-backend-domain.ondigitalocean.app`

4. **Set up Database Volume**
   - Add a persistent volume to the backend service
   - Mount at `/app/mergers.db`

### Option 2: DigitalOcean Droplet

1. **Create a Droplet**
   - Ubuntu 22.04 LTS
   - At least 2GB RAM
   - Enable backups

2. **Initial Setup**
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3-pip python3-venv nginx nodejs npm

# Install PM2 for process management
sudo npm install -g pm2
```

3. **Deploy Backend**
```bash
# Create app directory
sudo mkdir -p /var/www/merger-tracker
cd /var/www/merger-tracker

# Clone or upload your code
# Set up Python virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

# Copy mergers.json to backend directory
cp /path/to/mergers.json backend/

# Sync data
cd backend
python sync_data.py

# Start with PM2
pm2 start main.py --name merger-backend --interpreter python3
pm2 save
pm2 startup
```

4. **Deploy Frontend**
```bash
cd /var/www/merger-tracker/frontend

# Set environment variable
echo "VITE_API_URL=https://api.yourdomain.com" > .env

# Build
npm install
npm run build

# Copy to nginx directory
sudo cp -r dist/* /var/www/html/
```

5. **Configure Nginx** (see nginx configuration below)

## AWS EC2 Deployment

### 1. Launch EC2 Instance
- AMI: Ubuntu Server 22.04 LTS
- Instance Type: t3.small or larger
- Security Group: Allow ports 22 (SSH), 80 (HTTP), 443 (HTTPS)

### 2. Connect and Install Dependencies
```bash
ssh -i your-key.pem ubuntu@your-ec2-ip

# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3-pip python3-venv nginx nodejs npm certbot python3-certbot-nginx

# Install PM2
sudo npm install -g pm2
```

### 3. Deploy Application
Follow the same steps as DigitalOcean Droplet deployment above.

### 4. Configure Domain and SSL
```bash
# Configure DNS to point to your EC2 IP
# Then run certbot
sudo certbot --nginx -d yourdomain.com -d api.yourdomain.com
```

## Production Considerations

### 1. Database Backups
Set up automated backups for the SQLite database:

```bash
# Create backup script
cat > /var/www/merger-tracker/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/var/backups/merger-tracker"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR
cp /var/www/merger-tracker/backend/mergers.db $BACKUP_DIR/mergers_$DATE.db
# Keep only last 30 days
find $BACKUP_DIR -name "mergers_*.db" -mtime +30 -delete
EOF

chmod +x /var/www/merger-tracker/backup.sh

# Add to crontab (daily at 2 AM)
(crontab -l 2>/dev/null; echo "0 2 * * * /var/www/merger-tracker/backup.sh") | crontab -
```

### 2. Data Sync Automation
Set up a cron job to sync data periodically:

```bash
# Add to crontab (every 6 hours)
(crontab -l 2>/dev/null; echo "0 */6 * * * cd /var/www/merger-tracker/backend && /var/www/merger-tracker/venv/bin/python sync_data.py") | crontab -
```

### 3. Monitoring
Set up monitoring with PM2:

```bash
pm2 install pm2-logrotate
pm2 set pm2-logrotate:max_size 10M
pm2 set pm2-logrotate:retain 7
```

### 4. Security
- Use environment variables for sensitive configuration
- Enable firewall (ufw on Ubuntu)
- Keep system and dependencies updated
- Use SSL/TLS certificates (Let's Encrypt)
- Set up fail2ban for SSH protection

### 5. Performance
- Enable Nginx gzip compression
- Set up CDN for static assets (CloudFlare, etc.)
- Consider using PostgreSQL instead of SQLite for high traffic
- Implement Redis for caching if needed

## Nginx Configuration

### Frontend (Static Files)
```nginx
server {
    listen 80;
    server_name yourdomain.com;

    root /var/www/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

    # Cache static assets
    location ~* \.(jpg|jpeg|png|gif|ico|css|js|svg)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### Backend API
```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Save these to `/etc/nginx/sites-available/` and create symlinks:
```bash
sudo ln -s /etc/nginx/sites-available/frontend /etc/nginx/sites-enabled/
sudo ln -s /etc/nginx/sites-available/backend /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## Systemd Service (Alternative to PM2)

Create `/etc/systemd/system/merger-backend.service`:
```ini
[Unit]
Description=ACCC Merger Tracker Backend
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/merger-tracker/backend
Environment="PATH=/var/www/merger-tracker/venv/bin"
ExecStart=/var/www/merger-tracker/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable merger-backend
sudo systemctl start merger-backend
sudo systemctl status merger-backend
```
