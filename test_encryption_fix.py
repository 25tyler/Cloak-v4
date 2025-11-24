#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive test script to verify the encryption fix.
Tests that:
1. All 54 characters (including space) are used as targets in the cycle
2. No duplication occurs in the mapping
3. Encryption and decryption work correctly
4. Round-trip encryption/decryption preserves original text
"""

import sys
import os
from collections import Counter

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from generate_font import get_dynamic_mappings, UNIFIED_CHARS, UPPERCASE, LOWERCASE
from encrypt_api import encrypt_article_text, decrypt_article_text, nonce_creator
from Fiesty import enc54

def test_mapping_bijectivity(secret_key, nonce):
    """Test that the mapping is bijective (one-to-one, no duplicates)"""
    print(f"\n{'='*70}")
    print(f"Testing mapping bijectivity (secret_key={secret_key}, nonce={nonce})")
    print(f"{'='*70}")
    
    upper_map, lower_map, space_map = get_dynamic_mappings(secret_key, nonce)
    
    # Combine all mappings
    unified_map = {**upper_map, **lower_map, **space_map}
    
    # Check that all 54 characters are mapped
    missing_sources = set(UNIFIED_CHARS) - set(unified_map.keys())
    if missing_sources:
        print(f"❌ ERROR: Missing sources in mapping: {missing_sources}")
        return False
    else:
        print(f"✅ All {len(UNIFIED_CHARS)} characters are mapped as sources")
    
    # Check that all 54 characters are used as targets
    all_targets = set(unified_map.values())
    missing_targets = set(UNIFIED_CHARS) - all_targets
    if missing_targets:
        print(f"❌ ERROR: Missing targets in mapping: {missing_targets}")
        print(f"   This means some characters are not used as targets, causing duplication!")
        return False
    else:
        print(f"✅ All {len(UNIFIED_CHARS)} characters are used as targets")
    
    # Check for duplicates (multiple sources mapping to same target)
    target_counts = Counter(unified_map.values())
    duplicates = {target: count for target, count in target_counts.items() if count > 1}
    if duplicates:
        print(f"❌ ERROR: Found duplicates in mapping:")
        for target, count in duplicates.items():
            sources = [s for s, t in unified_map.items() if t == target]
            print(f"   Target '{target}' is mapped by {count} sources: {sources}")
        return False
    else:
        print(f"✅ No duplicates found - mapping is bijective")
    
    # Check that space is used as a target
    if ' ' in all_targets:
        space_sources = [s for s, t in unified_map.items() if t == ' ']
        print(f"✅ Space is used as a target (mapped by: {space_sources})")
    else:
        print(f"❌ ERROR: Space is NOT used as a target!")
        return False
    
    # Check that space does not map to itself
    if unified_map.get(' ') == ' ':
        print(f"❌ ERROR: Space maps to itself (should not happen)")
        return False
    else:
        print(f"✅ Space does not map to itself (maps to: '{unified_map.get(' ')}')")
    
    return True

def test_encryption_decryption(text, secret_key):
    """Test that encryption and decryption work correctly"""
    print(f"\n{'='*70}")
    print(f"Testing encryption/decryption")
    print(f"{'='*70}")
    print(f"Original text: {repr(text)}")
    
    # Encrypt
    encryption_result = encrypt_article_text(text, secret_key, generate_font=False)
    encrypted = encryption_result['encrypted']
    nonce = encryption_result['nonce']
    
    print(f"Encrypted text: {repr(encrypted)}")
    print(f"Nonce: {nonce}")
    
    # Decrypt
    decrypted = decrypt_article_text(encrypted, secret_key, nonce)
    print(f"Decrypted text: {repr(decrypted)}")
    
    # Check round-trip
    if text == decrypted:
        print(f"✅ Round-trip successful: original == decrypted")
        return True
    else:
        print(f"❌ Round-trip failed: original != decrypted")
        print(f"   Original length: {len(text)}")
        print(f"   Decrypted length: {len(decrypted)}")
        # Show differences
        for i, (orig_char, decr_char) in enumerate(zip(text, decrypted)):
            if orig_char != decr_char:
                print(f"   First difference at position {i}: '{orig_char}' != '{decr_char}'")
                break
        return False

def test_multiple_texts():
    """Test with multiple different texts"""
    print(f"\n{'='*70}")
    print(f"Testing with multiple texts")
    print(f"{'='*70}")
    
    test_cases = [
        ("Hello World", 29202393),
        ("The quick brown fox jumps over the lazy dog", 29202393),
        ("A" * 100, 29202393),
        ("Hello World", 12345),
        ("Test with spaces and punctuation. Yes!", 29202393),
        ("UPPERCASE AND lowercase mixed", 29202393),
        ("", 29202393),  # Empty string
        ("a", 29202393),  # Single character
        (" ", 29202393),  # Single space
        ("  ", 29202393),  # Multiple spaces
    ]
    
    all_passed = True
    for text, secret_key in test_cases:
        nonce = nonce_creator(text)
        print(f"\n--- Test: {repr(text[:50])} (secret_key={secret_key}) ---")
        
        # Test mapping bijectivity
        if not test_mapping_bijectivity(secret_key, nonce):
            all_passed = False
            continue
        
        # Test encryption/decryption
        if not test_encryption_decryption(text, secret_key):
            all_passed = False
    
    return all_passed

def test_space_as_target():
    """Specifically test that space is used as a target"""
    print(f"\n{'='*70}")
    print(f"Testing space as target (specific test)")
    print(f"{'='*70}")
    
    secret_key = 29202393
    test_texts = [
        "Hello World",
        "Test with spaces",
        "A B C D E",
    ]
    
    all_passed = True
    for text in test_texts:
        nonce = nonce_creator(text)
        upper_map, lower_map, space_map = get_dynamic_mappings(secret_key, nonce)
        unified_map = {**upper_map, **lower_map, **space_map}
        
        # Check that space is a target
        all_targets = set(unified_map.values())
        if ' ' not in all_targets:
            print(f"❌ ERROR: Space is not a target in mapping for text: {repr(text)}")
            all_passed = False
        else:
            space_sources = [s for s, t in unified_map.items() if t == ' ']
            print(f"✅ Space is a target (mapped by: {space_sources}) for text: {repr(text)}")
    
    return all_passed

def main():
    """Run all tests"""
    print("="*70)
    print("COMPREHENSIVE ENCRYPTION FIX TEST SUITE")
    print("="*70)
    print("\nThis test suite verifies that:")
    print("1. All 54 characters (including space) are used as targets")
    print("2. No duplication occurs in the mapping")
    print("3. Encryption and decryption work correctly")
    print("4. Round-trip encryption/decryption preserves original text")
    
    all_tests_passed = True
    
    # Test 1: Mapping bijectivity with different keys/nonces
    print("\n" + "="*70)
    print("TEST 1: Mapping Bijectivity")
    print("="*70)
    test_keys = [29202393, 12345, 99999]
    test_nonces = [100000, 200000, 300000]
    
    for sk in test_keys:
        for nonce in test_nonces:
            if not test_mapping_bijectivity(sk, nonce):
                all_tests_passed = False
    
    # Test 2: Space as target
    if not test_space_as_target():
        all_tests_passed = False
    
    # Test 3: Multiple texts encryption/decryption
    if not test_multiple_texts():
        all_tests_passed = False
    
    # Final summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    if all_tests_passed:
        print("✅ ALL TESTS PASSED!")
        return 0
    else:
        print("❌ SOME TESTS FAILED!")
        return 1

if __name__ == '__main__':
    sys.exit(main())

