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
from Fiesty import enc27, dec27, enc54, dec54
# Aliases for backward compatibility
enc = enc27
dec = dec27
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

def generate_font_artifacts(secret_key: int, nonce: int, upper_map, lower_map, space_map, base_url: str = None):
    """
    Create (or reuse) the decryption font for a secret_key + nonce pair and return its filename + URL.
    Automatically uploads to Cloudflare R2 if configured.
    """
    fallback_url = os.environ.get('FONT_URL', 'https://your-cdn.com/fonts/encrypted.woff2')
    base_font_path = os.path.join(os.path.dirname(__file__), 'Supertest.ttf')
    fonts_dir = os.path.join(os.path.dirname(__file__), 'fonts')
    os.makedirs(fonts_dir, exist_ok=True)

    # Add version to hash to force regeneration when mapping logic changes
    # Version 3: Fixed bijectivity to include space as target
    font_hash = hashlib.md5(f"{secret_key}_{nonce}_v3".encode('utf-8')).hexdigest()[:12]
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
        # Always regenerate fonts to ensure they're correct (in case mapping logic changed)
        # This ensures we don't use old fonts with incorrect mappings
        if DEBUG_MODE:
            print(f"Generating decryption font: {font_filename_woff2}")
        # Try to generate WOFF2, but fall back to TTF if it fails
        result = create_decryption_font_from_mappings(base_font_path, font_path_woff2, upper_map, lower_map, space_map)
        if result == True:
            font_filename = font_filename_woff2
            font_path = font_path_woff2
        else:
            # WOFF2 generation failed, use TTF
            font_filename = font_filename_ttf
            font_path = font_path_ttf
        font_was_generated = True
        
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
                # Use proxy URL to avoid CORS issues
                # Try base_url, then BASE_URL env var, then request.url_root (if in request context)
                if base_url:
                    resolved_base = base_url
                elif os.environ.get('BASE_URL'):
                    resolved_base = os.environ.get('BASE_URL')
                elif has_request_context():
                    resolved_base = request.url_root.rstrip('/')
                else:
                    resolved_base = None
                
                if resolved_base:
                    # Add cache-busting timestamp to force browser to reload font
                    import time
                    cache_buster = int(time.time())
                    proxy_url = f"{resolved_base.rstrip('/')}/proxy-font/{font_filename}?v={cache_buster}"
                else:
                    # Fallback: use R2 URL directly (may have CORS issues)
                    proxy_url = r2_url
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
    # Try base_url, then BASE_URL env var, then request.url_root (if in request context)
    if base_url:
        resolved_base = base_url
    elif os.environ.get('BASE_URL'):
        resolved_base = os.environ.get('BASE_URL')
    elif has_request_context():
        resolved_base = request.url_root.rstrip('/')
    else:
        resolved_base = None
    
    if resolved_base:
        # Use direct /fonts/ endpoint for local fonts (not /proxy-font/)
        # Add cache-busting timestamp to force browser to reload font
        import time
        cache_buster = int(time.time())
        font_url = f"{resolved_base.rstrip('/')}/fonts/{font_filename}?v={cache_buster}"
    else:
        font_url = fallback_url
    if DEBUG_MODE:
        print(f"Using local font URL: {font_url}")
    return font_filename, font_url

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
        tuple: (soup, text_mapping, nonce, font_url, space_char)
        - soup: BeautifulSoup object with encrypted text
        - text_mapping: dict mapping original_text -> encrypted_text
        - nonce: Nonce used for encryption
        - font_url: URL to the decryption font
        - space_char: Character that space encrypts to
    """
    if not BS4_AVAILABLE:
        raise ImportError("beautifulsoup4 is required for HTML encryption. Install with: pip install beautifulsoup4")
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Elements to skip (don't encrypt text in these)
    skip_tags = {'script', 'style', 'noscript', 'meta', 'title', 'head'}
    
    # Extract all visible text nodes
    # CRITICAL: Preserve leading and trailing spaces to maintain spacing around links
    text_nodes = []
    for element in soup.find_all(string=True):
        # Skip if parent is in skip list
        parent = element.parent
        if parent and parent.name in skip_tags:
            continue
        
        # Get text content - preserve leading and trailing spaces
        original_text = str(element)
        # Only process if there's non-whitespace content
        if original_text.strip() and len(original_text.strip()) > 0:
            text_nodes.append((element, original_text))
    
    if len(text_nodes) == 0:
        # No text to encrypt, return empty mapping
        return soup, {}, None, None, None
    
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
        container['style'] = 'display: inline; white-space: normal;'
        
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
        
        # Strip leading spaces if container will start on a new line
        # This prevents spaces from appearing at the beginning of lines
        if container_will_start_line:
            leading_spaces = ''
        
        # Add leading spaces as spaceChar characters (preserves spacing around links)
        if leading_spaces and space_char:
            leading_space_count = len(leading_spaces)
            leading_space_span = soup.new_tag('span')
            leading_space_span['style'] = 'display: inline-block; white-space: nowrap;'
            leading_space_span.string = space_char * leading_space_count
            container.append(leading_space_span)
        
        # Wrap encrypted text for proper word breaking (like client-side script)
        # CRITICAL: Handle spaces that are actually encrypted characters (like 't' or period)
        # When any character encrypts to space, those spaces need to be preserved and rendered
        # Split by both space_char (what space encrypts to) AND actual space (what other chars encrypt to)
        period_encrypted_to = combined_map.get('.', None)
        has_period_as_space = (period_encrypted_to == ' ')
        # Check if any character encrypts to space (e.g., 't' encrypts to space)
        chars_that_encrypt_to_space = [char for char, encrypted in combined_map.items() if encrypted == ' ']
        has_chars_as_space = len(chars_that_encrypt_to_space) > 0
        
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
                
                # Add space_char between words (except after last word)
                if i < len(parts) - 1:
                    space_span = soup.new_tag('span')
                    space_span['style'] = 'display: inline-block; white-space: nowrap;'
                    space_span.string = space_char
                    container.append(space_span)
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
                
                # Add space (encrypted character) between parts (except after last part)
                # Use non-breaking space (U+00A0) to prevent HTML from collapsing it
                # The font maps non-breaking space to the original character glyph (e.g., 't' or period)
                if i < len(parts) - 1:
                    char_span = soup.new_tag('span')
                    char_span['style'] = 'display: inline-block; white-space: nowrap;'
                    char_span.string = '\u00A0'  # Non-breaking space - will show as original char via font mapping
                    container.append(char_span)
        else:
            # No spaces, just wrap the whole encrypted text
            word_span = soup.new_tag('span')
            word_span['style'] = 'display: inline-block; white-space: nowrap; word-break: keep-all;'
            word_span.string = encrypted
            container.append(word_span)
        
        # Add trailing spaces as spaceChar characters (preserves spacing around links)
        if trailing_spaces and space_char:
            trailing_space_count = len(trailing_spaces)
            trailing_space_span = soup.new_tag('span')
            trailing_space_span['style'] = 'display: inline-block; white-space: nowrap;'
            trailing_space_span.string = space_char * trailing_space_count
            container.append(trailing_space_span)
        
        replacements.append((element, container))
    
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
    
    # Generate font for this encryption
    font_filename, font_url = generate_font_artifacts(
        secret_key, nonce, upper_map, lower_map, space_map, base_url=base_url
    )
    
    # Get the character that space maps to (already retrieved above)
    # space_char is already available from the loop above
    
    return soup, text_mapping, nonce, font_url, space_char

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
    # title_tag = soup.find('title')
    # if title_tag and title_tag.string:
    #     original_title = str(title_tag.string)
    #     encrypted_title = encrypt_text_with_mapping(original_title)
    #     title_tag.string = encrypted_title
    #     stats['title_encrypted'] = True
    
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
        base_url = os.environ.get('BASE_URL', request.url_root.rstrip('/'))
        
        # Encrypt HTML content
        soup, text_mapping, nonce, font_url, space_char = encrypt_html_content(
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
        head = soup.find('head')
        if head and font_url:
            # Create style tag with font CSS
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
            nyt_file = os.path.join(os.path.dirname(__file__), 'nyt.html')
            if not os.path.exists(nyt_file):
                return jsonify({'error': 'No HTML content provided and nyt.html file not found'}), 404
            
            with open(nyt_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
        
        # Get secret key (from JSON body, query param, or default)
        if secret_key is None:
            secret_key = request.args.get('secret_key', type=int)
        if secret_key is None:
            secret_key = DEFAULT_SECRET_KEY
        
        # Get base URL for font generation
        base_url = os.environ.get('BASE_URL', request.url_root.rstrip('/'))
        
        # Encrypt HTML content
        soup, text_mapping, nonce, font_url, space_char = encrypt_html_content(
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
        head = soup.find('head')
        if head and font_url:
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
}}

/* Exclude search overlay from encrypted font */
#encrypted-search-overlay,
#encrypted-search-overlay * {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
}}
"""
            # Insert style tag after preload
            head.insert(1, style_tag)
        
        # Inject copy-paste interception script (same as client-side script)
        # This allows users to copy-paste normally while scrapers see encrypted text
        if head and nonce is not None:
            # Get API base URL for decryption calls
            api_base_url = base_url.rstrip('/')
            
            # Create script tag with copy interception
            script_tag = soup.new_tag('script')
            script_tag.string = f"""
(function() {{
    'use strict';
    
    // Store encryption parameters (secret_key and nonce only - no mappings for security)
    const encryptionConfig = {{
        secretKey: {secret_key},
        nonce: {nonce},
        apiBaseUrl: '{api_base_url}'
    }};
    
    /**
     * Decrypt text using the decryption API
     * Handles zero-width spaces, non-breaking spaces, and special characters
     */
    async function decryptText(encryptedText) {{
        if (!encryptionConfig.secretKey || !encryptionConfig.nonce) {{
            return encryptedText;
        }}
        
        // Remove zero-width spaces (U+200B) that were inserted for word-breaking
        const textWithoutZWSP = encryptedText.replace(/\\u200B/g, '');
        
        // Replace non-breaking spaces (U+00A0) with regular spaces for decryption
        // The font maps both regular spaces and non-breaking spaces to the same glyph
        const normalizedText = textWithoutZWSP.replace(/\\u00A0/g, ' ');
        
        // Call the decryption API
        try {{
            const response = await fetch(`${{encryptionConfig.apiBaseUrl}}/api/decrypt`, {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/json',
                }},
                body: JSON.stringify({{
                    encrypted: normalizedText,
                    secret_key: encryptionConfig.secretKey,
                    nonce: encryptionConfig.nonce
                }})
            }});
            
            if (!response.ok) {{
                console.warn('Decryption API call failed:', response.status);
                return encryptedText; // Return original if API fails
            }}
            
            const data = await response.json();
            return data.decrypted || encryptedText;
        }} catch (error) {{
            console.warn('Error calling decryption API:', error);
            return encryptedText; // Return original if API call fails
        }}
    }}
    
    /**
     * Intercept copy events and replace clipboard content with decrypted text
     * This allows users to copy-paste normally while scrapers see encrypted text
     * Note: Uses synchronous XMLHttpRequest because clipboardData API requires synchronous access
     */
    function setupCopyInterception() {{
        document.addEventListener('copy', function(e) {{
            // Only intercept if we have encryption config
            if (!encryptionConfig.secretKey || !encryptionConfig.nonce) {{
                return; // Let default copy behavior proceed
            }}
            
            const selection = window.getSelection();
            if (!selection || selection.rangeCount === 0) {{
                return; // No selection, let default behavior proceed
            }}
            
            // Get selected text (this will be the encrypted text)
            const selectedText = selection.toString();
            
            if (!selectedText || selectedText.trim().length === 0) {{
                return; // Empty selection, let default behavior proceed
            }}
            
            // Prevent default copy behavior
            e.preventDefault();
            
            // Decrypt synchronously using XMLHttpRequest (required for clipboardData API)
            // Note: Synchronous XHR is deprecated but necessary here for clipboard operations
            // Modern browsers may block synchronous XHR for cross-origin requests
            let decryptedText = selectedText; // Default to encrypted text if decryption fails
            
            try {{
                // Normalize text (remove zero-width spaces and normalize non-breaking spaces)
                const textWithoutZWSP = selectedText.replace(/\\u200B/g, '');
                const normalizedText = textWithoutZWSP.replace(/\\u00A0/g, ' ');
                
                // Make synchronous API call
                const xhr = new XMLHttpRequest();
                const apiUrl = `${{encryptionConfig.apiBaseUrl}}/api/decrypt`;
                
                // Check if we're on the same origin (synchronous XHR works better on same origin)
                const isSameOrigin = new URL(apiUrl, window.location.href).origin === window.location.origin;
                
                if (!isSameOrigin) {{
                    console.warn('Cross-origin synchronous XHR may be blocked by browser. API URL:', apiUrl);
                }}
                
                xhr.open('POST', apiUrl, false); // false = synchronous
                xhr.setRequestHeader('Content-Type', 'application/json');
                
                // Send request
                xhr.send(JSON.stringify({{
                    encrypted: normalizedText,
                    secret_key: encryptionConfig.secretKey,
                    nonce: encryptionConfig.nonce
                }}));
                
                // Check response
                if (xhr.status === 200) {{
                    try {{
                        const data = JSON.parse(xhr.responseText);
                        decryptedText = data.decrypted || selectedText;
                    }} catch (parseError) {{
                        console.error('Failed to parse decryption response:', parseError, 'Response:', xhr.responseText);
                        decryptedText = selectedText;
                    }}
                }} else {{
                    console.error('Decryption API returned status:', xhr.status, xhr.statusText, 'Response:', xhr.responseText);
                    decryptedText = selectedText;
                }}
            }} catch (error) {{
                console.error('Decryption API call failed:', error);
                console.error('This may be due to:', {{
                    'Synchronous XHR blocked': 'Modern browsers block synchronous XHR for cross-origin requests',
                    'CORS issue': 'Check CORS configuration on the API server',
                    'Network error': 'Check if API is accessible at: ' + encryptionConfig.apiBaseUrl,
                    'Error details': error.message
                }});
                // If decryption fails, use encrypted text (better than nothing)
                decryptedText = selectedText;
            }}
            
            // Set clipboard data with decrypted text
            e.clipboardData.setData('text/plain', decryptedText);
        }}, true); // Use capture phase to intercept early
    }}
    
    // Setup copy interception immediately (before DOM is ready)
    // This ensures it's set up before any copy events can occur
    setupCopyInterception();
    
    // Also set up on DOMContentLoaded as a fallback
    if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', setupCopyInterception);
    }}
    
    // ============================================================================
    // SEARCH FUNCTIONALITY
    // ============================================================================
    
    // Search state
    const searchState = {{
        overlay: null,
        input: null,
        matchCounter: null,
        prevButton: null,
        nextButton: null,
        closeButton: null,
        currentMatches: [],
        currentMatchIndex: -1,
        highlightElements: [],
        lastOriginalQuery: '' // Store original query for case-insensitive search
    }};
    
    // Ligatures mapping
    const LIGATURES = {{"\\ufb00":"ff","\\ufb01":"fi","\\ufb02":"fl","\\ufb03":"ffi","\\ufb04":"ffl"}};
    
    function expandLigatures(text) {{
        return text.split('').map(ch => LIGATURES[ch] || ch).join('');
    }}
    
    /**
     * Encrypt search query using the API (no mappings exposed in HTML)
     */
    async function encryptSearchQuery(query) {{
        if (!query || query.length === 0) {{
            return '';
        }}
        
        if (!encryptionConfig.secretKey || !encryptionConfig.nonce) {{
            return query; // Return as-is if config is missing
        }}
        
        try {{
            const response = await fetch(`${{encryptionConfig.apiBaseUrl}}/api/encrypt/query`, {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/json',
                }},
                body: JSON.stringify({{
                    text: query,
                    secret_key: encryptionConfig.secretKey,
                    nonce: encryptionConfig.nonce
                }})
            }});
            
            if (!response.ok) {{
                console.warn('Encrypt query API call failed:', response.status);
                return query; // Return original if API fails
            }}
            
            const data = await response.json();
            return data.encrypted || query;
        }} catch (error) {{
            console.warn('Error calling encrypt query API:', error);
            return query; // Return original if API call fails
        }}
    }}
    
    function isElementVisible(element) {{
        if (!element || element.nodeType !== Node.ELEMENT_NODE) {{
            return false;
        }}
        
        // Check computed style
        const style = window.getComputedStyle(element);
        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {{
            return false;
        }}
        
        // Check if element has zero dimensions
        const rect = element.getBoundingClientRect();
        if (rect.width === 0 && rect.height === 0) {{
            // Might be a line break or whitespace-only element, check if it has visible children
            const children = Array.from(element.children);
            if (children.length > 0) {{
                // Check if any child is visible
                return children.some(child => isElementVisible(child));
            }}
            // If no children and zero size, it's likely not visible
            return false;
        }}
        
        return true;
    }}
    
    function extractTextNodesForSearch() {{
        const textNodes = [];
        const walker = document.createTreeWalker(
            document.body,
            NodeFilter.SHOW_TEXT,
            {{
                acceptNode: function(node) {{
                    let parent = node.parentElement;
                    while (parent && parent !== document.body) {{
                        const tagName = parent.tagName ? parent.tagName.toLowerCase() : '';
                        // Skip hidden elements
                        if (['script', 'style', 'noscript', 'meta', 'title', 'head'].includes(tagName)) {{
                            return NodeFilter.FILTER_REJECT;
                        }}
                        // Check if parent is visible
                        if (!isElementVisible(parent)) {{
                            return NodeFilter.FILTER_REJECT;
                        }}
                        parent = parent.parentElement;
                    }}
                    return NodeFilter.FILTER_ACCEPT;
                }}
            }}
        );
        
        const rawNodes = [];
        let node;
        while (node = walker.nextNode()) {{
            rawNodes.push(node);
        }}
        
        const processedParents = new Set();
        rawNodes.forEach(node => {{
            let parent = node.parentElement;
            while (parent && parent !== document.body) {{
                const fontFamily = window.getComputedStyle(parent).fontFamily;
                if (fontFamily.includes('EncryptedFont')) {{
                    // Only process if parent is visible
                    if (!isElementVisible(parent)) {{
                        break;
                    }}
                    
                    if (!processedParents.has(parent)) {{
                        processedParents.add(parent);
                        const text = parent.textContent;
                        const normalizedText = text.replace(/\\u200B/g, '').replace(/\\u00A0/g, ' ');
                        if (normalizedText.trim().length > 0) {{
                            textNodes.push({{ node: node, parent: parent, text: normalizedText }});
                        }}
                    }}
                    break;
                }}
                parent = parent.parentElement;
            }}
        }});
        
        return textNodes;
    }}
    
    async function searchEncryptedDOM(encryptedQuery) {{
        if (!encryptedQuery || encryptedQuery.length === 0) {{
            return [];
        }}
        
        const matches = [];
        const textNodes = extractTextNodesForSearch();
        const normalizedQuery = encryptedQuery.replace(/\\u200B/g, '').replace(/\\u00A0/g, ' ');
        
        // For case-insensitive search, encrypt common case variations of the original query
        const originalQuery = searchState.lastOriginalQuery || '';
        const queriesToSearch = [normalizedQuery]; // Always include the query as-is
        
        if (originalQuery) {{
            // Encrypt lowercase version
            const lowerEncrypted = await encryptSearchQuery(originalQuery.toLowerCase());
            if (lowerEncrypted && lowerEncrypted !== normalizedQuery) {{
                queriesToSearch.push(lowerEncrypted.replace(/\\u200B/g, '').replace(/\\u00A0/g, ' '));
            }}
            
            // Encrypt uppercase version
            const upperEncrypted = await encryptSearchQuery(originalQuery.toUpperCase());
            if (upperEncrypted && upperEncrypted !== normalizedQuery) {{
                queriesToSearch.push(upperEncrypted.replace(/\\u200B/g, '').replace(/\\u00A0/g, ' '));
            }}
            
            // Encrypt title case (first letter uppercase, rest lowercase)
            if (originalQuery.length > 0) {{
                const titleCase = originalQuery[0].toUpperCase() + originalQuery.slice(1).toLowerCase();
                const titleEncrypted = await encryptSearchQuery(titleCase);
                if (titleEncrypted && titleEncrypted !== normalizedQuery) {{
                    queriesToSearch.push(titleEncrypted.replace(/\\u200B/g, '').replace(/\\u00A0/g, ' '));
                }}
            }}
        }}
        
        // Remove duplicates
        const uniqueQueries = [...new Set(queriesToSearch)];
        
        for (const textNode of textNodes) {{
            const text = textNode.text;
            
            // Search for each encrypted query variation
            for (const queryToSearch of uniqueQueries) {{
                let startIndex = 0;
                while (true) {{
                    const index = text.indexOf(queryToSearch, startIndex);
                    if (index === -1) break;
                    
                    // Check if we already have this match (avoid duplicates)
                    const isDuplicate = matches.some(m => 
                        m.parent === textNode.parent && 
                        m.startIndex === index && 
                        m.endIndex === index + queryToSearch.length
                    );
                    
                    if (!isDuplicate) {{
                        matches.push({{
                            node: textNode.node,
                            parent: textNode.parent,
                            startIndex: index,
                            endIndex: index + queryToSearch.length,
                            text: queryToSearch
                        }});
                    }}
                    
                    startIndex = index + 1;
                }}
            }}
        }}
        
        return matches;
    }}
    
    function clearHighlights() {{
        searchState.highlightElements.forEach(el => {{
            if (el.parentNode) {{
                const parent = el.parentNode;
                parent.replaceChild(document.createTextNode(el.textContent), el);
                parent.normalize();
            }}
        }});
        searchState.highlightElements = [];
    }}
    
    function highlightMatches(matches, currentIndex) {{
        clearHighlights();
        if (matches.length === 0) return;
        
        const matchesByParent = new Map();
        matches.forEach((match, index) => {{
            const parent = match.parent;
            if (!parent) return;
            if (!matchesByParent.has(parent)) {{
                matchesByParent.set(parent, []);
            }}
            matchesByParent.get(parent).push({{...match, matchIndex: index}});
        }});
        
        matchesByParent.forEach((parentMatches, parent) => {{
            if (!parent || !parent.parentNode) return;
            
            const walker = document.createTreeWalker(parent, NodeFilter.SHOW_TEXT, null);
            const textNodes = [];
            let node;
            while (node = walker.nextNode()) {{
                textNodes.push(node);
            }}
            if (textNodes.length === 0) return;
            
            let charOffset = 0;
            const charToNode = [];
            textNodes.forEach(textNode => {{
                const text = textNode.textContent.replace(/\\u200B/g, '').replace(/\\u00A0/g, ' ');
                for (let i = 0; i < text.length; i++) {{
                    charToNode.push({{ node: textNode, offset: i, globalOffset: charOffset + i }});
                }}
                charOffset += text.length;
            }});
            
            parentMatches.sort((a, b) => b.startIndex - a.startIndex);
            parentMatches.forEach(match => {{
                try {{
                    const startChar = charToNode[match.startIndex];
                    const endChar = charToNode[match.endIndex - 1];
                    if (!startChar || !endChar) return;
                    
                    const range = document.createRange();
                    range.setStart(startChar.node, startChar.offset);
                    range.setEnd(endChar.node, endChar.offset + 1);
                    
                    const highlight = document.createElement('mark');
                    highlight.className = 'encrypted-search-highlight';
                    if (match.matchIndex === currentIndex) {{
                        highlight.className += ' encrypted-search-current';
                    }}
                    highlight.style.backgroundColor = match.matchIndex === currentIndex ? '#ffeb3b' : '#fff59d';
                    highlight.style.padding = '0';
                    highlight.style.borderRadius = '2px';
                    
                    try {{
                        range.surroundContents(highlight);
                        searchState.highlightElements.push(highlight);
                    }} catch (e) {{
                        const contents = range.extractContents();
                        highlight.appendChild(contents);
                        range.insertNode(highlight);
                        searchState.highlightElements.push(highlight);
                    }}
                }} catch (e) {{
                    console.warn('Error highlighting match:', e);
                }}
            }});
        }});
        
        if (currentIndex >= 0 && currentIndex < searchState.highlightElements.length) {{
            const highlight = searchState.highlightElements[currentIndex];
            if (highlight && highlight.parentNode) {{
                highlight.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
            }}
        }}
    }}
    
    function navigateToMatch(direction) {{
        const matches = searchState.currentMatches;
        if (matches.length === 0) return;
        
        if (direction === 'next') {{
            searchState.currentMatchIndex = (searchState.currentMatchIndex + 1) % matches.length;
        }} else if (direction === 'prev') {{
            searchState.currentMatchIndex = searchState.currentMatchIndex <= 0 
                ? matches.length - 1 
                : searchState.currentMatchIndex - 1;
        }}
        
        highlightMatches(matches, searchState.currentMatchIndex);
        updateMatchCounter();
    }}
    
    function updateMatchCounter() {{
        const count = searchState.currentMatches.length;
        const index = searchState.currentMatchIndex;
        if (count === 0) {{
            searchState.matchCounter.textContent = 'No matches';
        }} else {{
            searchState.matchCounter.textContent = `${{index + 1}} of ${{count}}`;
        }}
    }}
    
    async function handleSearchInput(event) {{
        const query = event.target.value;
        // Store original query for case-insensitive search
        searchState.lastOriginalQuery = query;
        
        if (!query || query.trim().length === 0) {{
            clearHighlights();
            searchState.currentMatches = [];
            searchState.currentMatchIndex = -1;
            updateMatchCounter();
            return;
        }}
        
        // Encrypt the query as-is (for display/search purposes)
        const encryptedQuery = await encryptSearchQuery(query);
        // The searchEncryptedDOM function will handle case-insensitive matching
        const matches = await searchEncryptedDOM(encryptedQuery);
        searchState.currentMatches = matches;
        
        if (matches.length > 0) {{
            searchState.currentMatchIndex = 0;
            highlightMatches(matches, 0);
        }} else {{
            searchState.currentMatchIndex = -1;
            clearHighlights();
        }}
        
        updateMatchCounter();
    }}
    
    function createSearchOverlay() {{
        const overlay = document.createElement('div');
        overlay.id = 'encrypted-search-overlay';
        overlay.style.cssText = `position: fixed; top: 20px; right: 20px; background: white; border: 1px solid #ccc; border-radius: 4px; box-shadow: 0 2px 10px rgba(0,0,0,0.2); padding: 8px; z-index: 10000; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important; font-size: 14px; display: none;`;
        
        const inputContainer = document.createElement('div');
        inputContainer.style.cssText = 'display: flex; align-items: center; gap: 8px;';
        
        const input = document.createElement('input');
        input.type = 'text';
        input.placeholder = 'Search...';
        input.style.cssText = `border: 1px solid #ccc; border-radius: 2px; padding: 4px 8px; font-size: 14px; width: 200px; outline: none; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;`;
        input.addEventListener('input', handleSearchInput);
        input.addEventListener('keydown', function(e) {{
            if (e.key === 'Enter' && !e.shiftKey) {{
                e.preventDefault();
                navigateToMatch('next');
            }} else if (e.key === 'Enter' && e.shiftKey) {{
                e.preventDefault();
                navigateToMatch('prev');
            }} else if (e.key === 'Escape') {{
                e.preventDefault();
                hideSearchOverlay();
            }}
        }});
        
        const matchCounter = document.createElement('span');
        matchCounter.style.cssText = 'color: #666; font-size: 12px; min-width: 60px; text-align: center; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;';
        matchCounter.textContent = 'No matches';
        
        const prevButton = document.createElement('button');
        prevButton.textContent = '↑';
        prevButton.title = 'Previous (Shift+Enter)';
        prevButton.style.cssText = `border: 1px solid #ccc; background: white; border-radius: 2px; padding: 2px 8px; cursor: pointer; font-size: 12px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;`;
        prevButton.addEventListener('click', () => navigateToMatch('prev'));
        
        const nextButton = document.createElement('button');
        nextButton.textContent = '↓';
        nextButton.title = 'Next (Enter)';
        nextButton.style.cssText = prevButton.style.cssText;
        nextButton.addEventListener('click', () => navigateToMatch('next'));
        
        const closeButton = document.createElement('button');
        closeButton.textContent = '×';
        closeButton.title = 'Close (Esc)';
        closeButton.style.cssText = `border: none; background: transparent; font-size: 18px; cursor: pointer; padding: 0 4px; line-height: 1; color: #666; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;`;
        closeButton.addEventListener('click', hideSearchOverlay);
        
        inputContainer.appendChild(input);
        inputContainer.appendChild(matchCounter);
        inputContainer.appendChild(prevButton);
        inputContainer.appendChild(nextButton);
        inputContainer.appendChild(closeButton);
        overlay.appendChild(inputContainer);
        
        searchState.overlay = overlay;
        searchState.input = input;
        searchState.matchCounter = matchCounter;
        searchState.prevButton = prevButton;
        searchState.nextButton = nextButton;
        searchState.closeButton = closeButton;
        
        return overlay;
    }}
    
    function showSearchOverlay() {{
        if (!searchState.overlay) {{
            const overlay = createSearchOverlay();
            document.body.appendChild(overlay);
        }}
        searchState.overlay.style.display = 'block';
        searchState.input.focus();
        searchState.input.select();
    }}
    
    function hideSearchOverlay() {{
        if (searchState.overlay) {{
            searchState.overlay.style.display = 'none';
            searchState.input.value = '';
            clearHighlights();
            searchState.currentMatches = [];
            searchState.currentMatchIndex = -1;
        }}
    }}
    
    function setupSearchInterception() {{
        document.addEventListener('keydown', function(e) {{
            if ((e.ctrlKey || e.metaKey) && e.key === 'f') {{
                e.preventDefault();
                e.stopPropagation();
                showSearchOverlay();
            }}
        }}, true);
    }}
    
    // Setup search interception immediately
    setupSearchInterception();
    if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', setupSearchInterception);
    }}
}})();
"""
            # Insert script tag in head (before closing head tag)
            # Try to insert after style tag, or at the end of head
            style_tags = head.find_all('style')
            if style_tags:
                # Insert after the last style tag
                style_tags[-1].insert_after(script_tag)
            else:
                # No style tag, append to head
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
