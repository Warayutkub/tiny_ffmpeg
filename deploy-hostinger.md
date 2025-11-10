# 🚀 Hostinger Deployment Guide

## Prerequisites

Your Hostinger plan must support Docker containers:
- ✅ **VPS Hosting** - Full Docker support
- ✅ **Cloud Hosting** - Docker support (check plan details)
- ❌ **Shared Hosting** - No Docker support

## Method 1: Docker Hub + VPS Deployment (Recommended)

### Step 1: Push to Docker Hub

1. **Create Docker Hub account** at https://hub.docker.com
2. **Tag and push your image:**

```bash
# Build and tag the image
docker build -t yourusername/video-merger-api:latest .

# Login to Docker Hub
docker login

# Push to Docker Hub
docker push yourusername/video-merger-api:latest
```

### Step 2: Deploy on Hostinger VPS

1. **SSH into your Hostinger VPS:**
```bash
ssh root@your-server-ip
```

2. **Install Docker** (if not installed):
```bash
# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Start Docker service
systemctl start docker
systemctl enable docker
```

3. **Create deployment directory:**
```bash
mkdir -p /opt/video-merger-api
cd /opt/video-merger-api
```

4. **Create production docker-compose.yml:**
```yaml
services:
  video-merger-api:
    image: yourusername/video-merger-api:latest
    container_name: video-merger-api
    ports:
      - "8000:8000"
    volumes:
      - ./output:/app/output
      - ./temp:/app/temp
      - ./logs:/app/logs
      - ./tasks:/app/tasks
    environment:
      - PYTHONPATH=/app
      - LOG_LEVEL=info
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

5. **Start the service:**
```bash
# Create directories
mkdir -p output temp logs tasks

# Start the container
docker-compose up -d

# Check status
docker-compose ps
docker-compose logs -f
```

## Method 2: Direct File Transfer + Build

### Upload project files to VPS:

```bash
# From your local machine
scp -r /path/to/tiny_api_ffmpeg root@your-server-ip:/opt/

# SSH to server
ssh root@your-server-ip
cd /opt/tiny_api_ffmpeg

# Build and run
docker-compose up --build -d
```

## Method 3: Automated Deployment Script

Save this as `deploy.sh` on your VPS:

```bash
#!/bin/bash

# Configuration
IMAGE_NAME="yourusername/video-merger-api"
CONTAINER_NAME="video-merger-api"
APP_DIR="/opt/video-merger-api"

echo "🚀 Starting deployment..."

# Create app directory
mkdir -p $APP_DIR
cd $APP_DIR

# Pull latest image
echo "📥 Pulling latest image..."
docker pull $IMAGE_NAME:latest

# Stop existing container
echo "🛑 Stopping existing container..."
docker stop $CONTAINER_NAME 2>/dev/null || true
docker rm $CONTAINER_NAME 2>/dev/null || true

# Create directories
mkdir -p output temp logs tasks

# Start new container
echo "🏃 Starting new container..."
docker run -d \
  --name $CONTAINER_NAME \
  -p 8000:8000 \
  -v $(pwd)/output:/app/output \
  -v $(pwd)/temp:/app/temp \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/tasks:/app/tasks \
  --restart unless-stopped \
  $IMAGE_NAME:latest

# Check health
echo "🏥 Checking health..."
sleep 10
curl -f http://localhost:8000/health

echo "✅ Deployment complete!"
echo "🌐 API available at: http://your-domain.com:8000"
```

## Domain & SSL Setup

### 1. Configure Domain (Optional)

If you have a domain, point it to your VPS IP:
- A Record: `api.yourdomain.com` → `your-vps-ip`

### 2. Add Reverse Proxy with Nginx (Recommended)

```bash
# Install Nginx
apt install nginx -y

# Create configuration
cat > /etc/nginx/sites-available/video-merger-api << EOF
server {
    listen 80;
    server_name api.yourdomain.com your-vps-ip;

    client_max_body_size 100M;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
    }
}
EOF

# Enable site
ln -s /etc/nginx/sites-available/video-merger-api /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

### 3. Add SSL with Let's Encrypt

```bash
# Install Certbot
apt install certbot python3-certbot-nginx -y

# Get SSL certificate
certbot --nginx -d api.yourdomain.com

# Auto-renewal (optional)
crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

## Environment Variables

Create `.env` file for production:

```bash
# Production environment
LOG_LEVEL=info
MAX_UPLOAD_SIZE=100MB
WORKER_PROCESSES=2
```

## Monitoring & Maintenance

### Health Check Script (`health-check.sh`):

```bash
#!/bin/bash
HEALTH_URL="http://localhost:8000/health"
WEBHOOK_URL="your-discord-or-slack-webhook" # Optional

if ! curl -f $HEALTH_URL > /dev/null 2>&1; then
    echo "❌ API is down! Restarting..."
    docker-compose restart
    
    # Optional: Send notification
    # curl -X POST $WEBHOOK_URL -d '{"content":"🚨 Video Merger API was down and restarted"}'
else
    echo "✅ API is healthy"
fi
```

### Add to crontab:
```bash
crontab -e
# Add: */5 * * * * /opt/video-merger-api/health-check.sh
```

## Firewall Configuration

```bash
# Allow HTTP/HTTPS and SSH
ufw allow ssh
ufw allow 80
ufw allow 443
ufw allow 8000  # If accessing directly
ufw enable
```

## Backup Strategy

```bash
#!/bin/bash
# backup.sh
BACKUP_DIR="/backups/video-merger-api"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup volumes
tar -czf $BACKUP_DIR/data_$DATE.tar.gz \
  /opt/video-merger-api/output \
  /opt/video-merger-api/tasks \
  /opt/video-merger-api/logs

# Keep only last 7 backups
find $BACKUP_DIR -name "data_*.tar.gz" -mtime +7 -delete
```

## Troubleshooting

### Common Issues:

1. **Port already in use:**
```bash
docker ps -a  # Check running containers
netstat -tulpn | grep 8000  # Check port usage
```

2. **Permission denied:**
```bash
chmod -R 755 /opt/video-merger-api
chown -R root:root /opt/video-merger-api
```

3. **Container won't start:**
```bash
docker logs video-merger-api
docker-compose logs -f
```

4. **Low disk space:**
```bash
# Clean old Docker images
docker system prune -a

# Clean temp files
rm -rf /opt/video-merger-api/temp/*
```

## Performance Tuning

### For high traffic:

```yaml
# docker-compose.yml additions
services:
  video-merger-api:
    # ... existing config
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
    environment:
      - WORKER_PROCESSES=4
      - MAX_WORKERS=8
```

## Final Checklist

- [ ] VPS has Docker installed
- [ ] Image pushed to Docker Hub
- [ ] docker-compose.yml configured
- [ ] Directories created (output, temp, logs, tasks)
- [ ] Firewall configured
- [ ] Domain pointed to VPS (optional)
- [ ] SSL certificate installed (optional)
- [ ] Health checks working
- [ ] Backup script configured

## Quick Commands

```bash
# View logs
docker-compose logs -f

# Restart service
docker-compose restart

# Update to latest version
docker-compose pull && docker-compose up -d

# Check resource usage
docker stats video-merger-api

# Access container shell
docker exec -it video-merger-api bash
```

Your API will be available at:
- Direct: `http://your-vps-ip:8000`
- With domain: `http://api.yourdomain.com`
- With SSL: `https://api.yourdomain.com`