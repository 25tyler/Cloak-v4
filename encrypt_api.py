#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backend API Server for Article Encryption
Uses the EXACT algorithm from EncTestNewTestF.py
"""
from flask import Flask, request, jsonify, send_from_directory, has_request_context
from flask_cors import CORS
# Caching removed - no longer using lru_cache
from collections import Counter
import hashlib
import os
import json
import re
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
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

# Default secret key - can be overridden per request
DEFAULT_SECRET_KEY = int(os.environ.get('DEFAULT_SECRET_KEY', '29202393'))

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
    Apply dynamic character remapping using unified Feistel cipher.
    Maps each character using the secret key and nonce.
    
    NOTE: Uses unified mapping for all 54 characters (26 uppercase + 28 lowercase+space+period).
    All characters are in one big cycle based on the Feistel cipher.
    The font handles case differences in rendering.
    
    precomputed_maps may be supplied to avoid recomputing (upper_map, lower_map, space_map).
    If return_maps is True, the tuple of maps is returned alongside the encrypted text.
    """
    if precomputed_maps:
        upper_map, lower_map, space_map = precomputed_maps
    else:
        upper_map, lower_map, space_map = get_dynamic_mappings(secret_key, nonce)
    
    # Combine all mappings (space is already in lower_map, space_map only has special chars)
    combined_map = {**upper_map, **lower_map, **space_map}
    
    # Apply mapping character by character
    result = []
    for char in text:
        if char in combined_map:
            result.append(combined_map[char])
        else:
            # Keep unmapped characters as-is
            result.append(char)
    
    encrypted = ''.join(result)
    
    # Note: Space can appear in encrypted text (as a target from other characters).
    # The font will render spaces correctly by showing the glyph of the character that maps to space.
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
    space_char = None
    if generate_font:
        upper_map, lower_map, space_map = maps
        font_filename, font_url = generate_font_artifacts(
            secret_key, nonce, upper_map, lower_map, space_map, base_url=base_url
        )
        # Get the character that space maps to (for CSS word-breaking)
        space_char = lower_map.get(' ', None)
    
    return {
        'encrypted': encrypted,
        'nonce': nonce,
        'font_filename': font_filename,
        'font_url': font_url,
        'space_char': space_char,  # Character that space encrypts to (for word-breaking)
    }

def decrypt_article_text(encrypted_text: str, secret_key: int, nonce: int = None) -> str:
    """
    Decrypt article text using unified Feistel cipher mapping.
    Uses the reverse of the unified mapping (all 54 characters in one cycle).
    
    NOTE: Uses unified mapping for all 54 characters (26 uppercase + 28 lowercase+space+period).
    All characters are in one big cycle based on the Feistel cipher.
    
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
    
    # Step 2: Get the mappings (space is included in lower_map)
    upper_map, lower_map, space_map = get_dynamic_mappings(secret_key, nonce)
    
    # Step 3: Create reverse mappings for decryption
    # Reverse upper_map: encrypted -> original
    reverse_upper = {v: k for k, v in upper_map.items()}
    # Reverse lower_map: encrypted -> original (includes space)
    reverse_lower = {v: k for k, v in lower_map.items()}
    # Reverse space_map: encrypted -> original (only special chars like null->newline)
    reverse_space = {v: k for k, v in space_map.items()}
    
    # Step 4: Decrypt each character
    result = []
    for char in encrypted_text:
        # Check if it's uppercase
        if char in reverse_upper:
            result.append(reverse_upper[char])
        # Check if it's lowercase or space (space is in lower_map)
        elif char in reverse_lower:
            result.append(reverse_lower[char])
        # Check if it's a special character (like newline)
        elif char in reverse_space:
            result.append(reverse_space[char])
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

def generate_font_artifacts(secret_key: int, nonce: int, upper_map, lower_map, space_map, base_url: str = None, base_font_path: str = None, font_family: str = None, font_weight: str = None, font_style: str = None):
    """
    Create (or reuse) the decryption font for a secret_key + nonce pair and return its filename + URL.
    Automatically uploads to Cloudflare R2 if configured.
    
    Args:
        secret_key: Secret key for encryption
        nonce: Nonce for encryption
        upper_map: Upper case character mapping
        lower_map: Lower case character mapping
        space_map: Space/special character mapping
        base_url: Base URL for font URLs
        base_font_path: Optional path to base font file (if None, uses Supertest.ttf)
        font_family: Optional font family name (for unique font filename)
        font_weight: Optional font weight (for unique font filename)
        font_style: Optional font style (for unique font filename)
    """
    fallback_url = os.environ.get('FONT_URL', 'https://your-cdn.com/fonts/encrypted.woff2')
    if base_font_path is None:
        base_font_path = os.path.join(os.path.dirname(__file__), 'Supertest.ttf')
    fonts_dir = os.path.join(os.path.dirname(__file__), 'fonts')
    os.makedirs(fonts_dir, exist_ok=True)

    # Add version to hash to force regeneration when mapping logic changes
    # Version 3: Fixed bijectivity to include space as target
    # Include font family, weight, and style in hash for unique fonts
    hash_input = f"{secret_key}_{nonce}_v3"
    if font_family:
        hash_input += f"_{font_family}"
    if font_weight:
        hash_input += f"_{font_weight}"
    if font_style:
        hash_input += f"_{font_style}"
    font_hash = hashlib.md5(hash_input.encode('utf-8')).hexdigest()[:12]
    font_filename_woff2 = f"decryption_{font_hash}.woff2"
    font_filename_ttf = f"decryption_{font_hash}.ttf"
    font_path_woff2 = os.path.join(fonts_dir, font_filename_woff2)
    font_path_ttf = os.path.join(fonts_dir, font_filename_ttf)

    if not os.path.exists(base_font_path):
        if DEBUG_MODE:
            print(f"Warning: Base font not found at {base_font_path}, skipping generation")
        return font_filename_woff2, fallback_url

    try:
        font_was_generated = False
        font_filename = None
        font_path = None
        # Always regenerate fonts to ensure they're correct (in case mapping logic changed)
        # This ensures we don't use old fonts with incorrect mappings
        if DEBUG_MODE:
            print(f"Generating decryption font: {font_filename_woff2}")
        # Try to generate WOFF2, but fall back to TTF if it fails
        # Pass font_family to preserve original font-family name
        try:
            result = create_decryption_font_from_mappings(base_font_path, font_path_woff2, upper_map, lower_map, space_map, preserve_font_family=font_family)
            if result == True:
                font_filename = font_filename_woff2
                font_path = font_path_woff2
                font_was_generated = True
        except Exception as woff2_error:
            # WOFF2 generation failed (e.g., brotli missing), try TTF fallback
            if DEBUG_MODE:
                print(f"⚠️  WOFF2 generation failed: {woff2_error}, trying TTF fallback...")
            try:
                result = create_decryption_font_from_mappings(base_font_path, font_path_ttf, upper_map, lower_map, space_map, preserve_font_family=font_family)
                if result == True:
                    font_filename = font_filename_ttf
                    font_path = font_path_ttf
                    font_was_generated = True
                    if DEBUG_MODE:
                        print(f"✅ TTF fallback successful: {font_filename}")
                else:
                    if DEBUG_MODE:
                        print(f"⚠️  TTF generation also failed")
            except Exception as ttf_error:
                if DEBUG_MODE:
                    print(f"⚠️  TTF generation failed: {ttf_error}")
                # Both failed, will use fallback URL
        
        # Check if we should use R2
        use_r2 = os.environ.get('USE_R2_FONTS', 'false').lower() == 'true'
        
        # Always try to upload to R2 if USE_R2_FONTS is enabled (even if font exists locally)
        # This ensures fonts are always available on R2
        if use_r2 and font_filename.endswith('.woff2'):
            # Only upload WOFF2 to R2, not TTF
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
                # ALWAYS use proxy URL to avoid CORS issues - never use direct R2 URL
                # Try base_url, then BASE_URL env var, then request.url_root (if in request context)
                # Default to API server URL if nothing else is available
                if base_url:
                    resolved_base = base_url
                elif os.environ.get('BASE_URL'):
                    resolved_base = os.environ.get('BASE_URL')
                elif has_request_context():
                    resolved_base = request.url_root.rstrip('/')
                else:
                    # Default to API server URL (port 5001) to ensure proxy works
                    api_port = os.environ.get('PORT', '5001')
                    resolved_base = f"http://localhost:{api_port}"
                    if DEBUG_MODE:
                        print(f"⚠️ No base_url found, defaulting to API server: {resolved_base}")
                
                # Add cache-busting timestamp to force browser to reload font
                import time
                cache_buster = int(time.time())
                proxy_url = f"{resolved_base.rstrip('/')}/proxy-font/{font_filename}?v={cache_buster}"
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
                # Even when R2 is not explicitly enabled, use proxy URL to avoid CORS
                if base_url:
                    resolved_base = base_url
                elif os.environ.get('BASE_URL'):
                    resolved_base = os.environ.get('BASE_URL')
                elif has_request_context():
                    resolved_base = request.url_root.rstrip('/')
                else:
                    api_port = os.environ.get('PORT', '5001')
                    resolved_base = f"http://localhost:{api_port}"
                
                import time
                cache_buster = int(time.time())
                proxy_url = f"{resolved_base.rstrip('/')}/proxy-font/{font_filename}?v={cache_buster}"
                return font_filename, proxy_url
        
    except Exception as e:
        if DEBUG_MODE:
            error_font_name = font_filename if 'font_filename' in locals() else 'unknown'
            print(f"Error generating font {error_font_name}: {e}")
            import traceback
            traceback.print_exc()
        return font_filename if 'font_filename' in locals() else None, fallback_url

    # Return local URL if font was generated but R2 upload not used
    if not font_was_generated:
        # Font generation failed, return fallback
        if DEBUG_MODE:
            print(f"⚠️  Font generation failed, using fallback URL")
        return font_filename if 'font_filename' in locals() else None, fallback_url
    
    # Try base_url, then BASE_URL env var, then request.url_root (if in request context)
    if base_url:
        resolved_base = base_url
    elif os.environ.get('BASE_URL'):
        resolved_base = os.environ.get('BASE_URL')
    elif has_request_context():
        resolved_base = request.url_root.rstrip('/')
    else:
        # Default to API server URL (port 5001) to ensure proxy works
        api_port = os.environ.get('PORT', '5001')
        resolved_base = f"http://localhost:{api_port}"
        if DEBUG_MODE:
            print(f"⚠️ No base_url found, defaulting to API server: {resolved_base}")
    
    if resolved_base and font_filename:
        # Use proxy-font endpoint to avoid CORS issues
        # Add cache-busting timestamp to force browser to reload font
        import time
        cache_buster = int(time.time())
        font_url = f"{resolved_base.rstrip('/')}/proxy-font/{font_filename}?v={cache_buster}"
        if DEBUG_MODE:
            print(f"✅ Generated font URL: {font_url}")
    else:
        if DEBUG_MODE:
            print(f"⚠️  No resolved_base or font_filename, using fallback URL")
        font_url = fallback_url
    if DEBUG_MODE:
        print(f"Using local font URL: {font_url}")
    return font_filename, font_url

# ============================================================================
# FONT EXTRACTION AND DOWNLOAD FUNCTIONS
# ============================================================================

def extract_fonts_from_html(soup, base_url: str = None):
    """
    Extract all fonts from HTML by parsing @font-face rules and <link> tags.
    
    Args:
        soup: BeautifulSoup object
        base_url: Base URL for resolving relative URLs
    
    Returns:
        List of font definitions: [{
            'url': str,           # Font file URL
            'family': str,         # Font family name
            'weight': str,         # Font weight (e.g., 'normal', 'bold', '400', '700')
            'style': str,          # Font style (e.g., 'normal', 'italic')
            'source_type': str,    # 'fontface' or 'link'
            'original_rule': str   # Original CSS rule or link href for replacement
        }]
    """
    fonts = []
    
    # Extract from @font-face rules in <style> tags
    for style_tag in soup.find_all('style'):
        if not style_tag.string:
            continue
        
        css_content = style_tag.string
        
        # Parse @font-face rules using regex
        # Match: @font-face { ... }
        fontface_pattern = r'@font-face\s*\{([^}]+)\}'
        matches = re.finditer(fontface_pattern, css_content, re.IGNORECASE | re.DOTALL)
        
        for match in matches:
            font_rule = match.group(1)
            font_info = {}
            
            # Extract font-family
            family_match = re.search(r'font-family\s*:\s*([^;]+)', font_rule, re.IGNORECASE)
            if family_match:
                # Remove quotes and whitespace
                family = family_match.group(1).strip().strip("'\"")
                font_info['family'] = family
            
            # Extract font-weight
            weight_match = re.search(r'font-weight\s*:\s*([^;]+)', font_rule, re.IGNORECASE)
            if weight_match:
                font_info['weight'] = weight_match.group(1).strip()
            else:
                font_info['weight'] = 'normal'
            
            # Extract font-style
            style_match = re.search(r'font-style\s*:\s*([^;]+)', font_rule, re.IGNORECASE)
            if style_match:
                font_info['style'] = style_match.group(1).strip()
            else:
                font_info['style'] = 'normal'
            
            # Extract src URLs
            src_match = re.search(r'src\s*:\s*([^;]+)', font_rule, re.IGNORECASE)
            if src_match:
                src_value = src_match.group(1).strip()
                # Extract URLs from src (can have multiple: url(...), url(...))
                url_pattern = r'url\s*\(\s*([^)]+)\s*\)'
                url_matches = re.finditer(url_pattern, src_value, re.IGNORECASE)
                
                for url_match in url_matches:
                    url = url_match.group(1).strip().strip("'\"")
                    
                    # Check if it's a font file
                    font_extensions = ['.woff2', '.woff', '.ttf', '.otf', '.eot']
                    if any(url.lower().endswith(ext) for ext in font_extensions):
                        # Resolve relative URLs
                        if base_url and not url.startswith(('http://', 'https://', '//', 'data:')):
                            from urllib.parse import urljoin
                            url = urljoin(base_url, url)
                        
                        font_info_copy = font_info.copy()
                        font_info_copy['url'] = url
                        font_info_copy['source_type'] = 'fontface'
                        font_info_copy['original_rule'] = match.group(0)  # Full @font-face rule
                        fonts.append(font_info_copy)
    
    # Extract from <link> tags
    for link_tag in soup.find_all('link'):
        href = link_tag.get('href', '')
        rel = link_tag.get('rel', [])
        
        # Check if it's a stylesheet or font file
        is_stylesheet = 'stylesheet' in rel or any(rel_item == 'stylesheet' for rel_item in rel if isinstance(rel_item, str))
        is_font_file = any(href.lower().endswith(ext) for ext in ['.woff2', '.woff', '.ttf', '.otf', '.eot'])
        
        if is_font_file or (is_stylesheet and any(href.lower().endswith(ext) for ext in ['.woff2', '.woff', '.ttf', '.otf', '.eot'])):
            # Resolve relative URLs
            if base_url and not href.startswith(('http://', 'https://', '//', 'data:')):
                from urllib.parse import urljoin
                href = urljoin(base_url, href)
            
            # Try to extract font-family from data attributes or infer from filename
            family = link_tag.get('data-font-family', '')
            if not family:
                # Try to infer from class or id
                family = link_tag.get('class', [''])[0] if link_tag.get('class') else ''
                if not family:
                    family = link_tag.get('id', '')
            
            fonts.append({
                'url': href,
                'family': family or 'Unknown',
                'weight': link_tag.get('data-font-weight', 'normal'),
                'style': link_tag.get('data-font-style', 'normal'),
                'source_type': 'link',
                'original_rule': href  # Original href for replacement
            })
        
        # Check if it's a CSS file that might contain @font-face rules
        # Use a flexible heuristic: check if URL contains 'font' (case-insensitive) or process all CSS
        # This is more flexible than hardcoding domains but still efficient
        elif is_stylesheet:
            # Heuristic: check if URL likely contains fonts (contains 'font' in path)
            # This catches patterns like: /fonts/css/, /font/, font.css, etc.
            href_lower = href.lower()
            likely_font_css = 'font' in href_lower or 'fonts' in href_lower
            
            # If it doesn't look like a font CSS file, skip it to avoid processing all CSS files
            # This maintains efficiency while being more flexible than hardcoded domains
            if not likely_font_css:
                if DEBUG_MODE:
                    print(f"⏭️  Skipping non-font CSS: {href}")
                continue
            
            # This is a CSS file that might contain @font-face rules
            # Download and parse it to extract fonts
            if base_url and not href.startswith(('http://', 'https://', '//', 'data:')):
                from urllib.parse import urljoin
                css_url = urljoin(base_url, href)
            else:
                css_url = href
            
            # Download and parse the CSS file
            if DEBUG_MODE:
                print(f"🔍 Processing potential font CSS: {css_url}")
            css_content = download_css(css_url, base_url=base_url)
            if css_content:
                if DEBUG_MODE:
                    print(f"✅ CSS downloaded successfully, checking for @font-face rules...")
                # Check if CSS contains @font-face rules before processing
                fontface_pattern = r'@font-face\s*\{([^}]+)\}'
                matches = list(re.finditer(fontface_pattern, css_content, re.IGNORECASE | re.DOTALL))
                
                if DEBUG_MODE:
                    print(f"📊 Found {len(matches)} @font-face rule(s) in CSS")
                
                # Only process if we found @font-face rules
                if matches:
                    # Parse @font-face rules from the CSS
                    for match in matches:
                        font_rule = match.group(1)
                        font_info = {}
                        
                        # Extract font-family
                        family_match = re.search(r'font-family\s*:\s*([^;]+)', font_rule, re.IGNORECASE)
                        if family_match:
                            family = family_match.group(1).strip().strip("'\"")
                            font_info['family'] = family
                        
                        # Extract font-weight
                        weight_match = re.search(r'font-weight\s*:\s*([^;]+)', font_rule, re.IGNORECASE)
                        if weight_match:
                            font_info['weight'] = weight_match.group(1).strip()
                        else:
                            font_info['weight'] = 'normal'
                        
                        # Extract font-style
                        style_match = re.search(r'font-style\s*:\s*([^;]+)', font_rule, re.IGNORECASE)
                        if style_match:
                            font_info['style'] = style_match.group(1).strip()
                        else:
                            font_info['style'] = 'normal'
                        
                        # Extract src URLs
                        src_match = re.search(r'src\s*:\s*([^;]+)', font_rule, re.IGNORECASE)
                        if src_match:
                            src_value = src_match.group(1).strip()
                            # Extract URLs from src (can have multiple: url(...), url(...))
                            url_pattern = r'url\s*\(\s*([^)]+)\s*\)'
                            url_matches = re.finditer(url_pattern, src_value, re.IGNORECASE)
                            
                            for url_match in url_matches:
                                url = url_match.group(1).strip().strip("'\"")
                                
                                # Check if it's a font file
                                font_extensions = ['.woff2', '.woff', '.ttf', '.otf', '.eot']
                                if any(url.lower().endswith(ext) for ext in font_extensions):
                                    # Resolve relative URLs (relative to CSS file location)
                                    from urllib.parse import urljoin
                                    css_base = '/'.join(css_url.split('/')[:-1]) + '/' if '/' in css_url else css_url
                                    resolved_url = urljoin(css_base, url)
                                    
                                    font_info_copy = font_info.copy()
                                    font_info_copy['url'] = resolved_url
                                    font_info_copy['source_type'] = 'css'
                                    font_info_copy['original_rule'] = match.group(0)  # Full @font-face rule
                                    font_info_copy['css_url'] = css_url  # Store CSS URL for later replacement
                                    fonts.append(font_info_copy)
                    
                    # Mark this link for CSS processing (so we can replace it with inline style later)
                    link_tag['data-encrypt-css'] = 'true'
                    link_tag['data-css-url'] = css_url
                    if DEBUG_MODE:
                        print(f"📄 Extracted {len([f for f in fonts if f.get('css_url') == css_url])} fonts from CSS: {css_url}")
    
    return fonts

def download_css(url: str, base_url: str = None):
    """
    Download a CSS file from a URL.
    
    Args:
        url: CSS file URL (can be relative or absolute)
        base_url: Base URL for resolving relative URLs
    
    Returns:
        CSS content as string if successful, None if failed
    """
    try:
        import requests
        from urllib.parse import urljoin
    except ImportError:
        if DEBUG_MODE:
            print(f"⚠️  requests library not available, cannot download CSS: {url}")
        return None
    
    # Resolve relative URLs
    if base_url and not url.startswith(('http://', 'https://', '//', 'data:')):
        url = urljoin(base_url, url)
    
    # Skip data URLs
    if url.startswith('data:'):
        if DEBUG_MODE:
            print(f"⚠️  Skipping data URL CSS: {url[:50]}...")
        return None
    
    # Download CSS
    try:
        if DEBUG_MODE:
            print(f"Downloading CSS from: {url}")
        response = requests.get(url, timeout=120, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        response.raise_for_status()
        
        css_content = response.text
        if DEBUG_MODE:
            print(f"✅ CSS downloaded: {len(css_content)} bytes")
        return css_content
    
    except Exception as e:
        if DEBUG_MODE:
            print(f"⚠️  Failed to download CSS from {url}: {e}")
        return None

def download_font(url: str, base_url: str = None, temp_dir: str = None):
    """
    Download a font file from a URL.
    
    Args:
        url: Font file URL (can be relative or absolute)
        base_url: Base URL for resolving relative URLs
        temp_dir: Directory to save downloaded fonts (default: fonts/downloaded/)
    
    Returns:
        Local file path if successful, None if failed
    """
    try:
        import requests
        from urllib.parse import urljoin, urlparse
    except ImportError:
        if DEBUG_MODE:
            print(f"⚠️  requests library not available, cannot download font: {url}")
        return None
    
    # Resolve relative URLs
    if base_url and not url.startswith(('http://', 'https://', '//', 'data:')):
        url = urljoin(base_url, url)
    
    # Skip data URLs
    if url.startswith('data:'):
        if DEBUG_MODE:
            print(f"⚠️  Skipping data URL font: {url[:50]}...")
        return None
    
    # Create temp directory
    if temp_dir is None:
        fonts_dir = os.path.join(os.path.dirname(__file__), 'fonts')
        temp_dir = os.path.join(fonts_dir, 'downloaded')
    os.makedirs(temp_dir, exist_ok=True)
    
    # Generate filename from URL
    parsed_url = urlparse(url)
    filename = os.path.basename(parsed_url.path)
    if not filename or '.' not in filename:
        # Generate filename from URL hash
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()[:12]
        filename = f"font_{url_hash}.woff2"
    
    local_path = os.path.join(temp_dir, filename)
    
    # Check if already downloaded
    if os.path.exists(local_path):
        if DEBUG_MODE:
            print(f"✅ Font already downloaded: {filename}")
        return local_path
    
    # Download font
    try:
        if DEBUG_MODE:
            print(f"Downloading font from: {url}")
        response = requests.get(url, timeout=120, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        response.raise_for_status()
        
        # Save to file
        with open(local_path, 'wb') as f:
            f.write(response.content)
        
        if DEBUG_MODE:
            print(f"✅ Font downloaded: {filename} ({len(response.content)} bytes)")
        return local_path
    
    except Exception as e:
        if DEBUG_MODE:
            print(f"⚠️  Failed to download font from {url}: {e}")
        return None

def encrypt_fonts_from_html(soup, secret_key: int, nonce: int, upper_map, lower_map, space_map, base_url: str = None):
    """
    Extract fonts from HTML, download them, and generate encrypted versions.
    
    Args:
        soup: BeautifulSoup object
        secret_key: Secret key for encryption
        nonce: Nonce for encryption
        upper_map: Upper case character mapping
        lower_map: Lower case character mapping
        space_map: Space/special character mapping
        base_url: Base URL for resolving relative URLs and generating font URLs
    
    Returns:
        Dictionary mapping original font info to encrypted font URL:
        {
            (family, weight, style, url): encrypted_font_url,
            ...
        }
    """
    font_mapping = {}
    
    # Extract fonts from HTML
    fonts = extract_fonts_from_html(soup, base_url=base_url)
    
    if not fonts:
        if DEBUG_MODE:
            print("No fonts found in HTML")
        return font_mapping
    
    if DEBUG_MODE:
        print(f"Found {len(fonts)} font(s) in HTML")
    
    # Process each font
    for font_info in fonts:
        url = font_info.get('url')
        family = font_info.get('family', 'Unknown')
        weight = font_info.get('weight', 'normal')
        style = font_info.get('style', 'normal')
        
        if not url:
            if DEBUG_MODE:
                print(f"⚠️  Skipping font with no URL: {family}")
            continue
        
        # Resolve URL to absolute URL for consistent matching
        # The URL from extract_fonts_from_html is already resolved, but let's ensure it's absolute
        resolved_url = url
        if base_url and not url.startswith(('http://', 'https://', '//', 'data:')):
            from urllib.parse import urljoin
            resolved_url = urljoin(base_url, url)
        
        if DEBUG_MODE:
            print(f"📥 Processing font: {family} ({weight}, {style}) from {resolved_url}")
        
        # Download font
        local_font_path = download_font(resolved_url, base_url=base_url)
        if not local_font_path:
            if DEBUG_MODE:
                print(f"⚠️  Failed to download font: {resolved_url}")
            continue
        
        # Generate encrypted font
        try:
            encrypted_font_filename, encrypted_font_url = generate_font_artifacts(
                secret_key=secret_key,
                nonce=nonce,
                upper_map=upper_map,
                lower_map=lower_map,
                space_map=space_map,
                base_url=base_url,
                base_font_path=local_font_path,
                font_family=family,
                font_weight=weight,
                font_style=style
            )
            
            # Create mapping key using resolved URL for consistent matching
            mapping_key = (family, weight, style, resolved_url)
            font_mapping[mapping_key] = {
                'url': encrypted_font_url,
                'filename': encrypted_font_filename,
                'family': family,
                'weight': weight,
                'style': style
            }
            
            if DEBUG_MODE:
                print(f"✅ Encrypted font generated: {family} ({weight}, {style}) -> {encrypted_font_filename}, URL: {encrypted_font_url}")
        
        except Exception as e:
            if DEBUG_MODE:
                print(f"⚠️  Failed to generate encrypted font for {family}: {e}")
                import traceback
                traceback.print_exc()
            continue
    
    return font_mapping

# ============================================================================
# HTML ENCRYPTION FUNCTIONS
# ============================================================================

def is_text_at_line_start(text_element):
    """
    Check if a text node is at the start of a new line.
    A text node is at line start if:
    1. It's the first child of its parent, OR
    2. The previous sibling is a block element or <br> tag, OR
    3. All previous siblings are whitespace-only and we're the first non-whitespace content
    4. We're the first non-whitespace content in a block element (even if nested in inline elements)
    """
    if not text_element or not text_element.parent:
        return False
    
    parent = text_element.parent
    
    # Block-level elements that cause line breaks
    block_elements = {
        'div', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'ul', 'ol', 'li', 'blockquote', 'pre', 'section',
        'article', 'header', 'footer', 'nav', 'aside',
        'table', 'tr', 'td', 'th', 'thead', 'tbody', 'tfoot',
        'dl', 'dt', 'dd', 'form', 'fieldset', 'legend',
        'address', 'hr', 'figure', 'figcaption', 'body'
    }
    
    # Helper to check if an element has visible text content
    def has_visible_content(elem):
        if hasattr(elem, 'get_text'):
            return bool(elem.get_text(strip=True))
        elif isinstance(elem, str) or (hasattr(elem, 'strip') and callable(getattr(elem, 'strip'))):
            return bool(str(elem).strip())
        return False
    
    # Check if this is the first child
    if not parent.contents or parent.contents[0] == text_element:
        return True
    
    # Find the previous sibling
    prev_sibling = text_element.previous_sibling
    
    # Skip over whitespace-only text nodes
    while prev_sibling:
        if hasattr(prev_sibling, 'name'):
            # It's a tag element
            if prev_sibling.name == 'br':
                return True
            if prev_sibling.name in block_elements:
                return True
            # If it's an inline element, check if it has any visible content
            if has_visible_content(prev_sibling):
                return False
            # Empty inline element, continue checking
            prev_sibling = getattr(prev_sibling, 'previous_sibling', None)
        elif isinstance(prev_sibling, str) or (hasattr(prev_sibling, 'strip') and callable(getattr(prev_sibling, 'strip'))):
            # It's a text node (NavigableString) - check if it's only whitespace
            if has_visible_content(prev_sibling):
                return False
            # Whitespace text, continue checking
            prev_sibling = getattr(prev_sibling, 'previous_sibling', None)
        else:
            break
    
    # If we got here, all previous siblings were whitespace or None
    # Now walk up the tree to find block element ancestors and check if we're first content
    current = parent
    while current:
        if hasattr(current, 'name') and current.name in block_elements:
            # Found a block element - check if we're the first non-whitespace content
            for sibling in current.children:
                # Check if this sibling is or contains our text element
                if sibling == text_element:
                    # Found ourselves - we're first
                    return True
                # Check if our text element is inside this sibling
                if hasattr(sibling, 'find_all'):
                    try:
                        if text_element in sibling.find_all(string=True):
                            # Our text is inside this sibling
                            # Check if any previous sibling has visible content
                            # (We already checked prev_siblings above, so if we got here, we're first)
                            return True
                    except:
                        pass
                # Check if this sibling has visible content before us
                if has_visible_content(sibling):
                    return False
            # We're the first non-whitespace content in this block element
            return True
        elif hasattr(current, 'parent'):
            current = current.parent
        else:
            break
    
    return False

def encrypt_html_content(html_content: str, secret_key: int, base_url: str = None):
    """
    Parse HTML, extract all visible text content, encrypt it, and build a mapping.
    
    Args:
        html_content: Raw HTML string
        secret_key: Secret key for encryption
        base_url: Base URL for font generation
    
    Returns:
        tuple: (soup, text_mapping, nonce, font_url, space_char, font_mapping)
        - soup: BeautifulSoup object with encrypted text
        - text_mapping: dict mapping original_text -> encrypted_text
        - nonce: Nonce used for encryption
        - font_url: URL to the decryption font (primary font URL)
        - space_char: Character that space encrypts to
        - font_mapping: dict mapping (family, weight, style, url) -> encrypted font info
    """
    if not BS4_AVAILABLE:
        raise ImportError("beautifulsoup4 is required for HTML encryption. Install with: pip install beautifulsoup4")
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Elements to skip (don't encrypt text in these)
    skip_tags = {'script', 'style', 'noscript', 'meta', 'title', 'head'}
    
    # Extract all visible text nodes
    # CRITICAL: Preserve leading and trailing spaces to maintain spacing around links
    text_nodes = []
    whitespace_only_nodes = []  # Track whitespace-only nodes separately
    for element in soup.find_all(string=True):
        # Skip if parent is in skip list
        parent = element.parent
        if parent and parent.name in skip_tags:
            continue
        
        # Get text content - preserve leading and trailing spaces
        original_text = str(element)
        # Process text nodes with non-whitespace content
        if original_text.strip() and len(original_text.strip()) > 0:
            text_nodes.append((element, original_text))
        # Also track whitespace-only nodes (spaces between elements like links)
        elif original_text.strip() == '' and len(original_text) > 0:
            # Skip whitespace-only nodes that are direct children of structural tags
            # (like whitespace between <html> and <head>, or <head> and <body>)
            # These are structural whitespace and shouldn't be rendered
            if parent and parent.name in {'html', 'head', 'body'}:
                continue
            # Only track whitespace nodes that are between content elements (like links)
            whitespace_only_nodes.append((element, original_text))
    
    if len(text_nodes) == 0:
        # No text to encrypt, return empty mapping
        # Note: Fonts cannot be encrypted without text (no nonce to generate mappings)
        return soup, {}, None, None, None, {}
    
    # Combine all text to calculate a single nonce for the entire page
    # Use stripped text for nonce calculation (spaces don't affect encryption mapping)
    combined_text = ' '.join([text.strip() for _, text in text_nodes])
    expanded = expand_ligatures(combined_text)
    nonce = nonce_creator(expanded)
    
    # Get mappings once for the entire page
    upper_map, lower_map, space_map = get_dynamic_mappings(secret_key, nonce)
    combined_map = {**upper_map, **lower_map, **space_map}
    
    # Encrypt all texts and build mapping
    text_mapping = {}
    replacements = []
    space_char = lower_map.get(' ', None)
    
    # Track containers by text element so we can find the last word span in previous inline elements
    element_to_container = {}
    
    # Helper function to find the last word span in a container
    def find_last_word_span(container):
        """Find the last word span in a container (span with word-break styling)"""
        if not container:
            return None
        # Find all spans with word-break styling
        word_spans = container.find_all('span', style=lambda x: x and 'word-break' in x)
        if word_spans:
            return word_spans[-1]
        # If no word spans found, check if container has direct string content
        if hasattr(container, 'string') and container.string:
            return container
        return None
    
    # Helper function to find the last word span in an inline element
    def find_last_word_span_in_element(elem):
        """Find the last word span in an inline element by searching for its containers"""
        if not elem:
            return None
        # Search for all containers we created from text nodes inside this element
        last_word_span = None
        for text_elem, container in element_to_container.items():
            # Check if this text element is inside the given element
            if text_elem and hasattr(text_elem, 'parent'):
                current = text_elem.parent
                while current:
                    if current == elem:
                        # Found a text node inside this element
                        word_span = find_last_word_span(container)
                        if word_span:
                            last_word_span = word_span
                        break
                    current = getattr(current, 'parent', None)
        return last_word_span
    
    for element, original_text in text_nodes:
        # CRITICAL: Preserve leading and trailing spaces from original text
        # This maintains spacing around hyperlinks and other inline elements
        # EXCEPT: Strip leading spaces if this text node is at the start of a new line
        # This prevents spaces from appearing at the beginning of lines
        is_at_line_start = is_text_at_line_start(element)
        
        leading_spaces_match = re.match(r'^(\s*)', original_text)
        trailing_spaces_match = re.search(r'(\s*)$', original_text)
        leading_spaces = leading_spaces_match.group(1) if leading_spaces_match else ''
        trailing_spaces = trailing_spaces_match.group(1) if trailing_spaces_match else ''
        
        # Encrypt the text content (without leading/trailing spaces for mapping)
        text_to_encrypt = original_text.strip()
        if not text_to_encrypt:
            # Only whitespace, skip
            continue
            
        expanded_text = expand_ligatures(text_to_encrypt)
        encrypted = ''.join(combined_map.get(char, char) for char in expanded_text)
        text_mapping[text_to_encrypt] = encrypted
        
        # Create a container to hold all spans (like client-side script)
        # Use minimal styling to avoid breaking parent layouts (flexbox, grid, etc.)
        container = soup.new_tag('span')
        container['style'] = 'display: inline; white-space: normal; height: auto;'
        
        # Check if container will start on a new line by checking the element's position
        # The container will start on a new line if:
        # 1. The original element is at line start, OR
        # 2. The element is the first child of its parent, OR
        # 3. All previous siblings are whitespace and parent is a block element
        container_will_start_line = is_at_line_start
        
        # Additional check: if element is first child or all previous siblings are whitespace
        if not container_will_start_line:
            parent = element.parent
            if parent:
                block_elements = {'div', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 
                                'blockquote', 'pre', 'section', 'article', 'header', 'footer', 
                                'nav', 'aside', 'table', 'tr', 'td', 'th', 'hr', 'figure', 'figcaption', 'body'}
                
                # Check if this is the first child
                if parent.contents and parent.contents[0] == element:
                    # If parent is a block element, container will start on new line
                    if hasattr(parent, 'name') and parent.name in block_elements:
                        container_will_start_line = True
                else:
                    # Check if all previous siblings are whitespace-only
                    prev = element.previous_sibling
                    all_prev_whitespace = True
                    while prev:
                        if hasattr(prev, 'name'):
                            if prev.name == 'br':
                                container_will_start_line = True
                                break
                            if prev.name in block_elements:
                                container_will_start_line = True
                                break
                            # Check if this element has visible content
                            if prev.get_text(strip=True):
                                all_prev_whitespace = False
                                break
                        elif isinstance(prev, str) or (hasattr(prev, 'strip') and callable(getattr(prev, 'strip'))):
                            if str(prev).strip():
                                all_prev_whitespace = False
                                break
                        prev = getattr(prev, 'previous_sibling', None)
                    
                    # If all previous siblings are whitespace, check if parent is block element
                    if all_prev_whitespace and hasattr(parent, 'name') and parent.name in block_elements:
                        container_will_start_line = True
        
        # Don't add leading spaces as spans at the start
        # Instead, we'll move them to be trailing spaces at the end
        # This ensures newlines only happen AFTER space character spans, never before them
        # (Works with dynamic layouts since space spans are always at the end)
        
        # Wrap encrypted text for proper word breaking (like client-side script)
        # CRITICAL: Handle spaces that are actually encrypted characters (like 't' or period)
        # When any character encrypts to space, those spaces need to be preserved and rendered
        # Split by both space_char (what space encrypts to) AND actual space (what other chars encrypt to)
        period_encrypted_to = combined_map.get('.', None)
        has_period_as_space = (period_encrypted_to == ' ')
        # Check if any character encrypts to space (e.g., 't' encrypts to space)
        chars_that_encrypt_to_space = [char for char, encrypted in combined_map.items() if encrypted == ' ']
        has_chars_as_space = len(chars_that_encrypt_to_space) > 0
        
        # Track the last word span so we can append spaces to it
        last_word_span = None
        
        if space_char and space_char in encrypted:
            # Split text by space_char (word boundaries from original spaces)
            parts = encrypted.split(space_char)
            
            for i, part in enumerate(parts):
                if part:  # Non-empty part (word segment)
                    # Check if this part contains spaces (which might be encrypted periods)
                    if has_period_as_space and ' ' in part:
                        # Split by space to separate encrypted periods from the word
                        subparts = part.split(' ')
                        for j, subpart in enumerate(subparts):
                            if subpart:  # Non-empty subpart
                                word_span = soup.new_tag('span')
                                word_span['style'] = 'display: inline-block; white-space: nowrap; word-break: keep-all;'
                                word_span.string = subpart
                                container.append(word_span)
                                last_word_span = word_span
                            
                            # Add space (encrypted period) between subparts (except after last subpart)
                            # Use non-breaking space (U+00A0) to prevent HTML from collapsing it
                            # The font maps non-breaking space to period glyph
                            if j < len(subparts) - 1:
                                period_span = soup.new_tag('span')
                                period_span['style'] = 'display: inline-block; white-space: nowrap;'
                                period_span.string = '\u00A0'  # Non-breaking space - will show as period via font mapping
                                container.append(period_span)
                    elif has_chars_as_space and ' ' in part:
                        # This part contains spaces from characters that encrypt to space (e.g., 't')
                        # Split by space and wrap each part, using non-breaking space for the spaces
                        subparts = part.split(' ')
                        for j, subpart in enumerate(subparts):
                            if subpart:  # Non-empty subpart
                                word_span = soup.new_tag('span')
                                word_span['style'] = 'display: inline-block; white-space: nowrap; word-break: keep-all;'
                                word_span.string = subpart
                                container.append(word_span)
                                last_word_span = word_span
                            
                            # Add space (encrypted character like 't') between subparts (except after last subpart)
                            # Use non-breaking space (U+00A0) to prevent HTML from collapsing it
                            # The font maps non-breaking space to the original character glyph (e.g., 't')
                            if j < len(subparts) - 1:
                                char_span = soup.new_tag('span')
                                char_span['style'] = 'display: inline-block; white-space: nowrap;'
                                char_span.string = '\u00A0'  # Non-breaking space - will show as original char via font mapping
                                container.append(char_span)
                    else:
                        # No spaces in this part, just wrap normally
                        word_span = soup.new_tag('span')
                        word_span['style'] = 'display: inline-block; white-space: nowrap; word-break: keep-all;'
                        word_span.string = part
                        container.append(word_span)
                        last_word_span = word_span
                
                # Add space_char to the end of the word span (not as separate span)
                # This ensures newlines happen after the space, which is inside the word span
                if i < len(parts) - 1 and last_word_span:
                    # Append space_char to the last word span
                    current_text = last_word_span.string or ''
                    last_word_span.string = current_text + space_char
        elif (has_period_as_space or has_chars_as_space) and ' ' in encrypted:
            # No space_char in encrypted, but has spaces (encrypted periods or other chars like 't')
            # Split by space to separate encrypted characters
            parts = encrypted.split(' ')
            for i, part in enumerate(parts):
                if part:  # Non-empty part
                    word_span = soup.new_tag('span')
                    word_span['style'] = 'display: inline-block; white-space: nowrap; word-break: keep-all;'
                    word_span.string = part
                    container.append(word_span)
                    last_word_span = word_span
                
                # Add space (encrypted character) to the end of the word span (not as separate span)
                # Use non-breaking space (U+00A0) to prevent HTML from collapsing it
                # The font maps non-breaking space to the original character glyph (e.g., 't' or period)
                if i < len(parts) - 1 and last_word_span:
                    current_text = last_word_span.string or ''
                    last_word_span.string = current_text + '\u00A0'  # Non-breaking space - will show as original char via font mapping
        else:
            # No spaces, just wrap the whole encrypted text
            word_span = soup.new_tag('span')
            word_span['style'] = 'display: inline-block; white-space: nowrap; word-break: keep-all;'
            word_span.string = encrypted
            container.append(word_span)
            last_word_span = word_span
        
        # Store container for this element so we can find it later
        element_to_container[element] = container
        
        # Handle leading spaces: if previous sibling is an inline element, append to its last word span
        # Otherwise, append to current text node's last word span
        leading_spaces_to_append = leading_spaces
        if leading_spaces and space_char:
            # Check if previous sibling is an inline element
            prev_sibling = element.previous_sibling
            inline_elements = {'a', 'span', 'strong', 'em', 'b', 'i', 'u', 'code', 'mark', 'small', 'sub', 'sup', 'time', 'abbr', 'cite', 'q', 'dfn', 'var', 'samp', 'kbd'}
            
            # Skip whitespace-only text nodes
            while prev_sibling:
                if hasattr(prev_sibling, 'name'):
                    # It's an element
                    if prev_sibling.name in inline_elements:
                        # Previous sibling is an inline element - append leading spaces to its last word span
                        prev_last_word_span = find_last_word_span_in_element(prev_sibling)
                        if prev_last_word_span:
                            leading_space_count = len(leading_spaces)
                            current_text = prev_last_word_span.string or ''
                            prev_last_word_span.string = current_text + (space_char * leading_space_count)
                            leading_spaces_to_append = ''  # Don't add to current text node
                            break
                    # If it's a block element or has visible content, stop looking
                    block_elements = {'div', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 
                                    'blockquote', 'pre', 'section', 'article', 'header', 'footer', 
                                    'nav', 'aside', 'table', 'tr', 'td', 'th', 'hr', 'figure', 'figcaption', 'body'}
                    if prev_sibling.name in block_elements or prev_sibling.get_text(strip=True):
                        break
                elif isinstance(prev_sibling, str) or (hasattr(prev_sibling, 'strip') and callable(getattr(prev_sibling, 'strip'))):
                    # It's a text node - if it has visible content, stop looking
                    if str(prev_sibling).strip():
                        break
                prev_sibling = getattr(prev_sibling, 'previous_sibling', None)
        
        # Add trailing spaces to the last word span (not as separate span)
        # Also include leading spaces if they weren't appended to previous element
        # This ensures spaces are inside the word span, so newlines happen after the space
        # (Works with dynamic layouts since spaces are part of the word span)
        total_spaces = trailing_spaces + leading_spaces_to_append
        if total_spaces and space_char:
            trailing_space_count = len(total_spaces)
            if last_word_span:
                # Append to existing word span
                current_text = last_word_span.string or ''
                last_word_span.string = current_text + (space_char * trailing_space_count)
            else:
                # No word span exists (shouldn't happen, but handle edge case)
                # Create a span just for the spaces to ensure they're converted to space_char
                space_span = soup.new_tag('span')
                space_span['style'] = 'display: inline-block; white-space: nowrap;'
                space_span.string = space_char * trailing_space_count
                container.append(space_span)
        
        replacements.append((element, container))
    
    # Process whitespace-only text nodes (spaces between elements like links)
    # These need to be converted to space_char spans to render correctly
    for element, original_text in whitespace_only_nodes:
        if space_char:
            # Count the number of spaces in the whitespace-only node
            space_count = len(original_text)
            # Create a span with space_char repeated
            space_span = soup.new_tag('span')
            space_span['style'] = 'display: inline-block; white-space: nowrap;'
            space_span.string = space_char * space_count
            element.replace_with(space_span)
        else:
            # If space_char is None, remove the whitespace node (shouldn't happen)
            element.extract()
    
    # Apply all replacements first
    for element, replacement in replacements:
        element.replace_with(replacement)
    
    # Post-process: Remove leading space spans from containers that are first children of block elements
    # This catches cases where the container itself starts on a new line
    # Note: space_char is available from the loop above
    block_elements = {'div', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 
                     'blockquote', 'pre', 'section', 'article', 'header', 'footer', 
                     'nav', 'aside', 'table', 'tr', 'td', 'th', 'hr', 'figure', 'figcaption', 'body',
                     'main', 'form', 'fieldset', 'dl', 'dt', 'dd'}
    
    for container in soup.find_all('span', style=lambda x: x and 'white-space: normal' in x):
        parent = container.parent
        if not parent:
            continue
        
        # Ensure container has height: auto !important
        container_style = container.get('style', '')
        if 'height: auto' not in container_style:
            # Remove any existing height declarations
            container_style = re.sub(r'height\s*:\s*[^;!]+(?:!important)?\s*;?', '', container_style)
            container['style'] = container_style.rstrip('; ') + ('; ' if container_style.rstrip() else '') + 'height: auto !important;'
        
        # Ensure parent element and all ancestors have height: auto !important
        current = parent
        while current and hasattr(current, 'name'):
            if current.name in block_elements or current.name in {'div', 'section', 'article', 'main', 'aside'}:
                current_style = current.get('style', '')
                if 'height: auto' not in current_style:
                    # Remove any existing height declarations
                    current_style = re.sub(r'height\s*:\s*[^;!]+(?:!important)?\s*;?', '', current_style)
                    current['style'] = current_style.rstrip('; ') + ('; ' if current_style.rstrip() else '') + 'height: auto !important;'
            current = getattr(current, 'parent', None)
            
        # Check if container is at start of a new line
        # This includes: first child of block element, after <br>, after block elements, or after whitespace-only content
        is_at_line_start = False
        
        # Check if container is first child of parent
        if parent.contents and parent.contents[0] == container:
            # If parent is a block element, we're at line start
            if hasattr(parent, 'name') and parent.name in block_elements:
                is_at_line_start = True
        else:
            # Check previous siblings
            prev = container.previous_sibling
            while prev:
                if hasattr(prev, 'name'):
                    # If previous sibling is <br> or a block element, we're at line start
                    if prev.name == 'br':
                        is_at_line_start = True
                        break
                    if prev.name in block_elements:
                        is_at_line_start = True
                        break
                    # If previous sibling has visible content, we're not at line start
                    if prev.get_text(strip=True):
                        break
                elif isinstance(prev, str) or (hasattr(prev, 'strip') and callable(getattr(prev, 'strip'))):
                    # If previous sibling is non-whitespace text, we're not at line start
                    if str(prev).strip():
                        break
                prev = getattr(prev, 'previous_sibling', None)
            
            # If all previous siblings were whitespace and parent is block element, we're at line start
            if not is_at_line_start and hasattr(parent, 'name') and parent.name in block_elements:
                # Re-check if all previous were whitespace
                prev = container.previous_sibling
                all_prev_whitespace = True
                while prev:
                    if hasattr(prev, 'name'):
                        if prev.name in block_elements or prev.name == 'br':
                            all_prev_whitespace = False
                            break
                        if prev.get_text(strip=True):
                            all_prev_whitespace = False
                            break
                    elif isinstance(prev, str) or (hasattr(prev, 'strip') and callable(getattr(prev, 'strip'))):
                        if str(prev).strip():
                            all_prev_whitespace = False
                            break
                    prev = getattr(prev, 'previous_sibling', None)
                if all_prev_whitespace:
                    is_at_line_start = True
        
        # If container is at line start, remove leading 'O' (space_char) spans
        if is_at_line_start and container.contents and space_char:
            # Keep checking and removing 'O' spans from the start until we hit a non-'O' span
            while container.contents:
                first_child = container.contents[0]
                if hasattr(first_child, 'name') and first_child.name == 'span':
                    first_child_text = first_child.string if hasattr(first_child, 'string') else str(first_child)
                    if first_child_text:
                        text_stripped = first_child_text.strip()
                        # Check if it's ONLY space_char (the character that space encrypts to, e.g., 'O')
                        # Remove all space_char characters and check if anything remains
                        text_without_space_char = text_stripped.replace(space_char, '')
                        if text_without_space_char == '' and len(text_stripped) > 0:
                            # First child is a leading space span - remove it
                            first_child.extract()
                            continue  # Check next child
                        # Also check if it's exactly a single space_char
                        elif text_stripped == space_char:
                            # Single space_char at start of line - remove it
                            first_child.extract()
                            continue  # Check next child
                # If we get here, first child is not an 'O' span, so stop
                break
    
    # Encrypt fonts from HTML (extract, download, and generate encrypted versions)
    font_mapping = encrypt_fonts_from_html(
        soup, secret_key, nonce, upper_map, lower_map, space_map, base_url=base_url
    )
    
    if DEBUG_MODE:
        print(f"🔍 Font mapping after encryption: {len(font_mapping)} fonts found")
        for key, value in font_mapping.items():
            print(f"   {key} -> {value['url']}")
    
    # Replace font URLs in @font-face rules
    for style_tag in soup.find_all('style'):
        if not style_tag.string:
            continue
        
        css_content = style_tag.string
        modified_css = css_content
        
        # Find all @font-face rules and replace URLs
        fontface_pattern = r'@font-face\s*\{([^}]+)\}'
        
        def replace_font_url(match):
            font_rule = match.group(1)
            
            # Extract font properties
            family_match = re.search(r'font-family\s*:\s*([^;]+)', font_rule, re.IGNORECASE)
            weight_match = re.search(r'font-weight\s*:\s*([^;]+)', font_rule, re.IGNORECASE)
            style_match = re.search(r'font-style\s*:\s*([^;]+)', font_rule, re.IGNORECASE)
            src_match = re.search(r'src\s*:\s*([^;]+)', font_rule, re.IGNORECASE)
            
            if not family_match or not src_match:
                return match.group(0)  # Return unchanged
            
            family = family_match.group(1).strip().strip("'\"")
            weight = weight_match.group(1).strip() if weight_match else 'normal'
            style = style_match.group(1).strip() if style_match else 'normal'
            src_value = src_match.group(1).strip()
            
            # Extract URLs from src
            url_pattern = r'url\s*\(\s*([^)]+)\s*\)'
            url_matches = list(re.finditer(url_pattern, src_value, re.IGNORECASE))
            
            if not url_matches:
                return match.group(0)  # Return unchanged
            
            # Replace each URL
            new_src_parts = []
            for url_match in url_matches:
                original_url = url_match.group(1).strip().strip("'\"")
                
                # Resolve relative URLs
                resolved_url = original_url
                if base_url and not original_url.startswith(('http://', 'https://', '//', 'data:')):
                    from urllib.parse import urljoin
                    resolved_url = urljoin(base_url, original_url)
                
                # Find matching encrypted font
                # Try exact match first
                encrypted_font = None
                for (map_family, map_weight, map_style, map_url), font_data in font_mapping.items():
                    if (map_family == family and 
                        map_weight == weight and 
                        map_style == style and 
                        map_url == resolved_url):
                        encrypted_font = font_data
                        break
                
                # If no exact match, try matching by URL only (in case family/weight/style don't match exactly)
                if not encrypted_font:
                    for (map_family, map_weight, map_style, map_url), font_data in font_mapping.items():
                        if map_url == resolved_url:
                            encrypted_font = font_data
                            if DEBUG_MODE:
                                print(f"⚠️  Matched by URL only (family/weight/style may differ): {resolved_url}")
                            break
                
                if encrypted_font:
                    # Replace with encrypted font URL
                    new_src_parts.append(f"url('{encrypted_font['url']}')")
                    if DEBUG_MODE:
                        print(f"✅ Replaced @font-face URL: {original_url} -> {encrypted_font['url']}")
                else:
                    # Keep original URL if no match found
                    if DEBUG_MODE:
                        print(f"⚠️  No encrypted font found for: family={family}, weight={weight}, style={style}, url={resolved_url}")
                        print(f"   Available fonts in mapping:")
                        for key, value in font_mapping.items():
                            print(f"     {key} -> {value['url']}")
                    new_src_parts.append(url_match.group(0))
            
            # Reconstruct @font-face rule with new URLs
            new_src = ', '.join(new_src_parts)
            new_font_rule = font_rule.replace(src_match.group(0), f"src: {new_src}")
            return f"@font-face {{{new_font_rule}}}"
        
        modified_css = re.sub(fontface_pattern, replace_font_url, modified_css, flags=re.IGNORECASE | re.DOTALL)
        
        if modified_css != css_content:
            style_tag.string = modified_css
            if DEBUG_MODE:
                print(f"✅ Modified CSS in style tag (before: {len(css_content)} chars, after: {len(modified_css)} chars)")
        elif DEBUG_MODE:
            print(f"⚠️  CSS was not modified - no font URLs replaced in this style tag")
    
    # Replace font URLs in <link> tags
    for link_tag in soup.find_all('link'):
        href = link_tag.get('href', '')
        rel = link_tag.get('rel', [])
        
        # Check if it's a font file
        is_font_file = any(href.lower().endswith(ext) for ext in ['.woff2', '.woff', '.ttf', '.otf', '.eot'])
        
        if is_font_file:
            # Resolve relative URLs
            resolved_href = href
            if base_url and not href.startswith(('http://', 'https://', '//', 'data:')):
                from urllib.parse import urljoin
                resolved_href = urljoin(base_url, href)
            
            # Find matching encrypted font
            family = link_tag.get('data-font-family', 'Unknown')
            weight = link_tag.get('data-font-weight', 'normal')
            style = link_tag.get('data-font-style', 'normal')
            
            encrypted_font = None
            for (map_family, map_weight, map_style, map_url), font_data in font_mapping.items():
                if map_url == resolved_href:
                    encrypted_font = font_data
                    break
            
            if encrypted_font:
                # Replace href with encrypted font URL
                link_tag['href'] = encrypted_font['url']
                if DEBUG_MODE:
                    print(f"✅ Replaced link font URL: {href} -> {encrypted_font['url']}")
        
        # Check if it's a CSS file from g1.nyt.com/fonts/css (or similar font CSS files)
        elif link_tag.get('data-encrypt-css') == 'true':
            css_url = link_tag.get('data-css-url', href)
            if not css_url:
                continue
            
            # Download and parse the CSS file
            css_content = download_css(css_url, base_url=base_url)
            if not css_content:
                if DEBUG_MODE:
                    print(f"⚠️  Failed to download CSS from {css_url}, skipping")
                continue
            
            # Parse @font-face rules from the CSS and extract fonts
            fontface_pattern = r'@font-face\s*\{([^}]+)\}'
            matches = list(re.finditer(fontface_pattern, css_content, re.IGNORECASE | re.DOTALL))
            
            if not matches:
                if DEBUG_MODE:
                    print(f"⚠️  No @font-face rules found in CSS from {css_url}")
                continue
            
            # Replace font URLs in the CSS
            modified_css = css_content
            
            def replace_font_url_in_css(match):
                font_rule = match.group(1)
                
                # Extract font properties
                family_match = re.search(r'font-family\s*:\s*([^;]+)', font_rule, re.IGNORECASE)
                weight_match = re.search(r'font-weight\s*:\s*([^;]+)', font_rule, re.IGNORECASE)
                style_match = re.search(r'font-style\s*:\s*([^;]+)', font_rule, re.IGNORECASE)
                src_match = re.search(r'src\s*:\s*([^;]+)', font_rule, re.IGNORECASE)
                
                if not family_match or not src_match:
                    return match.group(0)  # Return unchanged
                
                family = family_match.group(1).strip().strip("'\"")
                weight = weight_match.group(1).strip() if weight_match else 'normal'
                style = style_match.group(1).strip() if style_match else 'normal'
                src_value = src_match.group(1).strip()
                
                # Extract URLs from src
                url_pattern = r'url\s*\(\s*([^)]+)\s*\)'
                url_matches = list(re.finditer(url_pattern, src_value, re.IGNORECASE))
                
                if not url_matches:
                    return match.group(0)  # Return unchanged
                
                # Replace each URL
                new_src_parts = []
                for url_match in url_matches:
                    original_url = url_match.group(1).strip().strip("'\"")
                    
                    # Resolve relative URLs (relative to CSS file location)
                    from urllib.parse import urljoin, urlparse
                    css_base = '/'.join(css_url.split('/')[:-1]) + '/' if '/' in css_url else css_url
                    resolved_url = urljoin(css_base, original_url)
                    
                    # Find matching encrypted font
                    encrypted_font = None
                    if DEBUG_MODE:
                        print(f"🔍 Looking for match: family={family}, weight={weight}, style={style}, url={resolved_url}")
                        print(f"   Font mapping has {len(font_mapping)} entries")
                    
                    for (map_family, map_weight, map_style, map_url), font_data in font_mapping.items():
                        if (map_family == family and 
                            map_weight == weight and 
                            map_style == style and 
                            map_url == resolved_url):
                            encrypted_font = font_data
                            if DEBUG_MODE:
                                print(f"✅ Exact match found: {map_url}")
                            break
                    
                    # If no exact match, try matching by URL only
                    if not encrypted_font:
                        for (map_family, map_weight, map_style, map_url), font_data in font_mapping.items():
                            if map_url == resolved_url:
                                encrypted_font = font_data
                                if DEBUG_MODE:
                                    print(f"⚠️  Matched CSS font by URL only: {resolved_url}")
                                break
                    
                    # If still no match, try matching by normalized URL (handle trailing slashes, etc.)
                    if not encrypted_font:
                        normalized_resolved = resolved_url.rstrip('/')
                        for (map_family, map_weight, map_style, map_url), font_data in font_mapping.items():
                            normalized_map = map_url.rstrip('/')
                            if normalized_map == normalized_resolved:
                                encrypted_font = font_data
                                if DEBUG_MODE:
                                    print(f"⚠️  Matched CSS font by normalized URL: {resolved_url} == {map_url}")
                                break
                    
                    if encrypted_font:
                        # Replace with encrypted font URL
                        new_src_parts.append(f"url('{encrypted_font['url']}')")
                        if DEBUG_MODE:
                            print(f"✅ Replaced CSS font URL: {original_url} -> {encrypted_font['url']}")
                    else:
                        # Keep original URL if no match found
                        if DEBUG_MODE:
                            print(f"⚠️  No encrypted font found for CSS font: family={family}, weight={weight}, style={style}, url={resolved_url}")
                            if font_mapping:
                                print(f"   Available mappings (first 3):")
                                for i, ((mf, mw, ms, mu), fd) in enumerate(list(font_mapping.items())[:3]):
                                    print(f"     {i+1}. family={mf}, weight={mw}, style={ms}, url={mu}")
                        new_src_parts.append(url_match.group(0))
                
                # Reconstruct @font-face rule with new URLs
                new_src = ', '.join(new_src_parts)
                new_font_rule = font_rule.replace(src_match.group(0), f"src: {new_src}")
                return f"@font-face {{{new_font_rule}}}"
            
            # Replace all @font-face rules in the CSS
            modified_css = re.sub(fontface_pattern, replace_font_url_in_css, modified_css, flags=re.IGNORECASE | re.DOTALL)
            
            if modified_css != css_content:
                # Replace the link tag with a style tag containing the modified CSS
                style_tag = soup.new_tag('style')
                style_tag['type'] = 'text/css'
                style_tag.string = modified_css
                link_tag.replace_with(style_tag)
                if DEBUG_MODE:
                    print(f"✅ Replaced CSS link with inline style: {css_url} (modified {len(matches)} @font-face rules)")
            else:
                if DEBUG_MODE:
                    print(f"⚠️  CSS was not modified: {css_url}")
    
    # Get primary font URL for backward compatibility (use first font if available)
    primary_font_url = None
    if font_mapping:
        first_font = list(font_mapping.values())[0]
        primary_font_url = first_font['url']
    else:
        # Fallback: generate a default font if no fonts found in HTML
        font_filename, font_url = generate_font_artifacts(
            secret_key, nonce, upper_map, lower_map, space_map, base_url=base_url
        )
        primary_font_url = font_url
    
    # Get the character that space maps to (already retrieved above)
    # space_char is already available from the loop above
    
    return soup, text_mapping, nonce, primary_font_url, space_char, font_mapping

def encrypt_metadata(soup, text_mapping: dict, secret_key: int, nonce: int):
    """
    Search for matching text in metadata and encrypt those instances.
    
    Args:
        soup: BeautifulSoup object
        text_mapping: dict mapping original_text -> encrypted_text
        secret_key: Secret key used for encryption
        nonce: Nonce used for encryption
    
    Returns:
        dict: Statistics about what was encrypted
    """
    stats = {
        'title_encrypted': False,
        'meta_tags_encrypted': 0,
        'alt_attributes_encrypted': 0,
        'aria_labels_encrypted': 0,
        'title_attributes_encrypted': 0,
        'json_ld_encrypted': 0
    }
    
    # Get mappings for character-level encryption if needed
    upper_map, lower_map, space_map = get_dynamic_mappings(secret_key, nonce)
    combined_map = {**upper_map, **lower_map, **space_map}
    
    # Helper function to encrypt text using mapping
    def encrypt_text_with_mapping(text: str) -> str:
        """Encrypt text, trying text_mapping first, then character-level mapping"""
        # Try exact match in text_mapping first
        if text in text_mapping:
            return text_mapping[text]
        
        # Try substring matches (for partial text in metadata)
        for original, encrypted in text_mapping.items():
            if original in text:
                # Replace the substring
                text = text.replace(original, encrypted)
                return text
        
        # If no match found, encrypt character by character
        expanded = expand_ligatures(text)
        return ''.join(combined_map.get(char, char) for char in expanded)
    
    # Skip encrypting <title> tag - keep it unencrypted for browser tab display
    
    # Encrypt meta tags with text content
    meta_tags_to_encrypt = [
        ('name', 'description'),
        ('property', 'og:title'),
        ('property', 'og:description'),
        ('property', 'twitter:title'),
        ('property', 'twitter:description'),
        ('property', 'twitter:image:alt'),
        ('property', 'og:image:alt'),
    ]
    
    for attr_name, attr_value in meta_tags_to_encrypt:
        meta_tags = soup.find_all('meta', {attr_name: attr_value})
        for meta_tag in meta_tags:
            content = meta_tag.get('content', '')
            if content:
                encrypted_content = encrypt_text_with_mapping(content)
                meta_tag['content'] = encrypted_content
                stats['meta_tags_encrypted'] += 1
    
    # Encrypt alt attributes on images
    images = soup.find_all('img')
    for img in images:
        alt_text = img.get('alt', '')
        if alt_text:
            encrypted_alt = encrypt_text_with_mapping(alt_text)
            img['alt'] = encrypted_alt
            stats['alt_attributes_encrypted'] += 1
    
    # Encrypt aria-label attributes
    elements_with_aria = soup.find_all(attrs={'aria-label': True})
    for element in elements_with_aria:
        aria_label = element.get('aria-label', '')
        if aria_label:
            encrypted_label = encrypt_text_with_mapping(aria_label)
            element['aria-label'] = encrypted_label
            stats['aria_labels_encrypted'] += 1
    
    # Encrypt title attributes
    elements_with_title = soup.find_all(attrs={'title': True})
    for element in elements_with_title:
        title_attr = element.get('title', '')
        if title_attr:
            encrypted_title_attr = encrypt_text_with_mapping(title_attr)
            element['title'] = encrypted_title_attr
            stats['title_attributes_encrypted'] += 1
    
    # Encrypt JSON-LD structured data
    json_ld_scripts = soup.find_all('script', type='application/ld+json')
    for script in json_ld_scripts:
        try:
            json_data = json.loads(script.string)
            
            # Recursively encrypt text fields in JSON
            def encrypt_json_value(obj):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        # Encrypt specific fields that contain text
                        if key in ['description', 'headline', 'caption', 'name', 'alternativeHeadline', 'creditText']:
                            if isinstance(value, str) and value:
                                obj[key] = encrypt_text_with_mapping(value)
                        else:
                            encrypt_json_value(value)
                elif isinstance(obj, list):
                    for item in obj:
                        encrypt_json_value(item)
            
            encrypt_json_value(json_data)
            script.string = json.dumps(json_data, ensure_ascii=False)
            stats['json_ld_encrypted'] += 1
        except (json.JSONDecodeError, AttributeError):
            # Skip invalid JSON
            continue
    
    return stats

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
        
        # Use default secret key if not provided
        if secret_key is None:
            secret_key = DEFAULT_SECRET_KEY
        else:
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
                'font_filename': encryption['font_filename'],  # Include filename for reference
                'space_char': encryption['space_char']  # Character that space encrypts to (for word-breaking)
            })
    
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback.print_exc()
        return jsonify({'error': error_msg, 'type': type(e).__name__}), 500

@app.route('/api/encrypt/query', methods=['POST'])
def encrypt_query():
    """
    Encrypt a search query using the same nonce as the page.
    This endpoint is used by the search functionality to encrypt user queries.
    
    Request body:
        {
            "text": "search query",
            "secret_key": 29202393,
            "nonce": 462508
        }
    
    Response:
        {
            "encrypted": "encrypted query"
        }
    """
    try:
        data = request.json
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        query_text = data.get('text', '')
        secret_key = data.get('secret_key')
        nonce = data.get('nonce')
        
        if not query_text:
            return jsonify({'error': 'No text provided'}), 400
        
        if secret_key is None:
            secret_key = DEFAULT_SECRET_KEY
        else:
            try:
                secret_key = int(secret_key)
            except (ValueError, TypeError):
                return jsonify({'error': 'secret_key must be an integer'}), 400
        
        if nonce is None:
            return jsonify({'error': 'nonce is required'}), 400
        else:
            try:
                nonce = int(nonce)
            except (ValueError, TypeError):
                return jsonify({'error': 'nonce must be an integer'}), 400
        
        # Expand ligatures and encrypt using the provided nonce
        expanded = expand_ligatures(query_text)
        encrypted = remap_text_ultra_fast(expanded, secret_key, nonce)
        
        return jsonify({
            'encrypted': encrypted
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
        
        # Use default secret key if not provided
        if secret_key is None:
            secret_key = DEFAULT_SECRET_KEY
        else:
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
        
        # Use default secret key if not provided
        if secret_key is None:
            secret_key = DEFAULT_SECRET_KEY
        else:
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
        # Combine all mappings (space is in lower_map, space_map only has special chars)
        combined_map = {**upper_map, **lower_map, **space_map}
        
        # Encrypt all texts using the same mapping
        encrypted_texts = []
        for text in valid_texts:
            expanded_text = expand_ligatures(text)
            # All chars get mapped (spaces are in lower_map)
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
        
        # Get the character that space maps to (for CSS word-breaking)
        space_char = lower_map.get(' ', None)
        
        return jsonify({
            'encrypted_texts': result_texts,
            'font_url': font_url,
            'font_filename': font_filename,
            'nonce': nonce,
            'space_char': space_char,  # Character that space encrypts to (for word-breaking)
            # Include mappings for client-side decryption (for copy-paste functionality)
            'upper_map': upper_map,
            'lower_map': lower_map,
            'space_map': space_map
        })
    
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback.print_exc()
        return jsonify({'error': error_msg, 'type': type(e).__name__}), 500

@app.route('/api/encrypt/html', methods=['POST'])
def encrypt_html():
    """
    Encrypt entire HTML document - extracts and encrypts all text content and metadata.
    Returns complete encrypted HTML ready for deployment.
    
    Request body:
        {
            "html": "<html>...</html>",  # Full HTML document
            "secret_key": 29202393  # Optional
        }
    
    Response:
        {
            "encrypted_html": "<html>...</html>",  # Complete encrypted HTML with font CSS
            "font_url": "https://your-cdn.com/fonts/encrypted.woff2",
            "nonce": 462508,
            "stats": {
                "title_encrypted": true,
                "meta_tags_encrypted": 5,
                "alt_attributes_encrypted": 3,
                ...
            }
        }
    """
    try:
        if not BS4_AVAILABLE:
            return jsonify({'error': 'beautifulsoup4 is required for HTML encryption. Install with: pip install beautifulsoup4'}), 500
        
        data = request.json
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        html_content = data.get('html', '')
        secret_key = data.get('secret_key')
        
        if not html_content:
            return jsonify({'error': 'No HTML content provided'}), 400
        
        # Use default secret key if not provided
        if secret_key is None:
            secret_key = DEFAULT_SECRET_KEY
        else:
            # Convert secret_key to int if it's a string
            try:
                secret_key = int(secret_key)
            except (ValueError, TypeError):
                return jsonify({'error': 'secret_key must be an integer'}), 400
        
        # Get base URL for font generation
        # Always use API server URL (port 5001) for proxy fonts to avoid CORS
        # This ensures fonts are proxied through the API server, not the serving server
        base_url = os.environ.get('BASE_URL', request.url_root.rstrip('/'))
        if not base_url or 'localhost:8001' in base_url or '127.0.0.1:8001' in base_url:
            # If base_url points to the serving server, use API server instead
            api_port = os.environ.get('PORT', '5001')
            base_url = f"http://localhost:{api_port}"
        
        # Encrypt HTML content
        soup, text_mapping, nonce, font_url, space_char, font_mapping = encrypt_html_content(
            html_content, secret_key, base_url=base_url
        )
        
        if nonce is None:
            # No text to encrypt
            return jsonify({
                'encrypted_html': html_content,
                'font_url': None,
                'nonce': None,
                'stats': {}
            })
        
        # Encrypt metadata
        stats = encrypt_metadata(soup, text_mapping, secret_key, nonce)
        
        # Inject font CSS into <head>
        # Only inject global font override if no fonts were found in HTML
        head = soup.find('head')
        if head and font_url:
            if not font_mapping:
                # No fonts found in HTML, use fallback font with global override
                style_tag = soup.new_tag('style')
                style_tag.string = f"""
@font-face {{
    font-family: 'EncryptedFont';
    src: url('{font_url}') format('woff2');
    font-display: swap;
}}

body {{
    font-family: 'EncryptedFont', sans-serif;
}}
"""
                # Insert at the beginning of head
                head.insert(0, style_tag)
            else:
                # Fonts were found in HTML - they're already replaced in @font-face rules
                # Don't inject global override - preserve original font-family names
                pass
        
        # Convert back to HTML string
        encrypted_html = str(soup)
        
        return jsonify({
            'encrypted_html': encrypted_html,
            'font_url': font_url,
            'nonce': nonce,
            'space_char': space_char,
            'stats': stats
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
        
        # Use default secret key if not provided
        if secret_key is None:
            secret_key = DEFAULT_SECRET_KEY
        else:
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
            # Combine all mappings (space is in lower_map, space_map only has special chars)
            combined_map = {**upper_map, **lower_map, **space_map}
            # All chars get mapped (spaces are in lower_map)
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
    """Root endpoint - serve API info page"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Article Encryption API</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }}
            h1 {{ color: #333; }}
            .endpoint {{ background: #f5f5f5; padding: 10px; margin: 10px 0; border-radius: 5px; }}
            .method {{ color: #0066cc; font-weight: bold; }}
            code {{ background: #eee; padding: 2px 5px; border-radius: 3px; }}
        </style>
    </head>
    <body>
        <h1>Article Encryption API</h1>
        <p>Server is running and healthy!</p>
        <h2>Available Endpoints:</h2>
        <div class="endpoint"><span class="method">POST</span> <code>/api/encrypt/html</code> - Encrypt entire HTML document</div>
        <div class="endpoint"><span class="method">POST</span> <code>/api/encrypt</code> - Encrypt text</div>
        <div class="endpoint"><span class="method">POST</span> <code>/api/encrypt/page</code> - Encrypt page text nodes</div>
        <div class="endpoint"><span class="method">POST</span> <code>/api/encrypt/batch</code> - Batch encrypt multiple texts</div>
        <div class="endpoint"><span class="method">POST</span> <code>/api/decrypt</code> - Decrypt text</div>
        <div class="endpoint"><span class="method">GET</span> <code>/api/health</code> - Health check</div>
        <div class="endpoint"><span class="method">GET</span> <code>/api</code> - API information</div>
        <div class="endpoint"><span class="method">GET</span> <code>/nyt</code> - View NYT article</div>
        <div class="endpoint"><span class="method">GET</span> <code>/nyt-encrypt</code> - View encrypted NYT article (ready for deployment)</div>
        <div class="endpoint"><span class="method">GET</span> <code>/test-spacing</code> - Test spacing page</div>
        <p><a href="/api">View full API documentation</a></p>
    </body>
    </html>
    """

@app.route('/test-localhost', methods=['GET'])
def test_localhost():
    """Test page for localhost - regular website example"""
    return send_from_directory(os.path.dirname(__file__), 'test_localhost.html')

@app.route('/test-spacing', methods=['GET'])
def test_spacing():
    """Test page for spacing consistency"""
    return send_from_directory(os.path.dirname(__file__), 'test_spacing.html')

@app.route('/nyt', methods=['GET'])
def nyt():
    """NYT article page with encryption"""
    return send_from_directory(os.path.dirname(__file__), 'nyt.html')

@app.route('/nyt-encrypt', methods=['GET', 'POST'])
def nyt_encrypt():
    """Serve encrypted NYT article page - ready for deployment
    
    Accepts HTML content as:
    - GET: ?html=<url-encoded-html> (query parameter)
    - POST: {"html": "<html>...</html>"} (JSON body)
    
    If no HTML is provided, falls back to reading nyt.html file.
    """
    try:
        if not BS4_AVAILABLE:
            return jsonify({'error': 'beautifulsoup4 is required for HTML encryption. Install with: pip install beautifulsoup4'}), 500
        
        # Get HTML content and secret key from request
        html_content = None
        secret_key = None
        
        if request.method == 'POST':
            # Try to get from JSON body
            data = request.json
            if data:
                html_content = data.get('html', '')
                # Get secret_key from JSON body if provided
                if 'secret_key' in data:
                    secret_key = data.get('secret_key')
                    if isinstance(secret_key, str):
                        try:
                            secret_key = int(secret_key)
                        except ValueError:
                            return jsonify({'error': 'secret_key must be an integer'}), 400
                    elif not isinstance(secret_key, int):
                        return jsonify({'error': 'secret_key must be an integer'}), 400
        else:
            # GET request - try query parameter
            html_content = request.args.get('html', '')
        
        # If no HTML provided, fall back to reading nyt.html
        if not html_content:
            return jsonify({'error': 'No HTML content provided and nyt.html file not found'}), 404
        
        # Get secret key (from JSON body, query param, or default)
        if secret_key is None:
            secret_key = request.args.get('secret_key', type=int)
        if secret_key is None:
            secret_key = DEFAULT_SECRET_KEY
        
        # Get base URL for font generation
        # Always use API server URL (port 5001) for proxy fonts to avoid CORS
        # This ensures fonts are proxied through the API server, not the serving server
        base_url = os.environ.get('BASE_URL', request.url_root.rstrip('/'))
        if not base_url or 'localhost:8001' in base_url or '127.0.0.1:8001' in base_url:
            # If base_url points to the serving server, use API server instead
            api_port = os.environ.get('PORT', '5001')
            base_url = f"http://localhost:{api_port}"
        
        # Encrypt HTML content
        soup, text_mapping, nonce, font_url, space_char, font_mapping = encrypt_html_content(
            html_content, secret_key, base_url=base_url
        )
        
        if nonce is None:
            # No text to encrypt, return original
            return html_content, 200, {'Content-Type': 'text/html; charset=utf-8'}
        
        # Encrypt metadata
        stats = encrypt_metadata(soup, text_mapping, secret_key, nonce)
        
        # Remove client-side encryption script to prevent double encryption
        # Since we're doing server-side encryption, we don't need the client script
        for script in soup.find_all('script', src=lambda x: x and 'encrypt-page.js' in x):
            script.decompose()  # Remove the script tag completely
        
        # Convert relative asset paths to absolute URLs so CSS/JS load correctly
        # when served from a different domain (e.g., localhost:8001)
        # This preserves layout and formatting
        nyt_base_url = 'https://www.nytimes.com'
        
        # Convert relative CSS/JS links to absolute URLs
        for link in soup.find_all('link', href=True):
            href = link.get('href', '')
            if href.startswith('/') and not href.startswith('//'):
                link['href'] = nyt_base_url + href
        
        # Convert relative script src to absolute URLs
        for script in soup.find_all('script', src=True):
            src = script.get('src', '')
            if src.startswith('/') and not src.startswith('//'):
                script['src'] = nyt_base_url + src
        
        # Inject font CSS and preload link into <head>
        # Only inject global font override if no fonts were found in HTML
        head = soup.find('head')
        if head and font_url:
            # Check if fonts were found in HTML (font_mapping will have entries)
            if not font_mapping:
                # No fonts found in HTML, use fallback font with global override
                # Add preload link for faster font loading
                preload_link = soup.new_tag('link')
                preload_link['rel'] = 'preload'
                preload_link['as'] = 'font'
                preload_link['type'] = 'font/woff2'
                preload_link['crossorigin'] = 'anonymous'
                preload_link['href'] = font_url
                head.insert(0, preload_link)
                
                # Create style tag with font CSS
                # Use !important to override any existing font-family rules
                style_tag = soup.new_tag('style')
                style_tag.string = f"""
@font-face {{
    font-family: 'EncryptedFont';
    src: url('{font_url}') format('woff2');
    font-display: swap;
    font-weight: normal;
    font-style: normal;
}}

html, body, body *, * {{
    font-family: 'EncryptedFont', sans-serif !important;
    text-rendering: optimizeLegibility !important;
    height: auto !important;
}}

/* Override height for containers and companion columns */
span[style*="white-space: normal"],
span[style*="white-space: normal"] *,
[class*="companion"],
[class*="companion"] *,
[class*="container"],
[class*="container"] *,
:has(span[style*="white-space: normal"]) {{
    height: auto !important;
}}

/* Exclude search overlay from encrypted font */
#encrypted-search-overlay,
#encrypted-search-overlay * {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
}}
"""
                # Insert style tag after preload
                head.insert(1, style_tag)
            else:
                # Fonts were found in HTML - they're already replaced in @font-face rules
                # Add preload links for all encrypted fonts to ensure they load quickly
                for font_data in font_mapping.values():
                    encrypted_font_url = font_data['url']
                    if encrypted_font_url:
                        preload_link = soup.new_tag('link')
                        preload_link['rel'] = 'preload'
                        preload_link['as'] = 'font'
                        preload_link['type'] = 'font/woff2'
                        preload_link['crossorigin'] = 'anonymous'
                        preload_link['href'] = encrypted_font_url
                        head.insert(0, preload_link)
                        if DEBUG_MODE:
                            print(f"📦 Added preload link for encrypted font: {encrypted_font_url}")
                
                # Don't inject global override - preserve original font-family names
                # Just add a style for text rendering optimization
                style_tag = soup.new_tag('style')
                style_tag.string = """
/* Optimize text rendering for encrypted fonts */
body, body * {
    text-rendering: optimizeLegibility !important;
}

/* Override height for containers and companion columns */
span[style*="white-space: normal"],
span[style*="white-space: normal"] *,
[class*="companion"],
[class*="companion"] *,
[class*="container"],
[class*="container"] *,
:has(span[style*="white-space: normal"]) {
    height: auto !important;
}

/* Exclude search overlay from encrypted font */
#encrypted-search-overlay,
#encrypted-search-overlay * {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
}
"""
                head.insert(0, style_tag)
        
        # Inject copy-paste interception script (same as client-side script)
        # This allows users to copy-paste normally while scrapers see encrypted text
        if head and nonce is not None:
            # Get API base URL for decryption calls
            api_base_url = base_url.rstrip('/')
            
            # Create config script tag to set encryption parameters
            config_script = soup.new_tag('script')
            config_script.string = f"""
window.encryptionConfig = {{
    secretKey: {secret_key},
    nonce: {nonce},
    apiBaseUrl: '{api_base_url}'
}};
"""
            
            # Create script tag to load the external decrypt-interceptor.js
            script_tag = soup.new_tag('script')
            script_tag['src'] = f'{api_base_url}/client/decrypt-interceptor.js'
            
            # Insert config script first, then the external script
            # Try to insert after style tag, or at the end of head
            style_tags = head.find_all('style')
            if style_tags:
                # Insert after the last style tag
                style_tags[-1].insert_after(config_script)
                config_script.insert_after(script_tag)
            else:
                # No style tag, append to head
                head.append(config_script)
                head.append(script_tag)
        
        # Convert back to HTML string
        encrypted_html = str(soup)
        
        # Return as HTML
        return encrypted_html, 200, {'Content-Type': 'text/html; charset=utf-8'}
    
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback.print_exc()
        return jsonify({'error': error_msg, 'type': type(e).__name__}), 500

@app.route('/client/encrypt-page.js', methods=['GET'])
def serve_encrypt_page_script():
    """Serve the automatic page encryption client script"""
    client_dir = os.path.join(os.path.dirname(__file__), 'client')
    return send_from_directory(client_dir, 'encrypt-page.js', mimetype='application/javascript')

@app.route('/client/decrypt-interceptor.js', methods=['GET'])
def serve_decrypt_interceptor_script():
    """Serve the decryption interceptor script for server-side encrypted pages"""
    client_dir = os.path.join(os.path.dirname(__file__), 'client')
    return send_from_directory(client_dir, 'decrypt-interceptor.js', mimetype='application/javascript')

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
            'html': '/api/encrypt/html (POST)',
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
        
        # Use default secret key if not provided
        if secret_key is None:
            secret_key = DEFAULT_SECRET_KEY
        else:
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
            'space_char': encryption_result['space_char'],  # Character that space encrypts to (for word-breaking)
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

@app.route('/api/mappings', methods=['POST'])
def get_mappings():
    """
    Get character mappings for a given secret key and nonce.
    
    Request body:
        {
            "secret_key": 29202393,
            "nonce": 462508  # optional, will calculate from text if provided
            "text": "Hello"  # optional, for nonce calculation
        }
    """
    try:
        data = request.json
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        secret_key = data.get('secret_key')
        nonce = data.get('nonce')
        text = data.get('text', '')
        
        # Use default secret key if not provided
        if secret_key is None:
            secret_key = DEFAULT_SECRET_KEY
        else:
            try:
                secret_key = int(secret_key)
            except (ValueError, TypeError):
                return jsonify({'error': 'secret_key must be an integer'}), 400
        
        # Calculate nonce from text if not provided
        if nonce is None and text:
            expanded = expand_ligatures(text)
            nonce = nonce_creator(expanded)
        elif nonce is None:
            return jsonify({'error': 'Either nonce or text must be provided'}), 400
        else:
            try:
                nonce = int(nonce)
            except (ValueError, TypeError):
                return jsonify({'error': 'nonce must be an integer'}), 400
        
        # Get mappings
        upper_map, lower_map, space_map = get_dynamic_mappings(secret_key, nonce)
        
        # Combine all mappings for display
        combined_map = {**upper_map, **lower_map, **space_map}
        
        return jsonify({
            'secret_key': secret_key,
            'nonce': nonce,
            'upper_map': upper_map,
            'lower_map': lower_map,
            'space_map': space_map,
            'combined_map': combined_map
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'type': type(e).__name__}), 500

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
    # Determine MIME type based on extension
    if filename.endswith('.woff2'):
        mimetype = 'font/woff2'
    elif filename.endswith('.ttf'):
        mimetype = 'font/ttf'
    elif filename.endswith('.woff'):
        mimetype = 'font/woff'
    else:
        mimetype = None
    response = send_from_directory(fonts_dir, filename, mimetype=mimetype)
    # Add CORS headers for Mac browser compatibility
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, HEAD, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = '*'
    # Add no-cache headers to prevent browser caching of fonts
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# Proxy endpoint to serve R2 fonts with CORS headers
# Falls back to local fonts if R2 is not available
@app.route('/proxy-font/<path:filename>')
def proxy_font(filename):
    """
    Proxy font files from R2 to avoid CORS issues.
    Falls back to local fonts if R2 fetch fails.
    """
    fonts_dir = os.path.join(os.path.dirname(__file__), 'fonts')
    local_font_path = os.path.join(fonts_dir, filename)
    
    # First, try to fetch from R2 if configured
    try:
        import requests
    except ImportError:
        # If requests not available, serve local font
        if os.path.exists(local_font_path):
            return send_from_directory(fonts_dir, filename, mimetype='font/woff2')
        return jsonify({'error': 'requests library not installed and local font not found'}), 500
    
    r2_public_url = os.environ.get('R2_PUBLIC_URL', 'https://pub-d9bb596a8d3640a78a3d56af3fdebbbc.r2.dev')
    font_url = f"{r2_public_url.rstrip('/')}/{filename}"
    
    try:
        # Try to fetch font from R2
        response = requests.get(font_url, timeout=120)
        response.raise_for_status()
        
        # Return font with proper headers
        from flask import Response
        return Response(
            response.content,
            mimetype='font/woff2',
            headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
                'Cache-Control': 'public, max-age=31536000',
                'Access-Control-Allow-Headers': '*',
                'Content-Length': str(len(response.content))
            }
        )
    except requests.exceptions.RequestException as e:
        # R2 fetch failed, fall back to local font
        if DEBUG_MODE:
            print(f"R2 fetch failed for {filename}, falling back to local font: {e}")
        
        if os.path.exists(local_font_path):
            # Serve local font with CORS headers
            response = send_from_directory(fonts_dir, filename, mimetype='font/woff2')
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, HEAD, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = '*'
            return response
        else:
            if DEBUG_MODE:
                print(f"Local font also not found: {local_font_path}")
            return jsonify({'error': f'Font not found locally or on R2: {filename}'}), 404

@app.route('/api/encrypt/pdf', methods=['POST'])
def encrypt_pdf():
    """
    Encrypt PDF file by replacing text with encrypted text using custom fonts.
    
    Request:
        - Form data with 'file' field containing PDF file
        - Optional 'secret_key' field (defaults to DEFAULT_SECRET_KEY)
    
    Response:
        - Encrypted PDF file as binary data
    """
    try:
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Check if file is PDF
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'File must be a PDF'}), 400
        
        # Get secret key
        secret_key = request.form.get('secret_key')
        if secret_key is None:
            secret_key = DEFAULT_SECRET_KEY
        else:
            try:
                secret_key = int(secret_key)
            except (ValueError, TypeError):
                return jsonify({'error': 'secret_key must be an integer'}), 400
        
        # Import PDF processing function
        try:
            import fitz  # PyMuPDF
            from EncTestNewTestF import redact_and_overwrite
        except ImportError as e:
            return jsonify({'error': f'PDF processing library not available: {str(e)}'}), 500
        
        # Save uploaded file temporarily
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as input_file:
            file.save(input_file.name)
            input_pdf_path = input_file.name
        
        # Create output file path
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as output_file:
            output_pdf_path = output_file.name
        
        try:
            # Encrypt the PDF
            redact_and_overwrite(
                input_pdf_path,
                font_paths={},  # Empty dict - will extract from PDF or use fallback
                output_pdf=output_pdf_path,
                secret_key=secret_key,
                base_font_path=None  # Will extract from PDF
            )
            
            # Read encrypted PDF
            with open(output_pdf_path, 'rb') as f:
                pdf_data = f.read()
            
            # Clean up temporary files
            os.unlink(input_pdf_path)
            os.unlink(output_pdf_path)
            
            # Return PDF as response
            from flask import Response
            return Response(
                pdf_data,
                mimetype='application/pdf',
                headers={
                    'Content-Disposition': f'attachment; filename=encrypted_{file.filename}',
                    'Access-Control-Allow-Origin': '*',
                }
            )
        
        except Exception as e:
            # Clean up temporary files on error
            if os.path.exists(input_pdf_path):
                os.unlink(input_pdf_path)
            if os.path.exists(output_pdf_path):
                os.unlink(output_pdf_path)
            raise e
    
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback.print_exc()
        return jsonify({'error': error_msg, 'type': type(e).__name__}), 500

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
