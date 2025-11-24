#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Server that reads nyt.html, encrypts it via the API, and serves it on localhost:8001
"""
import os
import requests
from flask import Flask, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Configuration
API_URL = os.environ.get('API_URL', 'http://localhost:5001')
NYT_HTML_PATH = os.path.join(os.path.dirname(__file__), 'nyt.html')
SECRET_KEY = int(os.environ.get('SECRET_KEY', '17292006'))  # Default secret key

# Cache the encrypted HTML
_cached_encrypted_html = None

def get_encrypted_html():
    """Read nyt.html and encrypt it via the API"""
    global _cached_encrypted_html
    
    # Return cached version if available
    if _cached_encrypted_html is not None:
        return _cached_encrypted_html
    
    # Read nyt.html
    if not os.path.exists(NYT_HTML_PATH):
        raise FileNotFoundError(f'nyt.html not found at {NYT_HTML_PATH}')
    
    with open(NYT_HTML_PATH, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Call the API to encrypt
    try:
        response = requests.post(
            f'{API_URL}/nyt-encrypt',
            json={'html': html_content, 'secret_key': SECRET_KEY},
            timeout=30
        )
        response.raise_for_status()
        encrypted_html = response.text
        _cached_encrypted_html = encrypted_html
        return encrypted_html
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f'Failed to encrypt HTML via API: {e}')

@app.route('/')
def serve_encrypted():
    """Serve the encrypted NYT HTML"""
    try:
        encrypted_html = get_encrypted_html()
        return Response(
            encrypted_html,
            mimetype='text/html; charset=utf-8'
        )
    except Exception as e:
        return f'<html><body><h1>Error</h1><p>{str(e)}</p></body></html>', 500

@app.route('/refresh')
def refresh_cache():
    """Clear cache and re-encrypt"""
    global _cached_encrypted_html
    _cached_encrypted_html = None
    try:
        encrypted_html = get_encrypted_html()
        return Response(
            encrypted_html,
            mimetype='text/html; charset=utf-8'
        )
    except Exception as e:
        return f'<html><body><h1>Error</h1><p>{str(e)}</p></body></html>', 500

if __name__ == '__main__':
    print(f'Starting server on http://localhost:8001')
    print(f'API URL: {API_URL}')
    print(f'NYT HTML path: {NYT_HTML_PATH}')
    print(f'Secret key: {SECRET_KEY}')
    app.run(host='0.0.0.0', port=8001, debug=True)

