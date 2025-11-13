# Telegram Anti-Spam Bot

Production-ready Telegram bot for automated spam detection and moderation using python-telegram-bot v20+, running as a webhook on Render with Redis for state management.

## Features

- **Webhook-based**: Runs on Render Web Service with webhooks (no polling)
- **Heuristic spam detection**: Fast, rule-based scoring system
- **Strike policy**: Progressive enforcement (warn → mute → ban)
- **Redis persistence**: User strikes, dedup cache, per-chat settings
- **Admin logging**: Compact moderation logs to a dedicated channel
- **Strict mode**: Per-chat toggle for stricter enforcement
- **Safe by default**: Never acts on admins/owners, fail-safe behavior

## Repository Structure

```
telegram-anti-spam-bot/
├── bot.py              # Entrypoint: webhook server, startup logic
├── config.py           # Environment variable parsing (pydantic)
├── handlers.py         # Command + message handlers
├── rules.py            # Spam scoring rules & thresholds
├── actions.py          # Moderation actions (delete/warn/mute/ban)
├── storage.py          # Redis wrapper (strikes, dedup, settings)
├── utils.py            # Text extraction and analysis helpers
├── data/
│   └── rules.yaml      # Optional externalized rules config
├── tests/
│   └── test_rules.py   # Unit tests for scoring logic
├── requirements.txt
├── Dockerfile
├── .gitignore
├── .dockerignore
├── .env.example
└── README.md
```

## Prerequisites

1. **Telegram Bot**
   - Create bot via [@BotFather](https://t.me/BotFather)
   - Get `BOT_TOKEN`
   - Disable privacy mode: `/setprivacy` → Disable (so bot can read group messages)

2. **Admin Log Channel**
   - Create a private channel for moderation logs
   - Add your bot as an admin
   - Get channel chat ID (e.g., `-1003399150838`)

3. **Render Account**
   - Sign up at [render.com](https://render.com)
   - Create a Redis (Key Value Store) instance
   - Note the Internal and External Redis URLs

4. **GitHub Account**
   - Repository to push your code

---

## Deployment Runbook

### Step 1: Initialize Git Repository

```bash
# Navigate to your project directory
cd telegram-anti-spam-bot

# Initialize git
git init

# Add all files
git add .

# Make initial commit
git commit -m "Initial commit: Telegram anti-spam bot"

# Create GitHub repository (via GitHub UI or CLI)
# Then add remote
git remote add origin https://github.com/YOUR_USERNAME/telegram-anti-spam-bot.git

# Push to GitHub
git branch -M main
git push -u origin main
```

### Step 2: Create Render Redis (Key Value Store)

1. Log into [Render Dashboard](https://dashboard.render.com)
2. Click **"New +"** → **"Key Value Store"**
3. Configure:
   - **Name**: `telegram-bot-redis`
   - **Region**: Oregon (or your preferred region)
   - **Plan**: Free (or paid if needed)
4. Click **"Create Key Value Store"**
5. Note both URLs:
   - **Internal Redis URL**: `redis://red-xxxxxxxxxx:6379` (for production)
   - **External Redis URL**: `rediss://red-xxxxxxxxxx:<PASSWORD>@oregon-keyvalue.render.com:6379` (for local dev)

### Step 3: Create Render Web Service

1. In Render Dashboard, click **"New +"** → **"Web Service"**
2. Connect your GitHub repository:
   - Authorize Render to access your GitHub
   - Select `telegram-anti-spam-bot` repository
3. Configure the service:
   - **Name**: `telegram-anti-spam-bot`
   - **Region**: Oregon (same as Redis for best latency)
   - **Branch**: `main`
   - **Runtime**: Docker (Render will auto-detect the Dockerfile)
   - **Instance Type**: Free (or paid if needed)
4. Click **"Create Web Service"**
5. **Note the service URL**: `https://telegram-anti-spam-bot-xxxx.onrender.com`

### Step 4: Enable Private Networking (IMPORTANT!)

To use the Internal Redis URL (faster, no internet egress):

1. In your Web Service settings, go to **"Settings"** tab
2. Scroll to **"Private Networking"**
3. Click **"Enable Private Networking"**
4. Wait for the service to restart

### Step 5: Add Environment Variables

In your Web Service settings, go to **"Environment"** tab and add:

```bash
# Required
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz123456789
PUBLIC_BASE_URL=https://telegram-anti-spam-bot-xxxx.onrender.com
ADMIN_LOG_CHAT_ID=-1003399150838
REDIS_URL=redis://red-xxxxxxxxxx:6379

# Optional (defaults provided)
STRICT_MODE=false
PORT=8080
HOST=0.0.0.0
LOG_LEVEL=INFO
```

**Important notes:**
- `PUBLIC_BASE_URL`: Use your Render service URL (no trailing slash!)
- `REDIS_URL`: Use **Internal URL** (`redis://...`) if Private Networking is enabled
- If Private Networking is NOT enabled, use **External URL** (`rediss://...` with password)

Click **"Save Changes"** → Service will redeploy automatically

### Step 6: Verify Deployment

#### 6.1 Check Render Logs

1. Go to **"Logs"** tab in your Web Service
2. Look for:
   ```
   ✅ Redis connected (TLS=False)
   ✅ Webhook set: https://your-service.onrender.com/webhook
   ✅ Sent startup notification to admin channel
   Starting bot on 0.0.0.0:8080
   ```

#### 6.2 Test Health Endpoint

```bash
curl https://telegram-anti-spam-bot-xxxx.onrender.com/healthz
# Expected: ok
```

#### 6.3 Check Webhook Info

```bash
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"
```

Expected response:
```json
{
  "ok": true,
  "result": {
    "url": "https://telegram-anti-spam-bot-xxxx.onrender.com/webhook",
    "has_custom_certificate": false,
    "pending_update_count": 0,
    "last_error_date": 0
  }
}
```

#### 6.4 Test Bot in Telegram

1. Add bot to a test group
2. Make bot an admin (delete messages permission)
3. Send test command:
   ```
   /status
   ```
   Expected reply:
   ```
   ✅ Bot online
   Redis: OK
   Strict Mode: OFF
   ```

4. Test spam detection (send a spammy message):
   ```
   🚀 FREE CRYPTO GIVEAWAY 🚀
   https://bit.ly/freecrypto
   https://scam.xyz
   Join now: https://t.me/joinchat/test123
   ```
   - Message should be deleted
   - Admin log channel should receive a moderation log

5. Check admin log channel for startup notification and moderation logs

---

## Common Issues & Troubleshooting

### Issue: Bot doesn't respond to commands

**Possible causes:**
1. **Privacy mode enabled** → Disable via @BotFather: `/setprivacy` → Disable
2. **Bot not in group** → Add bot to the group
3. **Webhook not set** → Check logs for webhook errors, verify PUBLIC_BASE_URL

**Fix:**
```bash
# Check webhook status
curl "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo"

# If needed, delete and re-set webhook (trigger a redeploy on Render)
```

### Issue: Redis connection fails

**Possible causes:**
1. **Wrong REDIS_URL** → Check Render Key Value Store dashboard
2. **Private Networking disabled** → Enable it in Web Service settings
3. **Using external URL without IP allowlist** → Add your service IP or use internal URL

**Fix:**
- Use **Internal URL** (`redis://...`) with Private Networking enabled
- If using External URL (`rediss://...`), ensure IP is allowed in Redis settings

### Issue: Bot deletes legitimate messages

**Possible causes:**
1. **Strict mode enabled** → Toggle with `/togglestrict`
2. **Thresholds too low** → Adjust in `data/rules.yaml`

**Fix:**
```bash
# In Telegram, run:
/togglestrict

# Or edit data/rules.yaml and redeploy:
warn_threshold: 5        # Increase from 4
hard_delete_threshold: 10 # Increase from 8
```

### Issue: Webhook returns 403/401 errors

**Possible causes:**
1. **Wrong BOT_TOKEN** → Verify in Render environment variables
2. **Telegram can't reach your service** → Check Render logs, ensure service is running

**Fix:**
- Verify BOT_TOKEN is correct
- Check Render service status (should be "Live")
- Review Render logs for errors

### Issue: Service crashes on startup

**Possible causes:**
1. **Missing environment variables** → Check all required vars are set
2. **Docker build failed** → Check Render build logs
3. **Invalid config** → Check for typos in env vars

**Fix:**
```bash
# Check Render build logs for errors
# Verify all required env vars are set:
# - BOT_TOKEN
# - PUBLIC_BASE_URL
# - ADMIN_LOG_CHAT_ID
# - REDIS_URL
```

---

## Local Development

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/telegram-anti-spam-bot.git
   cd telegram-anti-spam-bot
   ```

2. Create virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create `.env` file (copy from `.env.example`):
   ```bash
   cp .env.example .env
   # Edit .env with your values
   ```

5. Run local Redis (via Docker):
   ```bash
   docker run -d -p 6379:6379 redis:7-alpine
   ```

6. Set up ngrok for webhook testing:
   ```bash
   ngrok http 8080
   # Copy the HTTPS URL to PUBLIC_BASE_URL in .env
   ```

7. Run the bot:
   ```bash
   python bot.py
   ```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run specific test file
pytest tests/test_rules.py -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

---

## Configuration

### Spam Detection Rules

Edit `data/rules.yaml` to customize thresholds and rules:

```yaml
# Thresholds
warn_threshold: 4          # Score to trigger warning
hard_delete_threshold: 8   # Score to trigger deletion + strikes

# Suspicious TLDs (add more as needed)
suspicious_tlds:
  - ru
  - xyz
  - top
  # ... add more
```

### Strike Policy

Defined in `handlers.py`:
1. **1st offense**: Delete + warn user
2. **2nd offense**: Delete + mute (24h)
3. **3rd+ offense**: Delete + ban

Strikes expire after 7 days (configurable in `storage.py`).

### Scoring Rules

Defined in `rules.py`:
- **2+ links**: +2 to +4 points
- **Suspicious TLD**: +2 per TLD (max +6)
- **URL shortener**: +3 points
- **Telegram invite**: +4 points
- **Spam keywords**: +5 points
- **Unicode tricks**: +3 points
- **Strict mode**: +1 (if non-zero score)

---

## Commands

- `/status` - Show bot status, Redis health, strict mode
- `/togglestrict` - Toggle strict mode for current chat (admin only)

---

## Security Best Practices

1. **Never commit secrets**: Use environment variables, never hardcode tokens
2. **Use Private Networking**: Faster Redis access, no internet egress
3. **Non-root user**: Dockerfile runs as `botuser` (UID 1000)
4. **Fail-safe behavior**: Bot never acts on admins, fails gracefully
5. **Rate limiting**: Telegram enforces rate limits; bot respects them
6. **Input validation**: All user inputs are sanitized
7. **Dedup cache**: Prevents double-actions on same content

---

## Monitoring & Maintenance

### Health Checks

- **Render**: Built-in health check at `/healthz` (30s interval)
- **Telegram**: Webhook info via API
- **Redis**: PING command in logs

### Logs

- **Render Logs**: View in dashboard (real-time)
- **Admin Channel**: Moderation actions logged here
- **Log Level**: Set via `LOG_LEVEL` env var (DEBUG/INFO/WARNING/ERROR)

### Backups

- **Redis data**: Strikes/settings stored in Redis (ephemeral on free tier)
- **Configuration**: `data/rules.yaml` in git
- **Code**: Always committed to GitHub

---

## Scaling & Performance

### Current Limits (Free Tier)

- **Render Free**: 750 hours/month, sleeps after 15min inactivity
- **Redis Free**: 25MB storage, basic persistence

### Upgrading for Production

1. **Render**: Upgrade to Starter ($7/mo) for always-on service
2. **Redis**: Upgrade to paid plan for more storage + persistence
3. **Optimize**: Add caching, batch operations, connection pooling

### Expected Performance

- **Latency**: <100ms per message (with Private Networking)
- **Throughput**: ~10-50 msg/sec (limited by Telegram rate limits)
- **Memory**: ~50-100MB RSS

---

## Future Enhancements

- [ ] LLM classification for borderline cases (Claude API)
- [ ] Admin web dashboard (Flask/FastAPI)
- [ ] More sophisticated ML models
- [ ] User reputation scoring
- [ ] Image/video content analysis
- [ ] Multi-language support
- [ ] Custom per-chat rules
- [ ] Whitelist/blacklist management commands

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit changes: `git commit -am 'Add new feature'`
4. Push to branch: `git push origin feature/my-feature`
5. Create Pull Request

---

## License

MIT License - see LICENSE file for details

---

## Support

- **Issues**: [GitHub Issues](https://github.com/YOUR_USERNAME/telegram-anti-spam-bot/issues)
- **Telegram**: [@YourUsername](https://t.me/YourUsername)

---

## Acknowledgments

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [Render](https://render.com)
- [Redis](https://redis.io)
