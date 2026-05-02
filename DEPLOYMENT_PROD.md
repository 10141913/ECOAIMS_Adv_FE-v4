# ECOAIMS Production Deployment Guide

This guide covers building, pushing, and deploying ECOAIMS Docker images to a production server.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Build Docker Images](#1-build-docker-images)
3. [Push to Docker Hub](#2-push-to-docker-hub)
4. [Deploy on Production Server](#3-deploy-on-production-server)
5. [Environment Variables Reference](#4-environment-variables-reference)
6. [Troubleshooting](#5-troubleshooting)

---

## Prerequisites

- **Docker** installed on your local machine and production server
- **Docker Hub** account (`juliansyah`)
- Access to both frontend and backend source code

### Local Development Machine

```bash
# Verify Docker
docker --version
docker-compose --version

# Login to Docker Hub (one-time)
docker login
```

### Production Server

```bash
# Verify Docker
docker --version
docker-compose --version

# Login to Docker Hub (one-time)
docker login
```

---

## 1. Build Docker Images

### Option A: Using the build script (recommended)

```bash
# Build only (no push) — verifies images compile correctly
bash build-push.sh --no-push

# Build with a version tag (no push)
bash build-push.sh v1.0.0 --no-push
```

### Option B: Manual build commands

```bash
# Backend
docker build \
  -t juliansyah/ecoaims-backend:latest \
  -t juliansyah/ecoaims-backend:v1.0.0 \
  -f "/Users/juliansyah/Documents/UNDIP/Disertasi/4. Apps/pythonProject/ECO_AIMS/ECOAIMS_Adv_BE v-4/Dockerfile" \
  "/Users/juliansyah/Documents/UNDIP/Disertasi/4. Apps/pythonProject/ECO_AIMS/ECOAIMS_Adv_BE v-4"

# Frontend
docker build \
  -t juliansyah/ecoaims-frontend:latest \
  -t juliansyah/ecoaims-frontend:v1.0.0 \
  -f Dockerfile \
  .
```

### Verify images

```bash
docker images --filter "reference=juliansyah/ecoaims-*"
```

Expected output:
```
REPOSITORY                      TAG       IMAGE ID       CREATED         SIZE
juliansyah/ecoaims-backend      latest    abc123def456   2 minutes ago   1.2GB
juliansyah/ecoaims-backend      v1.0.0    abc123def456   2 minutes ago   1.2GB
juliansyah/ecoaims-frontend     latest    def789abc123   2 minutes ago   500MB
juliansyah/ecoaims-frontend     v1.0.0    def789abc123   2 minutes ago   500MB
```

---

## 2. Push to Docker Hub

### Using the build script

```bash
# Build and push with 'latest' tag
bash build-push.sh

# Build and push with version tag
bash build-push.sh v1.0.0
```

### Manual push

```bash
# Push backend
docker push juliansyah/ecoaims-backend:latest
docker push juliansyah/ecoaims-backend:v1.0.0

# Push frontend
docker push juliansyah/ecoaims-frontend:latest
docker push juliansyah/ecoaims-frontend:v1.0.0
```

### Verify on Docker Hub

Visit: https://hub.docker.com/u/juliansyah

---

## 3. Deploy on Production Server

### Step 1: Copy production files to server

```bash
# On your local machine
scp .env.production docker-compose.prod.yml user@your-server:/opt/ecoaims/
```

### Step 2: Configure environment variables

```bash
# On the production server
cd /opt/ecoaims

# Edit .env.production with your actual secrets
nano .env.production
```

**Critical: Generate strong secrets**

```bash
# Generate ECOAIMS_AUTH_SECRET
python3 -c "import secrets; print(secrets.token_hex(32))"

# Generate admin password hash (requires bcrypt)
python3 -c "import bcrypt; print(bcrypt.hashpw(b'your-admin-password', bcrypt.gensalt()).decode())"
```

### Step 3: Deploy with Docker Compose

```bash
# Export environment variables
export $(grep -v '^#' .env.production | xargs)

# Pull latest images and start
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d

# Check status
docker-compose -f docker-compose.prod.yml ps
docker-compose -f docker-compose.prod.yml logs -f
```

### Step 4: Verify deployment

```bash
# Check backend health
curl http://localhost:8008/health

# Check frontend
curl -o /dev/null -s -w "%{http_code}" http://localhost:8050

# Check backend API docs
curl http://localhost:8008/docs
```

### Step 5: Set up reverse proxy (recommended)

For production, place Nginx or Caddy in front of both services:

```nginx
# /etc/nginx/sites-available/ecoaims
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8050;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8008;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 4. Environment Variables Reference

### Backend (`ecoaims-backend`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `ECOAIMS_ENV` | Yes | `production` | Environment mode |
| `ECOAIMS_AUTH_SECRET` | **Yes** | — | Strong random secret for auth |
| `ECOAIMS_ADMIN_PASSWORD_HASH` | **Yes** | — | bcrypt/scrypt hash of admin password |
| `ECOAIMS_ENFORCE_HTTPS` | No | `true` | Redirect HTTP to HTTPS |
| `ECOAIMS_ALLOWED_ORIGINS` | No | `http://localhost:8050` | CORS allowed origins |
| `SQLITE_PATH` | No | `/app/.run/ecoaims.db` | SQLite database path |

### Frontend (`ecoaims-frontend`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `ECOAIMS_API_BASE_URL` | Yes | `http://ecoaims-backend:8008` | Backend URL (internal Docker DNS) |
| `ECOAIMS_API_PUBLIC_URL` | Yes | `http://localhost:8008` | Backend URL (browser-accessible) |
| `ECOAIMS_AUTH_ENABLED` | No | `false` | Enable Dash auth |
| `ECOAIMS_DASH_DEBUG` | No | `false` | Dash debug mode |
| `ECOAIMS_DASH_USE_RELOADER` | No | `false` | Dash hot-reload |
| `ECOAIMS_DASH_HOST` | No | `0.0.0.0` | Dash listen address |

---

## 5. Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose -f docker-compose.prod.yml logs ecoaims-backend
docker-compose -f docker-compose.prod.yml logs ecoaims-frontend
```

### Backend healthcheck fails

```bash
# Check if backend is listening
docker exec ecoaims-backend-prod python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8008/health').read())"
```

### Frontend can't reach backend

```bash
# Check DNS resolution inside frontend container
docker exec ecoaims-frontend-prod python -c "import socket; print(socket.gethostbyname('ecoaims-backend'))"
```

### Database issues

```bash
# Check if SQLite volume exists
docker volume ls | grep backend_data

# Inspect volume location
docker volume inspect ecoaims_backend_data
```

### Reset everything

```bash
# Stop and remove containers, volumes, and images
docker-compose -f docker-compose.prod.yml down -v
docker rmi juliansyah/ecoaims-backend:latest juliansyah/ecoaims-frontend:latest

# Redeploy
docker-compose -f docker-compose.prod.yml up -d
```

---

## Quick Reference

```bash
# ── Local: Build only ──────────────────────────────────────
bash build-push.sh --no-push

# ── Local: Build & push ────────────────────────────────────
bash build-push.sh v1.0.0

# ── Server: Deploy ─────────────────────────────────────────
export $(grep -v '^#' .env.production | xargs)
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d

# ── Server: Update ─────────────────────────────────────────
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d

# ── Server: Stop ───────────────────────────────────────────
docker-compose -f docker-compose.prod.yml down

# ── Server: View logs ──────────────────────────────────────
docker-compose -f docker-compose.prod.yml logs -f
```
