# Exact Setup Instructions

Follow these steps **in order** to set up the complete encryption system.

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- A text editor or IDE
- Access to a server/cloud platform for deployment

## Step 1: Install Python Dependencies

Open terminal and run:

```bash
cd /Users/tyler/Cloakv3/backend
pip install -r requirements.txt
```

**What this does:** Installs Flask (web framework) and flask-cors (for cross-origin requests).

**Expected output:** Should show "Successfully installed flask flask-cors..."

## Step 2: Test the Algorithm

Verify the encryption algorithm works:

```bash
cd /Users/tyler/Cloakv3
python test_algorithm.py
```

**What this does:** Tests the encryption algorithm with sample text and shows you the encrypted output.

**Expected output:** You'll see test cases showing original text and encrypted text. Compare these with your PDF encryption to verify they match.

**If it doesn't match your PDF code:** The algorithm might need adjustment. Check the mapping dictionaries.

## Step 3: Start the Backend Server (Local Testing)

```bash
cd /Users/tyler/Cloakv3/backend
python encrypt_api.py
```

**What this does:** Starts the Flask API server on `http://localhost:5000`

**Expected output:** 
```
Starting Article Encryption API on 0.0.0.0:5000
Debug mode: False
API endpoint: http://0.0.0.0:5000/api/encrypt
 * Running on http://127.0.0.1:5000
```

**Keep this terminal window open** - the server needs to keep running.

## Step 4: Test the API (In a New Terminal)

Open a **new terminal window** and test the API:

```bash
curl -X POST http://localhost:5000/api/encrypt \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello World"}'
```

**What this does:** Sends "Hello World" to your API and gets back the encrypted version.

**Expected output:**
```json
{
  "encrypted": "Heoov rWvaog",
  "font_url": "https://your-cdn.com/fonts/encrypted.woff2"
}
```

**If you get an error:** 
- Make sure the server is still running in the other terminal
- Check that port 5000 is not in use by another program

## Step 5: Create the Custom Font

This is the **most important step**. The font makes encrypted text look normal.

### Option A: Manual Font Creation (FontForge)

1. **Install FontForge:**
   ```bash
   brew install fontforge  # macOS
   ```

2. **Open your font:**
   ```bash
   fontforge /Users/tyler/Cloakv3/Supertest.ttf
   ```

3. **Swap glyphs manually:**
   - In FontForge, for each character, you need to swap its glyph:
   
   **Uppercase letters (from UPPER_MAP):**
   - Select character 'A' → Copy glyph from 'R' → Paste to 'A'
   - Select character 'B' → Copy glyph from 'F' → Paste to 'B'
   - Select character 'C' → Copy glyph from 'M' → Paste to 'C'
   - Continue for all 26 letters...
   
   **Lowercase letters (from LOWER_MAP):**
   - Select character 'a' → Copy glyph from 'r' → Paste to 'a'
   - Select character 'b' → Copy glyph from 'f' → Paste to 'b'
   - Continue for all 26 letters...
   
   **Space:**
   - Select character ' ' (space) → Copy glyph from 'r' → Paste to ' '

4. **Export as WOFF2:**
   - File → Generate Fonts
   - Format: WOFF2
   - Save as `encrypted.woff2`

### Option B: Automated Font Creation (Recommended)

I can create a Python script to automate this. Would you like me to create `create_font.py`?

## Step 6: Host the Font File

Upload `encrypted.woff2` to a CDN or web server:

- **Cloudflare CDN** (free tier available)
- **AWS S3 + CloudFront**
- **Google Cloud Storage**
- **Your own web server**

**Get the URL** - you'll need this for the next step.

Example: `https://your-cdn.com/fonts/encrypted.woff2`

## Step 7: Update Configuration

### Update Backend API

Edit `/Users/tyler/Cloakv3/backend/encrypt_api.py`:

Find this line (around line 120):
```python
font_url = os.environ.get('FONT_URL', 'https://your-cdn.com/fonts/encrypted.woff2')
```

Replace `'https://your-cdn.com/fonts/encrypted.woff2'` with your actual font URL.

**OR** set it as an environment variable:
```bash
export FONT_URL=https://your-actual-cdn.com/fonts/encrypted.woff2
```

### Update JavaScript

Edit `/Users/tyler/Cloakv3/client/encrypt-articles.js`:

Find this line (around line 12):
```javascript
apiEndpoint: 'https://your-api-server.com/api/encrypt',
```

Replace `'https://your-api-server.com/api/encrypt'` with your actual API URL.

## Step 8: Deploy Backend API

Choose one deployment method:

### Method A: Heroku (Easiest)

```bash
# Install Heroku CLI first: https://devcenter.heroku.com/articles/heroku-cli

cd /Users/tyler/Cloakv3/backend

# Create Procfile
echo "web: gunicorn encrypt_api:app" > Procfile

# Login to Heroku
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

Your API will be at: `https://your-app-name.herokuapp.com/api/encrypt`

### Method B: AWS Elastic Beanstalk

1. Install AWS CLI and EB CLI
2. Run `eb init` in the backend directory
3. Run `eb create` to create environment
4. Set environment variables in AWS console

### Method C: DigitalOcean App Platform

1. Create new app in DigitalOcean
2. Connect GitHub repository
3. Set build command: `pip install -r requirements.txt`
4. Set run command: `gunicorn encrypt_api:app`
5. Set environment variables

## Step 9: Deploy JavaScript to CDN

Upload `/Users/tyler/Cloakv3/client/encrypt-articles.js` to your CDN.

**Get the URL** - this is what news sites will use.

Example: `https://your-cdn.com/encrypt-articles.js`

## Step 10: Test on a Sample Page

Create a test HTML file:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Encryption Test</title>
</head>
<body>
    <article>
        <h1>Test Article</h1>
        <p>This is a test article. The quick brown fox jumps over the lazy dog.</p>
        <p>All of this text should be encrypted when the page loads.</p>
    </article>
    
    <!-- Replace with your actual CDN URL -->
    <script src="https://your-cdn.com/encrypt-articles.js" async></script>
</body>
</html>
```

Open this file in a browser. The text should be encrypted (though it will look normal due to the font).

**To verify it's working:**
- Open browser Developer Tools (F12)
- Go to Network tab
- Refresh page
- You should see a request to `/api/encrypt`
- Check the response - it should contain encrypted text

## Step 11: Integration with News Sites

News sites add this ONE line to their HTML (usually in the `<head>` or before `</body>`):

```html
<script src="https://your-cdn.com/encrypt-articles.js" async></script>
```

**That's it!** All articles will be automatically encrypted.

## Troubleshooting

### "Module not found" error
- Make sure you ran `pip install -r requirements.txt`
- Check you're using Python 3.8+

### API returns 500 error
- Check server logs in the terminal where you're running the server
- Verify the algorithm code is correct

### Font not loading
- Verify font URL is accessible (try opening in browser)
- Check CORS headers on font file
- Check browser console for errors

### Articles not encrypting
- Open browser Developer Tools (F12)
- Check Console tab for JavaScript errors
- Check Network tab - is API being called?
- Verify API endpoint URL is correct in JavaScript file

### Algorithm doesn't match PDF code
- Compare the mapping dictionaries in `encrypt_api.py` with `EncTestNewTestF.py`
- They should be identical
- Run test script to verify outputs

## Next Steps

1. ✅ Test locally
2. ✅ Create font
3. ✅ Deploy API
4. ✅ Deploy JavaScript
5. ✅ Test on sample page
6. ✅ Integrate with news sites
7. ✅ Monitor and optimize

## Security Checklist

Before going to production:

- [ ] Use HTTPS for API (not HTTP)
- [ ] Use HTTPS for JavaScript and font files
- [ ] Add API key authentication
- [ ] Set up rate limiting
- [ ] Configure CORS to only allow your news sites
- [ ] Set up monitoring/logging
- [ ] Test with real news site content

## Support

If you get stuck:
1. Check the error message carefully
2. Verify each step was completed
3. Check server logs
4. Check browser console
5. Test API with curl command

Good luck! 🚀

