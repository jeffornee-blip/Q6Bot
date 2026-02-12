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

### 3. **Configure Environment Variables**
In Railway Dashboard, go to Variables and set:

**Discord Bot:**
- `DC_BOT_TOKEN` = Your Discord bot token
- `DC_CLIENT_ID` = Your bot's client ID
- `DC_OWNER_ID` = Your Discord user ID

**Database:**
- `DATABASE_URL` = The URL from your Railway MySQL service (it auto-generates this)
  - Railway MySQL creates this automatically, just reference it via `${{DATABASE_URL}}`

**Optional:**
- `DC_SLACK_SERVERS` = JSON array of server IDs if limiting slash commands
- `LOG_LEVEL` = DEBUG, INFO, or ERRORS
- `STATUS` = Bot presence/status message
- `WS_ENABLE` = true/false for web server

### 4. **Important Notes**
- The bot expects a `.version` file - ensure it's in the repository
- `saved_state.json` is created at runtime
- Database must be accessible from Railway (verify connection string)
- Use `DATABASE_URL` environment variable provided by Railway MySQL

### 5. **Troubleshooting**

**Bot keeps crashing:**
1. Check logs: Railway Dashboard → Service → Logs
2. Verify `DC_BOT_TOKEN` is correct
3. Verify `DATABASE_URL` is correctly formatted
4. Ensure bot has required Discord permissions

**Database connection fails:**
1. Check the auto-generated `DATABASE_URL` format
2. Ensure MySQL service is running in Railway
3. Restart the bot service

### Example Environment Variables for Railway:
```
DC_BOT_TOKEN=<your_token>
DC_CLIENT_ID=<your_id>
DC_OWNER_ID=<your_id>
DATABASE_URL=${{DATABASE_URL}}
LOG_LEVEL=INFO
```

The config system now supports both local development (using config.cfg) and Railway deployment (using environment variables).
