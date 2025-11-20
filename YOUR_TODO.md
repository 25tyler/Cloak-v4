# YOUR TODO - Exact Steps You Need To Do

## ✅ AUTOMATED - Already Done For You

I've already run these tests:
- ✅ Python 3.9.6 is installed
- ✅ Flask and flask-cors are installed
- ✅ Algorithm test passed - encryption is working
- ✅ All files are in place
- ✅ Server code is ready

---

## 🔴 MANUAL STEPS - You Must Do These

### STEP 1: Verify Algorithm Matches Your PDF Code

**What to do:**
1. Run your PDF encryption code (`EncTestNewTestF.py`) on these test strings:
   - "Hello World"
   - "The quick brown fox jumps over the lazy dog"
   - "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

2. Compare the outputs with what the test showed:
   - "Hello World" → Should encrypt to: `FeoovrWvaog`
   - If it matches → ✅ Algorithm is correct
   - If it doesn't match → ⚠️ Need to check mapping dictionaries

**Time:** 2 minutes

---

### STEP 2: Start the Server and Test It

**What to do:**

1. **Open Terminal** (new window)

2. **Navigate to backend:**
   ```bash
   cd /Users/tyler/Cloakv3/backend
   ```

3. **Start the server:**
   ```bash
   python3 encrypt_api.py
   ```

4. **You should see:**
   ```
   Starting Article Encryption API on 0.0.0.0:5000
   Debug mode: False
   API endpoint: http://0.0.0.0:5000/api/encrypt
    * Running on http://127.0.0.1:5000
   ```

5. **Keep this terminal open** - server must keep running

6. **Open a NEW terminal window** and test:
   ```bash
   curl -X POST http://localhost:5000/api/encrypt \
     -H "Content-Type: application/json" \
     -d '{"text": "Hello World"}'
   ```

7. **Expected response:**
   ```json
   {
     "encrypted": "FeoovrWvaog",
     "font_url": "https://your-cdn.com/fonts/encrypted.woff2"
   }
   ```

**If it works:** ✅ Server is ready
**If error:** Check that port 5000 is not in use

**Time:** 3 minutes

---

### STEP 3: Create the Font (MOST IMPORTANT!)

**Why:** Without the font, encrypted text will look garbled. This is critical.

**What to do:**

#### 3.1 Get Font Creation Instructions

```bash
cd /Users/tyler/Cloakv3
python3 create_font.py
```

This will show you the exact mappings needed.

#### 3.2 Install FontForge

**macOS:**
```bash
brew install fontforge
```

**If you don't have Homebrew:**
1. Go to: https://brew.sh
2. Copy the install command
3. Run it in terminal
4. Then run `brew install fontforge`

**Windows:**
- Download from: https://fontforge.org/
- Install the .exe file

**Linux:**
```bash
sudo apt-get install fontforge
```

#### 3.3 Open Your Font in FontForge

```bash
fontforge /Users/tyler/Cloakv3/Supertest.ttf
```

#### 3.4 Swap Glyphs (Follow mappings from Step 3.1)

**For each character mapping:**
1. Find the encrypted character (left side)
2. Find the original character (right side)
3. Copy the glyph from original → Paste to encrypted

**Example:**
- Character 'R' should display the glyph for 'A'
- Character 'F' should display the glyph for 'B'
- Character 'r' should display the glyph for 'a'
- Character ' ' (space) should display the glyph for 'r'

**Do this for ALL mappings shown by `create_font.py`**

#### 3.5 Export as WOFF2

1. In FontForge: **File → Generate Fonts**
2. Format: **WOFF2**
3. Save as: `encrypted.woff2`
4. Save it somewhere you can find it

**Time:** 30-60 minutes (first time), 10 minutes (after you know how)

---

### STEP 4: Host the Font File

**What to do:**

You need to upload `encrypted.woff2` to a web server/CDN so browsers can download it.

**Option A: Cloudflare (Free, Recommended)**

1. **Create account:** https://dash.cloudflare.com/sign-up
   - Enter email
   - Create password
   - Verify email

2. **Create a website:**
   - Click "Add a Site"
   - Enter any domain (or use a free subdomain)
   - Follow setup (free plan is fine)

3. **Upload font:**
   - Go to Workers & Pages
   - Create a new Page
   - Upload your `encrypted.woff2` file
   - Get the URL (e.g., `https://your-page.pages.dev/encrypted.woff2`)

**Option B: AWS S3 (If you have AWS account)**

1. **Login:** https://aws.amazon.com/console/
2. **Go to S3:** Search "S3" in services
3. **Create bucket:** Click "Create bucket"
4. **Upload font:** Upload `encrypted.woff2`
5. **Make public:** Set permissions to public read
6. **Get URL:** Copy the object URL

**Option C: Your Own Web Server**

1. Upload `encrypted.woff2` to your web server
2. Make sure it's accessible via HTTP/HTTPS
3. Get the full URL

**Save the font URL** - you'll need it in Step 5.

**Time:** 10-15 minutes

---

### STEP 5: Update Configuration Files

**What to do:**

#### 5.1 Update JavaScript API Endpoint

**File:** `/Users/tyler/Cloakv3/client/encrypt-articles.js`

**Find lines 16-18:**
```javascript
apiEndpoint: 'https://your-api-server.com/api/encrypt',
batchEndpoint: 'https://your-api-server.com/api/encrypt/batch',
```

**For now (local testing), change to:**
```javascript
apiEndpoint: 'http://localhost:5000/api/encrypt',
batchEndpoint: 'http://localhost:5000/api/encrypt/batch',
```

**Later (production), change to your deployed API URL:**
```javascript
apiEndpoint: 'https://your-deployed-api.com/api/encrypt',
batchEndpoint: 'https://your-deployed-api.com/api/encrypt/batch',
```

#### 5.2 Update Backend Font URL

**File:** `/Users/tyler/Cloakv3/backend/encrypt_api.py`

**Find line 111:**
```python
font_url = os.environ.get('FONT_URL', 'https://your-cdn.com/fonts/encrypted.woff2')
```

**Change the default URL to your font URL from Step 4:**
```python
font_url = os.environ.get('FONT_URL', 'https://your-actual-font-url.com/encrypted.woff2')
```

**Time:** 2 minutes

---

### STEP 6: Test in Browser

**What to do:**

1. **Make sure server is running** (Step 2)

2. **Open test.html:**
   - Navigate to: `/Users/tyler/Cloakv3/test.html`
   - Open in browser (double-click or right-click → Open With → Browser)

3. **Open Developer Tools:**
   - Press `F12` or `Cmd+Option+I` (Mac) / `Ctrl+Shift+I` (Windows)
   - Go to **Network** tab

4. **Refresh the page**

5. **You should see:**
   - API calls to `/api/encrypt` or `/api/encrypt/batch`
   - Articles get encrypted
   - Text looks normal (if font is loaded)

6. **Check Console tab** for any errors

**If it works:** ✅ Everything is ready!
**If errors:** Check that server is running and font URL is correct

**Time:** 2 minutes

---

### STEP 7: Deploy Backend API

**What to do:**

#### Option A: Heroku (Easiest)

1. **Install Heroku CLI:**
   - Go to: https://devcenter.heroku.com/articles/heroku-cli
   - Download for macOS
   - Install it

2. **Login to Heroku:**
   ```bash
   heroku login
   ```
   - This opens browser
   - Click "Log in" button
   - Return to terminal

3. **Create Heroku app:**
   ```bash
   cd /Users/tyler/Cloakv3/backend
   heroku create your-app-name
   ```
   - Replace `your-app-name` with something unique
   - Example: `article-encrypt-api-12345`

4. **Set font URL:**
   ```bash
   heroku config:set FONT_URL=https://your-font-url.com/encrypted.woff2
   ```
   - Use the font URL from Step 4

5. **Deploy:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git push heroku main
   ```

6. **Your API will be at:** `https://your-app-name.herokuapp.com/api/encrypt`

**Save this URL** - you'll need it for Step 8.

**Time:** 15-20 minutes

#### Option B: Other Platforms

See `SETUP_INSTRUCTIONS.md` for AWS, DigitalOcean, etc.

---

### STEP 8: Update JavaScript for Production

**What to do:**

**File:** `/Users/tyler/Cloakv3/client/encrypt-articles.js`

**Update lines 16-18 with your deployed API URL from Step 7:**
```javascript
apiEndpoint: 'https://your-app-name.herokuapp.com/api/encrypt',
batchEndpoint: 'https://your-app-name.herokuapp.com/api/encrypt/batch',
```

**Time:** 1 minute

---

### STEP 9: Deploy JavaScript to CDN

**What to do:**

Upload `client/encrypt-articles.js` to a CDN.

**Option A: Cloudflare Pages (Free)**

1. **Login:** https://dash.cloudflare.com
2. **Go to:** Workers & Pages → Create application → Pages
3. **Upload:** Drag and drop `encrypt-articles.js`
4. **Get URL:** Copy the URL (e.g., `https://your-page.pages.dev/encrypt-articles.js`)

**Option B: GitHub + jsDelivr (Free)**

1. **Create GitHub repo:**
   - Go to: https://github.com/new
   - Create new repository
   - Upload `encrypt-articles.js`
   - Commit

2. **Use jsDelivr:**
   - URL format: `https://cdn.jsdelivr.net/gh/your-username/your-repo@main/encrypt-articles.js`
   - Replace with your username and repo name

**Option C: Your Own CDN**

Upload to your existing CDN/web server.

**Save the JavaScript URL** - news sites will use this.

**Time:** 10 minutes

---

### STEP 10: Use on News Sites

**What to do:**

News sites add this ONE line to their HTML:

```html
<script src="https://your-cdn-url.com/encrypt-articles.js" async></script>
```

**Or via Google Tag Manager:**

1. **Login:** https://tagmanager.google.com
2. **Create new tag:** Custom HTML
3. **Add code:**
   ```html
   <script src="https://your-cdn-url.com/encrypt-articles.js" async></script>
   ```
4. **Trigger:** All Pages
5. **Publish**

**That's it!** All articles will be automatically encrypted.

**Time:** 5 minutes per site

---

## 📋 Quick Checklist

Before going live:

- [ ] Step 1: Verified algorithm matches PDF code
- [ ] Step 2: Server running and tested locally
- [ ] Step 3: Font created (encrypted.woff2)
- [ ] Step 4: Font hosted on CDN (have URL)
- [ ] Step 5: Configuration files updated
- [ ] Step 6: Tested in browser (test.html works)
- [ ] Step 7: Backend deployed to production (have API URL)
- [ ] Step 8: JavaScript updated with production API URL
- [ ] Step 9: JavaScript deployed to CDN (have CDN URL)
- [ ] Step 10: Ready to use on news sites!

---

## ⏱️ Time Estimate

- **Testing & Setup:** 30 minutes
- **Font Creation:** 30-60 minutes (first time)
- **Deployment:** 30 minutes
- **Total:** 1.5 - 2 hours

---

## 🆘 Need Help?

**If algorithm doesn't match:**
- Compare mapping dictionaries in `backend/encrypt_api.py` with `EncTestNewTestF.py`
- They should be identical

**If server won't start:**
- Check port 5000 is not in use: `lsof -ti:5000`
- Kill process if needed: `kill -9 $(lsof -ti:5000)`

**If font looks wrong:**
- Verify all glyph swaps were done correctly
- Check font URL is accessible in browser
- Check browser console for font loading errors

**If API errors:**
- Check server logs in terminal
- Verify CORS is enabled
- Check API URL is correct

---

## 🎯 You're Ready!

Once you complete these steps, your encryption system will be:
- ✅ Production-ready
- ✅ Optimized for high-traffic sites
- ✅ Easy to integrate (one script tag)
- ✅ Fully automated (encrypts all articles)

Good luck! 🚀

