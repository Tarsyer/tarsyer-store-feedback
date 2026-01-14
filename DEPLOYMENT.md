# Production Deployment Checklist

## Pre-Deployment Security Checklist

### 1. Environment Configuration
- [ ] Copy `.env.production.template` to `.env`
- [ ] Generate new JWT secret key: `python3 -c "import secrets; print(secrets.token_urlsafe(64))"`
- [ ] Update all `CHANGE_THIS` values in `.env`
- [ ] Set proper file permissions: `chmod 600 .env`
- [ ] Verify DEBUG=false in production `.env`
- [ ] Configure MongoDB connection with authentication
- [ ] Update CORS_ORIGINS to production domain only

### 2. SSL/TLS Certificates
- [ ] Install certbot: `sudo apt-get install certbot python3-certbot-nginx`
- [ ] Obtain SSL certificate: `sudo certbot --nginx -d store-feedback.tarsyer.com`
- [ ] Verify certificate auto-renewal: `sudo certbot renew --dry-run`
- [ ] Configure HSTS header in Nginx
- [ ] Test SSL configuration at https://www.ssllabs.com/ssltest/

### 3. Database Security
- [ ] Enable MongoDB authentication
- [ ] Create dedicated database user with limited permissions
- [ ] Configure MongoDB to bind to 127.0.0.1 only
- [ ] Set up automated daily backups
- [ ] Test backup restoration procedure
- [ ] Create database indexes for performance

### 4. Application Security
- [ ] Install all dependencies: `pip install -r requirements.txt`
- [ ] Run security audit: `pip-audit` (install with `pip install pip-audit`)
- [ ] Update all packages to latest secure versions
- [ ] Configure proper file upload limits (50MB)
- [ ] Set up log rotation for application logs
- [ ] Configure proper directory permissions for uploads

### 5. Web Server Configuration
- [ ] Install Nginx: `sudo apt-get install nginx`
- [ ] Copy Nginx configuration from SECURITY.md
- [ ] Enable Nginx configuration: `sudo ln -s /etc/nginx/sites-available/store-feedback /etc/nginx/sites-enabled/`
- [ ] Test Nginx configuration: `sudo nginx -t`
- [ ] Configure rate limiting for API endpoints
- [ ] Configure rate limiting for auth endpoints (stricter)
- [ ] Set up log rotation for Nginx logs

### 6. Firewall Configuration
- [ ] Enable UFW: `sudo ufw enable`
- [ ] Allow SSH: `sudo ufw allow 22/tcp`
- [ ] Allow HTTP: `sudo ufw allow 80/tcp`
- [ ] Allow HTTPS: `sudo ufw allow 443/tcp`
- [ ] Verify MongoDB is NOT accessible externally
- [ ] Verify API backend is NOT directly accessible (only via Nginx)

### 7. Process Management
- [ ] Install PM2: `npm install -g pm2`
- [ ] Create PM2 ecosystem file (see below)
- [ ] Start application with PM2
- [ ] Configure PM2 startup: `pm2 startup`
- [ ] Save PM2 configuration: `pm2 save`
- [ ] Verify application auto-starts on reboot

### 8. Monitoring & Logging
- [ ] Configure application logging to file
- [ ] Set up log rotation (logrotate)
- [ ] Install and configure fail2ban for brute force protection
- [ ] Set up health check monitoring
- [ ] Configure error alerting (optional: Sentry)
- [ ] Set up uptime monitoring (optional: UptimeRobot)

### 9. Frontend Build
- [ ] Install frontend dependencies: `cd frontend && npm install`
- [ ] Build production bundle: `npm run build`
- [ ] Copy build to web root: `cp -r dist/* /var/www/store-feedback/frontend/dist/`
- [ ] Verify static files are served correctly
- [ ] Test PWA installation on mobile device
- [ ] Verify service worker is registered

### 10. API Security Testing
- [ ] Test JWT authentication flow
- [ ] Verify all protected endpoints require authentication
- [ ] Test token expiration and renewal
- [ ] Verify CORS headers are correct
- [ ] Test rate limiting on auth endpoints
- [ ] Verify file upload size limits
- [ ] Test XSS protection headers
- [ ] Verify CSP headers are present

---

## PM2 Ecosystem Configuration

Create `/var/www/store-feedback/ecosystem.config.js`:

```javascript
module.exports = {
  apps: [
    {
      name: 'feedback-api',
      script: '/var/www/store-feedback/backend/venv/bin/uvicorn',
      args: 'app.server:app --host 127.0.0.1 --port 8000 --workers 4',
      cwd: '/var/www/store-feedback/backend',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        NODE_ENV: 'production',
        PYTHONPATH: '/var/www/store-feedback/backend'
      },
      error_file: '/var/log/store-feedback/api-error.log',
      out_file: '/var/log/store-feedback/api-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      name: 'feedback-worker',
      script: '/var/www/store-feedback/backend/venv/bin/python',
      args: 'worker.py',
      cwd: '/var/www/store-feedback/backend',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '2G',
      env: {
        PYTHONPATH: '/var/www/store-feedback/backend'
      },
      error_file: '/var/log/store-feedback/worker-error.log',
      out_file: '/var/log/store-feedback/worker-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    }
  ]
};
```

---

## Deployment Commands

### Initial Deployment

```bash
# 1. Create application directory
sudo mkdir -p /var/www/store-feedback
sudo chown $USER:$USER /var/www/store-feedback

# 2. Clone repository
cd /var/www
git clone https://github.com/your-org/store-feedback.git

# 3. Set up Python environment
cd /var/www/store-feedback/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Configure environment
cp ../.env.production.template ../.env
nano ../.env  # Edit with production values
chmod 600 ../.env

# 5. Create upload directory
sudo mkdir -p /var/data/store-feedback/uploads
sudo chown www-data:www-data /var/data/store-feedback/uploads
sudo chmod 755 /var/data/store-feedback/uploads

# 6. Create log directory
sudo mkdir -p /var/log/store-feedback
sudo chown www-data:www-data /var/log/store-feedback

# 7. Build frontend
cd /var/www/store-feedback/frontend
npm install
npm run build

# 8. Start services with PM2
cd /var/www/store-feedback/backend
pm2 start ecosystem.config.js
pm2 save
pm2 startup

# 9. Configure and start Nginx
sudo cp /path/to/nginx-config /etc/nginx/sites-available/store-feedback
sudo ln -s /etc/nginx/sites-available/store-feedback /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# 10. Obtain SSL certificate
sudo certbot --nginx -d store-feedback.tarsyer.com

# 11. Verify deployment
curl -I https://store-feedback.tarsyer.com
curl https://store-feedback.tarsyer.com/health
```

### Subsequent Deployments

```bash
# 1. Pull latest code
cd /var/www/store-feedback
git pull origin main

# 2. Update backend dependencies (if changed)
cd backend
source venv/bin/activate
pip install -r requirements.txt

# 3. Rebuild frontend
cd ../frontend
npm install  # Only if package.json changed
npm run build

# 4. Restart services
pm2 restart all

# 5. Reload Nginx (if config changed)
sudo nginx -t
sudo systemctl reload nginx

# 6. Verify deployment
curl https://store-feedback.tarsyer.com/health
```

---

## Rollback Procedure

If deployment fails:

```bash
# 1. Stop current services
pm2 stop all

# 2. Checkout previous working version
cd /var/www/store-feedback
git log --oneline -10  # Find previous commit
git checkout <previous-commit-hash>

# 3. Rebuild if needed
cd frontend
npm run build

# 4. Restart services
pm2 restart all

# 5. Verify
curl https://store-feedback.tarsyer.com/health
```

---

## Health Checks

### Application Health

```bash
# API health check
curl https://store-feedback.tarsyer.com/health

# Should return:
# {"status":"healthy","version":"2.0.0","environment":"production"}
```

### Service Status

```bash
# Check PM2 processes
pm2 status

# Check Nginx status
sudo systemctl status nginx

# Check MongoDB status
sudo systemctl status mongod

# Check SSL certificate expiry
sudo certbot certificates
```

### Log Monitoring

```bash
# API logs
pm2 logs feedback-api --lines 50

# Worker logs
pm2 logs feedback-worker --lines 50

# Nginx access logs
sudo tail -f /var/log/nginx/access.log

# Nginx error logs
sudo tail -f /var/log/nginx/error.log
```

---

## Backup Procedures

### Database Backup

```bash
# Manual backup
mongodump --uri="mongodb://feedback_app:PASSWORD@localhost:27017/store_feedback" \
  --out=/var/backups/mongodb/backup_$(date +%Y%m%d_%H%M%S)

# Automated daily backup (crontab)
0 2 * * * /usr/local/bin/mongodb-backup.sh
```

### Application Backup

```bash
# Backup uploaded files
tar -czf /var/backups/uploads_$(date +%Y%m%d).tar.gz \
  /var/data/store-feedback/uploads

# Backup configuration
tar -czf /var/backups/config_$(date +%Y%m%d).tar.gz \
  /var/www/store-feedback/.env \
  /etc/nginx/sites-available/store-feedback
```

---

## Troubleshooting

### API Not Responding

```bash
# Check PM2 status
pm2 status

# Check application logs
pm2 logs feedback-api --err

# Check if port is in use
sudo netstat -tulpn | grep 8000

# Restart API
pm2 restart feedback-api
```

### Database Connection Issues

```bash
# Check MongoDB status
sudo systemctl status mongod

# Check MongoDB logs
sudo tail -f /var/log/mongodb/mongod.log

# Test connection
mongosh --uri="mongodb://feedback_app:PASSWORD@localhost:27017/store_feedback"
```

### SSL Certificate Issues

```bash
# Check certificate status
sudo certbot certificates

# Renew certificate manually
sudo certbot renew

# Check Nginx SSL configuration
sudo nginx -t
```

---

## Security Incident Response

If you suspect a security breach:

1. **Immediately**:
   - Stop all services: `pm2 stop all`
   - Block suspicious IPs in firewall
   - Check access logs for unusual activity

2. **Investigate**:
   - Review all logs (Nginx, API, MongoDB)
   - Check for unauthorized database changes
   - Verify file system integrity

3. **Remediate**:
   - Change all passwords and secrets
   - Rotate JWT secret key
   - Update all dependencies
   - Restore from last known good backup if needed

4. **Monitor**:
   - Increase log verbosity temporarily
   - Monitor closely for 48 hours
   - Consider enabling additional security tools

---

## Support Contacts

- **System Administrator**: admin@tarsyer.com
- **Security Issues**: security@tarsyer.com
- **Technical Support**: support@tarsyer.com

---

## Documentation

- **API Documentation**: https://store-feedback.tarsyer.com/api/docs
- **Security Guide**: See SECURITY.md
- **Architecture**: See README.md
