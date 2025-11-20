#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backend API Server for Article Encryption
Uses the EXACT algorithm from EncTestNewTestF.py
"""
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from functools import lru_cache
import hashlib
import os

app = Flask(__name__)
CORS(app)  # Allow cross-origin requests from news websites

# ============================================================================
# EXACT ALGORITHM FROM EncTestNewTestF.py
# ============================================================================

# Mapping - optimized with combined lookup (EXACT COPY)
LIGATURES = {"\ufb00":"ff","\ufb01":"fi","\ufb02":"fl","\ufb03":"ffi","\ufb04":"ffl"}
SPECIAL_MAP = {" ": "r", "\x00": "\n"}
UPPER_MAP = {
    "R":"A","F":"B","M":"C","S":"D","E":"E","H":"F","D":"G","G":"H","N":"I","A":"J",
    "K":"K","C":"L","Y":"M","U":"N","L":"O","P":"P","X":"Q","V":"R","I":"S","Q":"T",
    "T":"U","O":"V","W":"W","B":"X","Z":"Y","J":"Z"
}
LOWER_MAP = {
    "r":"a","f":"b","m":"c","s":"d","e":"e","h":"f","d":"g","g":"h",
    "n":"i","a":"j","k":"k","c":"l","y":"m","u":"n","l":"o","p":"p",
    "x":"q","v":" ","i":"s","q":"t","t":"u","o":"v","w":"w",
    "b":"x","z":"y","j":"z"
}

# Combined character mapping for faster lookup
COMBINED_MAP = {**SPECIAL_MAP, **UPPER_MAP, **LOWER_MAP}

# Create translation table for ultra-fast character mapping
CHAR_TRANSLATION_TABLE = str.maketrans(COMBINED_MAP)

@lru_cache(maxsize=1000)
def expand_ligatures(s: str) -> str:
    """EXACT copy from EncTestNewTestF.py"""
    return "".join(LIGATURES.get(ch, ch) for ch in s)

def remap_text_ultra_fast(text: str) -> str:
    """EXACT copy from EncTestNewTestF.py - core encryption algorithm"""
    return text.translate(CHAR_TRANSLATION_TABLE)

def encrypt_article_text(text: str) -> str:
    """
    EXACT algorithm from EncTestNewTestF.py:
    1. Expand ligatures first (handles Unicode ligatures)
    2. Then apply character remapping (translation table)
    
    This is the SAME algorithm used in the PDF encryption code.
    """
    # Step 1: Expand ligatures
    expanded = expand_ligatures(text)
    
    # Step 2: Apply character remapping
    encrypted = remap_text_ultra_fast(expanded)
    
    return encrypted

# ============================================================================
# CACHING AND API ENDPOINTS
# ============================================================================

# Cache encrypted results to avoid re-encrypting same content
@lru_cache(maxsize=10000)
def encrypt_cached(text_hash: str, text: str) -> str:
    """Cache encrypted results for performance"""
    return encrypt_article_text(text)

@app.route('/api/encrypt', methods=['POST'])
def encrypt_article():
    """
    Main API endpoint for encrypting article text.
    
    Request body:
        {
            "text": "The article text to encrypt"
        }
    
    Response:
        {
            "encrypted": "Encrypted text using exact algorithm",
            "font_url": "https://your-cdn.com/fonts/encrypted.woff2"
        }
    """
    try:
        data = request.json
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        article_text = data.get('text', '')
        
        if not article_text:
            return jsonify({'error': 'No text provided'}), 400
        
        # Create hash for caching (improves performance for repeated content)
        text_hash = hashlib.md5(article_text.encode('utf-8')).hexdigest()
        
        # Use EXACT algorithm from EncTestNewTestF.py
        encrypted_text = encrypt_cached(text_hash, article_text)
        
        # Return encrypted text and font URL
        # The font URL should point to your CDN where the custom font is hosted
        font_url = os.environ.get('FONT_URL', 'https://your-cdn.com/fonts/encrypted.woff2')
        
        return jsonify({
            'encrypted': encrypted_text,
            'font_url': font_url
        })
    
    except Exception as e:
        print(f"Error encrypting article: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/encrypt/batch', methods=['POST'])
def encrypt_articles_batch():
    """
    Batch encryption endpoint for encrypting multiple articles at once.
    Much more efficient for high-traffic sites.
    
    Request body:
        {
            "texts": ["Article 1 text", "Article 2 text", ...]
        }
    
    Response:
        {
            "encrypted": ["Encrypted text 1", "Encrypted text 2", ...],
            "font_url": "https://your-cdn.com/fonts/encrypted.woff2"
        }
    """
    try:
        data = request.json
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        texts = data.get('texts', [])
        
        if not texts or not isinstance(texts, list):
            return jsonify({'error': 'No texts array provided'}), 400
        
        if len(texts) > 100:  # Limit batch size
            return jsonify({'error': 'Batch size too large (max 100)'}), 400
        
        # Encrypt all texts using exact algorithm
        encrypted_texts = []
        for text in texts:
            if not text or not isinstance(text, str):
                encrypted_texts.append('')
                continue
            
            text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
            encrypted = encrypt_cached(text_hash, text)
            encrypted_texts.append(encrypted)
        
        font_url = os.environ.get('FONT_URL', 'https://your-cdn.com/fonts/encrypted.woff2')
        
        return jsonify({
            'encrypted': encrypted_texts,
            'font_url': font_url
        })
    
    except Exception as e:
        print(f"Error encrypting batch: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'article-encryption-api'
    })

@app.route('/api/test', methods=['POST'])
def test_encryption():
    """
    Test endpoint to verify algorithm works correctly.
    Useful for debugging and verification.
    """
    try:
        data = request.json
        test_text = data.get('text', 'Hello World')
        
        # Encrypt using exact algorithm
        encrypted = encrypt_article_text(test_text)
        
        return jsonify({
            'original': test_text,
            'encrypted': encrypted,
            'algorithm': 'exact_match_EncTestNewTestF'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Serve font files if hosting locally (optional)
@app.route('/fonts/<path:filename>')
def serve_font(filename):
    """Serve font files (optional - usually use CDN instead)"""
    fonts_dir = os.path.join(os.path.dirname(__file__), 'fonts')
    return send_from_directory(fonts_dir, filename)

if __name__ == '__main__':
    # Configuration
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    print(f"Starting Article Encryption API on {host}:{port}")
    print(f"Debug mode: {debug}")
    print(f"API endpoint: http://{host}:{port}/api/encrypt")
    
    app.run(host=host, port=port, debug=debug)

