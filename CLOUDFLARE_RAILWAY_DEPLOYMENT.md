# Cloudflare Pages + Railway Deployment Guide

This guide will walk you through deploying the ACCC Merger Tracker to **Cloudflare Pages** (frontend) and **Railway** (backend) for **FREE** using your custom domain `mergers.fyi`.

## 📋 Prerequisites

- GitHub account with access to this repository
- Domain name: `mergers.fyi` (already owned)
- Railway account (sign up at https://railway.app)
- Cloudflare account (sign up at https://cloudflare.com)

## 🚂 Part 1: Deploy Backend to Railway

### Step 1: Create Railway Account and Project

1. Go to https://railway.app and sign up/login with GitHub
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Connect your GitHub account if not already connected
5. Select the `accc-mergers` repository
6. Railway will detect the Python application

### Step 2: Configure Backend Service

⚠️ **Important**: Railway's "Root Directory" setting may not work as expected. Instead, we use configuration files and a start command that changes to the correct directory.

**Recommended Configuration:**

1. After Railway creates the project, click on the service
2. Go to **Settings** tab
3. **Leave Root Directory empty** (or set to `.`)
4. The **Start Command** is already configured in `railway.toml` and `merger-tracker/backend/railway.json`:
   ```
   cd merger-tracker/backend && uvicorn main:app --host 0.0.0.0 --port $PORT
   ```

The repository includes configuration files (`railway.toml`, `nixpacks.toml`, and `merger-tracker/backend/railway.json`) that Railway will automatically detect and use.

The repository includes a wrapper `main.py` at the root that imports the backend application.

### Step 3: Add Environment Variables

1. Go to the **Variables** tab
2. Add the following environment variables:

```
ALLOWED_ORIGINS=https://mergers.fyi,https://www.mergers.fyi
DATABASE_PATH=mergers.db
```

### Step 4: Set Up Persistent Storage for Database

1. Go to the **Data** tab (or **Volumes**)
2. Click **"New Volume"**
3. Mount path: `/app/merger-tracker/backend`
4. This ensures your SQLite database persists across deployments
5. The database file will be created at `/app/merger-tracker/backend/mergers.db`

### Step 5: Initialize Database

1. Once deployed, go to the **Deployments** tab
2. Wait for the initial deployment to complete
3. Open the deployment logs
4. The database should auto-initialize when the app starts

**Optional: Manually sync data**
1. Click on your service
2. Go to **Settings** → **Deploy**
3. You can run a one-time command: `python sync_data.py`

### Step 6: Get Your Backend URL

1. Go to **Settings** tab
2. Under **Networking** → **Public Networking**
3. Click **Generate Domain**
4. You'll get a URL like: `https://your-backend.railway.app`
5. **Copy this URL** - you'll need it for the frontend

### Step 7: Set Up Custom Domain (api.mergers.fyi)

1. In Railway, go to **Settings** → **Networking**
2. Click **Custom Domain**
3. Enter: `api.mergers.fyi`
4. Railway will show you DNS records to add
5. **Keep this tab open** - you'll configure DNS in Part 3

---

## ☁️ Part 2: Deploy Frontend to Cloudflare Pages

### Step 1: Transfer Domain to Cloudflare (if not already)

1. Go to https://dash.cloudflare.com
2. Click **"Add Site"**
3. Enter `mergers.fyi`
4. Follow the instructions to update your nameservers at your domain registrar
5. Wait for DNS propagation (can take up to 24-48 hours)

### Step 2: Create Cloudflare Pages Project

1. In Cloudflare dashboard, go to **Pages**
2. Click **"Create a project"**
3. Select **"Connect to Git"**
4. Connect your GitHub account
5. Select the `accc-mergers` repository
6. Click **"Begin setup"**

### Step 3: Configure Build Settings

Set the following configuration:

```
Project name: mergers-fyi (or any name you prefer)
Production branch: main (or your default branch)
Build command: npm run build
Build output directory: dist
Root directory: merger-tracker/frontend
```

### Step 4: Add Environment Variables

Before deploying, add environment variable:

1. Scroll to **Environment variables** section
2. Click **"Add variable"**
3. Add:
   - **Variable name**: `VITE_API_URL`
   - **Value**: `https://api.mergers.fyi` (your Railway custom domain)

**Important:** Use the custom domain `api.mergers.fyi` NOT the Railway-generated URL

### Step 5: Deploy

1. Click **"Save and Deploy"**
2. Cloudflare will build and deploy your frontend
3. Wait 3-5 minutes for the build to complete
4. You'll get a temporary URL like: `https://mergers-fyi.pages.dev`

### Step 6: Configure Custom Domain

1. Go to **Custom domains** tab
2. Click **"Set up a custom domain"**
3. Enter: `mergers.fyi`
4. Click **"Continue"**
5. Cloudflare will automatically configure DNS (if domain is on Cloudflare)
6. Add `www.mergers.fyi` as well (optional but recommended)
   - Click **"Add custom domain"**
   - Enter: `www.mergers.fyi`
   - Set it to redirect to `mergers.fyi`

---

## 🌐 Part 3: Configure DNS

### Option A: If Domain is on Cloudflare (Recommended)

DNS will be automatically configured when you set up custom domains in Parts 1 & 2.

**Verify your DNS records:**

1. Go to **DNS** → **Records** in Cloudflare
2. You should see:
   - `CNAME` record: `mergers.fyi` → `mergers-fyi.pages.dev`
   - `CNAME` record: `www.mergers.fyi` → `mergers-fyi.pages.dev`
   - `CNAME` record: `api.mergers.fyi` → `your-backend.railway.app`

### Option B: If Domain is NOT on Cloudflare

1. Log in to your domain registrar (e.g., GoDaddy, Namecheap, etc.)
2. Go to DNS settings
3. Add the following records:

**For Frontend (mergers.fyi):**
```
Type: CNAME
Name: @ (or leave blank for root domain)
Value: mergers-fyi.pages.dev
TTL: Auto or 3600
```

```
Type: CNAME
Name: www
Value: mergers-fyi.pages.dev
TTL: Auto or 3600
```

**For Backend (api.mergers.fyi):**
```
Type: CNAME
Name: api
Value: [Railway provided DNS target]
TTL: Auto or 3600
```

4. Save changes and wait for DNS propagation (5 minutes to 24 hours)

---

## ✅ Part 4: Verify Deployment

### Test Backend API

Open your browser or use curl:

```bash
curl https://api.mergers.fyi/
```

You should see:
```json
{"message": "ACCC Merger Tracker API", "version": "1.0.0"}
```

### Test Frontend

1. Open: https://mergers.fyi
2. You should see the merger tracker application
3. Navigate through the pages to ensure everything works
4. Check browser console for any errors

### Test Full Integration

1. Go to https://mergers.fyi
2. Check if mergers data loads correctly
3. Test search functionality
4. View individual merger details
5. Check statistics page

---

## 🔄 Part 5: Set Up Automated Data Sync (Optional)

### Option 1: GitHub Actions (Recommended)

Create `.github/workflows/sync-data.yml`:

```yaml
name: Sync Merger Data

on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours
  workflow_dispatch:  # Manual trigger

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd merger-tracker/backend
          pip install -r requirements.txt

      - name: Sync data
        run: |
          cd merger-tracker/backend
          python sync_data.py
        env:
          RAILWAY_API_TOKEN: ${{ secrets.RAILWAY_API_TOKEN }}
```

### Option 2: Railway Cron Job

Railway doesn't have built-in cron, but you can use an external service:

1. Use https://cron-job.org (free)
2. Create a new cron job
3. URL: `https://api.mergers.fyi/api/sync` (you'd need to add this endpoint)
4. Schedule: Every 6 hours

---

## 💰 Cost Breakdown

### Railway (Backend)
- **Free Tier**: $5/month in credits
- **Your Usage**: ~$2-3/month estimated
- **Cost**: **FREE** (within free tier)

### Cloudflare Pages (Frontend)
- **Free Tier**: 500 builds/month, unlimited requests
- **Your Usage**: Well within limits
- **Cost**: **FREE**

### Domain (mergers.fyi)
- Already owned by you
- **Cost**: Whatever you're currently paying (~$10-15/year)

**Total Monthly Cost: $0 🎉**

---

## 🔧 Troubleshooting

### Backend Issues

**Problem**: Railway deployment fails

**Solution**:
- Check deployment logs in Railway dashboard
- Ensure `requirements.txt` is in the correct directory
- Verify Python version (should be 3.11+)

**Problem**: Database not persisting

**Solution**:
- Ensure volume is mounted to `/app`
- Check that `DATABASE_PATH` env var is set correctly

### Frontend Issues

**Problem**: Build fails on Cloudflare Pages

**Solution**:
- Check build logs for errors
- Ensure `package.json` is correct
- Verify Node version (20.11.0)

**Problem**: API calls failing (CORS errors)

**Solution**:
- Verify `VITE_API_URL` is set correctly in Cloudflare Pages
- Check CORS configuration in backend `main.py`
- Ensure `mergers.fyi` is in allowed origins

### DNS Issues

**Problem**: Domain not resolving

**Solution**:
- Wait for DNS propagation (can take up to 48 hours)
- Use https://dnschecker.org to check DNS status
- Verify CNAME records are correct

---

## 🚀 Next Steps

### Monitoring

1. **Railway**:
   - Check deployment logs regularly
   - Set up usage alerts

2. **Cloudflare**:
   - Monitor analytics in Cloudflare dashboard
   - Check Core Web Vitals

### Security

1. Enable Cloudflare security features:
   - DDoS protection (automatic)
   - Rate limiting (optional)
   - Bot protection (optional)

2. Railway:
   - Rotate secrets regularly
   - Review access logs

### Performance

1. Enable Cloudflare caching:
   - Go to **Caching** → **Configuration**
   - Set cache rules for static assets

2. Consider CDN:
   - Cloudflare provides this automatically

---

## 🎉 You're Done!

Your merger tracker is now live at:
- **Frontend**: https://mergers.fyi
- **API**: https://api.mergers.fyi

Enjoy your free, production-ready deployment! 🚀
