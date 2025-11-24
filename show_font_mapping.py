#!/usr/bin/env python3
from generate_font import get_dynamic_mappings
from encrypt_api import nonce_creator, expand_ligatures, DEFAULT_SECRET_KEY

# Use the default secret key
sk = DEFAULT_SECRET_KEY
print(f"Using secret_key: {sk}")

# Get a sample text to calculate nonce (or use a specific one)
test_text = "Hello World"
nonce = nonce_creator(expand_ligatures(test_text))
print(f"Using nonce: {nonce}\n")

upper_map, lower_map, space_map = get_dynamic_mappings(sk, nonce)

print("=" * 60)
print("ENCRYPTION MAPPING (original -> encrypted)")
print("=" * 60)
print("\nUppercase:")
for char in sorted(upper_map.keys()):
    print(f"  {repr(char)} -> {repr(upper_map[char])}")

print("\nLowercase (includes space):")
for char in sorted(lower_map.keys()):
    if char == ' ':
        print(f"  {repr(char)} (space) -> {repr(lower_map[char])}")
    else:
        print(f"  {repr(char)} -> {repr(lower_map[char])}")

print("\nSpecial:")
for char in sorted(space_map.keys()):
    print(f"  {repr(char)} -> {repr(space_map[char])}")

print("\n" + "=" * 60)
print("FONT MAPPING (encrypted -> original)")
print("=" * 60)
print("(This is what the font uses to display encrypted text)")

font_mapping_upper = {v: k for k, v in upper_map.items()}
font_mapping_lower = {v: k for k, v in lower_map.items()}
font_mapping_special = {v: k for k, v in space_map.items()}

print("\nUppercase:")
for char in sorted(font_mapping_upper.keys()):
    print(f"  {repr(char)} -> {repr(font_mapping_upper[char])}")

print("\nLowercase:")
for char in sorted(font_mapping_lower.keys()):
    if font_mapping_lower[char] == ' ':
        print(f"  {repr(char)} -> {repr(font_mapping_lower[char])} (space)")
    else:
        print(f"  {repr(char)} -> {repr(font_mapping_lower[char])}")

print("\nSpecial:")
for char in sorted(font_mapping_special.keys()):
    print(f"  {repr(char)} -> {repr(font_mapping_special[char])}")

print("\n" + "=" * 60)
print("VERIFICATION")
print("=" * 60)
# Check bijectivity
targets_lower = list(lower_map.values())
duplicates_lower = [t for t in set(targets_lower) if targets_lower.count(t) > 1]
targets_upper = list(upper_map.values())
duplicates_upper = [t for t in set(targets_upper) if targets_upper.count(t) > 1]

print(f"Lowercase duplicates: {duplicates_lower if duplicates_lower else 'None ✅'}")
print(f"Uppercase duplicates: {duplicates_upper if duplicates_upper else 'None ✅'}")
chars_to_space = [k for k, v in lower_map.items() if v == ' ']
print(f"Characters mapping to space: {chars_to_space if chars_to_space else 'None ✅'}")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"Space encrypts to: {repr(lower_map.get(' ', 'NOT_FOUND'))}")
space_char = lower_map.get(' ', 'NOT_FOUND')
if space_char != 'NOT_FOUND':
    print(f"Character '{space_char}' will display as space in the font")

