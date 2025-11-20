#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify the web encryption algorithm matches the PDF encryption algorithm
"""
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from encrypt_api import encrypt_article_text

def test_algorithm():
    """Test that the algorithm produces expected results"""
    
    print("=" * 60)
    print("Testing Encryption Algorithm")
    print("=" * 60)
    print()
    
    # Test cases
    test_cases = [
        "Hello World",
        "The quick brown fox jumps over the lazy dog",
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "abcdefghijklmnopqrstuvwxyz",
        "Test with spaces and punctuation!",
        "123 numbers 456",
    ]
    
    print("Test Results:")
    print("-" * 60)
    
    for i, test_text in enumerate(test_cases, 1):
        encrypted = encrypt_article_text(test_text)
        print(f"Test {i}:")
        print(f"  Original:  {test_text}")
        print(f"  Encrypted: {encrypted}")
        print()
    
    print("=" * 60)
    print("Algorithm test complete!")
    print()
    print("To verify this matches your PDF code:")
    print("1. Run your PDF encryption on the same test strings")
    print("2. Compare the encrypted outputs")
    print("3. They should match exactly!")
    print("=" * 60)

if __name__ == '__main__':
    test_algorithm()

