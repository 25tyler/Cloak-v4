#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, math
import fitz  # PyMuPDF
from functools import lru_cache
from collections import deque

#  mapping - optimized with combined lookup
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

# Cache frequently used operations
@lru_cache(maxsize=1000)
def expand_ligatures(s: str) -> str:
    return "".join(LIGATURES.get(ch, ch) for ch in s)

@lru_cache(maxsize=10000)
def remap_char(ch: str) -> str:
    return COMBINED_MAP.get(ch, ch)

def remap_text_bulk(text: str) -> str:
    """Bulk text remapping for better performance"""
    return "".join(COMBINED_MAP.get(ch, ch) for ch in text)

def remap_text_ultra_fast(text: str) -> str:
    """Ultra-fast character mapping using string translation"""
    return text.translate(CHAR_TRANSLATION_TABLE)

# Font style detection functions
def is_bold(font_name: str) -> bool:
    """Detect if font is bold based on font name"""
    if not font_name:
        return False
    font_lower = font_name.lower()
    return any(keyword in font_lower for keyword in ['bold', 'black', 'heavy', 'demibold'])

def is_italic(font_name: str) -> bool:
    """Detect if font is italic based on font name"""
    if not font_name:
        return False
    font_lower = font_name.lower()
    return any(keyword in font_lower for keyword in ['italic', 'oblique', 'slanted'])

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
def build_draw_and_redact_cmds(page, default_fontsize=11):
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
                chars = span.get("chars")

                if chars:
                    # Process characters more efficiently
                    for ch in chars:
                        c0 = ch.get("c", "")
                        if not c0:
                            continue
                            
                        expanded = expand_ligatures(c0)
                        # Use ultra-fast remapping for better performance
                        mapped_seq = remap_text_ultra_fast(expanded)
                        if not mapped_seq:
                            continue

                        x, y = ch["origin"]
                        size = ch.get("size", span_size)
                        # Avoid redundant color calculation
                        ch_color = ch.get("color")
                        color = rgb_int_to_tuple(ch_color) if ch_color else span_color
                        bbox = pad_rect(ch["bbox"])

                        draw_cmds.append({
                            "pos": (x, y),
                            "text": mapped_seq,
                            "fontsize": size,
                            "rotate": angle,
                            "font_style": get_font_style_key(span_font),
                            "is_bold": is_bold(span_font),
                            "is_italic": is_italic(span_font),
                        })
                        redact_rects.append(bbox)

                else:
                    key = (b_idx, l_idx)
                    if key not in words_by_line:
                        text = expand_ligatures(span.get("text", ""))
                        mapped = remap_text_ultra_fast(text)
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
                    word_list = words_by_line[key]
                    for x0, y0, x1, y1, wtext, wno in word_list:
                        if not wtext:
                            continue
                            
                        wtext_expanded = expand_ligatures(wtext)
                        length = len(wtext_expanded)
                        if length == 0:
                            continue

                        # Pre-calculate common values using constants
                        width = x1 - x0
                        width_div_length = width / length
                        offset_factor = POSITION_CONSTANTS['offset_factor']
                        denominator_offset = POSITION_CONSTANTS['denominator_offset']
                        
                        for i, ch in enumerate(wtext_expanded):
                            mapped = remap_char(ch)
                            if not mapped:
                                continue
                                
                            # Optimized position calculation with pre-computed constants
                            xi = x0 + width_div_length * (i + offset_factor) + (width * offset_factor) / (length + denominator_offset)
                            yi = y1
                            draw_cmds.append({
                                "pos": (xi, yi),
                                "text": mapped,
                                "fontsize": span_size,
                                "color": span_color,
                                "rotate": angle,
                                "font_style": get_font_style_key(span_font),
                                "is_bold": is_bold(span_font),
                                "is_italic": is_italic(span_font),
                            })
                            
                            # Optimized redact rect calculation
                            xL = x0 + width_div_length * i
                            xR = x0 + width_div_length * (i + 1)
                            redact_rects.append(pad_rect((xL, y0, xR, y1)))

    return draw_cmds, redact_rects

def redact_and_overwrite(input_pdf: str, font_paths: dict, output_pdf: str, bg_fill=(1,1,1)):
    """
    Modified function to handle multiple font files for different styles
    
    font_paths should be a dict like:
    {
        "regular": "path/to/regular.ttf",
        "bold": "path/to/bold.ttf", 
        "italic": "path/to/italic.ttf",
        "bold_italic": "path/to/bold_italic.ttf"
    }
    """
    doc = fitz.open(input_pdf)
    
    # Load different font variants using global cache
    fonts = {}
    for style, path in font_paths.items():
        fonts[style] = get_cached_font(path)

    # Process all pages
    pages = list(doc)  # Convert to list for better performance
    for page in pages:
        draw_cmds, rects = build_draw_and_redact_cmds(page)

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
            tw = fitz.TextWriter(page.rect)
            for font_style, commands in commands_by_font.items():
                selected_font = fonts.get(font_style, fonts.get("regular", fitz.Font("helv")))
                for cmd in commands:
                    tw.append(
                        pos=cmd["pos"],
                        text=cmd["text"],
                        font=selected_font,
                        fontsize=cmd["fontsize"]
                    )
            tw.write_text(page, overlay=True)

    # Optimize save settings for better performance
    doc.save(output_pdf, deflate=True, garbage=4, clean=True)
    doc.close()
    print(f"[OK] Saved -> {output_pdf}")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python3 encrypt_per_char.py input.pdf regular.ttf [bold.ttf] [italic.ttf] [bold_italic.ttf] output.pdf")
        print("Minimum: input.pdf regular.ttf output.pdf")
        print("Full: input.pdf regular.ttf bold.ttf italic.ttf bold_italic.ttf output.pdf")
        sys.exit(1)
    
    input_pdf = sys.argv[1]
    output_pdf = sys.argv[-1]  # Last argument is output
    
    # Build font paths dictionary
    font_paths = {
        "regular": sys.argv[2]  # Always required
    }
    
    # Add optional font variants if provided
    if len(sys.argv) >= 5:  # bold.ttf provided
        font_paths["bold"] = sys.argv[3]
    if len(sys.argv) >= 6:  # italic.ttf provided
        font_paths["italic"] = sys.argv[4]
    if len(sys.argv) >= 7:  # bold_italic.ttf provided
        font_paths["bold_italic"] = sys.argv[5]
    
    # If only one font provided, use it for all styles
    if len(sys.argv) == 4:
        font_paths = {
            "regular": sys.argv[2],
            "bold": sys.argv[2],
            "italic": sys.argv[2],
            "bold_italic": sys.argv[2]
        }
    
    redact_and_overwrite(input_pdf, font_paths, output_pdf)
