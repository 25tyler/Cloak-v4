#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automated Font Generation Script
Creates the encrypted font automatically by swapping glyphs
"""
import sys
import os

try:
    from fontTools.ttLib import TTFont
    from fontTools.unicode import Unicode
except ImportError:
    print("ERROR: fonttools not installed!")
    print("Installing fonttools and brotli...")
    os.system("pip install fonttools brotli")
    from fontTools.ttLib import TTFont
    from fontTools.unicode import Unicode

# Import the exact mapping from the encryption algorithm
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
from encrypt_api import UPPER_MAP, LOWER_MAP, SPECIAL_MAP

def create_encrypted_font(input_font_path, output_font_path):
    """
    Create encrypted font by swapping glyphs according to mapping
    """
    print(f"Loading font: {input_font_path}")
    font = TTFont(input_font_path)
    
    # Get the cmap (character map) table
    cmap = font.getBestCmap()
    
    # Create reverse mapping: encrypted_char -> original_char
    # This is what we need for the font (encrypted char should show original glyph)
    reverse_upper = {}
    for encrypted, original in UPPER_MAP.items():
        reverse_upper[original] = encrypted
    
    reverse_lower = {}
    for encrypted, original in LOWER_MAP.items():
        reverse_lower[original] = encrypted
    
    reverse_special = {}
    for encrypted, original in SPECIAL_MAP.items():
        reverse_special[original] = encrypted
    
    print("Swapping glyphs...")
    
    # Get glyph set
    glyph_set = font.getGlyphSet()
    
    # Create a mapping of encrypted char -> original char glyph name
    char_to_glyph = {}
    for unicode_val, glyph_name in cmap.items():
        char_to_glyph[chr(unicode_val)] = glyph_name
    
    # Swap glyphs
    swaps_made = 0
    
    # Uppercase letters
    for original_char, encrypted_char in reverse_upper.items():
        if original_char in char_to_glyph and encrypted_char in char_to_glyph:
            original_glyph = char_to_glyph[original_char]
            encrypted_glyph = char_to_glyph[encrypted_char]
            
            # Get the glyph data
            if original_glyph in glyph_set and encrypted_glyph in glyph_set:
                # Copy glyph data from original to encrypted
                original_glyph_data = glyph_set[original_glyph]
                encrypted_glyph_data = glyph_set[encrypted_glyph]
                
                # For TTF fonts, we need to copy the glyph outline
                # This is a simplified approach - may need adjustment for complex fonts
                try:
                    # Get the glyph table
                    glyf_table = font['glyf']
                    if original_glyph in glyf_table and encrypted_glyph in glyf_table:
                        # Copy the glyph
                        glyf_table[encrypted_glyph] = glyf_table[original_glyph]
                        swaps_made += 1
                        print(f"  Swapped: '{encrypted_char}' now shows '{original_char}' glyph")
                except Exception as e:
                    print(f"  Warning: Could not swap '{encrypted_char}' -> '{original_char}': {e}")
    
    # Lowercase letters
    for original_char, encrypted_char in reverse_lower.items():
        if original_char in char_to_glyph and encrypted_char in char_to_glyph:
            original_glyph = char_to_glyph[original_char]
            encrypted_glyph = char_to_glyph[encrypted_char]
            
            try:
                glyf_table = font['glyf']
                if original_glyph in glyf_table and encrypted_glyph in glyf_table:
                    glyf_table[encrypted_glyph] = glyf_table[original_glyph]
                    swaps_made += 1
                    print(f"  Swapped: '{encrypted_char}' now shows '{original_char}' glyph")
            except Exception as e:
                print(f"  Warning: Could not swap '{encrypted_char}' -> '{original_char}': {e}")
    
    # Special characters (space)
    for original_char, encrypted_char in reverse_special.items():
        if original_char in char_to_glyph and encrypted_char in char_to_glyph:
            original_glyph = char_to_glyph[original_char]
            encrypted_glyph = char_to_glyph[encrypted_char]
            
            try:
                glyf_table = font['glyf']
                if original_glyph in glyf_table and encrypted_glyph in glyf_table:
                    glyf_table[encrypted_glyph] = glyf_table[original_glyph]
                    swaps_made += 1
                    print(f"  Swapped: '{encrypted_char}' now shows '{original_char}' glyph")
            except Exception as e:
                print(f"  Warning: Could not swap '{encrypted_char}' -> '{original_char}': {e}")
    
    print(f"\nMade {swaps_made} glyph swaps")
    
    # Save as TTF first
    ttf_output = output_font_path.replace('.woff2', '.ttf')
    print(f"Saving TTF: {ttf_output}")
    font.save(ttf_output)
    
    # Convert to WOFF2
    print(f"Converting to WOFF2: {output_font_path}")
    try:
        woff2_font = TTFont(ttf_output)
        woff2_font.flavor = 'woff2'
        woff2_font.save(output_font_path)
        print(f"✅ Font created successfully: {output_font_path}")
        return True
    except Exception as e:
        print(f"⚠️  Could not create WOFF2, but TTF was saved: {e}")
        print(f"   You can convert {ttf_output} to WOFF2 manually")
        return False

if __name__ == '__main__':
    input_font = os.path.join(os.path.dirname(__file__), 'Supertest.ttf')
    output_font = os.path.join(os.path.dirname(__file__), 'fonts', 'encrypted.woff2')
    
    # Create fonts directory if it doesn't exist
    os.makedirs(os.path.dirname(output_font), exist_ok=True)
    
    if not os.path.exists(input_font):
        print(f"ERROR: Input font not found: {input_font}")
        sys.exit(1)
    
    print("=" * 70)
    print("AUTOMATED FONT GENERATION")
    print("=" * 70)
    print()
    
    success = create_encrypted_font(input_font, output_font)
    
    if success:
        print()
        print("=" * 70)
        print("✅ Font generation complete!")
        print(f"   Font saved to: {output_font}")
        print("=" * 70)
    else:
        print()
        print("=" * 70)
        print("⚠️  Font generation completed with warnings")
        print("   Check output above for details")
        print("=" * 70)

