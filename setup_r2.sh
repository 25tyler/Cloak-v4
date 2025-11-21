#!/bin/bash
# Setup script for R2 environment variables
# Run this before starting your Flask server: source setup_r2.sh

export R2_ACCOUNT_ID='your-account-id-here'
export R2_ACCESS_KEY_ID='your-access-key-here'
export R2_SECRET_ACCESS_KEY='your-secret-key-here'
export R2_BUCKET_NAME='your-bucket-name-here'
export R2_PUBLIC_URL='https://pub-5eb60ded9abd4136b4908ea55a742d6e.r2.dev'  # Optional, adjust if different
export USE_R2_FONTS='true'  # Set to 'true' to use R2 URLs, 'false' to use local URLs

echo "✅ R2 environment variables set!"
echo "   Now you can run: python encrypt_api.py"

