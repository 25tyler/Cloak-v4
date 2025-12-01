#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import math
import fitz  # PyMuPDF
from functools import lru_cache
from collections import deque
import os

# Import dynamic mapping functions from existing codebase
from encrypt_api import expand_ligatures, remap_text_ultra_fast, nonce_creator
from generate_font import get_dynamic_mappings, create_decryption_font_from_mappings

# Import fonttools for better font extraction
try:
    from fontTools.ttLib import TTFont
    FONTOOLS_AVAILABLE = True
except ImportError:
    FONTOOLS_AVAILABLE = False

# Debug mode
DEBUG_MODE = os.environ.get('DEBUG', 'false').lower() == 'true'

# Font style detection functions
def is_bold(font_name: str) -> bool:
    """Detect if font is bold based on font name"""
    if not font_name:
        return False
    font_lower = font_name.lower()
    # Check for bold indicators in font name
    bold_keywords = ['bold', 'black', 'heavy', 'demibold', 'semibold', 'demi', 'semi']
    # Also check for common patterns like "Arial-Bold", "ArialBold", etc.
    if any(keyword in font_lower for keyword in bold_keywords):
        return True
    # Check for patterns like "Bold" at the end or "-B" suffix
    if font_lower.endswith('bold') or font_lower.endswith('-b') or font_lower.endswith('_b'):
        return True
    return False

def is_italic(font_name: str) -> bool:
    """Detect if font is italic based on font name"""
    if not font_name:
        return False
    font_lower = font_name.lower()
    # Check for italic indicators in font name
    italic_keywords = ['italic', 'oblique', 'slanted', 'slope']
    if any(keyword in font_lower for keyword in italic_keywords):
        return True
    # Check for patterns like "Italic" at the end or "-I" suffix
    if font_lower.endswith('italic') or font_lower.endswith('-i') or font_lower.endswith('_i'):
        return True
    # Check for "Ital" abbreviation
    if 'ital' in font_lower and 'initial' not in font_lower:
        return True
    return False

@lru_cache(maxsize=1000)
def get_font_style_key(font_name: str) -> str:
    """Get a key representing the font style combination"""
    bold = is_bold(font_name)
    italic = is_italic(font_name)
    
    if bold and italic:
        return "bold_italic"
    elif bold:
        return "bold"
    elif italic:
        return "italic"
    else:
        return "regular"

# Global font cache to avoid reloading fonts
FONT_CACHE = {}

# Object pool for frequently created objects
class RectPool:
    """Object pool for frequently created rectangles"""
    def __init__(self, pool_size=1000):
        self.pool = deque(maxlen=pool_size)
        self._create_initial_objects()
    
    def _create_initial_objects(self):
        for _ in range(100):  # Pre-create some objects
            self.pool.append(fitz.Rect())
    
    def get_rect(self, x0=0, y0=0, x1=0, y1=0):
        if self.pool:
            rect = self.pool.popleft()
            rect.x0, rect.y0, rect.x1, rect.y1 = x0, y0, x1, y1
            return rect
        return fitz.Rect(x0, y0, x1, y1)
    
    def return_rect(self, rect):
        """Return rect to pool for reuse"""
        if len(self.pool) < self.pool.maxlen:
            self.pool.append(rect)

# Global rect pool instance
RECT_POOL = RectPool()

# Pre-compute common mathematical values for better performance
POSITION_CONSTANTS = {
    'offset_factor': 0.15,
    'denominator_offset': 0.3,
    'padding': 0.2,
    'word_padding': 0.5
}

def get_cached_font(font_path: str):
    """Cache fonts globally to avoid reloading"""
    if font_path not in FONT_CACHE:
        try:
            FONT_CACHE[font_path] = fitz.Font(fontfile=font_path)
        except Exception as e:
            print(f"Warning: Could not load font from {font_path}: {e}")
            FONT_CACHE[font_path] = fitz.Font("helv")  # fallback
    return FONT_CACHE[font_path]

def extract_fonts_from_pdf(pdf_path: str, output_dir: str = None):
    """
    Extract fonts from PDF and save them to files, similar to extract_fonts_from_html.
    
    Args:
        pdf_path: Path to PDF file
        output_dir: Directory to save extracted fonts (default: fonts/extracted/)
    
    Returns:
        Dictionary mapping font style keys to font file paths:
        {
            "regular": "path/to/font.ttf",
            "bold": "path/to/bold.ttf",
            "italic": "path/to/italic.ttf",
            "bold_italic": "path/to/bold_italic.ttf"
        }
    """
    if output_dir is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(script_dir, 'fonts', 'extracted')
    os.makedirs(output_dir, exist_ok=True)
    
    doc = fitz.open(pdf_path)
    extracted_fonts = {}
    font_style_map = {}  # Map font names to their style keys
    
    # Collect all unique fonts from the PDF
    font_info_map = {}  # Map font name to (is_bold, is_italic, font_ref)
    
    for page_num, page in enumerate(doc):
        # Get font information from page
        try:
            # Get font list from page
            font_list = page.get_fonts(full=True)
            
            for font_item in font_list:
                font_name = font_item[1]  # Font name
                font_ref = font_item[0]    # Font reference number
                
                # Determine font style
                is_bold_font = is_bold(font_name)
                is_italic_font = is_italic(font_name)
                
                # Create style key
                if is_bold_font and is_italic_font:
                    style_key = "bold_italic"
                elif is_bold_font:
                    style_key = "bold"
                elif is_italic_font:
                    style_key = "italic"
                else:
                    style_key = "regular"
                
                # Store font info if not already seen or if this is a better match
                if font_name not in font_info_map:
                    font_info_map[font_name] = (is_bold_font, is_italic_font, font_ref, style_key)
                else:
                    # Prefer more specific styles (bold_italic > bold/italic > regular)
                    existing_style = font_info_map[font_name][3]
                    style_priority = {"bold_italic": 3, "bold": 2, "italic": 2, "regular": 1}
                    if style_priority.get(style_key, 0) > style_priority.get(existing_style, 0):
                        font_info_map[font_name] = (is_bold_font, is_italic_font, font_ref, style_key)
        except Exception as e:
            print(f"[WARNING] Error extracting fonts from page {page_num + 1}: {e}")
            continue
    
    # Extract font files from PDF
    try:
        # Get all font references from the document
        font_refs = {}
        
        # Iterate through all pages to collect font references
        for page_num in range(len(doc)):
            try:
                page = doc[page_num]
                font_list = page.get_fonts(full=True)
                for font_item in font_list:
                    font_ref = font_item[0]
                    font_name = font_item[1]
                    if font_ref not in font_refs:
                        font_refs[font_ref] = font_name
            except:
                continue
        
        # Try to extract embedded fonts - more thorough extraction
        for font_ref, font_name in font_refs.items():
            try:
                font_buffer = None
                
                # Method 1: Try direct xref stream (for Type3 fonts or direct embedding)
                try:
                    stream_data = doc.xref_stream(font_ref)
                    # Check if it's a valid font file
                    if stream_data and len(stream_data) > 100:
                        # Check for font file signatures
                        if (stream_data[:4] in [b'\x00\x01\x00\x00', b'OTTO', b'wOFF', b'wO'] or
                            stream_data[:2] == b'wO'):
                            font_buffer = stream_data
                except:
                    pass
                
                # Method 2: Get font descriptor and extract FontFile/FontFile2/FontFile3
                if not font_buffer:
                    try:
                        font_descriptor = doc.xref_get_key(font_ref, "FontDescriptor")
                        if font_descriptor[0] == "xref":
                            desc_xref = int(font_descriptor[1])
                            
                            # Try FontFile3 (most common for modern PDFs - can be TTF/OTF)
                            for font_file_key_name in ["FontFile3", "FontFile2", "FontFile"]:
                                try:
                                    font_file_key = doc.xref_get_key(desc_xref, font_file_key_name)
                                    if font_file_key and font_file_key[0] == "xref":
                                        file_xref = int(font_file_key[1])
                                        font_buffer = doc.xref_stream(file_xref)
                                        
                                        # Validate it's a font file
                                        if font_buffer and len(font_buffer) > 100:
                                            # Check for valid font signatures
                                            if (font_buffer[:4] in [b'\x00\x01\x00\x00', b'OTTO', b'wOFF'] or
                                                font_buffer[:2] == b'wO' or
                                                font_buffer[:5] != b'%PDF-'):
                                                break
                                            else:
                                                font_buffer = None
                                except:
                                    continue
                    except Exception as e:
                        pass
                
                # Method 3: Try to get font data from ToUnicode or other font resources
                if not font_buffer:
                    try:
                        # Some PDFs embed fonts in different ways
                        # Try to get the font's base font name and search for embedded data
                        base_font = doc.xref_get_key(font_ref, "BaseFont")
                        if base_font and base_font[1]:
                            # Font might be referenced but not embedded
                            # We'll handle this in the system font search below
                            pass
                    except:
                        pass
                
                if font_buffer and len(font_buffer) > 100:  # Valid font file should be > 100 bytes
                    # Determine font style
                    is_bold_font = is_bold(font_name)
                    is_italic_font = is_italic(font_name)
                    
                    if is_bold_font and is_italic_font:
                        style_key = "bold_italic"
                    elif is_bold_font:
                        style_key = "bold"
                    elif is_italic_font:
                        style_key = "italic"
                    else:
                        style_key = "regular"
                    
                    # Clean font name for filename
                    safe_font_name = "".join(c for c in font_name if c.isalnum() or c in (' ', '-', '_')).strip()
                    safe_font_name = safe_font_name.replace(' ', '_')[:50]  # Limit length
                    
                    # Determine file extension from buffer
                    font_ext = '.ttf'  # Default
                    if font_buffer[:4] == b'OTTO':
                        font_ext = '.otf'
                    elif font_buffer[:4] == b'\x00\x01\x00\x00':
                        font_ext = '.ttf'
                    elif font_buffer[:4] == b'wOFF':
                        font_ext = '.woff'
                    elif font_buffer[:2] == b'wO':
                        font_ext = '.woff2'
                    elif font_buffer[:5] == b'%PDF-':
                        # Embedded PDF font descriptor, skip
                        continue
                    
                    font_filename = f"{safe_font_name}_{style_key}_{font_ref}{font_ext}"
                    font_filepath = os.path.join(output_dir, font_filename)
                    
                    # Only save if we don't already have a font for this style
                    if style_key not in extracted_fonts:
                        with open(font_filepath, 'wb') as f:
                            f.write(font_buffer)
                        
                        extracted_fonts[style_key] = font_filepath
                        print(f"[INFO] Extracted {style_key} font from PDF: {font_filename} ({len(font_buffer)} bytes)")
            except Exception as e:
                # Font might not be embedded or extraction failed
                continue
    except Exception as e:
        print(f"[WARNING] Error extracting fonts from PDF: {e}")
    
    doc.close()
    
    # If we couldn't extract embedded fonts, search system fonts more thoroughly
    if not extracted_fonts:
        print("[INFO] No embedded fonts found in PDF. Searching system fonts...")
        
        def search_font_in_directory(directory, font_name, extensions=['.ttf', '.otf', '.ttc']):
            """Search for a font file in a directory"""
            if not os.path.exists(directory):
                return None
            
            # Try exact match first
            for ext in extensions:
                font_path = os.path.join(directory, f"{font_name}{ext}")
                if os.path.exists(font_path):
                    return font_path
            
            # Try case-insensitive search
            try:
                for root, dirs, files in os.walk(directory):
                    for file in files:
                        if any(file.lower().endswith(ext) for ext in extensions):
                            # Check if font name matches (case-insensitive, partial match)
                            file_lower = file.lower()
                            font_lower = font_name.lower()
                            # Remove extensions and compare
                            file_base = os.path.splitext(file)[0].lower()
                            if font_lower in file_base or file_base in font_lower:
                                return os.path.join(root, file)
            except:
                pass
            
            return None
        
        # Search system fonts for each font found in PDF
        for font_name, (is_bold_font, is_italic_font, font_ref, style_key) in font_info_map.items():
            if style_key not in extracted_fonts:
                font_found = False
                
                # Build search directories based on platform
                search_dirs = []
                if sys.platform == 'darwin':  # macOS
                    search_dirs = [
                        "/System/Library/Fonts",
                        "/Library/Fonts",
                        f"{os.path.expanduser('~')}/Library/Fonts",
                    ]
                elif sys.platform.startswith('linux'):
                    search_dirs = [
                        "/usr/share/fonts/truetype",
                        "/usr/share/fonts/opentype",
                        f"{os.path.expanduser('~')}/.fonts",
                        f"{os.path.expanduser('~')}/.local/share/fonts",
                    ]
                elif sys.platform == 'win32':
                    search_dirs = [
                        "C:/Windows/Fonts",
                    ]
                
                # Try exact font name
                for search_dir in search_dirs:
                    font_path = search_font_in_directory(search_dir, font_name)
                    if font_path:
                        extracted_fonts[style_key] = font_path
                        print(f"[INFO] Found system font for {style_key}: {font_path}")
                        font_found = True
                        break
                
                # If not found, try with cleaned font name (remove style suffixes)
                if not font_found:
                    base_font_name = font_name
                    # Remove common style suffixes
                    for suffix in ['-Bold', '-Italic', '-BoldItalic', '-BoldItalic', '-Regular', 
                                   'Bold', 'Italic', 'BI', 'BoldItalic', 'Regular']:
                        base_font_name = base_font_name.replace(suffix, '').replace(suffix.lower(), '')
                    base_font_name = base_font_name.strip('-').strip()
                    
                    if base_font_name and base_font_name != font_name:
                        for search_dir in search_dirs:
                            font_path = search_font_in_directory(search_dir, base_font_name)
                            if font_path:
                                extracted_fonts[style_key] = font_path
                                print(f"[INFO] Found system font for {style_key} (base name '{base_font_name}'): {font_path}")
                                font_found = True
                                break
                
                if not font_found:
                    print(f"[WARNING] Could not find system font file for '{font_name}' (style: {style_key})")
    
    return extracted_fonts, font_info_map

#  compat helpers - optimized
@lru_cache(maxsize=1000)
def rgb_int_to_tuple(rgb_int: int):
    return ((rgb_int >> 16) & 255) / 255.0, ((rgb_int >> 8) & 255) / 255.0, (rgb_int & 255) / 255.0

@lru_cache(maxsize=100)
def line_angle_from_dir(dir_tuple):
    dx, dy = dir_tuple if dir_tuple else (1.0, 0.0)
    return math.degrees(math.atan2(dy, dx))

def pad_rect(r, pad=None) -> fitz.Rect:
    """Compat replacement for Rect.inflate(). Returns a NEW padded rect."""
    if pad is None:
        pad = POSITION_CONSTANTS['padding']
    
    # Handle both fitz.Rect objects and tuples/lists
    if hasattr(r, 'x0'):
        # It's already a fitz.Rect object
        x0, y0, x1, y1 = r.x0, r.y0, r.x1, r.y1
    else:
        # It's a tuple/list with [x0, y0, x1, y1] format
        x0, y0, x1, y1 = r
    
    # Use object pool for better performance
    rr = RECT_POOL.get_rect(x0 - pad, y0 - pad, x1 + pad, y1 + pad)
    return rr

#  core - optimized
def build_draw_and_redact_cmds(page, default_fontsize=11, combined_map=None):
    """
    Build draw and redact commands for a PDF page.
    
    Args:
        page: PyMuPDF page object
        default_fontsize: Default font size
        combined_map: Combined character mapping dict for dynamic encryption (optional)
    """
    # Pre-allocate with estimated capacity to avoid list resizing
    raw_text = page.get_text()
    estimated_chars = len(raw_text)
    
    # Use deque for better performance with frequent appends
    draw_cmds = deque()
    redact_rects = deque()

    raw = page.get_text("rawdict")
    words = page.get_text("words")  # (x0,y0,x1,y1,text,block,line,word)
    
    # Pre-build words_by_line with sorted entries
    words_by_line = {}
    for x0, y0, x1, y1, wtext, bno, lno, wno in words:
        key = (bno, lno)
        if key not in words_by_line:
            words_by_line[key] = []
        words_by_line[key].append((x0, y0, x1, y1, wtext, wno))
    
    # Sort all word lists once
    for key in words_by_line:
        words_by_line[key].sort(key=lambda t: t[-1])

    # Process blocks more efficiently
    blocks = raw.get("blocks", [])
    for b_idx, block in enumerate(blocks):
        if block.get("type", 1) != 0:  # skip non-text
            continue
            
        lines = block.get("lines", [])
        for l_idx, line in enumerate(lines):
            angle = line_angle_from_dir(line.get("dir"))
            spans = line.get("spans", [])
            
            for span in spans:
                span_color = rgb_int_to_tuple(span.get("color", 0))
                span_size = span.get("size", default_fontsize)
                span_font = span.get("font", "")  # Extract font information
                
                # Always detect and log font style for debugging
                detected_style = get_font_style_key(span_font) if span_font else "regular"
                if detected_style != "regular":
                    # Log bold/italic detection
                    span_text = span.get("text", "")[:20] if span.get("text") else ""
                    if not span_text and span.get("chars"):
                        # Try to get text from first char
                        first_char = span.get("chars")[0] if span.get("chars") else {}
                        span_text = first_char.get("c", "")[:20]
                    print(f"[DEBUG] Detected {detected_style} font: '{span_font}' -> text: '{span_text}'")
                
                chars = span.get("chars")

                if chars:
                    # Process characters - group consecutive characters to preserve spacing
                    # This helps maintain proper character spacing when characters are remapped
                    current_text = ""
                    current_start_pos = None
                    current_size = span_size
                    current_bbox = None
                    
                    for ch in chars:
                        c0 = ch.get("c", "")
                        if not c0:
                            continue
                            
                        expanded = expand_ligatures(c0)
                        # Use dynamic mapping
                        if combined_map:
                            mapped_seq = ''.join(combined_map.get(ch, ch) for ch in expanded)
                        else:
                            raise ValueError("combined_map is required for encryption")
                        if not mapped_seq:
                            continue

                        x, y = ch["origin"]
                        size = ch.get("size", span_size)
                        # Avoid redundant color calculation
                        ch_color = ch.get("color")
                        color = rgb_int_to_tuple(ch_color) if ch_color else span_color
                        bbox = pad_rect(ch["bbox"])
                        
                        # Group consecutive characters that are close together (same word)
                        # This preserves spacing better than rendering each character separately
                        if current_text and current_start_pos:
                            # Check if this character is part of the same word (close horizontally)
                            prev_x = current_start_pos[0]
                            if abs(x - prev_x) < size * 1.5:  # Characters within reasonable distance
                                current_text += mapped_seq
                                # Expand bbox to include this character
                                if current_bbox:
                                    current_bbox = fitz.Rect(
                                        min(current_bbox.x0, bbox.x0),
                                        min(current_bbox.y0, bbox.y0),
                                        max(current_bbox.x1, bbox.x1),
                                        max(current_bbox.y1, bbox.y1)
                                    )
                                else:
                                    current_bbox = bbox
                                continue
                            else:
                                # Flush the accumulated text
                                draw_cmds.append({
                                    "pos": current_start_pos,
                                    "text": current_text,
                                    "fontsize": current_size,
                                    "rotate": angle,
                                    "font_style": get_font_style_key(span_font),
                                    "is_bold": is_bold(span_font),
                                    "is_italic": is_italic(span_font),
                                })
                                if current_bbox:
                                    redact_rects.append(current_bbox)
                        
                        # Start new text group
                        current_text = mapped_seq
                        current_start_pos = (x, y)
                        current_size = size
                        current_bbox = bbox
                    
                    # Flush any remaining text
                    if current_text and current_start_pos:
                        draw_cmds.append({
                            "pos": current_start_pos,
                            "text": current_text,
                            "fontsize": current_size,
                            "rotate": angle,
                            "font_style": get_font_style_key(span_font),
                            "is_bold": is_bold(span_font),
                            "is_italic": is_italic(span_font),
                        })
                        if current_bbox:
                            redact_rects.append(current_bbox)

                else:
                    key = (b_idx, l_idx)
                    if key not in words_by_line:
                        text = expand_ligatures(span.get("text", ""))
                        if combined_map:
                            mapped = ''.join(combined_map.get(ch, ch) for ch in text)
                        else:
                            raise ValueError("combined_map is required for encryption")
                        # Optimize origin calculation
                        span_bbox = span.get("bbox", [0,0,0,0])
                        x, y = span.get("origin", (span_bbox[0], span_bbox[3]))
                        draw_cmds.append({
                            "pos": (x, y),
                            "text": mapped,
                            "fontsize": span_size,
                            "rotate": angle,
                            "font_style": get_font_style_key(span_font),
                            "is_bold": is_bold(span_font),
                            "is_italic": is_italic(span_font),
                        })
                        redact_rects.append(pad_rect(span["bbox"], POSITION_CONSTANTS['word_padding']))
                        continue

                    # Process words more efficiently
                    # Render whole words at once to preserve proper spacing
                    word_list = words_by_line[key]
                    for x0, y0, x1, y1, wtext, wno in word_list:
                        if not wtext:
                            continue
                            
                        wtext_expanded = expand_ligatures(wtext)
                        if combined_map:
                            # Map the entire word at once
                            mapped_word = ''.join(combined_map.get(ch, ch) for ch in wtext_expanded)
                        else:
                            raise ValueError("combined_map is required for encryption")
                        
                        if not mapped_word:
                            continue
                        
                        # Render the entire word at the word's starting position
                        # PyMuPDF's TextWriter will handle character spacing correctly
                        # based on the font's actual character widths
                        draw_cmds.append({
                            "pos": (x0, y1),  # Use word's left edge and baseline
                            "text": mapped_word,
                            "fontsize": span_size,
                            "color": span_color,
                            "rotate": angle,
                            "font_style": get_font_style_key(span_font),
                            "is_bold": is_bold(span_font),
                            "is_italic": is_italic(span_font),
                        })
                        
                        # Redact the entire word area
                        redact_rects.append(pad_rect((x0, y0, x1, y1)))

    return draw_cmds, redact_rects

def redact_and_overwrite(input_pdf: str, font_paths: dict, output_pdf: str, bg_fill=(1,1,1), secret_key: int = None, base_font_path: str = None):
    """
    Modified function to handle multiple font files for different styles with dynamic mappings
    
    font_paths should be a dict like:
    {
        "regular": "path/to/regular.ttf",
        "bold": "path/to/bold.ttf", 
        "italic": "path/to/italic.ttf",
        "bold_italic": "path/to/bold_italic.ttf"
    }
    
    If secret_key is provided, uses dynamic mappings. Otherwise uses static mappings.
    base_font_path is used for generating encrypted fonts if not provided in font_paths.
    """
    doc = fitz.open(input_pdf)
    
    # Calculate nonce from PDF text if using dynamic mappings
    combined_map = None
    nonce = None
    upper_map = None
    lower_map = None
    space_map = None
    
    if secret_key is not None:
        # Extract all text to calculate nonce
        all_text = ""
        for page in doc:
            all_text += page.get_text()
        
        if not all_text:
            raise ValueError("PDF contains no text to encrypt")
        
        expanded_text = expand_ligatures(all_text)
        nonce = nonce_creator(expanded_text)
        upper_map, lower_map, space_map = get_dynamic_mappings(secret_key, nonce)
        # Combine all mappings for fast lookup
        combined_map = {**upper_map, **lower_map, **space_map}
        print(f"[INFO] Using dynamic mappings with secret_key={secret_key}, nonce={nonce}")
    else:
        raise ValueError("secret_key is required for encryption")
    
    # Initialize base_fonts_by_style to store base fonts for each style
    base_fonts_by_style = {}
    font_info_map = {}
    
    # Extract fonts from PDF if base_font_path not provided
    if base_font_path is None:
        print("[INFO] No base font provided, extracting fonts from PDF...")
        extracted_fonts, font_info_map = extract_fonts_from_pdf(input_pdf)
        
        if not extracted_fonts:
            # No fonts found - try Supertest.ttf variants as fallback
            print("\n[WARNING] Could not extract fonts from PDF.")
            if font_info_map:
                print("\nFonts found in PDF (but not extracted):")
                for font_name, (is_bold, is_italic, font_ref, style_key) in font_info_map.items():
                    print(f"  - {font_name} (style: {style_key})")
            
            # Try to find Supertest.ttf variants as fallback
            script_dir = os.path.dirname(os.path.abspath(__file__))
            supertest_fonts = {
                "regular": os.path.join(script_dir, 'Supertest.ttf'),
                "bold": os.path.join(script_dir, 'SupertestBold.ttf'),
                "italic": os.path.join(script_dir, 'SupertestItalic.ttf'),
                "bold_italic": os.path.join(script_dir, 'SupertestBoldItalic.ttf')
            }
            
            # Check which Supertest variants are available
            available_supertest = {}
            for style, font_path in supertest_fonts.items():
                if os.path.exists(font_path):
                    available_supertest[style] = font_path
                    print(f"[INFO] Found Supertest variant: {style} -> {font_path}")
            
            if available_supertest:
                # Use regular as base_font_path, or first available
                if "regular" in available_supertest:
                    base_font_path = available_supertest["regular"]
                else:
                    base_font_path = list(available_supertest.values())[0]
                
                extracted_fonts = available_supertest.copy()
                base_fonts_by_style = available_supertest.copy()
                print(f"\n[INFO] Using Supertest font variants as fallback:")
                for style, path in available_supertest.items():
                    print(f"  - {style}: {path}")
                print("[WARNING] The encrypted PDF may look different from the original due to font substitution.")
            else:
                # No fonts found and no Supertest.ttf - provide helpful error message
                print("\n[ERROR] Could not extract fonts from PDF and Supertest.ttf not found.")
                print("\nTo proceed, please provide a base font file using --base-font:")
                print("  python3 EncTestNewTestF.py input.pdf --secret-key 29202393 --base-font /path/to/font.ttf output.pdf")
                print("\nYou can:")
                print("  1. Find the actual font files on your system that match the font names above")
                print("  2. Use --base-font to specify a font file manually")
                print("  3. Place Supertest.ttf (and SupertestBold.ttf, SupertestItalic.ttf, SupertestBoldItalic.ttf) in the same directory as this script")
                raise ValueError(
                    "Could not extract fonts from PDF and Supertest.ttf not found. Please provide --base-font.\n"
                    "Example: --base-font /path/to/your/font.ttf"
                )
        else:
            # Use extracted fonts as base fonts
            # Prefer regular font as base, or use first available
            if "regular" in extracted_fonts:
                base_font_path = extracted_fonts["regular"]
            else:
                base_font_path = list(extracted_fonts.values())[0]
            
            # Store extracted fonts as base fonts (we'll use them to generate encrypted fonts)
            base_fonts_by_style = extracted_fonts.copy()
            print(f"[INFO] Extracted {len(extracted_fonts)} base fonts from PDF")
            for style, font_path in extracted_fonts.items():
                print(f"[INFO]  - {style}: {font_path}")
    else:
        # base_font_path was provided, use it as the base for regular style
        base_fonts_by_style["regular"] = base_font_path
    
    # Generate encrypted fonts for each style
    if upper_map is not None:
        if base_font_path is None:
            raise ValueError("--base-font is required when using --secret-key for dynamic mappings")
        
        if not os.path.exists(base_font_path):
            raise FileNotFoundError(f"Base font file not found: {base_font_path}")
        
        if base_font_path and os.path.exists(base_font_path):
            # Generate encrypted fonts for each style
            fonts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
            os.makedirs(fonts_dir, exist_ok=True)
            
            style_font_map = {
                "regular": ("normal", "normal"),
                "bold": ("bold", "normal"),
                "italic": ("normal", "italic"),
                "bold_italic": ("bold", "italic")
            }
            
            # Add provided fonts to base fonts (these are already provided by user as base fonts)
            for style, path in font_paths.items():
                if os.path.exists(path) and not path.endswith('.woff2') and not path.endswith('.woff'):
                    # Check if this is already an encrypted font (has 'encrypted' in name)
                    if 'encrypted' not in os.path.basename(path).lower():
                        base_fonts_by_style[style] = path
                        print(f"[INFO] Using provided base font for {style}: {path}")
            
            for style, (weight, font_style) in style_font_map.items():
                # Skip if we already have an encrypted font for this style (provided by user)
                if style in font_paths:
                    # Check if it's already encrypted (has 'encrypted' in path or is in fonts dir)
                    font_path = font_paths[style]
                    if 'encrypted' in os.path.basename(font_path).lower() or fonts_dir in font_path:
                        print(f"[INFO] Using provided encrypted font for {style}: {font_path}")
                        continue
                
                try:
                    # Generate encrypted font for this style
                    # CRITICAL: PyMuPDF needs TTF files, not WOFF2
                    # create_decryption_font_from_mappings saves TTF first, then converts to WOFF2
                    # We'll request WOFF2 but use the TTF that gets created
                    font_filename_woff2 = f"encrypted_{style}_{nonce}.woff2"
                    font_path_output_woff2 = os.path.join(fonts_dir, font_filename_woff2)
                    font_path_output_ttf = font_path_output_woff2.replace('.woff2', '.ttf')
                    
                    # CRITICAL: Use the correct base font for each style
                    # Priority: 1) extracted/provided font for this style, 2) base_font_path, 3) regular font
                    style_base_font = None
                    
                    # First, try to use a base font for this specific style
                    if style in base_fonts_by_style and os.path.exists(base_fonts_by_style[style]):
                        style_base_font = base_fonts_by_style[style]
                        print(f"[INFO] ✓ Using {style} base font: {style_base_font}")
                    # If no style-specific font, try to find a matching extracted font
                    elif font_info_map:
                        # Search for a font with matching style in font_info_map
                        for font_name, (is_bold_font, is_italic_font, font_ref, style_key) in font_info_map.items():
                            if style_key == style and style_key in base_fonts_by_style:
                                style_base_font = base_fonts_by_style[style_key]
                                print(f"[INFO] ✓ Found matching {style} font from extraction: {style_base_font}")
                                break
                    
                    # If no style-specific font found, try to find Supertest variant as fallback
                    if style_base_font is None:
                        # Try Supertest variant for this style
                        script_dir = os.path.dirname(os.path.abspath(__file__))
                        supertest_variants = {
                            "regular": os.path.join(script_dir, 'Supertest.ttf'),
                            "bold": os.path.join(script_dir, 'SupertestBold.ttf'),
                            "italic": os.path.join(script_dir, 'SupertestItalic.ttf'),
                            "bold_italic": os.path.join(script_dir, 'SupertestBoldItalic.ttf')
                        }
                        
                        if style in supertest_variants and os.path.exists(supertest_variants[style]):
                            style_base_font = supertest_variants[style]
                            print(f"[INFO] ✓ Using Supertest {style} variant as fallback: {style_base_font}")
                            # Add to base_fonts_by_style for future reference
                            base_fonts_by_style[style] = style_base_font
                        else:
                            # Last resort: use base_font_path but warn
                            style_base_font = base_font_path
                            if style != "regular":
                                print(f"[WARNING] ⚠ No {style} base font found! Using regular font as base for {style}.")
                                print(f"         This means the encrypted {style} font will look like regular text.")
                                print(f"         Available base fonts: {list(base_fonts_by_style.keys())}")
                                print(f"         Tried Supertest variants but {style} variant not found at: {supertest_variants.get(style, 'N/A')}")
                            else:
                                print(f"[INFO] Using default base font for {style}: {style_base_font}")
                    
                    if not style_base_font or not os.path.exists(style_base_font):
                        raise FileNotFoundError(f"Base font not found for {style}: {style_base_font}")
                    
                    print(f"[INFO] Generating encrypted {style} font from base: {style_base_font}")
                    
                    # Generate font - this will create both TTF and WOFF2
                    result = create_decryption_font_from_mappings(
                        style_base_font,
                        font_path_output_woff2,  # Request WOFF2, but TTF is saved first
                        upper_map,
                        lower_map,
                        space_map,
                        preserve_font_family=None
                    )
                    
                    # Always use TTF path for PyMuPDF (TTF is always created first)
                    if os.path.exists(font_path_output_ttf):
                        font_paths[style] = font_path_output_ttf
                        print(f"[INFO] Generated encrypted font for {style}: {font_path_output_ttf} (TTF)")
                    elif isinstance(result, str) and os.path.exists(result):
                        # TTF path was returned (WOFF2 generation failed, but TTF exists)
                        font_paths[style] = result
                        print(f"[INFO] Generated encrypted font for {style}: {result} (TTF)")
                    else:
                        raise FileNotFoundError(
                            f"TTF font not found. Expected at {font_path_output_ttf} or {result if isinstance(result, str) else 'unknown'}"
                        )
                except Exception as e:
                    print(f"[WARNING] Could not generate font for {style}: {e}")
                    import traceback
                    traceback.print_exc()
                    # Fallback to regular font if available
                    if "regular" in font_paths:
                        font_paths[style] = font_paths["regular"]
                        print(f"[WARNING] Using regular font as fallback for {style}")
                    else:
                        raise ValueError(f"Could not generate or find font for {style}")
    
    # Load different font variants using global cache
    # CRITICAL: PyMuPDF can only load TTF/OTF files, not WOFF2
    fonts = {}
    for style, path in font_paths.items():
        # Check if path is WOFF2 - PyMuPDF can't load WOFF2 directly
        if path.endswith('.woff2') or path.endswith('.woff'):
            # Try to find corresponding TTF file (created alongside WOFF2)
            ttf_path = path.replace('.woff2', '.ttf').replace('.woff', '.ttf')
            if os.path.exists(ttf_path):
                print(f"[INFO] Using TTF version of {style} font: {ttf_path}")
                path = ttf_path  # Use TTF path instead
            else:
                # Try to convert WOFF2 to TTF using fonttools
                if FONTOOLS_AVAILABLE:
                    try:
                        from fontTools.ttLib import TTFont
                        print(f"[INFO] Converting {style} font from WOFF2 to TTF...")
                        # Load WOFF2 font
                        woff2_font = TTFont(path)
                        # Save as TTF
                        ttf_output = ttf_path
                        woff2_font.flavor = None  # Remove WOFF2 flavor
                        woff2_font.save(ttf_output)
                        print(f"[INFO] Converted {style} font to TTF: {ttf_output}")
                        path = ttf_output  # Use converted TTF path
                        font_paths[style] = ttf_output  # Update for future reference
                    except Exception as e:
                        print(f"[ERROR] Could not convert {style} font from WOFF2 to TTF: {e}")
                        raise ValueError(f"Cannot load WOFF2 font {path}. PyMuPDF requires TTF/OTF files.")
                else:
                    raise ValueError(f"Cannot load WOFF2 font {path}. PyMuPDF requires TTF/OTF files. Install fonttools to convert.")
        
        # Load TTF/OTF file
        if not os.path.exists(path):
            raise FileNotFoundError(f"Font file not found: {path}")
        
        try:
            test_font = fitz.Font(fontfile=path)
            # Verify font loaded correctly by checking if it has glyphs
            if hasattr(test_font, 'glyph_count') and test_font.glyph_count == 0:
                print(f"[WARNING] Font {path} appears to be empty")
            fonts[style] = get_cached_font(path)
            print(f"[INFO] Successfully loaded {style} font: {path}")
        except Exception as e:
            print(f"[ERROR] Failed to load font {path} for style {style}: {e}")
            import traceback
            traceback.print_exc()
            raise ValueError(f"Cannot load font file {path}: {e}")

    # Debug: Print all fonts found in the PDF
    print("\n[INFO] Analyzing fonts in PDF...")
    all_fonts_in_pdf = {}
    for page_num, page in enumerate(doc):
        try:
            font_list = page.get_fonts(full=True)
            for font_item in font_list:
                font_name = font_item[1] if len(font_item) > 1 else ""
                if font_name:
                    style_key = get_font_style_key(font_name)
                    if font_name not in all_fonts_in_pdf:
                        all_fonts_in_pdf[font_name] = style_key
                    if style_key != "regular":
                        print(f"  Page {page_num+1}: Font '{font_name}' -> {style_key}")
        except:
            pass
    
    if all_fonts_in_pdf:
        print(f"[INFO] Found {len(all_fonts_in_pdf)} unique fonts in PDF:")
        for font_name, style in sorted(all_fonts_in_pdf.items()):
            print(f"  - '{font_name}' -> {style}")
    
    print(f"\n[INFO] Available base fonts for encryption:")
    for style, path in base_fonts_by_style.items():
        exists = "✓" if os.path.exists(path) else "✗"
        print(f"  {exists} {style:12} -> {path}")
    print()
    
    # Process all pages
    pages = list(doc)  # Convert to list for better performance
    for page in pages:
        draw_cmds, rects = build_draw_and_redact_cmds(page, combined_map=combined_map)

        # Batch redaction operations
        if rects:
            for r in rects:
                page.add_redact_annot(fitz.Rect(r), fill=bg_fill)
            page.apply_redactions()

        # Batch text writing operations with appropriate fonts
        if draw_cmds:
            # Group commands by font to minimize font switching
            commands_by_font = {}
            for cmd in draw_cmds:
                font_style = cmd.get("font_style", "regular")
                if font_style not in commands_by_font:
                    commands_by_font[font_style] = []
                commands_by_font[font_style].append(cmd)
            
            # Render text grouped by font
            # CRITICAL: TextWriter needs fonts to be embedded in the document
            # We need to ensure fonts are properly embedded
            tw = fitz.TextWriter(page.rect)
            
            # Debug: Print all detected font styles
            font_style_counts = {}
            font_style_samples = {}  # Store sample text for each style
            for cmd in draw_cmds:
                style = cmd.get("font_style", "regular")
                font_style_counts[style] = font_style_counts.get(style, 0) + 1
                # Store a sample of text for each style
                if style not in font_style_samples:
                    text_sample = cmd.get("text", "")[:30]
                    font_style_samples[style] = text_sample
            print(f"[INFO] Font style distribution: {font_style_counts}")
            for style, sample in font_style_samples.items():
                print(f"  - {style}: '{sample}'")
            print(f"[INFO] Available encrypted fonts: {list(fonts.keys())}")
            
            for font_style, commands in commands_by_font.items():
                # Get the font for this style, with fallback
                selected_font = fonts.get(font_style)
                if selected_font is None:
                    # Fallback to regular font, or system font
                    if "regular" in fonts:
                        selected_font = fonts["regular"]
                        print(f"[WARNING] ⚠ Font for style '{font_style}' not found in fonts dict!")
                        print(f"         Available fonts: {list(fonts.keys())}")
                        print(f"         Using regular font as fallback")
                    else:
                        selected_font = fitz.Font("helv")  # System fallback
                        print(f"[WARNING] No fonts available, using system font Helvetica")
                
                # Verify font is valid
                if selected_font is None:
                    raise ValueError(f"Could not load font for style '{font_style}'")
                
                # Debug: Print font info and verify it's working
                print(f"[INFO] Rendering {len(commands)} text commands with '{font_style}' font")
                # Show which font file is being used
                if font_style in font_paths:
                    print(f"         Using font file: {font_paths[font_style]}")
                if DEBUG_MODE:
                    try:
                        font_name = getattr(selected_font, 'name', 'unknown')
                        print(f"[DEBUG] Using font '{font_name}' for style '{font_style}' with {len(commands)} text commands")
                        # Test if font can render a character
                        test_char = 'A'
                        try:
                            # Try to get glyph for test character
                            glyph = selected_font.glyph_advance(ord(test_char))
                            print(f"[DEBUG] Font can render '{test_char}' (advance: {glyph})")
                        except:
                            print(f"[WARNING] Font may not be able to render characters properly")
                    except Exception as e:
                        print(f"[DEBUG] Could not get font info: {e}")
                
                for cmd in commands:
                    try:
                        # Ensure we have valid text
                        text_to_render = cmd.get("text", "")
                        if not text_to_render:
                            continue
                        
                        tw.append(
                            pos=cmd["pos"],
                            text=text_to_render,
                            font=selected_font,
                            fontsize=cmd.get("fontsize", 11)
                        )
                    except Exception as e:
                        print(f"[WARNING] Error rendering text '{cmd.get('text', '')[:20]}...' with font {font_style}: {e}")
                        import traceback
                        traceback.print_exc()
                        # Try with system font as last resort
                        try:
                            tw.append(
                                pos=cmd["pos"],
                                text=cmd.get("text", ""),
                                font=fitz.Font("helv"),
                                fontsize=cmd.get("fontsize", 11)
                            )
                        except:
                            print(f"[ERROR] Could not render text even with system font")
                            raise
            
            # Write all text to page - this embeds the fonts
            try:
                tw.write_text(page, overlay=True)
                print(f"[DEBUG] Wrote {len(draw_cmds)} text commands to page")
            except Exception as e:
                print(f"[ERROR] Failed to write text to page: {e}")
                import traceback
                traceback.print_exc()
                raise

    # Optimize save settings for better performance
    doc.save(output_pdf, deflate=True, garbage=4, clean=True)
    doc.close()
    print(f"[OK] Saved -> {output_pdf}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Encrypt PDF text with dynamic mappings and multiple font support',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dynamic mappings with fonts extracted from PDF:
  python3 EncTestNewTestF.py input.pdf --secret-key 29202393 output.pdf
  
  # Dynamic mappings with custom base font:
  python3 EncTestNewTestF.py input.pdf --secret-key 29202393 --base-font base_font.ttf output.pdf
  
  # Dynamic mappings with custom fonts for specific styles:
  python3 EncTestNewTestF.py input.pdf --secret-key 29202393 --base-font base_font.ttf --bold bold.ttf output.pdf
        """
    )
    
    parser.add_argument('input_pdf', help='Input PDF file to encrypt')
    parser.add_argument('output_pdf', help='Output PDF file path')
    
    # Font arguments (optional, for custom fonts)
    parser.add_argument('--regular', help='Custom regular font file (optional, will generate from base-font if not provided)')
    parser.add_argument('--bold', help='Custom bold font file (optional, will generate from base-font if not provided)')
    parser.add_argument('--italic', help='Custom italic font file (optional, will generate from base-font if not provided)')
    parser.add_argument('--bold-italic', dest='bold_italic', help='Custom bold-italic font file (optional, will generate from base-font if not provided)')
    
    # Dynamic mapping arguments
    parser.add_argument('--secret-key', type=int, required=True, help='Secret key for dynamic encryption (required)')
    parser.add_argument('--base-font', help='Base font file for generating encrypted fonts (optional, will extract from PDF if not provided)')
    
    args = parser.parse_args()
    
    input_pdf = args.input_pdf
    output_pdf = args.output_pdf
    
    # Validate required arguments
    if not args.secret_key:
        print("[ERROR] --secret-key is required")
        parser.print_help()
        sys.exit(1)
    
    # base_font is optional - will extract from PDF if not provided
    if args.base_font and not os.path.exists(args.base_font):
        print(f"[ERROR] Base font file not found: {args.base_font}")
        sys.exit(1)
    
    # Build font paths dictionary from custom fonts if provided
    font_paths = {}
    if args.regular:
        font_paths["regular"] = args.regular
    if args.bold:
        font_paths["bold"] = args.bold
    if args.italic:
        font_paths["italic"] = args.italic
    if getattr(args, 'bold_italic', None):
        font_paths["bold_italic"] = args.bold_italic
    
    # Validate custom font files if provided
    for style, path in font_paths.items():
        if not os.path.exists(path):
            print(f"[ERROR] Font file not found for {style}: {path}")
            sys.exit(1)
    
    redact_and_overwrite(input_pdf, font_paths, output_pdf, secret_key=args.secret_key, base_font_path=args.base_font)
