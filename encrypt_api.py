#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backend API Server for Article Encryption
Uses the EXACT algorithm from EncTestNewTestF.py
"""
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
# Caching removed - no longer using lru_cache
from collections import Counter
import hashlib
import os
from Fiesty import enc, dec
from generate_font import (
    create_decryption_font_from_mappings,
    get_dynamic_mappings,
    UPPERCASE,
    LOWERCASE,
)

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, that's okay

# Optional R2 upload support
try:
    import boto3
    from botocore.config import Config
    R2_AVAILABLE = True
except ImportError:
    R2_AVAILABLE = False

app = Flask(__name__)
CORS(app)  # Allow cross-origin requests from news websites

# Debug mode - set via environment variable
DEBUG_MODE = os.environ.get('DEBUG', 'false').lower() == 'true'

# ============================================================================
# DYNAMIC ENCRYPTION USING FEISTEL CIPHER
# ============================================================================

# Secret key will be provided as input to the API

LIGATURES = {"\ufb00":"ff","\ufb01":"fi","\ufb02":"fl","\ufb03":"ffi","\ufb04":"ffl"}

def expand_ligatures(s: str) -> str:
    """EXACT copy from EncTestNewTestF.py"""
    return "".join(LIGATURES.get(ch, ch) for ch in s)

def remap_text_ultra_fast(text: str, secret_key: int, nonce: int, precomputed_maps=None, return_maps: bool = False):
    """
    Apply dynamic character remapping using Feistel cipher.
    Maps each character using the secret key and nonce.
    Now handles space as position 26 (0-26 range).
    precomputed_maps may be supplied to avoid recomputing (upper_map, lower_map, space_map).
    If return_maps is True, the tuple of maps is returned alongside the encrypted text.
    """
    if precomputed_maps:
        upper_map, lower_map, space_map = precomputed_maps
    else:
        upper_map, lower_map, space_map = get_dynamic_mappings(secret_key, nonce)
    
    # Combine all mappings
    combined_map = {**space_map, **upper_map, **lower_map}
    
    # Apply mapping character by character
    result = []
    for char in text:
        if char in combined_map:
            result.append(combined_map[char])
        else:
            # Keep unmapped characters as-is
            result.append(char)
    
    encrypted = ''.join(result)
    if return_maps:
        return encrypted, (upper_map, lower_map, space_map)
    return encrypted

def encrypt_article_text(text: str, secret_key: int, generate_font: bool = False, base_url: str = None) -> dict:
    """
    Encrypt article text using dynamic Feistel cipher mapping:
    1. Expand ligatures first (handles Unicode ligatures)
    2. Calculate nonce from text
    3. Apply dynamic character remapping using secret key and nonce
    4. Optionally generate the matching decryption font (so tests/debug flows also get a font)
    
    Returns:
        dict with encrypted text, nonce, and optional font metadata
    """
    expanded = expand_ligatures(text)
    nonce = nonce_creator(expanded)
    encrypted, maps = remap_text_ultra_fast(expanded, secret_key, nonce, return_maps=True)

    font_filename = None
    font_url = None
    if generate_font:
        upper_map, lower_map, space_map = maps
        font_filename, font_url = generate_font_artifacts(
            secret_key, nonce, upper_map, lower_map, space_map, base_url=base_url
        )
    
    return {
        'encrypted': encrypted,
        'nonce': nonce,
        'font_filename': font_filename,
        'font_url': font_url,
    }

def decrypt_article_text(encrypted_text: str, secret_key: int, nonce: int = None) -> str:
    """
    Decrypt article text using Feistel cipher dec() function directly.
    Does not rely on stored mappings - uses dec() from Fiesty.py.
    Now handles space as position 26 (0-26 range).
    
    Args:
        encrypted_text: The encrypted text to decrypt
        secret_key: The secret key used for encryption
        nonce: The nonce used for encryption. If None, will attempt to calculate
               from encrypted text (may not be accurate if text changed significantly)
    
    Returns:
        Decrypted text
    """
    # Step 1: Calculate nonce if not provided
    if nonce is None:
        # Try to calculate nonce from encrypted text (may not be perfect)
        nonce = nonce_creator(encrypted_text)
    
    # Step 2: Calculate what space encrypts to (for ambiguity resolution)
    # Space is at position 26
    space_encrypted_pos = enc(secret_key, nonce, 26)
    if space_encrypted_pos < 26:
        space_encrypted_char = LOWERCASE[space_encrypted_pos]
    else:
        space_encrypted_char = ' '  # Space encrypts to itself
    
    # Step 3: Pre-calculate which positions encrypt to 26 (space)
    # This helps us decrypt spaces correctly
    positions_that_encrypt_to_26 = []
    for pos in range(27):  # Check 0-26
        if enc(secret_key, nonce, pos) == 26:
            positions_that_encrypt_to_26.append(pos)
    
    # Step 4: Decrypt each character using dec() function
    result = []
    for char in encrypted_text:
        # Handle space in encrypted text
        # A space means position 26 in the encrypted alphabet
        # We need to find which original position(s) encrypt to 26
        if char == ' ':
            # Decrypt position 26 to see what it came from
            decrypted_from_26 = dec(secret_key, nonce, 26)
            # If position 26 decrypts to 26, then the space came from space
            # Otherwise, it came from a letter at that position
            if decrypted_from_26 == 26:
                result.append(' ')
            elif decrypted_from_26 < 26:
                # It came from a lowercase letter
                result.append(LOWERCASE[decrypted_from_26])
            else:
                result.append(' ')  # Fallback
        # Check if it's uppercase
        elif char in UPPERCASE:
            # Find position of encrypted character
            encrypted_pos = UPPERCASE.index(char)
            # Decrypt the position using dec()
            original_pos = dec(secret_key, nonce, encrypted_pos)
            # Map back to original character (0-25 for letters, 26 for space)
            if original_pos < 26:
                result.append(UPPERCASE[original_pos])
            else:
                result.append(' ')  # Position 26 is space
        # Check if it's lowercase
        elif char in LOWERCASE:
            # Find position of encrypted character
            encrypted_pos = LOWERCASE.index(char)
            # Decrypt the position using dec()
            original_pos = dec(secret_key, nonce, encrypted_pos)
            # Map back to original character (0-25 for letters, 26 for space)
            if original_pos < 26:
                result.append(LOWERCASE[original_pos])
            else:
                result.append(' ')  # Position 26 is space
        # Handle null character
        elif char == '\n':
            result.append('\x00')
        else:
            # Keep unmapped characters as-is
            result.append(char)
    
    decrypted = ''.join(result)
    
    # Note: Ligature expansion is one-way, so we can't reverse it
    # The decrypted text will have expanded ligatures (e.g., "ff" instead of ligature character)
    
    return decrypted

def nonce_creator(text: str) -> int:
    """
    Returns a list of the prevalences of each unique character in the input string,
    sorted in descending order (largest count first), with only the counts (not the characters).
    
    Example:
        text = "aabbccac"
        counts: 'a':3, 'b':2, 'c':3  --> output: [3, 3, 2] --> after sorting: [3, 3, 2]

    Then that is concatenated ([3, 3, 2] --> "332") and hashed to an integer.
    """
    
    counts = Counter(text)
    sort = sorted(counts.values(), reverse=True)
    sort_str = "".join(str(i) for i in sort)
    return int(hashlib.md5(sort_str.encode('utf-8')).hexdigest(), 16) % 1000000

def upload_font_to_r2(font_path: str, font_filename: str) -> str:
    """
    Upload font to Cloudflare R2 and return the public URL.
    Returns None if upload fails or R2 is not configured.
    """
    if not R2_AVAILABLE:
        return None
    
    # Check if R2 credentials are configured
    r2_account_id = os.environ.get('R2_ACCOUNT_ID')
    r2_access_key = os.environ.get('R2_ACCESS_KEY_ID')
    r2_secret_key = os.environ.get('R2_SECRET_ACCESS_KEY')
    r2_bucket = os.environ.get('R2_BUCKET_NAME')
    r2_public_url = os.environ.get('R2_PUBLIC_URL', 'https://pub-5eb60ded9abd4136b4908ea55a742d6e.r2.dev')
    
    if not all([r2_account_id, r2_access_key, r2_secret_key, r2_bucket]):
        return None
    
    try:
        # Create S3-compatible client for R2
        s3_client = boto3.client(
            's3',
            endpoint_url=f'https://{r2_account_id}.r2.cloudflarestorage.com',
            aws_access_key_id=r2_access_key,
            aws_secret_access_key=r2_secret_key,
            config=Config(signature_version='s3v4')
        )
        
        # Upload font to R2
        s3_client.upload_file(
            font_path,
            r2_bucket,
            font_filename,
            ExtraArgs={'ContentType': 'font/woff2'}
        )
        
        # Return public URL
        r2_url = f"{r2_public_url.rstrip('/')}/{font_filename}"
        if DEBUG_MODE:
            print(f"✅ Font uploaded to R2: {r2_url}")
        return r2_url
    except Exception as e:
        if DEBUG_MODE:
            print(f"⚠️ Failed to upload font to R2: {e}")
            import traceback
            traceback.print_exc()
        return None

def generate_font_artifacts(secret_key: int, nonce: int, upper_map, lower_map, space_map, base_url: str = None):
    """
    Create (or reuse) the decryption font for a secret_key + nonce pair and return its filename + URL.
    Automatically uploads to Cloudflare R2 if configured.
    """
    fallback_url = os.environ.get('FONT_URL', 'https://your-cdn.com/fonts/encrypted.woff2')
    base_font_path = os.path.join(os.path.dirname(__file__), 'Supertest.ttf')
    fonts_dir = os.path.join(os.path.dirname(__file__), 'fonts')
    os.makedirs(fonts_dir, exist_ok=True)

    font_hash = hashlib.md5(f"{secret_key}_{nonce}".encode('utf-8')).hexdigest()[:12]
    font_filename = f"decryption_{font_hash}.woff2"
    font_path = os.path.join(fonts_dir, font_filename)

    if not os.path.exists(base_font_path):
        if DEBUG_MODE:
            print(f"Warning: Base font not found at {base_font_path}, skipping generation")
        return font_filename, fallback_url

    try:
        font_was_generated = False
        if os.path.exists(font_path):
            if DEBUG_MODE:
                print(f"Font already exists locally: {font_filename}")
        else:
            if DEBUG_MODE:
                print(f"Generating decryption font: {font_filename}")
            create_decryption_font_from_mappings(base_font_path, font_path, upper_map, lower_map, space_map)
            font_was_generated = True
        
        # Check if we should use R2
        use_r2 = os.environ.get('USE_R2_FONTS', 'false').lower() == 'true'
        
        # Always try to upload to R2 if USE_R2_FONTS is enabled (even if font exists locally)
        # This ensures fonts are always available on R2
        if use_r2:
            if DEBUG_MODE:
                print(f"USE_R2_FONTS is enabled, uploading {font_filename} to R2...")
            if not os.path.exists(font_path):
                if DEBUG_MODE:
                    print(f"ERROR: Font file does not exist at {font_path}")
            elif DEBUG_MODE:
                print(f"Font file exists, size: {os.path.getsize(font_path)} bytes")
            r2_url = upload_font_to_r2(font_path, font_filename)
            if r2_url:
                if DEBUG_MODE:
                    print(f"✅ Font uploaded to R2: {r2_url}")
                # Use proxy URL to avoid CORS issues
                resolved_base = base_url or os.environ.get('BASE_URL', 'http://localhost:5000')
                proxy_url = f"{resolved_base.rstrip('/')}/proxy-font/{font_filename}"
                if DEBUG_MODE:
                    print(f"✅ Using proxy font URL (avoids CORS): {proxy_url}")
                return font_filename, proxy_url
            elif DEBUG_MODE:
                print(f"⚠️ R2 upload failed or not configured, falling back to local URL")
        elif font_was_generated:
            # If font was just generated but R2 is not enabled, try uploading anyway (one-time)
            if DEBUG_MODE:
                print(f"Font was generated, attempting R2 upload...")
            r2_url = upload_font_to_r2(font_path, font_filename)
            if r2_url:
                return font_filename, r2_url
        
    except Exception as e:
        if DEBUG_MODE:
            print(f"Error generating font {font_filename}: {e}")
            import traceback
            traceback.print_exc()
        return font_filename, fallback_url

    # Return local URL if R2 upload not used
    resolved_base = base_url or os.environ.get('BASE_URL')
    if resolved_base:
        font_url = f"{resolved_base.rstrip('/')}/fonts/{font_filename}"
    else:
        font_url = fallback_url
    if DEBUG_MODE:
        print(f"Using local font URL: {font_url}")
    return font_filename, font_url

# ============================================================================
# CACHING AND API ENDPOINTS
# ============================================================================

# Caching removed - encrypt directly without caching

@app.route('/api/encrypt', methods=['POST'])
def encrypt_article():
    """
    Main API endpoint for encrypting article text.
    
    Request body:
        {
            "text": "The article text to encrypt",
            "secret_key": 29202393
        }
    
    Response:
        {
            "encrypted": "Encrypted text using dynamic Feistel cipher",
            "font_url": "https://your-cdn.com/fonts/encrypted.woff2"
        }
    """
    try:
        data = request.json
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        article_text = data.get('text', '')
        secret_key = data.get('secret_key')
        
        if not article_text:
            return jsonify({'error': 'No text provided'}), 400
        
        if secret_key is None:
            return jsonify({'error': 'No secret_key provided'}), 400
        
        # Convert secret_key to int if it's a string
        try:
            secret_key = int(secret_key)
        except (ValueError, TypeError):
            return jsonify({'error': 'secret_key must be an integer'}), 400
        
        # Debug: Log the secret_key being used (only in debug mode)
        if DEBUG_MODE:
            print(f"DEBUG: Encrypting text='{article_text[:20]}...' with secret_key={secret_key} (type: {type(secret_key).__name__})")
        
        base_url = os.environ.get('BASE_URL', request.url_root.rstrip('/'))
        encryption = encrypt_article_text(article_text, secret_key, generate_font=True, base_url=base_url)
        
        # Debug: Log the result (only in debug mode)
        if DEBUG_MODE:
            print(f"DEBUG: Encrypted result: '{encryption['encrypted']}'")
        
        return jsonify({
            'encrypted': encryption['encrypted'],
            'nonce': encryption['nonce'],  # Include nonce for decryption
            'secret_key_used': secret_key if DEBUG_MODE else None,  # Only include in debug mode
            'font_url': encryption['font_url'],
            'font_filename': encryption['font_filename']  # Include filename for reference
        })
    
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback.print_exc()
        return jsonify({'error': error_msg, 'type': type(e).__name__}), 500

@app.route('/api/decrypt', methods=['POST'])
def decrypt_article():
    """
    API endpoint for decrypting article text.
    
    Request body:
        {
            "encrypted": "Encrypted text to decrypt",
            "secret_key": 29202393,
            "nonce": 462508  # optional, will try to calculate if not provided
        }
    
    Response:
        {
            "decrypted": "Decrypted text",
            "nonce_used": 462508
        }
    """
    try:
        data = request.json
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        encrypted_text = data.get('encrypted', '')
        secret_key = data.get('secret_key')
        nonce = data.get('nonce')  # Optional
        
        if not encrypted_text:
            return jsonify({'error': 'No encrypted text provided'}), 400
        
        if secret_key is None:
            return jsonify({'error': 'No secret_key provided'}), 400
        
        # Convert secret_key to int if it's a string
        try:
            secret_key = int(secret_key)
        except (ValueError, TypeError):
            return jsonify({'error': 'secret_key must be an integer'}), 400
        
        # Convert nonce to int if provided
        if nonce is not None:
            try:
                nonce = int(nonce)
            except (ValueError, TypeError):
                return jsonify({'error': 'nonce must be an integer'}), 400
        
        # Decrypt using dynamic Feistel cipher
        decrypted_text = decrypt_article_text(encrypted_text, secret_key, nonce)
        
        # If nonce wasn't provided, calculate what was used
        if nonce is None:
            nonce = nonce_creator(encrypted_text)
        
        return jsonify({
            'decrypted': decrypted_text,
            'nonce_used': nonce
        })
    
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback.print_exc()
        return jsonify({'error': error_msg, 'type': type(e).__name__}), 500

@app.route('/api/encrypt/page', methods=['POST'])
def encrypt_page():
    """
    Encrypt entire webpage - extracts and encrypts all text content from HTML.
    Designed for single API call per page.
    
    Request body:
        {
            "html": "<html>...</html>",  # Optional: full HTML
            "texts": ["Text 1", "Text 2", ...],  # All text nodes from page
            "secret_key": 29202393
        }
    
    Response:
        {
            "encrypted_texts": ["Encrypted 1", "Encrypted 2", ...],
            "font_url": "https://your-cdn.com/fonts/encrypted.woff2",
            "nonce": 462508
        }
    """
    try:
        data = request.json
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        texts = data.get('texts', [])
        secret_key = data.get('secret_key')
        
        if not texts or not isinstance(texts, list):
            return jsonify({'error': 'No texts array provided'}), 400
        
        if secret_key is None:
            return jsonify({'error': 'No secret_key provided'}), 400
        
        # Convert secret_key to int if it's a string
        try:
            secret_key = int(secret_key)
        except (ValueError, TypeError):
            return jsonify({'error': 'secret_key must be an integer'}), 400
        
        if len(texts) > 1000:  # Limit batch size for entire pages
            return jsonify({'error': 'Too many text nodes (max 1000)'}), 400
        
        # Filter out empty or very short texts
        valid_texts = []
        text_indices = []  # Track original indices
        for i, text in enumerate(texts):
            if text and isinstance(text, str) and len(text.strip()) > 0:
                valid_texts.append(text.strip())
                text_indices.append(i)
        
        if len(valid_texts) == 0:
            return jsonify({
                'encrypted_texts': [],
                'font_url': None,
                'nonce': None
            })
        
        # Combine all text to calculate a single nonce for the entire page
        # This ensures consistent encryption across the page
        combined_text = ' '.join(valid_texts)
        expanded = expand_ligatures(combined_text)
        nonce = nonce_creator(expanded)
        
        # Get mappings once for the entire page
        upper_map, lower_map, space_map = get_dynamic_mappings(secret_key, nonce)
        combined_map = {**space_map, **upper_map, **lower_map}
        
        # Encrypt all texts using the same mapping
        encrypted_texts = []
        for text in valid_texts:
            expanded_text = expand_ligatures(text)
            encrypted = ''.join(combined_map.get(char, char) for char in expanded_text)
            encrypted_texts.append(encrypted)
        
        # Generate font for this encryption
        base_url = os.environ.get('BASE_URL', request.url_root.rstrip('/'))
        font_filename, font_url = generate_font_artifacts(
            secret_key, nonce, upper_map, lower_map, space_map, base_url=base_url
        )
        
        # Create result array matching original indices (with empty strings for filtered texts)
        result_texts = [''] * len(texts)
        for idx, encrypted_text in zip(text_indices, encrypted_texts):
            result_texts[idx] = encrypted_text
        
        return jsonify({
            'encrypted_texts': result_texts,
            'font_url': font_url,
            'font_filename': font_filename,
            'nonce': nonce
        })
    
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback.print_exc()
        return jsonify({'error': error_msg, 'type': type(e).__name__}), 500

@app.route('/api/encrypt/batch', methods=['POST'])
def encrypt_articles_batch():
    """
    Batch encryption endpoint for encrypting multiple articles at once.
    Much more efficient for high-traffic sites.
    
    Request body:
        {
            "texts": ["Article 1 text", "Article 2 text", ...],
            "secret_key": 29202393
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
        secret_key = data.get('secret_key')
        
        if not texts or not isinstance(texts, list):
            return jsonify({'error': 'No texts array provided'}), 400
        
        if secret_key is None:
            return jsonify({'error': 'No secret_key provided'}), 400
        
        # Convert secret_key to int if it's a string
        try:
            secret_key = int(secret_key)
        except (ValueError, TypeError):
            return jsonify({'error': 'secret_key must be an integer'}), 400
        
        if len(texts) > 100:  # Limit batch size
            return jsonify({'error': 'Batch size too large (max 100)'}), 400
        
        # Encrypt all texts using dynamic Feistel cipher
        encrypted_texts = []
        nonces = []
        font_urls = {}  # Map nonce -> font_url
        mappings_cache = {}  # Cache mappings by nonce to avoid recalculation
        
        base_url = os.environ.get('BASE_URL', request.url_root.rstrip('/'))
        
        for text in texts:
            if not text or not isinstance(text, str):
                encrypted_texts.append('')
                nonces.append(None)
                continue
            
            # Expand ligatures and calculate nonce
            expanded = expand_ligatures(text)
            nonce = nonce_creator(expanded)
            nonces.append(nonce)
            
            # Get mappings (use cache if available)
            if nonce not in mappings_cache:
                upper_map, lower_map, space_map = get_dynamic_mappings(secret_key, nonce)
                mappings_cache[nonce] = (upper_map, lower_map, space_map)
            else:
                upper_map, lower_map, space_map = mappings_cache[nonce]
            
            # Use mappings to encrypt the text
            combined_map = {**space_map, **upper_map, **lower_map}
            encrypted = ''.join(combined_map.get(char, char) for char in expanded)
            encrypted_texts.append(encrypted)
            
            # Generate font for this nonce if we haven't already
            if nonce not in font_urls:
                font_filename, font_url = generate_font_artifacts(
                    secret_key, nonce, upper_map, lower_map, space_map, base_url=base_url
                )
                font_urls[nonce] = font_url
        
        # Use the first font URL as the primary font_url for backward compatibility
        primary_font_url = font_urls.get(nonces[0] if nonces else None, 
                                        os.environ.get('FONT_URL', 'https://your-cdn.com/fonts/encrypted.woff2'))
        
        return jsonify({
            'encrypted': encrypted_texts,
            'nonces': nonces,  # Include nonces for each encrypted text
            'font_url': primary_font_url,  # Primary font URL (backward compatibility)
            'font_urls': font_urls  # Map of nonce -> font_url for each unique encryption
        })
    
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback.print_exc()
        return jsonify({'error': error_msg, 'type': type(e).__name__}), 500

@app.route('/', methods=['GET'])
def root():
    """Root endpoint - serve test page"""
    return send_from_directory(os.path.dirname(__file__), 'test_page_encryption.html')

@app.route('/client/encrypt-page.js', methods=['GET'])
def serve_encrypt_page_script():
    """Serve the automatic page encryption client script"""
    client_dir = os.path.join(os.path.dirname(__file__), 'client')
    return send_from_directory(client_dir, 'encrypt-page.js', mimetype='application/javascript')

@app.route('/api', methods=['GET'])
def api_info():
    """API information endpoint"""
    return jsonify({
        'service': 'article-encryption-api',
        'status': 'running',
        'endpoints': {
            'encrypt': '/api/encrypt (POST)',
            'decrypt': '/api/decrypt (POST)',
            'batch': '/api/encrypt/batch (POST)',
            'page': '/api/encrypt/page (POST)',
            'test': '/api/test (POST)',
            'health': '/api/health (GET)',
            'debug_mapping': '/api/debug/mapping (POST)'
        }
    })

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
        test_text = data.get('text')
        secret_key = data.get('secret_key')
        
        # Convert secret_key to int if it's a string
        try:
            secret_key = int(secret_key)
        except (ValueError, TypeError):
            return jsonify({'error': 'secret_key must be an integer'}), 400
        
        # Debug: Log the secret_key being used (only in debug mode)
        if DEBUG_MODE:
            print(f"DEBUG TEST: Encrypting text='{test_text}' with secret_key={secret_key}")
        
        base_url = os.environ.get('BASE_URL', request.url_root.rstrip('/'))
        encryption_result = encrypt_article_text(test_text, secret_key, generate_font=True, base_url=base_url)
        encrypted = encryption_result['encrypted']
        
        # Debug: Log the result (only in debug mode)
        if DEBUG_MODE:
            print(f"DEBUG TEST: Encrypted result: '{encrypted}'")
        
        nonce = encryption_result['nonce']
        
        # Decrypt to verify it works
        decrypted = decrypt_article_text(encrypted, secret_key, nonce)
        
        return jsonify({
            'original': test_text,
            'encrypted': encrypted,
            'decrypted': decrypted,
            'nonce': nonce,
            'font_url': encryption_result['font_url'],
            'font_filename': encryption_result['font_filename'],
            'algorithm': 'dynamic_feistel_cipher',
            'secret_key': secret_key,
            'secret_key_received': str(data.get('secret_key')),
            'secret_key_type': str(type(data.get('secret_key')).__name__) if data.get('secret_key') is not None else 'None',
            'roundtrip_success': test_text == decrypted
        })
    
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback.print_exc()
        return jsonify({'error': error_msg, 'type': type(e).__name__}), 500

@app.route('/api/debug/mapping', methods=['POST'])
def debug_mapping():
    """
    Debug endpoint to show character mappings for different secret keys.
    Useful for verifying that mappings change with secret_key.
    
    Request body:
        {
            "secret_key1": 29202393,
            "secret_key2": 12345,
            "text": "Hello"  # optional, for nonce calculation
        }
    """
    try:
        data = request.json
        sk1 = data.get('secret_key1')
        sk2 = data.get('secret_key2')
        text = data.get('text', 'Hello')
        
        # Convert to int
        try:
            sk1 = int(sk1)
            sk2 = int(sk2)
        except (ValueError, TypeError):
            return jsonify({'error': 'secret_key1 and secret_key2 must be integers'}), 400
        
        # Calculate nonce
        expanded = expand_ligatures(text)
        nonce = nonce_creator(expanded)
        
        # Get mappings
        upper1, lower1, _ = get_dynamic_mappings(sk1, nonce)
        upper2, lower2, _ = get_dynamic_mappings(sk2, nonce)
        
        # Compare mappings
        upper_diff = {char: (upper1[char], upper2[char]) for char in UPPERCASE if upper1[char] != upper2[char]}
        lower_diff = {char: (lower1[char], lower2[char]) for char in LOWERCASE if lower1[char] != lower2[char]}
        
        # Test encryption with both keys to show they're different
        from encrypt_api import encrypt_article_text
        enc1 = encrypt_article_text(text, sk1)['encrypted']
        enc2 = encrypt_article_text(text, sk2)['encrypted']
        
        return jsonify({
            'nonce': nonce,
            'secret_key1': sk1,
            'secret_key2': sk2,
            'encrypted_text_sk1': enc1,
            'encrypted_text_sk2': enc2,
            'encrypted_texts_are_different': enc1 != enc2,
            'mappings_are_different': upper1 != upper2 or lower1 != lower2,
            'uppercase_mappings_different': len(upper_diff),
            'lowercase_mappings_different': len(lower_diff),
            'uppercase_differences': upper_diff,
            'lowercase_differences': lower_diff,
            'sample_uppercase_mapping_sk1': {k: upper1[k] for k in list(UPPERCASE)[:10]},
            'sample_uppercase_mapping_sk2': {k: upper2[k] for k in list(UPPERCASE)[:10]},
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'type': type(e).__name__}), 500

# Serve font files if hosting locally (optional)
@app.route('/fonts/<path:filename>')
def serve_font(filename):
    """Serve font files (optional - usually use CDN instead)"""
    fonts_dir = os.path.join(os.path.dirname(__file__), 'fonts')
    return send_from_directory(fonts_dir, filename)

# Proxy endpoint to serve R2 fonts with CORS headers
@app.route('/proxy-font/<path:filename>')
def proxy_font(filename):
    """
    Proxy font files from R2 to avoid CORS issues.
    Fetches font from R2 and serves it with proper CORS headers.
    """
    try:
        import requests
    except ImportError:
        return jsonify({'error': 'requests library not installed'}), 500
    
    r2_public_url = os.environ.get('R2_PUBLIC_URL', 'https://pub-d9bb596a8d3640a78a3d56af3fdebbbc.r2.dev')
    font_url = f"{r2_public_url.rstrip('/')}/{filename}"
    
    try:
        # Fetch font from R2
        response = requests.get(font_url, timeout=10)
        response.raise_for_status()
        
        # Return font with proper headers
        from flask import Response
        return Response(
            response.content,
            mimetype='font/woff2',
            headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
                'Access-Control-Allow-Headers': '*',
                'Cache-Control': 'public, max-age=31536000',  # Cache for 1 year
                'Content-Length': str(len(response.content))
            }
        )
    except requests.exceptions.RequestException as e:
        if DEBUG_MODE:
            print(f"Error proxying font {filename}: {e}")
        return jsonify({'error': f'Failed to fetch font: {str(e)}'}), 500

if __name__ == '__main__':
    # Configuration
    # Default to 5001 to avoid macOS AirPlay Receiver conflict on port 5000
    port = int(os.environ.get('PORT', 5001))
    host = os.environ.get('HOST', '0.0.0.0')
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    print(f"Starting Article Encryption API on {host}:{port}")
    print(f"Debug mode: {debug}")
    print(f"API endpoint: http://{host}:{port}/api/encrypt")
    print(f"Test page: http://{host}:{port}/")
    
    app.run(host=host, port=port, debug=debug)
