# Security Configuration Guide

## Overview

This document provides comprehensive security configuration for deploying the Store Feedback System to production with HTTPS/TLS encryption and JWT authentication.

## Table of Contents

1. [SSL/TLS Certificate Setup](#ssltls-certificate-setup)
2. [Nginx Reverse Proxy Configuration](#nginx-reverse-proxy-configuration)
3. [Environment Variables](#environment-variables)
4. [JWT Token Security](#jwt-token-security)
5. [Database Security](#database-security)
6. [Security Best Practices](#security-best-practices)

---

## SSL/TLS Certificate Setup

### Option 1: Let's Encrypt (Recommended for Production)

Let's Encrypt provides free SSL certificates with automatic renewal.

```bash
# Install Certbot
sudo apt-get update
sudo apt-get install certbot python3-certbot-nginx

# Obtain certificate for your domain
sudo certbot --nginx -d store-feedback.tarsyer.com

# Test automatic renewal
sudo certbot renew --dry-run
```

### Option 2: Custom SSL Certificate

If you have a purchased SSL certificate:

```bash
# Place your certificate files
sudo cp your-domain.crt /etc/ssl/certs/
sudo cp your-domain.key /etc/ssl/private/
sudo chmod 600 /etc/ssl/private/your-domain.key
```

---

## Nginx Reverse Proxy Configuration

Create an Nginx configuration file for HTTPS termination and reverse proxy.

### File: `/etc/nginx/sites-available/store-feedback`

```nginx
# Redirect HTTP to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name store-feedback.tarsyer.com;

    # ACME challenge for Let's Encrypt
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # Redirect all other traffic to HTTPS
    location / {
        return 301 https://$server_name$request_uri;
    }
}

# HTTPS Server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name store-feedback.tarsyer.com;

    # SSL Certificate Configuration
    ssl_certificate /etc/letsencrypt/live/store-feedback.tarsyer.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/store-feedback.tarsyer.com/privkey.pem;
    ssl_trusted_certificate /etc/letsencrypt/live/store-feedback.tarsyer.com/chain.pem;

    # SSL Security Settings (Mozilla Intermediate Configuration)
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384';
    ssl_prefer_server_ciphers off;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_session_tickets off;

    # OCSP Stapling
    ssl_stapling on;
    ssl_stapling_verify on;
    resolver 8.8.8.8 8.8.4.4 valid=300s;
    resolver_timeout 5s;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;

    # Content Security Policy
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' https://kwen.tarsyer.com; media-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'" always;

    # Request Size Limits
    client_max_body_size 50M;
    client_body_buffer_size 128k;

    # Timeouts
    client_body_timeout 12;
    client_header_timeout 12;
    keepalive_timeout 15;
    send_timeout 10;

    # Rate Limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=auth_limit:10m rate=5r/m;

    # Frontend (React PWA)
    location / {
        root /var/www/store-feedback/frontend/dist;
        try_files $uri $uri/ /index.html;

        # Cache static assets
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }

    # Reports Dashboard
    location /reports.html {
        root /var/www/store-feedback/frontend/dist;
        try_files /reports.html =404;
    }

    # API Backend (with rate limiting)
    location /api/ {
        limit_req zone=api_limit burst=20 nodelay;

        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Authentication endpoints (stricter rate limiting)
    location /api/v1/auth/ {
        limit_req zone=auth_limit burst=5 nodelay;

        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Media files (uploaded recordings)
    location /media/ {
        alias /var/data/store-feedback/uploads/;

        # Require authentication (add JWT validation if needed)
        # Note: Consider adding auth_request or JWT validation here

        # Security headers
        add_header X-Content-Type-Options "nosniff" always;
        add_header Content-Security-Policy "default-src 'none'; media-src 'self'" always;

        # Prevent directory listing
        autoindex off;
    }

    # Health check endpoint (no rate limiting)
    location /health {
        proxy_pass http://127.0.0.1:8000;
        access_log off;
    }

    # Deny access to hidden files
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }
}
```

### Enable the Configuration

```bash
# Create symbolic link
sudo ln -s /etc/nginx/sites-available/store-feedback /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

---

## Environment Variables

### Production `.env` File

Create `/var/www/store-feedback/.env` with secure values:

```bash
# ============================================
# PRODUCTION ENVIRONMENT CONFIGURATION
# ============================================
# WARNING: Keep this file secure! Never commit to git!
# Permissions: chmod 600 .env

# Application Settings
DEBUG=false
APP_NAME=Store Feedback System
API_V1_PREFIX=/api/v1

# Server Configuration
HOST=127.0.0.1
PORT=8000

# MongoDB Connection
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=store_feedback

# JWT Authentication (CRITICAL - CHANGE THIS!)
# Generate with: python3 -c "import secrets; print(secrets.token_urlsafe(64))"
JWT_SECRET_KEY=YOUR_GENERATED_SECRET_KEY_HERE_CHANGE_THIS
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480

# File Storage
UPLOAD_DIR=/var/data/store-feedback/uploads
MAX_FILE_SIZE_MB=50

# Whisper Transcription
WHISPER_CLI_PATH=/opt/whisper.cpp/build/bin/whisper-cli
WHISPER_MODEL_PATH=/opt/whisper.cpp/models/ggml-medium.bin
WHISPER_LANGUAGE=hi

# Qwen3 LLM API
QWEN_API_URL=https://kwen.tarsyer.com/v1/chat/completions
QWEN_API_KEY=YOUR_QWEN_API_KEY
QWEN_TARGET_SERVER=BK
QWEN_MAX_TOKENS=1000

# Background Processing
PROCESS_INTERVAL_SECONDS=30
MAX_CONCURRENT_TRANSCRIPTIONS=2

# CORS Origins (comma-separated)
CORS_ORIGINS=https://store-feedback.tarsyer.com

# Frontend Environment
VITE_API_URL=https://store-feedback.tarsyer.com
```

### Secure the Environment File

```bash
# Set proper permissions
chmod 600 /var/www/store-feedback/.env
chown www-data:www-data /var/www/store-feedback/.env
```

---

## JWT Token Security

### Token Generation

The JWT tokens include:
- **Expiration**: Tokens expire after 8 hours (480 minutes)
- **Encryption**: HS256 algorithm with 512-bit secret key
- **Payload**: Contains user ID, role, name, and accessible stores

### Token Storage (Client-Side)

Tokens are stored in:
- `localStorage.auth_token` - JWT token
- `localStorage.token_expiry` - Expiration timestamp
- `localStorage.user_role` - User role for UI logic

### Security Considerations

1. **Secret Key**: Must be at least 256 bits, randomly generated
2. **HTTPS Only**: Tokens must only be transmitted over HTTPS
3. **Token Rotation**: Consider implementing refresh tokens for long sessions
4. **Logout**: Properly clear all localStorage on logout

### Generate New Secret Key

```bash
# Generate a new 512-bit secret key
python3 -c "import secrets; print(secrets.token_urlsafe(64))"

# Update in .env file
JWT_SECRET_KEY=<generated_key_here>
```

---

## Database Security

### MongoDB Security Configuration

#### 1. Enable Authentication

```bash
# Connect to MongoDB
mongosh

# Create admin user
use admin
db.createUser({
  user: "admin",
  pwd: passwordPrompt(),
  roles: [ { role: "userAdminAnyDatabase", db: "admin" } ]
})

# Create application user
use store_feedback
db.createUser({
  user: "feedback_app",
  pwd: passwordPrompt(),
  roles: [ { role: "readWrite", db: "store_feedback" } ]
})
```

#### 2. Configure MongoDB with Auth

Edit `/etc/mongod.conf`:

```yaml
security:
  authorization: enabled

net:
  bindIp: 127.0.0.1
  port: 27017
```

#### 3. Update Connection String

```bash
MONGODB_URL=mongodb://feedback_app:PASSWORD@localhost:27017/store_feedback?authSource=store_feedback
```

### Backup Strategy

```bash
# Daily backup script
#!/bin/bash
BACKUP_DIR=/var/backups/mongodb
DATE=$(date +%Y%m%d_%H%M%S)

mongodump --uri="mongodb://feedback_app:PASSWORD@localhost:27017/store_feedback" \
  --out="$BACKUP_DIR/backup_$DATE"

# Keep only last 30 days
find $BACKUP_DIR -type d -mtime +30 -exec rm -rf {} +
```

---

## Security Best Practices

### 1. Firewall Configuration

```bash
# Allow SSH, HTTP, HTTPS only
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# MongoDB should NOT be accessible externally
# It should only listen on 127.0.0.1
```

### 2. Keep Systems Updated

```bash
# Regular updates
sudo apt-get update && sudo apt-get upgrade -y

# Enable automatic security updates
sudo apt-get install unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

### 3. Log Monitoring

```bash
# Monitor Nginx access logs
tail -f /var/log/nginx/access.log

# Monitor Nginx error logs
tail -f /var/log/nginx/error.log

# Monitor application logs
tail -f /var/log/store-feedback/app.log
```

### 4. Fail2Ban for Brute Force Protection

```bash
# Install Fail2Ban
sudo apt-get install fail2ban

# Configure for Nginx
sudo nano /etc/fail2ban/jail.local
```

Add:
```ini
[nginx-auth]
enabled = true
filter = nginx-auth
logpath = /var/log/nginx/error.log
maxretry = 5
bantime = 3600
```

### 5. Regular Security Audits

- Review user access logs monthly
- Check for failed login attempts
- Monitor unusual API activity
- Update dependencies regularly
- Rotate JWT secret keys annually

---

## Testing HTTPS Configuration

### Test SSL Configuration

```bash
# Test SSL with OpenSSL
openssl s_client -connect store-feedback.tarsyer.com:443

# Check SSL Labs Rating
# Visit: https://www.ssllabs.com/ssltest/
# Enter: store-feedback.tarsyer.com
```

### Test Security Headers

```bash
curl -I https://store-feedback.tarsyer.com

# Should include:
# - Strict-Transport-Security
# - X-Frame-Options
# - X-Content-Type-Options
# - Content-Security-Policy
```

---

## Emergency Procedures

### Compromised JWT Secret

If JWT secret key is compromised:

1. Generate new secret key immediately
2. Update `.env` file
3. Restart application
4. All users will be logged out (expected behavior)
5. Notify users to re-authenticate

### Database Breach

1. Immediately disable network access to MongoDB
2. Review access logs
3. Change MongoDB passwords
4. Restore from last known good backup
5. Investigate breach source

---

## Contact & Support

For security issues, contact: security@tarsyer.com

**Report security vulnerabilities responsibly.**
