#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automated Font Generation Script
Builds a font whose glyphs are remapped based on the Feistel cipher output so
encrypted text renders as the original characters.
"""
import sys
import os
import copy
import hashlib

try:
    from fontTools.ttLib import TTFont
except ImportError:
    print("ERROR: fonttools not installed!")
    print("Installing fonttools and brotli...")
    os.system("pip install fonttools brotli")
    from fontTools.ttLib import TTFont

# Import encryption functions for dynamic mapping
from Fiesty import enc
UPPERCASE = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
LOWERCASE = "abcdefghijklmnopqrstuvwxyz"

def generate_char_mapping(sk: int, nonce: int, char_set: str) -> dict:
    """
    Generate dynamic character mapping using Feistel cipher.
    Maps each character in char_set to its encrypted version.
    Shared by the API and font generator to keep a single source of truth.
    
    Args:
        sk: Secret key
        nonce: Nonce value
        char_set: String of characters to map (e.g., "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    
    Returns:
        Dictionary mapping original char -> encrypted char
    """
    mapping = {}
    for i, char in enumerate(char_set):
        # Encrypt the position [0..25] using Feistel cipher (now supports 0-26)
        encrypted_pos = enc(sk, nonce, i)
        # Map to the character at that position
        # If encrypted_pos is 26, map to space; otherwise map to char_set[encrypted_pos]
        if encrypted_pos < len(char_set):
            mapping[char] = char_set[encrypted_pos]
        else:
            # Position 26 maps to space
            mapping[char] = ' '
    return mapping

def get_dynamic_mappings(sk: int, nonce: int) -> tuple:
    """
    Get all dynamic mappings (uppercase, lowercase, space) for given sk and nonce.
    Returns (upper_map, lower_map, space_map)
    """
    upper_map = generate_char_mapping(sk, nonce, UPPERCASE)
    lower_map = generate_char_mapping(sk, nonce, LOWERCASE)
    
    # Space is now a regular character - create mapping for it
    # Space is at position 26, encrypt it using Feistel
    space_encrypted_pos = enc(sk, nonce, 26)
    # Map to character at that position (0-25 maps to letters, 26 maps to space)
    if space_encrypted_pos < 26:
        # Map to lowercase letter (we'll use lowercase for space mapping)
        space_map = {" ": LOWERCASE[space_encrypted_pos]}
    else:
        # If it encrypts to 26, it stays as space
        space_map = {" ": " "}
    
    # Other special characters (null -> newline)
    special_map = {"\x00": "\n"}
    space_map.update(special_map)
    
    return upper_map, lower_map, space_map

def swap_glyphs_in_font(font, font_mapping_upper, font_mapping_lower, font_mapping_special):
    """
    Helper function to swap glyphs in a font based on mappings.
    Returns the number of swaps made.
    """
    # Get the cmap (character map) table
    cmap = font.getBestCmap()
    
    # Get glyph set
    glyph_set = font.getGlyphSet()
    
    # Create a mapping of char -> glyph name
    char_to_glyph = {}
    for unicode_val, glyph_name in cmap.items():
        char_to_glyph[chr(unicode_val)] = glyph_name
    
    swaps_made = 0
    
    # Uppercase letters
    for encrypted_char, original_char in font_mapping_upper.items():
        if original_char in char_to_glyph and encrypted_char in char_to_glyph:
            original_glyph = char_to_glyph[original_char]
            encrypted_glyph = char_to_glyph[encrypted_char]
            
            try:
                glyf_table = font['glyf']
                if original_glyph in glyf_table and encrypted_glyph in glyf_table:
                    original_glyph_obj = glyf_table[original_glyph]
                    glyf_table[encrypted_glyph] = copy.deepcopy(original_glyph_obj)
                    
                    # Also copy horizontal metrics (width, lsb) if hmtx table exists
                    if 'hmtx' in font:
                        hmtx = font['hmtx']
                        if original_glyph in hmtx.metrics and encrypted_glyph in hmtx.metrics:
                            hmtx.metrics[encrypted_glyph] = copy.deepcopy(hmtx.metrics[original_glyph])
                    
                    swaps_made += 1
                    print(f"  Swapped: '{encrypted_char}' now shows '{original_char}' glyph")
            except Exception as e:
                print(f"  Warning: Could not swap '{encrypted_char}' -> '{original_char}': {e}")
    
    # Lowercase letters
    for encrypted_char, original_char in font_mapping_lower.items():
        encrypted_display = repr(encrypted_char) if encrypted_char == ' ' else f"'{encrypted_char}'"
        original_display = repr(original_char) if original_char == ' ' else f"'{original_char}'"
        
        if original_char in char_to_glyph and encrypted_char in char_to_glyph:
            original_glyph = char_to_glyph[original_char]
            encrypted_glyph = char_to_glyph[encrypted_char]
            
            try:
                glyf_table = font['glyf']
                if original_glyph in glyf_table and encrypted_glyph in glyf_table:
                    original_glyph_obj = glyf_table[original_glyph]
                    glyf_table[encrypted_glyph] = copy.deepcopy(original_glyph_obj)
                    
                    if 'hmtx' in font:
                        hmtx = font['hmtx']
                        if original_glyph in hmtx.metrics and encrypted_glyph in hmtx.metrics:
                            hmtx.metrics[encrypted_glyph] = copy.deepcopy(hmtx.metrics[original_glyph])
                    
                    swaps_made += 1
                    print(f"  Swapped: {encrypted_display} now shows {original_display} glyph")
            except Exception as e:
                print(f"  Warning: Could not swap {encrypted_display} -> {original_display}: {e}")
        else:
            missing = []
            if original_char not in char_to_glyph:
                missing.append(f"original '{original_char}'")
            if encrypted_char not in char_to_glyph:
                missing.append(f"encrypted {encrypted_display}")
            print(f"  Skipped: {encrypted_display} -> {original_display} (missing: {', '.join(missing)})")
    
    # Special characters (space, null)
    for encrypted_char, original_char in font_mapping_special.items():
        encrypted_display = repr(encrypted_char) if encrypted_char in [' ', '\x00', '\n'] else f"'{encrypted_char}'"
        original_display = repr(original_char) if original_char in [' ', '\x00', '\n'] else f"'{original_char}'"
        
        if original_char in char_to_glyph and encrypted_char in char_to_glyph:
            original_glyph = char_to_glyph[original_char]
            encrypted_glyph = char_to_glyph[encrypted_char]
            
            try:
                glyf_table = font['glyf']
                if original_glyph in glyf_table and encrypted_glyph in glyf_table:
                    original_glyph_obj = glyf_table[original_glyph]
                    glyf_table[encrypted_glyph] = copy.deepcopy(original_glyph_obj)
                    
                    if 'hmtx' in font:
                        hmtx = font['hmtx']
                        if original_glyph in hmtx.metrics and encrypted_glyph in hmtx.metrics:
                            hmtx.metrics[encrypted_glyph] = copy.deepcopy(hmtx.metrics[original_glyph])
                    
                    swaps_made += 1
                    print(f"  Swapped: {encrypted_display} now shows {original_display} glyph")
            except Exception as e:
                print(f"  Warning: Could not swap {encrypted_display} -> {original_display}: {e}")
        else:
            missing = []
            if original_char not in char_to_glyph:
                missing.append(f"original {original_display}")
            if encrypted_char not in char_to_glyph:
                missing.append(f"encrypted {encrypted_display}")
            print(f"  Skipped: {encrypted_display} -> {original_display} (missing: {', '.join(missing)})")
    
    return swaps_made

def create_decryption_font_from_mappings(input_font_path, output_font_path, upper_map, lower_map, space_map):
    """
    Create a decryption font using pre-computed mappings.
    This avoids recalculating mappings that were already computed during encryption.
    
    Args:
        input_font_path: Path to the base font file
        output_font_path: Path where the decryption font will be saved
        upper_map: Dictionary mapping original -> encrypted for uppercase (from get_dynamic_mappings)
        lower_map: Dictionary mapping original -> encrypted for lowercase (from get_dynamic_mappings)
        space_map: Dictionary mapping original -> encrypted for space/special (from get_dynamic_mappings)
    """
    print(f"Loading font: {input_font_path}")
    font = TTFont(input_font_path)
    
    # Create reverse mappings for the font (encrypted -> original)
    # When encrypted text is displayed, we want to show original glyphs
    font_mapping_upper = {v: k for k, v in upper_map.items()}  # encrypted -> original
    font_mapping_lower = {v: k for k, v in lower_map.items()}  # encrypted -> original
    font_mapping_special = {v: k for k, v in space_map.items()}  # encrypted -> original
    
    print("Swapping glyphs...")
    swaps_made = swap_glyphs_in_font(font, font_mapping_upper, font_mapping_lower, font_mapping_special)
    
    print(f"\nMade {swaps_made} glyph swaps")
    
    # Update font family name
    if 'name' in font:
        name_table = font['name']
        for record in name_table.names:
            if record.nameID == 1:  # Family name
                record.string = 'DecryptionFont'
        print("Updated font family name to 'DecryptionFont'")
    
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
        print(f"✅ Decryption font created successfully: {output_font_path}")
        return True
    except Exception as e:
        print(f"⚠️  Could not create WOFF2, but TTF was saved: {e}")
        print(f"   You can convert {ttf_output} to WOFF2 manually")
        return False

def create_decryption_font(input_font_path, output_font_path, secret_key: int, nonce: int):
    """
    Create a decryption font using dynamic mappings from generate_char_mapping.
    This font will reverse the encryption mapping, so when encrypted characters
    are displayed in Unicode, they will show the decrypted (original) glyphs.
    
    NOTE: This function recalculates mappings. For better performance, use
    create_decryption_font_from_mappings() with pre-computed mappings.
    
    Args:
        input_font_path: Path to the base font file
        output_font_path: Path where the decryption font will be saved
        secret_key: Secret key used for encryption
        nonce: Nonce value used for encryption
    """
    print(f"Generating dynamic mappings with secret_key={secret_key}, nonce={nonce}...")
    # Get the encryption mappings (original -> encrypted)
    upper_map, lower_map, space_map = get_dynamic_mappings(secret_key, nonce)
    
    # Use the optimized function that takes mappings directly
    return create_decryption_font_from_mappings(input_font_path, output_font_path, upper_map, lower_map, space_map)

def create_encrypted_font(input_font_path, output_font_path):
    """
    Dynamic font generation was previously split between a hardcoded path and a
    Feistel-based path. The static path has been removed in favor of the dynamic
    approach. Use create_decryption_font instead.
    """
    raise RuntimeError("Static mapping font generation was removed. Use dynamic mappings.")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate a dynamic decryption font based on secret key + nonce')
    parser.add_argument('--input', type=str, default=None,
                        help='Input font path (default: Supertest.ttf)')
    parser.add_argument('--output', type=str, default=None,
                        help='Output font path (default: fonts/decryption_<hash>.woff2)')
    parser.add_argument('--secret-key', type=int, required=True,
                        help='Secret key for dynamic mapping')
    parser.add_argument('--nonce', type=int, required=True,
                        help='Nonce for dynamic mapping')
    
    args = parser.parse_args()
    
    # Set default paths
    if args.input is None:
        input_font = os.path.join(os.path.dirname(__file__), 'Supertest.ttf')
    else:
        input_font = args.input
    
    if args.output is None:
        font_hash = hashlib.md5(f"{args.secret_key}_{args.nonce}".encode('utf-8')).hexdigest()[:12]
        output_font = os.path.join(os.path.dirname(__file__), 'fonts', f'decryption_{font_hash}.woff2')
    else:
        output_font = args.output
    
    # Create fonts directory if it doesn't exist
    os.makedirs(os.path.dirname(output_font), exist_ok=True)
    
    if not os.path.exists(input_font):
        print(f"ERROR: Input font not found: {input_font}")
        sys.exit(1)
    
    print("=" * 70)
    print("DYNAMIC FONT GENERATION (Feistel-based mappings)")
    print("=" * 70)
    print()
    
    success = create_decryption_font(input_font, output_font, args.secret_key, args.nonce)
    
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
