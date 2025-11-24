#!/usr/bin/env python3
"""
Debug script to trace font mapping issues.
Specifically checks the case where "space maps to K but K is rendering as J"
"""
from generate_font import get_dynamic_mappings, create_decryption_font_from_mappings
from encrypt_api import nonce_creator, expand_ligatures, DEFAULT_SECRET_KEY
from fontTools.ttLib import TTFont
import os

# Use the default secret key
sk = DEFAULT_SECRET_KEY
print(f"Using secret_key: {sk}\n")

# Read nyt.html to get the actual text
nyt_path = os.path.join(os.path.dirname(__file__), 'nyt.html')
with open(nyt_path, 'r', encoding='utf-8') as f:
    nyt_content = f.read()

# Calculate nonce from the actual NYT content
expanded = expand_ligatures(nyt_content)
nonce = nonce_creator(expanded)
print(f"Nonce from nyt.html: {nonce}\n")

# Get the mappings
upper_map, lower_map, space_map = get_dynamic_mappings(sk, nonce)

print("=" * 70)
print("ENCRYPTION MAPPING (original -> encrypted)")
print("=" * 70)
print(f"\nSpace encrypts to: {repr(lower_map.get(' ', 'NOT FOUND'))}")

# Check what 'K' encrypts to
if 'K' in upper_map:
    print(f"K encrypts to: {repr(upper_map['K'])}")
if 'k' in lower_map:
    print(f"k encrypts to: {repr(lower_map['k'])}")

# Check what 'J' encrypts to
if 'J' in upper_map:
    print(f"J encrypts to: {repr(upper_map['J'])}")
if 'j' in lower_map:
    print(f"j encrypts to: {repr(lower_map['j'])}")

print("\n" + "=" * 70)
print("FONT MAPPING (encrypted -> original)")
print("=" * 70)

# Create unified encryption map (original -> encrypted)
unified_encryption_map = {**upper_map, **lower_map}
print(f"\nUnified encryption map has {len(unified_encryption_map)} entries")

# Check for duplicates in encryption map (shouldn't happen if bijective)
encryption_targets = list(unified_encryption_map.values())
duplicates = [t for t in set(encryption_targets) if encryption_targets.count(t) > 1]
if duplicates:
    print(f"⚠️  WARNING: Duplicate targets in encryption map: {duplicates}")
    for dup in duplicates:
        sources = [k for k, v in unified_encryption_map.items() if v == dup]
        print(f"  {repr(dup)} is target of: {[repr(s) for s in sources]}")
else:
    print("✅ Encryption map is bijective (no duplicates)")

# Create font mapping (encrypted -> original) by reversing
unified_font_mapping = {v: k for k, v in unified_encryption_map.items()}
print(f"\nUnified font mapping has {len(unified_font_mapping)} entries")

# Check what 'K' maps to in font
if 'K' in unified_font_mapping:
    print(f"K in font mapping -> {repr(unified_font_mapping['K'])}")
if 'k' in unified_font_mapping:
    print(f"k in font mapping -> {repr(unified_font_mapping['k'])}")

# Check what 'J' maps to in font
if 'J' in unified_font_mapping:
    print(f"J in font mapping -> {repr(unified_font_mapping['J'])}")
if 'j' in unified_font_mapping:
    print(f"j in font mapping -> {repr(unified_font_mapping['j'])}")

# Check if space is in font mapping (it should be if some char encrypts to space)
if ' ' in unified_font_mapping:
    print(f"Space in font mapping -> {repr(unified_font_mapping[' '])}")

# Now check the split font mappings
font_mapping_upper = {}
font_mapping_lower = {}

for encrypted_char, original_char in unified_font_mapping.items():
    if encrypted_char.isupper():
        font_mapping_upper[encrypted_char] = original_char
    elif encrypted_char.islower() or encrypted_char in "abcdefghijklmnopqrstuvwxyz ." or encrypted_char == ' ':
        font_mapping_lower[encrypted_char] = original_char

print("\n" + "=" * 70)
print("SPLIT FONT MAPPINGS (for swap_glyphs_in_font)")
print("=" * 70)
print(f"\nfont_mapping_upper has {len(font_mapping_upper)} entries")
print(f"font_mapping_lower has {len(font_mapping_lower)} entries")

# Check what 'K' maps to in split mappings
if 'K' in font_mapping_upper:
    print(f"K in font_mapping_upper -> {repr(font_mapping_upper['K'])}")
if 'k' in font_mapping_lower:
    print(f"k in font_mapping_lower -> {repr(font_mapping_lower['k'])}")

# Check what 'J' maps to in split mappings
if 'J' in font_mapping_upper:
    print(f"J in font_mapping_upper -> {repr(font_mapping_upper['J'])}")
if 'j' in font_mapping_lower:
    print(f"j in font_mapping_lower -> {repr(font_mapping_lower['j'])}")

# Check if space is in split mappings
if ' ' in font_mapping_lower:
    print(f"Space in font_mapping_lower -> {repr(font_mapping_lower[' '])}")

# Now generate the font and check the actual glyph mappings
print("\n" + "=" * 70)
print("GENERATING FONT AND CHECKING GLYPH MAPPINGS")
print("=" * 70)

base_font_path = os.path.join(os.path.dirname(__file__), 'Supertest.ttf')
if not os.path.exists(base_font_path):
    print(f"⚠️  Base font not found: {base_font_path}")
    print("Skipping font generation test")
else:
    # Generate font
    font_hash = f"debug_{nonce}"
    output_font_path = os.path.join(os.path.dirname(__file__), 'fonts', f'debug_{font_hash}.woff2')
    os.makedirs(os.path.dirname(output_font_path), exist_ok=True)
    
    result = create_decryption_font_from_mappings(
        base_font_path, output_font_path, upper_map, lower_map, space_map
    )
    
    if result:
        # Load the generated font and check glyph mappings
        if isinstance(result, str):
            font_path = result  # TTF path
        else:
            font_path = output_font_path  # WOFF2 path
        
        # Load as TTF to check glyphs
        ttf_path = font_path.replace('.woff2', '.ttf')
        if os.path.exists(ttf_path):
            font = TTFont(ttf_path)
            cmap = font.getBestCmap()
            char_to_glyph = {chr(unicode_val): glyph_name for unicode_val, glyph_name in cmap.items()}
            glyf_table = font['glyf']
            
            print("\nChecking actual glyph mappings in generated font:")
            
            # Check 'K' glyph
            if 'K' in char_to_glyph:
                k_glyph = char_to_glyph['K']
                if k_glyph in glyf_table:
                    k_glyph_obj = glyf_table[k_glyph]
                    if hasattr(k_glyph_obj, 'coordinates'):
                        coords = k_glyph_obj.coordinates
                        print(f"K glyph '{k_glyph}' has {len(coords) if coords else 0} coordinates")
                        # Check if it matches space glyph
                        if ' ' in char_to_glyph:
                            space_glyph = char_to_glyph[' ']
                            if space_glyph in glyf_table:
                                space_glyph_obj = glyf_table[space_glyph]
                                if hasattr(space_glyph_obj, 'coordinates'):
                                    space_coords = space_glyph_obj.coordinates
                                    print(f"Space glyph '{space_glyph}' has {len(space_coords) if space_coords else 0} coordinates")
                                    if coords == space_coords:
                                        print("✅ K glyph matches space glyph (correct!)")
                                    else:
                                        print("❌ K glyph does NOT match space glyph")
            
            # Check 'J' glyph
            if 'J' in char_to_glyph:
                j_glyph = char_to_glyph['J']
                if j_glyph in glyf_table:
                    j_glyph_obj = glyf_table[j_glyph]
                    if hasattr(j_glyph_obj, 'coordinates'):
                        coords = j_glyph_obj.coordinates
                        print(f"J glyph '{j_glyph}' has {len(coords) if coords else 0} coordinates")
                        # Check if it matches K glyph
                        if 'K' in char_to_glyph:
                            k_glyph = char_to_glyph['K']
                            if k_glyph in glyf_table:
                                k_glyph_obj = glyf_table[k_glyph]
                                if hasattr(k_glyph_obj, 'coordinates'):
                                    k_coords = k_glyph_obj.coordinates
                                    if coords == k_coords:
                                        print("⚠️  J glyph matches K glyph (this would cause the bug!)")
                                    else:
                                        print("✅ J glyph does NOT match K glyph (correct)")

print("\n" + "=" * 70)
print("DEBUG COMPLETE")
print("=" * 70)

