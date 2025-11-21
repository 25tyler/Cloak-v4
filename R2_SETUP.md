# Setting Up Cloudflare R2 Environment Variables

There are several ways to set the R2 environment variables. Choose the method that works best for your setup.

## Method 1: Using a .env File (Recommended for Local Development)

1. **Install python-dotenv** (already added to requirements.txt):
   ```bash
   pip install python-dotenv
   ```

2. **Create a `.env` file** in the project root:
   ```bash
   cp env_template.txt .env
   ```

3. **Edit `.env`** with your actual R2 credentials:
   ```bash
   R2_ACCOUNT_ID=your-actual-account-id
   R2_ACCESS_KEY_ID=your-actual-access-key
   R2_SECRET_ACCESS_KEY=your-actual-secret-key
   R2_BUCKET_NAME=your-bucket-name
   R2_PUBLIC_URL=https://pub-5eb60ded9abd4136b4908ea55a742d6e.r2.dev
   USE_R2_FONTS=true
   ```

4. **Start your server** - the .env file will be automatically loaded:
   ```bash
   python encrypt_api.py
   ```

## Method 2: Export in Terminal (Temporary - Current Session Only)

**For macOS/Linux (zsh/bash):**
```bash
export R2_ACCOUNT_ID='your-account-id'
export R2_ACCESS_KEY_ID='your-access-key'
export R2_SECRET_ACCESS_KEY='your-secret-key'
export R2_BUCKET_NAME='your-bucket-name'
export R2_PUBLIC_URL='https://pub-5eb60ded9abd4136b4908ea55a742d6e.r2.dev'
export USE_R2_FONTS='true'

# Then start your server
python encrypt_api.py
```

**Or use the setup script:**
```bash
# Edit setup_r2.sh with your credentials first, then:
source setup_r2.sh
python encrypt_api.py
```

## Method 3: Add to Your Shell Profile (Permanent for Terminal)

Add to `~/.zshrc` (or `~/.bashrc` on Linux):

```bash
# Cloudflare R2 Configuration
export R2_ACCOUNT_ID='your-account-id'
export R2_ACCESS_KEY_ID='your-access-key'
export R2_SECRET_ACCESS_KEY='your-secret-key'
export R2_BUCKET_NAME='your-bucket-name'
export R2_PUBLIC_URL='https://pub-5eb60ded9abd4136b4908ea55a742d6e.r2.dev'
export USE_R2_FONTS='true'
```

Then reload your shell:
```bash
source ~/.zshrc
```

## Method 4: For Heroku/Production Deployment

**Using Heroku CLI:**
```bash
heroku config:set R2_ACCOUNT_ID='your-account-id'
heroku config:set R2_ACCESS_KEY_ID='your-access-key'
heroku config:set R2_SECRET_ACCESS_KEY='your-secret-key'
heroku config:set R2_BUCKET_NAME='your-bucket-name'
heroku config:set R2_PUBLIC_URL='https://pub-5eb60ded9abd4136b4908ea55a742d6e.r2.dev'
heroku config:set USE_R2_FONTS='true'
```

**Or via Heroku Dashboard:**
1. Go to your app settings
2. Click "Reveal Config Vars"
3. Add each variable manually

## Getting Your R2 Credentials

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. Navigate to **R2** > **Manage R2 API Tokens**
3. Click **Create API Token**
4. Give it a name and select:
   - **Permissions**: Object Read & Write
   - **Bucket**: Your bucket name (or "All buckets")
5. Copy the credentials:
   - **Account ID**: Found in R2 dashboard URL or account settings
   - **Access Key ID**: From the token you just created
   - **Secret Access Key**: From the token (only shown once!)
   - **Bucket Name**: Your R2 bucket name
   - **Public URL**: Your R2 public domain (if you have one set up)

## Verifying Setup

After setting the variables, test if R2 upload works:

1. Start your server: `python encrypt_api.py`
2. Make an API call to encrypt text (which will generate a font)
3. Check the logs - you should see: `✅ Font uploaded to R2: https://...`

If you see `⚠️ Failed to upload font to R2`, check:
- All environment variables are set correctly
- `boto3` is installed: `pip install boto3`
- Your R2 credentials have the correct permissions
- Your bucket name is correct

## Notes

- **Security**: Never commit `.env` files to git! They're already in `.gitignore`
- **Fallback**: If R2 is not configured, fonts will be served locally from `/fonts/` endpoint
- **USE_R2_FONTS**: Set to `'true'` to always use R2 URLs, `'false'` to use local URLs

