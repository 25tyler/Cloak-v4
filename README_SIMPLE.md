# Simple Setup - Everything Automated!

## ✅ Already Done Automatically

- ✅ Font generated: `fonts/encrypted.woff2` (130KB)
- ✅ All code ready
- ✅ Dependencies installed
- ✅ 53 glyph swaps completed

## 📋 What You Need To Do (Only 3 Things)

### 1. Upload Font to CDN

**File:** `fonts/encrypted.woff2`

Upload to Cloudflare/AWS/your CDN and get the URL.

---

### 2. Deploy Backend to Heroku

```bash
cd /Users/tyler/Cloakv3/backend

# Login
heroku login

# Create app
heroku create your-app-name

# Set font URL
heroku config:set FONT_URL=https://your-font-url.com/encrypted.woff2

# Deploy
git init
git add .
git commit -m "Initial commit"
git push heroku main
```

**Save API URL:** `https://your-app-name.herokuapp.com/api/encrypt`

---

### 3. Update & Deploy JavaScript

**Edit:** `client/encrypt-articles.js` (lines 16-18)
- Change API URLs to your Heroku URL

**Upload** `client/encrypt-articles.js` to CDN

**Get URL:** `https://your-cdn.com/encrypt-articles.js`

---

### 4. Use on News Sites

Add this one line:
```html
<script src="https://your-cdn.com/encrypt-articles.js" async></script>
```

**Done!**

---

## 🎯 That's It!

Everything else is automated. Just:
1. Upload font
2. Deploy backend (Heroku)
3. Upload JavaScript
4. Use it

**Time: ~20 minutes**

