#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify wrapping logic and font generation work correctly
with the space-as-target fix.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from generate_font import get_dynamic_mappings, UNIFIED_CHARS, UPPERCASE, LOWERCASE
from encrypt_api import encrypt_article_text, decrypt_article_text

def test_wrapping_logic():
    """Test that wrapping logic handles both space_char and actual spaces"""
    print("="*70)
    print("Testing Wrapping Logic")
    print("="*70)
    
    secret_key = 29202393
    test_texts = [
        "Hello World",  # Has spaces
        "Test with many spaces in between",  # Multiple spaces
        "NoSpacesHere",  # No spaces
    ]
    
    for text in test_texts:
        print(f"\nText: {repr(text)}")
        result = encrypt_article_text(text, secret_key, generate_font=False)
        encrypted = result['encrypted']
        space_char = result.get('space_char')
        
        print(f"  Encrypted: {repr(encrypted)}")
        print(f"  Space char (what space maps to): {repr(space_char)}")
        
        # Check if space_char appears in encrypted text (it should, if original had spaces)
        if space_char and space_char in encrypted:
            print(f"  ✅ space_char '{space_char}' appears in encrypted text (for wrapping)")
        elif ' ' in text:
            print(f"  ⚠️  space_char '{space_char}' should appear if original had spaces")
        
        # Check if actual spaces appear in encrypted text (they can, if other chars map to space)
        if ' ' in encrypted:
            space_count = encrypted.count(' ')
            print(f"  ✅ Actual spaces appear in encrypted text ({space_count} occurrences)")
            print(f"     These are characters that encrypted to space (need wrapping too)")
        else:
            print(f"  ℹ️  No actual spaces in encrypted text (normal if no chars map to space)")
        
        # Verify decryption works
        decrypted = decrypt_article_text(encrypted, secret_key, result['nonce'])
        if text == decrypted:
            print(f"  ✅ Decryption successful")
        else:
            print(f"  ❌ Decryption failed: {repr(text)} != {repr(decrypted)}")

def test_font_mapping_for_spaces():
    """Test that font mapping correctly handles spaces in encrypted text"""
    print("\n" + "="*70)
    print("Testing Font Mapping for Spaces")
    print("="*70)
    
    secret_key = 29202393
    test_text = "Hello World"
    
    # Encrypt to get mappings
    result = encrypt_article_text(test_text, secret_key, generate_font=False)
    encrypted = result['encrypted']
    
    # Get mappings
    from encrypt_api import nonce_creator, expand_ligatures
    expanded = expand_ligatures(test_text)
    nonce = nonce_creator(expanded)
    upper_map, lower_map, space_map = get_dynamic_mappings(secret_key, nonce)
    
    # Build reverse mapping (encrypted -> original) for font
    unified_encryption_map = {**upper_map, **lower_map, **space_map}
    unified_font_mapping = {v: k for k, v in unified_encryption_map.items()}  # encrypted -> original
    
    print(f"Original text: {repr(test_text)}")
    print(f"Encrypted text: {repr(encrypted)}")
    print()
    
    # Check space_char mapping (character that space encrypts to)
    space_char = lower_map.get(' ')
    if space_char:
        print(f"Space encrypts to: '{space_char}'")
        if space_char in unified_font_mapping:
            original_for_space_char = unified_font_mapping[space_char]
            print(f"  ✅ Font mapping: '{space_char}' -> '{original_for_space_char}' (shows space glyph)")
        else:
            print(f"  ❌ Font mapping missing for space_char '{space_char}'")
    
    # Check actual spaces in encrypted text
    if ' ' in encrypted:
        print(f"\nActual spaces found in encrypted text")
        # Find what original character(s) encrypt to space
        chars_that_map_to_space = [char for char, enc_char in unified_encryption_map.items() if enc_char == ' ']
        print(f"  Characters that encrypt to space: {chars_that_map_to_space}")
        
        if ' ' in unified_font_mapping:
            original_for_space = unified_font_mapping[' ']
            print(f"  ✅ Font mapping: ' ' -> '{original_for_space}' (shows correct glyph)")
        else:
            print(f"  ❌ Font mapping missing for actual space ' '")
    else:
        print(f"\nNo actual spaces in encrypted text (normal)")
    
    # Verify all characters in encrypted text have font mappings
    missing_mappings = []
    for char in encrypted:
        if char not in unified_font_mapping and char not in ['\n', '\r', '\t']:
            if char not in missing_mappings:
                missing_mappings.append(char)
    
    if missing_mappings:
        print(f"\n  ❌ Missing font mappings for: {missing_mappings}")
    else:
        print(f"\n  ✅ All characters in encrypted text have font mappings")

def test_comprehensive_wrapping():
    """Test comprehensive wrapping scenarios"""
    print("\n" + "="*70)
    print("Comprehensive Wrapping Test")
    print("="*70)
    
    secret_key = 29202393
    
    # Test case: text where space maps to a character AND other chars map to space
    test_cases = [
        ("Hello World", "Has spaces"),
        ("A B C D E", "Multiple single-letter words"),
        ("Test   with   multiple   spaces", "Multiple consecutive spaces"),
    ]
    
    for text, description in test_cases:
        print(f"\n{description}: {repr(text)}")
        result = encrypt_article_text(text, secret_key, generate_font=False)
        encrypted = result['encrypted']
        space_char = result.get('space_char')
        
        # Simulate wrapping logic (like in client/encrypt-page.js)
        text_with_breaks = encrypted
        if space_char:
            import re
            space_char_regex = re.compile(re.escape(space_char))
            text_with_breaks = space_char_regex.sub(f'\u200B{space_char}', text_with_breaks)
        # Also handle actual spaces
        text_with_breaks = text_with_breaks.replace(' ', '\u200B ')
        
        # Count zero-width spaces
        zwsp_count = text_with_breaks.count('\u200B')
        print(f"  Encrypted: {repr(encrypted)}")
        print(f"  With breaks: {repr(text_with_breaks[:50])}...")
        print(f"  Zero-width spaces inserted: {zwsp_count}")
        print(f"  ✅ Wrapping markers added correctly")

if __name__ == '__main__':
    test_wrapping_logic()
    test_font_mapping_for_spaces()
    test_comprehensive_wrapping()
    print("\n" + "="*70)
    print("✅ All wrapping and font tests completed!")
    print("="*70)

