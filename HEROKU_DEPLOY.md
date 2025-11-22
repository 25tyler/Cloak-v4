# Heroku Deployment Guide

## Quick Deploy

1. **Install Heroku CLI** (if not already installed)
   ```bash
   # macOS
   brew tap heroku/brew && brew install heroku
   ```

2. **Login to Heroku**
   ```bash
   heroku login
   ```

3. **Create Heroku App**
   ```bash
   heroku create your-app-name
   ```

4. **Set Environment Variables**
   ```bash
   # Required: Set your app's base URL
   heroku config:set BASE_URL=https://your-app-name.herokuapp.com
   
   # Optional: If using R2 for fonts
   heroku config:set USE_R2_FONTS=true
   heroku config:set R2_ACCOUNT_ID=your_account_id
   heroku config:set R2_ACCESS_KEY_ID=your_access_key
   heroku config:set R2_SECRET_ACCESS_KEY=your_secret_key
   heroku config:set R2_BUCKET_NAME=your_bucket_name
   heroku config:set R2_PUBLIC_URL=your_r2_public_url
   ```

5. **Deploy**
   ```bash
   git add .
   git commit -m "Deploy to Heroku"
   git push heroku main
   ```

6. **Verify**
   ```bash
   heroku open
   # Or visit: https://your-app-name.herokuapp.com
   ```

## Important Notes

- **BASE_URL**: Must be set to your Heroku app URL for font URLs to work correctly
- **Fonts**: Generated fonts are stored in the `fonts/` directory (ephemeral on Heroku)
- **R2**: If using R2, fonts will be uploaded automatically and served via proxy
- **Secret Key**: The default secret key is `29202393` - change this in production!

## Testing

After deployment, test the API:
```bash
curl https://your-app-name.herokuapp.com/api/health
```

Test page encryption:
```bash
curl -X POST https://your-app-name.herokuapp.com/api/encrypt/page \
  -H "Content-Type: application/json" \
  -d '{"texts":["Hello World"],"secret_key":29202393}'
```

## Using on Your Website

Include the script on any webpage:
```html
<script src="https://your-app-name.herokuapp.com/client/encrypt-page.js" 
        data-secret-key="29202393"></script>
```

The script will automatically encrypt all text on the page!

