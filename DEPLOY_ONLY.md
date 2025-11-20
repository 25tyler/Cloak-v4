# What You Need To Do - Deployment Only

Everything else is automated! Just follow these steps:

## 🚀 Quick Setup (Run Once)

```bash
cd /Users/tyler/Cloakv3
./setup.sh
```

This automatically:
- ✅ Installs dependencies
- ✅ Generates the encrypted font
- ✅ Sets up all directories

---

## 📋 What You Need To Do

### 1. Upload Font to CDN

**File:** `fonts/encrypted.woff2` (created automatically)

**Upload to:**
- Cloudflare Pages (free)
- AWS S3 + CloudFront
- Your own CDN

**Get the URL** (e.g., `https://your-cdn.com/fonts/encrypted.woff2`)

---

### 2. Update Backend Configuration

**File:** `backend/encrypt_api.py`

**Line 111:** Change font URL:
```python
font_url = os.environ.get('FONT_URL', 'https://your-actual-font-url.com/encrypted.woff2')
```

---

### 3. Deploy Backend to Heroku

```bash
cd /Users/tyler/Cloakv3/backend

# Login (opens browser)
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

**Save your API URL:** `https://your-app-name.herokuapp.com/api/encrypt`

---

### 4. Update JavaScript Configuration

**File:** `client/encrypt-articles.js`

**Lines 16-18:** Change to your Heroku API URL:
```javascript
apiEndpoint: 'https://your-app-name.herokuapp.com/api/encrypt',
batchEndpoint: 'https://your-app-name.herokuapp.com/api/encrypt/batch',
```

---

### 5. Upload JavaScript to CDN

**File:** `client/encrypt-articles.js`

**Upload to:**
- Cloudflare Pages
- GitHub + jsDelivr
- Your own CDN

**Get the URL** (e.g., `https://your-cdn.com/encrypt-articles.js`)

---

### 6. Use on News Sites

News sites add this ONE line:
```html
<script src="https://your-cdn.com/encrypt-articles.js" async></script>
```

**Done!**

---

## ✅ That's It!

Everything else is automated:
- ✅ Font generation
- ✅ Code setup
- ✅ Dependencies
- ✅ File structure

You only handle:
1. Upload font to CDN
2. Deploy backend (Heroku)
3. Upload JavaScript to CDN
4. Use on sites

**Total time: ~30 minutes**

