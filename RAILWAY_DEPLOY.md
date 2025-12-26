# 🚂 Railway Deployment Guide

This guide explains how to deploy Gheezy Crypto bot to [Railway.app](https://railway.app) for 24/7 operation.

## 📋 Prerequisites

- GitHub account
- Railway account (sign up at [railway.app](https://railway.app))
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)
- API keys (CoinGecko, Etherscan, etc.)

## 🚀 Deployment Steps

### 1. Connect Repository to Railway

1. Go to [Railway.app](https://railway.app) and sign in
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose your fork of `gheezy-crypto`
5. Railway will automatically detect the configuration

### 2. Configure Environment Variables

In your Railway project dashboard:

1. Go to **"Variables"** tab
2. Add the following environment variables:

#### Required Variables

```
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

#### Optional Variables (for full functionality)

```
# Database (Railway provides PostgreSQL addon)
DATABASE_URL=postgresql://user:pass@host:port/db

# Redis (Railway provides Redis addon)
REDIS_URL=redis://host:port

# API Keys
COINGECKO_API_KEY=your_coingecko_key
ETHERSCAN_API_KEY=your_etherscan_key

# Other configurations
LOG_LEVEL=INFO
```

#### Getting Environment Variables from .env file

If you have a local `.env` file:

1. Open your `.env` file
2. Copy each line (excluding comments and empty lines)
3. In Railway Variables tab, click **"Add Variable"**
4. Paste the variable name and value

### 3. Add PostgreSQL Database (Optional)

1. In your Railway project, click **"New"**
2. Select **"Database"** → **"Add PostgreSQL"**
3. Railway will automatically set `DATABASE_URL` variable
4. The bot will use this database for storing data

### 4. Add Redis (Optional)

1. In your Railway project, click **"New"**
2. Select **"Database"** → **"Add Redis"**
3. Railway will automatically set `REDIS_URL` variable
4. The bot will use Redis for caching

### 5. Deploy

1. Railway will automatically deploy when you push to GitHub
2. Or click **"Deploy"** button in Railway dashboard
3. Wait for build to complete (2-5 minutes)
4. Check logs to verify bot is running

## 📊 Monitoring the Bot

### View Logs

1. Go to your Railway project
2. Click on your service
3. Select **"Logs"** tab
4. You'll see real-time logs:
   ```
   ================================================== 
   GHEEZY CRYPTO BOT
   ==================================================
   Запуск Telegram бота...
   ```

### Check Bot Status

1. Open Telegram
2. Send `/start` to your bot
3. Bot should respond immediately

### Monitor Resource Usage

1. In Railway dashboard, go to **"Metrics"** tab
2. View:
   - Memory usage
   - CPU usage
   - Network traffic

## 💰 Pricing & Free Tier

Railway offers:
- **$5 free credits per month** for all users
- **500 free hours per month** (~21 days) for Hobby plan
- Bot typically uses minimal resources (100-200 MB RAM)

### Estimated Monthly Cost

With free credits:
- **Free** if bot runs ~21 days/month (500 hours)
- After free hours, approximately $1-3/month depending on usage

## 🔄 Updates & Redeployment

Railway automatically redeploys when you push to GitHub:

```bash
# Make changes to your code
git add .
git commit -m "Update bot features"
git push origin main

# Railway will automatically detect and redeploy
```

## 🐛 Troubleshooting

### Bot not starting

1. Check logs in Railway dashboard
2. Verify `TELEGRAM_BOT_TOKEN` is set correctly
3. Ensure no typos in environment variables

### Bot stops after a while

1. Check Railway free hours limit (500/month)
2. Add payment method for unlimited uptime
3. Check logs for error messages

### Database connection errors

1. Verify `DATABASE_URL` is set
2. Ensure PostgreSQL addon is active
3. Check database credentials

### Import errors

If you see missing package errors:
1. Check `requirements.txt` includes the package
2. Redeploy to reinstall dependencies
3. Check Railway build logs

## 📚 Additional Resources

- [Railway Documentation](https://docs.railway.app)
- [Railway Discord Support](https://discord.gg/railway)
- [Gheezy Crypto README](README.md)

## 🔧 Advanced Configuration

### Custom Start Command

If you need to modify the start command:

1. Edit `Procfile` in repository root
2. Current: `worker: cd src && python main.py`
3. Commit and push changes

### Python Version

To change Python version:

1. Edit `runtime.txt` in repository root
2. Current: `python-3.11.0`
3. Available versions: 3.8, 3.9, 3.10, 3.11, 3.12

### Environment-Specific Configuration

You can use Railway environment variables in your code:

```python
import os

# Check if running on Railway
is_railway = os.getenv('RAILWAY_ENVIRONMENT') is not None

if is_railway:
    # Railway-specific configuration
    pass
```

## ✅ Success Checklist

After deployment, verify:

- [ ] Bot responds to `/start` command
- [ ] Logs show successful startup
- [ ] No error messages in Railway logs
- [ ] All API integrations working
- [ ] Database connections successful (if used)
- [ ] Bot runs continuously without crashes

---

**Need help?** Open an issue on [GitHub](https://github.com/kissismeowww19-droid/gheezy-crypto/issues)
