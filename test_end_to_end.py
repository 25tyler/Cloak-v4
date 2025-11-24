#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
End-to-end test to verify wrapping logic and font generation work correctly
with the space-as-target fix.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from encrypt_api import encrypt_article_text, decrypt_article_text
from generate_font import get_dynamic_mappings

def test_end_to_end():
    """Complete end-to-end test"""
    print("="*70)
    print("END-TO-END TEST: Wrapping Logic + Font Generation")
    print("="*70)
    
    secret_key = 29202393
    test_cases = [
        "Hello World",
        "The quick brown fox jumps over the lazy dog",
        "Test with multiple   spaces",
        "A B C D E F G",
    ]
    
    all_passed = True
    
    for text in test_cases:
        print(f"\n{'='*70}")
        print(f"Test: {repr(text)}")
        print(f"{'='*70}")
        
        # Encrypt with font generation
        result = encrypt_article_text(text, secret_key, generate_font=True)
        encrypted = result['encrypted']
        space_char = result.get('space_char')
        nonce = result['nonce']
        
        print(f"✅ Encryption successful")
        print(f"   Encrypted: {repr(encrypted)}")
        print(f"   Space char: {repr(space_char)}")
        print(f"   Nonce: {nonce}")
        
        # Verify space_char is set
        if space_char is None:
            print(f"   ❌ ERROR: space_char is None (should be set for wrapping)")
            all_passed = False
        else:
            print(f"   ✅ space_char is set: '{space_char}'")
        
        # Check for actual spaces in encrypted text
        if ' ' in encrypted:
            space_count = encrypted.count(' ')
            print(f"   ✅ Actual spaces in encrypted text: {space_count} (characters that encrypted to space)")
        else:
            print(f"   ℹ️  No actual spaces in encrypted text")
        
        # Simulate wrapping logic (like client-side)
        text_with_breaks = encrypted
        if space_char:
            import re
            space_char_regex = re.compile(re.escape(space_char))
            text_with_breaks = space_char_regex.sub(f'\u200B{space_char}', text_with_breaks)
        text_with_breaks = text_with_breaks.replace(' ', '\u200B ')
        
        zwsp_count = text_with_breaks.count('\u200B')
        print(f"   ✅ Wrapping markers: {zwsp_count} zero-width spaces inserted")
        
        # Verify font mapping handles spaces correctly
        upper_map, lower_map, space_map = get_dynamic_mappings(secret_key, nonce)
        unified_map = {**upper_map, **lower_map, **space_map}
        unified_font_mapping = {v: k for k, v in unified_map.items()}  # encrypted -> original
        
        # Check space_char font mapping
        if space_char and space_char in unified_font_mapping:
            original_for_space_char = unified_font_mapping[space_char]
            if original_for_space_char == ' ':
                print(f"   ✅ Font mapping correct: '{space_char}' -> ' ' (shows space glyph)")
            else:
                print(f"   ❌ Font mapping incorrect: '{space_char}' -> '{original_for_space_char}' (should be ' ')")
                all_passed = False
        
        # Check actual space font mapping
        if ' ' in encrypted:
            if ' ' in unified_font_mapping:
                original_for_space = unified_font_mapping[' ']
                print(f"   ✅ Font mapping for actual space: ' ' -> '{original_for_space}' (shows correct glyph)")
            else:
                print(f"   ❌ Font mapping missing for actual space ' '")
                all_passed = False
        
        # Verify all encrypted characters have font mappings
        missing = []
        for char in encrypted:
            if char not in unified_font_mapping and char not in ['\n', '\r', '\t']:
                if char not in missing:
                    missing.append(char)
        
        if missing:
            print(f"   ❌ Missing font mappings: {missing}")
            all_passed = False
        else:
            print(f"   ✅ All encrypted characters have font mappings")
        
        # Verify decryption
        decrypted = decrypt_article_text(encrypted, secret_key, nonce)
        if text == decrypted:
            print(f"   ✅ Decryption successful: {repr(decrypted)}")
        else:
            print(f"   ❌ Decryption failed: {repr(text)} != {repr(decrypted)}")
            all_passed = False
    
    return all_passed

if __name__ == '__main__':
    success = test_end_to_end()
    print("\n" + "="*70)
    if success:
        print("✅ ALL END-TO-END TESTS PASSED!")
        print("   - Wrapping logic works correctly")
        print("   - Font generation handles spaces correctly")
        print("   - Encryption/decryption works correctly")
    else:
        print("❌ SOME TESTS FAILED!")
    print("="*70)
    sys.exit(0 if success else 1)

