#!/usr/bin/env python3
"""
Test script to find a nonce where space maps to 'K' and verify the font mapping
"""
from generate_font import get_dynamic_mappings, create_decryption_font_from_mappings
from encrypt_api import DEFAULT_SECRET_KEY
from fontTools.ttLib import TTFont
import os

sk = DEFAULT_SECRET_KEY
print(f"Using secret_key: {sk}\n")

# Try different nonces to find one where space maps to 'K'
print("Searching for nonce where space maps to 'K'...")
found_nonce = None
for nonce in range(100000, 200000, 1000):  # Check every 1000th nonce
    upper_map, lower_map, space_map = get_dynamic_mappings(sk, nonce)
    if lower_map.get(' ') == 'K':
        found_nonce = nonce
        print(f"✅ Found nonce {nonce} where space maps to 'K'")
        break

if not found_nonce:
    print("⚠️  Could not find nonce where space maps to 'K' in range 100000-200000")
    print("Trying a different range...")
    for nonce in range(1, 100000, 100):
        upper_map, lower_map, space_map = get_dynamic_mappings(sk, nonce)
        if lower_map.get(' ') == 'K':
            found_nonce = nonce
            print(f"✅ Found nonce {nonce} where space maps to 'K'")
            break

if not found_nonce:
    print("❌ Could not find nonce where space maps to 'K'")
    exit(1)

# Now verify the font mapping for this nonce
print(f"\n{'='*70}")
print(f"VERIFYING FONT MAPPING FOR NONCE {found_nonce}")
print(f"{'='*70}\n")

upper_map, lower_map, space_map = get_dynamic_mappings(sk, found_nonce)

print("Encryption mapping:")
print(f"  Space -> {repr(lower_map.get(' ', 'NOT FOUND'))}")
print(f"  K -> {repr(upper_map.get('K', 'NOT FOUND'))}")
print(f"  J -> {repr(upper_map.get('J', 'NOT FOUND'))}")

# Create unified font mapping
unified_encryption_map = {**upper_map, **lower_map}
unified_font_mapping = {v: k for k, v in unified_encryption_map.items()}

print("\nFont mapping (encrypted -> original):")
if 'K' in unified_font_mapping:
    print(f"  K -> {repr(unified_font_mapping['K'])}")
if 'J' in unified_font_mapping:
    print(f"  J -> {repr(unified_font_mapping['J'])}")
if ' ' in unified_font_mapping:
    print(f"  Space -> {repr(unified_font_mapping[' '])}")

# Check what character maps to space in the font
space_source = None
for enc_char, orig_char in unified_font_mapping.items():
    if orig_char == ' ':
        space_source = enc_char
        print(f"\n  Character {repr(enc_char)} displays space glyph")

# Generate font and verify
base_font_path = os.path.join(os.path.dirname(__file__), 'Supertest.ttf')
if not os.path.exists(base_font_path):
    print(f"\n⚠️  Base font not found: {base_font_path}")
    print("Skipping font generation test")
else:
    font_hash = f"test_space_to_k_{found_nonce}"
    output_font_path = os.path.join(os.path.dirname(__file__), 'fonts', f'test_{font_hash}.woff2')
    os.makedirs(os.path.dirname(output_font_path), exist_ok=True)
    
    print(f"\n{'='*70}")
    print("GENERATING FONT")
    print(f"{'='*70}\n")
    
    result = create_decryption_font_from_mappings(
        base_font_path, output_font_path, upper_map, lower_map, space_map
    )
    
    if result:
        ttf_path = output_font_path.replace('.woff2', '.ttf')
        if os.path.exists(ttf_path):
            font = TTFont(ttf_path)
            cmap = font.getBestCmap()
            char_to_glyph = {chr(unicode_val): glyph_name for unicode_val, glyph_name in cmap.items()}
            glyf_table = font['glyf']
            
            print(f"\n{'='*70}")
            print("VERIFYING GLYPH MAPPINGS IN GENERATED FONT")
            print(f"{'='*70}\n")
            
            # Check 'K' glyph
            if 'K' in char_to_glyph:
                k_glyph = char_to_glyph['K']
                if k_glyph in glyf_table:
                    k_glyph_obj = glyf_table[k_glyph]
                    if hasattr(k_glyph_obj, 'coordinates'):
                        k_coords = k_glyph_obj.coordinates
                        print(f"K glyph '{k_glyph}' has {len(k_coords) if k_coords else 0} coordinates")
                        
                        # Check if it matches space glyph
                        if ' ' in char_to_glyph:
                            space_glyph = char_to_glyph[' ']
                            if space_glyph in glyf_table:
                                space_glyph_obj = glyf_table[space_glyph]
                                if hasattr(space_glyph_obj, 'coordinates'):
                                    space_coords = space_glyph_obj.coordinates
                                    print(f"Space glyph '{space_glyph}' has {len(space_coords) if space_coords else 0} coordinates")
                                    
                                    if k_coords == space_coords:
                                        print("✅ K glyph matches space glyph (CORRECT!)")
                                    else:
                                        print("❌ K glyph does NOT match space glyph (BUG!)")
                                        print(f"   Expected: space glyph coordinates")
                                        print(f"   Got: K glyph coordinates")
            
            # Check 'J' glyph
            if 'J' in char_to_glyph:
                j_glyph = char_to_glyph['J']
                if j_glyph in glyf_table:
                    j_glyph_obj = glyf_table[j_glyph]
                    if hasattr(j_glyph_obj, 'coordinates'):
                        j_coords = j_glyph_obj.coordinates
                        print(f"\nJ glyph '{j_glyph}' has {len(j_coords) if j_coords else 0} coordinates")
                        
                        # Check if it matches K glyph (shouldn't)
                        if 'K' in char_to_glyph:
                            k_glyph = char_to_glyph['K']
                            if k_glyph in glyf_table:
                                k_glyph_obj = glyf_table[k_glyph]
                                if hasattr(k_glyph_obj, 'coordinates'):
                                    k_coords = k_glyph_obj.coordinates
                                    if j_coords == k_coords:
                                        print("⚠️  J glyph matches K glyph (this would cause the bug!)")
                                    else:
                                        print("✅ J glyph does NOT match K glyph (correct)")

print(f"\n{'='*70}")
print("TEST COMPLETE")
print(f"{'='*70}")

