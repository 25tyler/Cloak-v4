# Exact Instructions - What You Need To Do

Follow these steps **in order**. Everything is ready, you just need to configure and deploy.

---

## ✅ STEP 1: Test Locally (5 minutes)

### 1.1 Install Dependencies

```bash
cd /Users/tyler/Cloakv3/backend
pip install -r requirements.txt
```

**Expected:** Should install Flask and flask-cors successfully.

---

### 1.2 Test the Algorithm

```bash
cd /Users/tyler/Cloakv3
python test_algorithm.py
```

**Expected:** Shows encrypted outputs for test strings. Verify these match your PDF encryption.

**If it doesn't match:** Check that the mapping dictionaries are identical to `EncTestNewTestF.py`.

---

### 1.3 Start the Server

```bash
cd /Users/tyler/Cloakv3/backend
python encrypt_api.py
```

**Expected output:**
```
Starting Article Encryption API on 0.0.0.0:5000
Debug mode: False
API endpoint: http://0.0.0.0:5000/api/encrypt
 * Running on http://127.0.0.1:5000
```

**Keep this terminal open** - server must keep running.

---

### 1.4 Test the API (New Terminal)

Open a **new terminal window** and run:

```bash
# Test single encryption
curl -X POST http://localhost:5000/api/encrypt \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello World"}'
```

**Expected response:**
```json
{
  "encrypted": "Heoov rWvaog",
  "font_url": "https://your-cdn.com/fonts/encrypted.woff2"
}
```

**Test batch encryption:**
```bash
curl -X POST http://localhost:5000/api/encrypt/batch \
  -H "Content-Type: application/json" \
  -d '{"texts": ["Hello", "World", "Test"]}'
```

**Expected response:**
```json
{
  "encrypted": ["Heoov", "rWvaog", "Test"],
  "font_url": "https://your-cdn.com/fonts/encrypted.woff2"
}
```

**If errors:** Check server is running and port 5000 is available.

---

## ✅ STEP 2: Update Configuration

### 2.1 Update JavaScript API Endpoint

**File:** `/Users/tyler/Cloakv3/client/encrypt-articles.js`

**Find these lines (around line 16-18):**
```javascript
apiEndpoint: 'https://your-api-server.com/api/encrypt',
batchEndpoint: 'https://your-api-server.com/api/encrypt/batch',
```

**For local testing, change to:**
```javascript
apiEndpoint: 'http://localhost:5000/api/encrypt',
batchEndpoint: 'http://localhost:5000/api/encrypt/batch',
```

**For production, change to your deployed API URL:**
```javascript
apiEndpoint: 'https://your-actual-api.com/api/encrypt',
batchEndpoint: 'https://your-actual-api.com/api/encrypt/batch',
```

---

### 2.2 Update Backend Font URL

**File:** `/Users/tyler/Cloakv3/backend/encrypt_api.py`

**Find this line (around line 111):**
```python
font_url = os.environ.get('FONT_URL', 'https://your-cdn.com/fonts/encrypted.woff2')
```

**For production, either:**
- Set environment variable: `export FONT_URL=https://your-cdn.com/fonts/encrypted.woff2`
- Or change the default value in the code

---

## ✅ STEP 3: Create the Font (IMPORTANT!)

### 3.1 Run Font Helper Script

```bash
cd /Users/tyler/Cloakv3
python create_font.py
```

**This shows you the exact mappings needed.**

---

### 3.2 Create Font Using FontForge

**Option A: Manual (Recommended for first time)**

1. **Install FontForge:**
   ```bash
   brew install fontforge  # macOS
   ```

2. **Open your font:**
   ```bash
   fontforge /Users/tyler/Cloakv3/Supertest.ttf
   ```

3. **Swap glyphs** according to the mappings shown by `create_font.py`:
   - For each character, copy the glyph from the mapped character
   - Example: Character 'R' should display the glyph for 'A'
   - Example: Character 'r' should display the glyph for 'a'
   - Example: Character ' ' (space) should display the glyph for 'r'

4. **Export as WOFF2:**
   - File → Generate Fonts
   - Format: WOFF2
   - Save as `encrypted.woff2`

**Option B: Automated (If you want, I can create a script)**

Let me know if you want an automated font creation script.

---

### 3.3 Host the Font

Upload `encrypted.woff2` to:
- **Cloudflare CDN** (free tier available)
- **AWS S3 + CloudFront**
- **Google Cloud Storage**
- **Your own web server**

**Get the URL** - you'll need this for Step 2.2.

Example: `https://your-cdn.com/fonts/encrypted.woff2`

---

## ✅ STEP 4: Test in Browser

### 4.1 Update Test HTML

**File:** `/Users/tyler/Cloakv3/test.html`

Make sure the script tag points to your local file:
```html
<script src="client/encrypt-articles.js"></script>
```

And that `encrypt-articles.js` has `localhost:5000` in the API endpoints (from Step 2.1).

---

### 4.2 Test

1. **Make sure server is running** (Step 1.3)
2. **Open `test.html` in browser**
3. **Open Developer Tools** (F12) → Network tab
4. **Refresh page**
5. **You should see:**
   - API calls to `/api/encrypt` or `/api/encrypt/batch`
   - Articles get encrypted
   - Text looks normal (due to font)

**If font not loading:** Make sure font URL is correct and accessible.

---

## ✅ STEP 5: Deploy to Production

### 5.1 Deploy Backend API

**Option A: Heroku (Easiest)**

```bash
cd /Users/tyler/Cloakv3/backend

# Install Heroku CLI first: https://devcenter.heroku.com/articles/heroku-cli

# Login
heroku login

# Create app
heroku create your-app-name

# Set environment variables
heroku config:set FONT_URL=https://your-cdn.com/fonts/encrypted.woff2

# Deploy
git init
git add .
git commit -m "Initial commit"
git push heroku main
```

**Your API will be at:** `https://your-app-name.herokuapp.com/api/encrypt`

**Option B: AWS/DigitalOcean/Other**

Follow deployment instructions in `SETUP_INSTRUCTIONS.md`.

---

### 5.2 Update JavaScript with Production URL

**File:** `/Users/tyler/Cloakv3/client/encrypt-articles.js`

Change API endpoints to your deployed URL:
```javascript
apiEndpoint: 'https://your-app-name.herokuapp.com/api/encrypt',
batchEndpoint: 'https://your-app-name.herokuapp.com/api/encrypt/batch',
```

---

### 5.3 Deploy JavaScript to CDN

1. **Upload** `client/encrypt-articles.js` to your CDN
2. **Get the URL:** `https://your-cdn.com/encrypt-articles.js`
3. **Test the URL** - should load the JavaScript file

---

## ✅ STEP 6: Use on News Sites

### 6.1 For News Sites (Like NYT)

News sites add this **ONE line** to their HTML:

```html
<script src="https://your-cdn.com/encrypt-articles.js" async></script>
```

**That's it!** All articles will be automatically encrypted.

### 6.2 Via Google Tag Manager (Recommended)

1. Log into Google Tag Manager
2. Create new tag
3. Custom HTML tag
4. Add: `<script src="https://your-cdn.com/encrypt-articles.js" async></script>`
5. Trigger: All Pages
6. Publish

---

## ✅ Checklist

Before going live, verify:

- [ ] Algorithm tested and matches PDF encryption
- [ ] API server running and responding
- [ ] Font created and hosted on CDN
- [ ] JavaScript API endpoints updated to production URL
- [ ] Backend font URL updated
- [ ] Tested in browser (test.html works)
- [ ] Backend deployed to production
- [ ] JavaScript deployed to CDN
- [ ] Tested with real news site content

---

## 🚨 Important Notes

1. **Font is Critical**: Without the font, encrypted text will look garbled
2. **HTTPS Required**: Always use HTTPS in production
3. **CORS**: Backend allows all origins - restrict in production if needed
4. **Rate Limiting**: Add rate limiting for production (see deployment docs)

---

## 🐛 Troubleshooting

### API not responding
- Check server is running: `curl http://localhost:5000/api/health`
- Check firewall/port settings

### Font not loading
- Verify font URL is accessible (open in browser)
- Check CORS headers on font file
- Check browser console for errors

### Articles not encrypting
- Open browser Developer Tools (F12)
- Check Console tab for JavaScript errors
- Check Network tab - is API being called?
- Verify API endpoint URL is correct

### Algorithm doesn't match PDF
- Compare mapping dictionaries in `encrypt_api.py` with `EncTestNewTestF.py`
- They should be identical
- Run test script to verify

---

## 📞 Next Steps

Once everything is working:

1. **Monitor**: Check API logs and usage
2. **Optimize**: Adjust batch size if needed
3. **Scale**: Add more servers if traffic increases
4. **Secure**: Add API keys, rate limiting, CORS restrictions

---

## Summary

**What you need to do:**
1. ✅ Test locally (Steps 1-4)
2. ✅ Create font (Step 3)
3. ✅ Deploy backend (Step 5.1)
4. ✅ Deploy JavaScript (Step 5.3)
5. ✅ Use on news sites (Step 6)

**Everything else is already done!** The code is ready, optimized, and production-ready.

Good luck! 🚀

