#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Font Creation Helper Script

This script helps create the encrypted font by providing instructions
and a mapping reference for manual font creation.

For automated font creation, you'll need fonttools:
    pip install fonttools brotli

Then you can use fonttools to programmatically swap glyphs.
"""
import sys
import os

# Import the exact mapping from the encryption algorithm
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
from encrypt_api import UPPER_MAP, LOWER_MAP, SPECIAL_MAP

def print_font_mapping_instructions():
    """Print detailed instructions for creating the font"""
    
    print("=" * 70)
    print("FONT CREATION INSTRUCTIONS")
    print("=" * 70)
    print()
    print("The encrypted font needs to swap glyphs so that:")
    print("  - When the browser renders encrypted character 'R', it shows 'A'")
    print("  - When the browser renders encrypted character 'F', it shows 'B'")
    print("  - etc.")
    print()
    print("This is the REVERSE of the encryption mapping.")
    print()
    print("=" * 70)
    print("UPPERCASE LETTER MAPPINGS (Character → Display Glyph)")
    print("=" * 70)
    print()
    
    # Create reverse mapping for display
    reverse_upper = {}
    for encrypted, original in UPPER_MAP.items():
        reverse_upper[original] = encrypted
    
    for original in sorted(reverse_upper.keys()):
        encrypted = reverse_upper[original]
        print(f"  Character '{encrypted}' should display the glyph for '{original}'")
    
    print()
    print("=" * 70)
    print("LOWERCASE LETTER MAPPINGS (Character → Display Glyph)")
    print("=" * 70)
    print()
    
    reverse_lower = {}
    for encrypted, original in LOWER_MAP.items():
        reverse_lower[original] = encrypted
    
    for original in sorted(reverse_lower.keys()):
        encrypted = reverse_lower[original]
        print(f"  Character '{encrypted}' should display the glyph for '{original}'")
    
    print()
    print("=" * 70)
    print("SPECIAL CHARACTER MAPPINGS")
    print("=" * 70)
    print()
    
    for encrypted, original in SPECIAL_MAP.items():
        if encrypted == ' ':
            print(f"  Character ' ' (space) should display the glyph for '{original}'")
        else:
            print(f"  Character '{encrypted}' should display the glyph for '{original}'")
    
    print()
    print("=" * 70)
    print("FONTFORGE INSTRUCTIONS")
    print("=" * 70)
    print()
    print("1. Open FontForge:")
    print("   fontforge Supertest.ttf")
    print()
    print("2. For each mapping above:")
    print("   a. Select the encrypted character (left side)")
    print("   b. Copy the glyph from the original character (right side)")
    print("   c. Paste it to the encrypted character")
    print()
    print("3. Example for uppercase 'A':")
    print("   - Select character 'R' (this is what encrypted 'A' becomes)")
    print("   - Copy the glyph from character 'A'")
    print("   - Paste it to character 'R'")
    print("   - Now when browser renders 'R', it shows 'A'")
    print()
    print("4. Export as WOFF2:")
    print("   File → Generate Fonts → Format: WOFF2")
    print()
    print("=" * 70)
    print("AUTOMATED FONT CREATION (Advanced)")
    print("=" * 70)
    print()
    print("To automate this with Python, install fonttools:")
    print("  pip install fonttools brotli")
    print()
    print("Then use the fonttools library to programmatically swap glyphs.")
    print("See: https://fonttools.readthedocs.io/")
    print()
    print("=" * 70)

def generate_font_mapping_file():
    """Generate a JSON file with the mapping for reference"""
    import json
    
    # Create reverse mapping (what we need for font)
    font_mapping = {
        'uppercase': {},
        'lowercase': {},
        'special': {}
    }
    
    # Reverse the encryption mapping for font creation
    for encrypted, original in UPPER_MAP.items():
        font_mapping['uppercase'][encrypted] = original
    
    for encrypted, original in LOWER_MAP.items():
        font_mapping['lowercase'][encrypted] = original
    
    for encrypted, original in SPECIAL_MAP.items():
        font_mapping['special'][encrypted] = original
    
    # Save to file
    output_file = os.path.join(os.path.dirname(__file__), 'font_mapping.json')
    with open(output_file, 'w') as f:
        json.dump(font_mapping, f, indent=2)
    
    print(f"Font mapping saved to: {output_file}")
    print("You can use this as a reference when creating the font.")
    print()

if __name__ == '__main__':
    print_font_mapping_instructions()
    print()
    generate_font_mapping_file()

