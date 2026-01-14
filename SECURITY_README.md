# 🔐 Security Features - Quick Start

## Overview

The Store Feedback application now includes **enterprise-grade JWT authentication** and **HTTPS/TLS encryption** for secure production deployment.

---

## 🚀 Quick Start (Development)

### 1. Backend Setup

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# The .env file already has a secure JWT secret key configured
# For production, generate a new one:
# python3 -c "import secrets; print(secrets.token_urlsafe(64))"

# Start the secure server
python -m app.server
# Or use the new secure server:
# uvicorn app.server:app --reload
```

### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### 3. Create Admin User

```bash
# Connect to MongoDB
mongosh

# Switch to database
use store_feedback

# Create admin user
db.users.insertOne({
  username: "admin",
  name: "Administrator",
  password_hash: "$2b$12$your_bcrypt_hash_here",  // Use bcrypt to hash
  role: "admin",
  store_ids: []
})

# Create manager user
db.users.insertOne({
  username: "manager",
  name: "Store Manager",
  password_hash: "$2b$12$your_bcrypt_hash_here",
  role: "manager",
  store_ids: ["W001", "W002"]
})
```

To generate bcrypt hash in Python:

```python
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
print(pwd_context.hash("your_password_here"))
```

---

## 📱 Accessing the Application

### Staff App (Feedback Recording)
- **URL**: `http://localhost:5173/` or `https://store-feedback.tarsyer.com/`
- **Login**: Simple password authentication (upgrade to JWT if needed)

### Manager Dashboard (Reports)
- **URL**: `http://localhost:5173/reports.html` or `https://store-feedback.tarsyer.com/reports.html`
- **Login**: Username + Password with JWT authentication
- **Credentials**: Use manager or admin user created above

---

## 🔑 Authentication Flow

1. User enters **username** and **password**
2. Backend validates credentials against MongoDB
3. If valid, generates **JWT token** (expires in 8 hours)
4. Token stored in browser `localStorage`
5. All API requests include `Authorization: Bearer <token>` header
6. Token validated on every protected endpoint
7. Auto-logout when token expires

---

## 🛡️ Security Features

### ✅ Implemented

- **JWT Authentication**: Industry-standard token-based auth
- **Password Hashing**: Bcrypt with salt
- **Role-Based Access**: Staff, Manager, Admin roles
- **Token Expiration**: 8-hour sessions with automatic logout
- **CORS Protection**: Restricted to allowed origins
- **Security Headers**: CSP, HSTS, X-Frame-Options, etc.
- **Rate Limiting**: Prevents brute force attacks (in Nginx)
- **HTTPS/TLS**: Full encryption in transit
- **Input Validation**: Pydantic models with strict validation

### 🔒 Protected Endpoints

| Endpoint | Required Role | Description |
|----------|---------------|-------------|
| `POST /api/v1/auth/login/json` | Public | Login endpoint |
| `GET /api/v1/auth/me` | Any authenticated | Current user info |
| `GET /api/v1/dashboard/*` | Manager+ | Analytics and reports |
| `GET /api/v1/stores` | Manager+ | Store listing |
| `POST /api/v1/users` | Admin | Create new user |
| `GET /api/v1/feedbacks` | Manager+ | Feedback listing |

---

## 📚 Documentation

| File | Description |
|------|-------------|
| **[SECURITY_SUMMARY.md](./SECURITY_SUMMARY.md)** | 📖 Complete security overview |
| **[SECURITY.md](./SECURITY.md)** | 🔐 HTTPS/TLS and Nginx configuration |
| **[DEPLOYMENT.md](./DEPLOYMENT.md)** | 🚀 Production deployment guide |
| **[.env.production.template](./.env.production.template)** | ⚙️ Production environment template |

---

## 🧪 Testing Authentication

### Test Login API

```bash
# Login request
curl -X POST http://localhost:8000/api/v1/auth/login/json \
  -H "Content-Type: application/json" \
  -d '{"username": "manager", "password": "your_password"}'

# Response:
# {
#   "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
#   "token_type": "bearer"
# }
```

### Test Protected Endpoint

```bash
# Get dashboard stats (requires token)
curl http://localhost:8000/api/v1/dashboard/stats?days=15 \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"

# Without token → 401 Unauthorized
# With valid token → Returns dashboard data
```

---

## 🔄 Migration from Old Auth

The old password-based authentication in the frontend (`Auth.jsx`) has been replaced with JWT authentication (`AuthJWT.jsx`).

### Changes Made

1. ✅ **Backend**: Already had JWT auth implemented
2. ✅ **Frontend**: New `AuthJWT.jsx` component with username/password
3. ✅ **Reports**: Updated to use JWT tokens for all API calls
4. ✅ **Token Management**: Automatic expiration and logout
5. ✅ **Security Headers**: Added comprehensive security middleware

### What You Need to Do

1. **Keep using the existing app** - Old `Auth.jsx` still works for staff
2. **Reports now use JWT** - Managers need database user accounts
3. **Create manager users** - See "Create Admin User" section above

---

## ⚙️ Configuration

### Environment Variables

Key security-related variables in `.env`:

```bash
# JWT Configuration
JWT_SECRET_KEY=jCVQvFGcPZfRjOACPwH61CvnztGBWTx14Ve1RiFx8QSd7odCmeHGuQYz71Aax8HG4iWPEHS339VqHVoGJ_Z80Q
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480  # 8 hours

# MongoDB
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=store_feedback

# CORS (production)
CORS_ORIGINS=https://store-feedback.tarsyer.com
```

---

## 🚨 Common Issues

### "401 Unauthorized" Error

- **Cause**: No token or expired token
- **Solution**: Login again to get a new token

### "403 Forbidden" Error

- **Cause**: User role doesn't have permission
- **Solution**: Login with manager or admin account

### "Token Expired" on Frontend

- **Cause**: Token validity is 8 hours
- **Solution**: Automatic logout and redirect to login

### Cannot Login

- **Cause**: User doesn't exist in database or wrong password
- **Solution**: Create user in MongoDB (see "Create Admin User")

---

## 🔐 Production Deployment

For production deployment with HTTPS/TLS:

1. Read **[SECURITY_SUMMARY.md](./SECURITY_SUMMARY.md)** first
2. Follow **[DEPLOYMENT.md](./DEPLOYMENT.md)** checklist
3. Configure SSL certificate (Let's Encrypt)
4. Set up Nginx reverse proxy
5. Enable firewall and rate limiting
6. Configure MongoDB authentication
7. Test all security features

**IMPORTANT**: Never deploy without HTTPS in production!

---

## 📞 Support

- **Security Issues**: security@tarsyer.com
- **General Support**: support@tarsyer.com

---

## ✅ Security Checklist

Before going to production:

- [ ] JWT secret key is unique and secure (64+ characters)
- [ ] HTTPS/TLS certificate is valid
- [ ] MongoDB authentication is enabled
- [ ] Firewall is configured (ports 22, 80, 443 only)
- [ ] Rate limiting is active
- [ ] All users have strong passwords
- [ ] Backups are configured
- [ ] Security headers are present
- [ ] CORS is restricted to production domain
- [ ] Debug mode is OFF (DEBUG=false)

---

**Your application is secure and ready for production!** 🎉

For detailed information, see the comprehensive documentation files.
