# 🚀 Quick Deployment to Hostinger VPS

## Prerequisites
- Hostinger VPS plan (not shared hosting)
- Docker Hub account
- SSH access to your VPS

## 🎯 Quick Steps

### 1. Push to Docker Hub (Local Machine)

**Windows:**
```cmd
# Edit push-to-dockerhub.bat - change 'yourusername' to your Docker Hub username
push-to-dockerhub.bat
```

**Linux/Mac:**
```bash
# Edit push-to-dockerhub.sh - change 'yourusername' to your Docker Hub username
chmod +x push-to-dockerhub.sh
./push-to-dockerhub.sh
```

### 2. Deploy to VPS

**Upload deployment script:**
```bash
# Upload to your VPS
scp deploy-vps.sh root@your-vps-ip:/root/

# SSH to VPS
ssh root@your-vps-ip

# Edit the script - change 'yourusername' to your Docker Hub username
nano deploy-vps.sh

# Run deployment
chmod +x deploy-vps.sh
./deploy-vps.sh
```

### 3. Access Your API

After deployment:
- **Direct access:** `http://your-vps-ip:8000`
- **API docs:** `http://your-vps-ip:8000/docs`
- **Health check:** `http://your-vps-ip:8000/health`

## 🛠️ Management Commands

```bash
# Check status
docker ps

# View logs
docker-compose logs -f

# Restart service
docker-compose restart

# Update to latest version
./update.sh

# Create backup
./backup.sh

# Health check
./health-check.sh
```

## 🌐 Domain Setup (Optional)

1. Point your domain A record to VPS IP
2. The deployment script will configure Nginx automatically
3. For SSL: `certbot --nginx -d yourdomain.com`

## 📊 Monitoring

- Health checks run every 5 minutes
- Automatic restarts on failure
- Daily backups at 2 AM
- Logs in `/opt/video-merger-api/logs/`

## 🔧 Troubleshooting

**Container won't start:**
```bash
docker-compose logs
```

**Port already in use:**
```bash
netstat -tulpn | grep 8000
```

**Permission issues:**
```bash
chmod -R 755 /opt/video-merger-api
```

**Out of disk space:**
```bash
docker system prune -a
rm -rf temp/*
```

## 📞 Support

Check the full documentation in `deploy-hostinger.md` for detailed instructions and troubleshooting.