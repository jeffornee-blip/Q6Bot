# Railway Deployment Guide

## Steps to Deploy to Railway

### 1. **Secure Your Repository**
```bash
# Remove credentials from git history
git rm --cached config.cfg
git commit -m "Remove config.cfg from tracking"
git push

# Add to .gitignore (already done)
```

### 2. **Set Up Railway Project**
- Go to https://railway.app
- Create new project → Deploy from GitHub
- Connect your repository
- Click "Add Service" → Railway MySQL (or connect your existing MySQL)

### 3. **Configure Environment Variables - REQUIRED!**
In Railway Dashboard, go to your Q6Bot service → **Variables** and add these:

**Discord Bot (REQUIRED - Must set these):**
- `DC_BOT_TOKEN` = Your Discord bot token (from Discord Developer Portal)
- `DC_CLIENT_ID` = Your bot's client ID (from Discord Developer Portal)
- `DC_OWNER_ID` = Your Discord user ID (right-click profile in Discord)

**Database (REQUIRED):**
- `DATABASE_URL` = Copy from Railway MySQL service variables
  - Go to MySQL service → Variables
  - Copy the MySQL connection URL and paste it here
  - Format should be: `mysql://username:password@host:port/database`

**Optional:**
- `LOG_LEVEL` = DEBUG, INFO, or ERRORS (default: INFO)
- `STATUS` = Bot's Discord status message
- `WS_ENABLE` = true to enable web server (default: false)

### 4. **IMPORTANT: How to Get Database URL**
1. In your Railway project, click on the **MySQL** service
2. Go to the **Variables** tab
3. Copy the auto-generated `DATABASE_URL` 
4. Paste it into your Q6Bot service variables with the same key: `DATABASE_URL`

### 5. **Troubleshooting**

**Bot won't start - Check these steps:**

1. **View detailed logs:**
   - Go to Railway Dashboard → Q6Bot service → Logs filter
   - Look for startup messages with `[STARTUP]` or `[ERROR]`

2. **Missing environment variables:**
   ```
   Error message: "✗ DC_BOT_TOKEN is NOT set" or "✗ DATABASE_URL is NOT set"
   Solution: Add the missing variables in Railway Dashboard → Variables
   ```

3. **Database connection failed:**
   ```
   Error message: "Failed to connect to database"
   Solution: 
   - Verify DATABASE_URL is copied correctly from MySQL service
   - Make sure it starts with "mysql://"
   - Check that MySQL service is running (green status)
   ```

4. **Bot starts but stays offline:**
   - Check that DC_BOT_TOKEN is valid (hasn't been regenerated in Discord)
   - Ensure bot has required Discord permissions
   - Check logs for connection errors

**Example successful startup looks like:**
```
[STARTUP] Checking environment variables...
✓ DC_BOT_TOKEN is set
✓ DATABASE_URL is set
[STARTUP] Loading bot core modules...
[STARTUP] ✓ Core modules loaded
[STARTUP] Connecting to database...
[STARTUP] ✓ Database connected
[STARTUP] Loading bot...
[STARTUP] ✓ Bot loaded
[STARTUP] Checking web server configuration...
[STARTUP] Web server disabled
```

### 6. **Quick Checklist Before Deploying**

- [ ] Discord bot token created (Discord Developer Portal)
- [ ] Bot invited to your server with proper permissions
- [ ] MySQL database created in Railway
- [ ] All 3 required variables set in Railway Q6Bot service:
  - `DC_BOT_TOKEN`
  - `DC_CLIENT_ID` 
  - `DC_OWNER_ID`
  - `DATABASE_URL`
- [ ] Code pushed to GitHub
- [ ] Railway service restarted after variable changes
