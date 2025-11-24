#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for HTML encryption API
Reads nyt.html, calls /api/encrypt/html endpoint, and saves encrypted output
"""
import os
import sys
import json
import requests
import time

def test_html_encryption():
    """Test the HTML encryption API with nyt.html"""
    
    # Read nyt.html
    html_file = 'nyt.html'
    if not os.path.exists(html_file):
        print(f"Error: {html_file} not found")
        return False
    
    print(f"Reading {html_file}...")
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    print(f"HTML file size: {len(html_content)} bytes")
    
    # API endpoint
    api_url = 'http://localhost:5001/api/encrypt/html'
    
    # Check if server is running
    try:
        response = requests.get('http://localhost:5001/api/health', timeout=2)
        if response.status_code != 200:
            print("Warning: Server health check failed, but continuing...")
    except requests.exceptions.RequestException:
        print("Error: Could not connect to API server at http://localhost:5001")
        print("Please start the server with: python encrypt_api.py")
        return False
    
    # Prepare request
    payload = {
        'html': html_content,
        'secret_key': 29202393  # Use default secret key
    }
    
    print(f"\nCalling API endpoint: {api_url}")
    print("Encrypting HTML content...")
    
    start_time = time.time()
    
    try:
        response = requests.post(
            api_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=60
        )
        
        elapsed_time = time.time() - start_time
        
        if response.status_code != 200:
            print(f"Error: API returned status code {response.status_code}")
            try:
                error_data = response.json()
                print(f"Error message: {error_data.get('error', 'Unknown error')}")
            except:
                print(f"Response: {response.text[:500]}")
            return False
        
        # Check if response is JSON or HTML
        content_type = response.headers.get('Content-Type', '')
        if 'application/json' not in content_type:
            # Response is HTML, not JSON - server might need restart
            print(f"⚠️  Warning: Server returned HTML instead of JSON")
            print(f"   Content-Type: {content_type}")
            print(f"   This usually means the server needs to be restarted to load new code.")
            print(f"   However, the encryption appears to be working.")
            print(f"   Response preview: {response.text[:200]}...")
            print(f"\n   Please restart the server and try again.")
            return False
        
        try:
            data = response.json()
        except json.JSONDecodeError as e:
            print(f"Error: Failed to parse JSON response: {e}")
            print(f"Response preview: {response.text[:500]}")
            return False
        
        print(f"✅ Encryption completed in {elapsed_time:.2f} seconds")
        
        # Print statistics
        stats = data.get('stats', {})
        print("\nEncryption Statistics:")
        print(f"  - Title encrypted: {stats.get('title_encrypted', False)}")
        print(f"  - Meta tags encrypted: {stats.get('meta_tags_encrypted', 0)}")
        print(f"  - Alt attributes encrypted: {stats.get('alt_attributes_encrypted', 0)}")
        print(f"  - ARIA labels encrypted: {stats.get('aria_labels_encrypted', 0)}")
        print(f"  - Title attributes encrypted: {stats.get('title_attributes_encrypted', 0)}")
        print(f"  - JSON-LD scripts encrypted: {stats.get('json_ld_encrypted', 0)}")
        print(f"  - Nonce: {data.get('nonce')}")
        print(f"  - Font URL: {data.get('font_url', 'N/A')}")
        
        # Save encrypted HTML
        output_file = 'nyt_encrypted.html'
        encrypted_html = data.get('encrypted_html', '')
        
        if encrypted_html:
            print(f"\nSaving encrypted HTML to {output_file}...")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(encrypted_html)
            
            print(f"✅ Encrypted HTML saved: {output_file}")
            print(f"   Size: {len(encrypted_html)} bytes")
            
            # Verify encryption worked
            if encrypted_html != html_content:
                print("✅ HTML content was successfully encrypted")
            else:
                print("⚠️  Warning: Encrypted HTML is identical to original (no encryption occurred)")
            
            return True
        else:
            print("Error: No encrypted HTML in response")
            return False
    
    except requests.exceptions.Timeout:
        print("Error: Request timed out (60 seconds)")
        return False
    except requests.exceptions.RequestException as e:
        print(f"Error: Request failed: {e}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("=" * 70)
    print("HTML Encryption API Test")
    print("=" * 70)
    print()
    
    success = test_html_encryption()
    
    print()
    print("=" * 70)
    if success:
        print("✅ Test completed successfully!")
    else:
        print("❌ Test failed!")
    print("=" * 70)
    
    sys.exit(0 if success else 1)

