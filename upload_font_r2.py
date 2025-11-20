#!/usr/bin/env python3
"""
Upload font file to Cloudflare R2 using S3-compatible API
Requires: pip install boto3
"""
import os
import sys
import boto3
from botocore.config import Config

# R2 Configuration
R2_ACCOUNT_ID = os.environ.get('R2_ACCOUNT_ID', '')
R2_ACCESS_KEY_ID = os.environ.get('R2_ACCESS_KEY_ID', '')
R2_SECRET_ACCESS_KEY = os.environ.get('R2_SECRET_ACCESS_KEY', '')
R2_BUCKET_NAME = os.environ.get('R2_BUCKET_NAME', '')
R2_PUBLIC_URL = 'https://pub-5eb60ded9abd4136b4908ea55a742d6e.r2.dev'

def upload_font():
    if not all([R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME]):
        print("ERROR: Missing R2 credentials!")
        print("\nSet environment variables:")
        print("  export R2_ACCOUNT_ID='your-account-id'")
        print("  export R2_ACCESS_KEY_ID='your-access-key'")
        print("  export R2_SECRET_ACCESS_KEY='your-secret-key'")
        print("  export R2_BUCKET_NAME='your-bucket-name'")
        print("\nOr use Cloudflare Dashboard (Option 1) instead.")
        return False
    
    font_file = 'fonts/encrypted.woff2'
    if not os.path.exists(font_file):
        print(f"ERROR: Font file not found: {font_file}")
        return False
    
    try:
        # Create S3-compatible client for R2
        s3_client = boto3.client(
            's3',
            endpoint_url=f'https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com',
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            config=Config(signature_version='s3v4')
        )
        
        print(f"Uploading {font_file} to R2...")
        s3_client.upload_file(
            font_file,
            R2_BUCKET_NAME,
            'encrypted.woff2',
            ExtraArgs={'ContentType': 'font/woff2'}
        )
        
        print(f"✅ Upload successful!")
        print(f"   URL: {R2_PUBLIC_URL}/encrypted.woff2")
        return True
        
    except ImportError:
        print("ERROR: boto3 not installed!")
        print("Install with: pip install boto3")
        return False
    except Exception as e:
        print(f"ERROR: Upload failed: {e}")
        return False

if __name__ == '__main__':
    upload_font()
