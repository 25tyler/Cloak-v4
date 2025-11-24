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
from Fiesty import enc27, enc54, dec54
UPPERCASE = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
LOWERCASE = "abcdefghijklmnopqrstuvwxyz ."  # Includes space and period (28 characters)
# Unified character set: uppercase (0-25) + lowercase+space+period (26-53) = 54 total
UNIFIED_CHARS = UPPERCASE + LOWERCASE  # 26 + 28 = 54 characters

def generate_unified_mapping(sk: int, nonce: int) -> dict:
    """
    Generate unified character mapping using Feistel cipher for all 54 characters.
    Maps each character in UNIFIED_CHARS to its encrypted version.
    Creates one big cycle: uppercase (0-25) + lowercase+space+period (26-53).
    
    Args:
        sk: Secret key
        nonce: Nonce value
    
    Returns:
        Dictionary mapping original char -> encrypted char
    """
    mapping = {}
    used_chars = set()  # Track which characters are already mapped to
    
    # First pass: map all positions that encrypt to valid range
    for i, char in enumerate(UNIFIED_CHARS):
        encrypted_pos = enc54(sk, nonce, i)
        if encrypted_pos < len(UNIFIED_CHARS):
            target_char = UNIFIED_CHARS[encrypted_pos]
            mapping[char] = target_char
            used_chars.add(target_char)
    
    # Second pass: handle positions that encrypt outside range (shouldn't happen with enc54, but safety)
    for i, char in enumerate(UNIFIED_CHARS):
        if char not in mapping:
            encrypted_pos = enc54(sk, nonce, i)
            # Wrap to valid range
            target_pos = encrypted_pos % len(UNIFIED_CHARS)
            target_char = UNIFIED_CHARS[target_pos]
            # If target is already used, find first unused
            if target_char in used_chars:
                for j in range(len(UNIFIED_CHARS)):
                    candidate = UNIFIED_CHARS[j]
                    if candidate not in used_chars:
                        target_char = candidate
                        break
            mapping[char] = target_char
            used_chars.add(target_char)
    
    return mapping

def generate_char_mapping(sk: int, nonce: int, char_set: str) -> dict:
    """
    Generate dynamic character mapping using Feistel cipher.
    Maps each character in char_set to its encrypted version.
    Shared by the API and font generator to keep a single source of truth.
    
    CRITICAL: Ensures bijective (one-to-one) mapping to prevent collisions.
    When position 26 wraps, it uses the first available unused character.
    
    Args:
        sk: Secret key
        nonce: Nonce value
        char_set: String of characters to map (e.g., "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    
    Returns:
        Dictionary mapping original char -> encrypted char
    """
    mapping = {}
    used_chars = set()  # Track which characters are already mapped to
    
    # First pass: map all positions that encrypt to < 26
    for i, char in enumerate(char_set):
        encrypted_pos = enc27(sk, nonce, i)
        if encrypted_pos < len(char_set):
            target_char = char_set[encrypted_pos]
            mapping[char] = target_char
            used_chars.add(target_char)
    
    # Second pass: handle positions that encrypt to 26 (wrap to unused character)
    for i, char in enumerate(char_set):
        encrypted_pos = enc27(sk, nonce, i)
        if encrypted_pos >= len(char_set):  # Position 26
            # Find first unused character to avoid collision
            for j in range(len(char_set)):
                candidate = char_set[j]
                if candidate not in used_chars:
                    mapping[char] = candidate
                    used_chars.add(candidate)
                    break
            else:
                # Should never happen (26 positions, 26 characters)
                # But fallback: use modulo
                mapping[char] = char_set[encrypted_pos % len(char_set)]
    
    return mapping

def get_dynamic_mappings(sk: int, nonce: int) -> tuple:
    """
    Get unified dynamic mapping for all 54 characters (uppercase + lowercase + space + period).
    Returns (unified_map, unified_map, space_map) for compatibility.
    
    Uses a single Feistel cipher cycle for all characters.
    The font will handle case differences in rendering.
    
    CRITICAL: All 54 characters (including space) must be used as targets in the cycle.
    Space can be a target (other characters can map to it), but space itself should not map to space.
    """
    # Generate unified mapping for all 54 characters
    unified_map = generate_unified_mapping(sk, nonce)
    
    # CRITICAL: Ensure space does not map to itself (to prevent CSS line breaks).
    # But space CAN be used as a target by other characters - all 54 characters must be in the cycle.
    if unified_map.get(' ', ' ') == ' ':
        # Space maps to itself - we need to swap it with another character
        # Find a character that doesn't map to space, and swap their targets
        for char in UNIFIED_CHARS:
            if char != ' ' and unified_map.get(char) != ' ':
                # Swap: space -> char's target, char -> space
                char_target = unified_map[char]
                unified_map[' '] = char_target
                unified_map[char] = ' '
                break
    
    # Fix bijectivity issues (duplicates) in a loop
    # This ensures the mapping is one-to-one (bijective) so decryption works correctly
    # Key insight: All 54 characters (including space) must be used as both sources and targets
    # The only constraint is that space should not map to itself
    max_iterations = 100
    iterations_used = 0
    for iteration in range(max_iterations):
        iterations_used = iteration + 1
        # CRITICAL: Snapshot current state before checking for duplicates
        # This ensures we're working with consistent data
        current_state = dict(unified_map)
        
        # Build target -> sources mapping to find duplicates
        # Use the snapshot to ensure consistency
        target_to_sources = {}
        for source, target in current_state.items():
            if target not in target_to_sources:
                target_to_sources[target] = []
            target_to_sources[target].append(source)
        
        # Collect all sources that need reassignment (duplicates and space->space)
        sources_to_reassign = []
        for target, sources in target_to_sources.items():
            if target == ' ' and ' ' in sources:
                # Space is mapping to itself - reassign space (keep others that map to space)
                sources_to_reassign.append(' ')
            elif len(sources) > 1:
                # Multiple sources map to same target - keep first, reassign ALL others
                sources_to_reassign.extend(sources[1:])
        
        # If no issues found, we're done
        if not sources_to_reassign:
            break
        
        # Remove duplicates from sources_to_reassign (a source might appear multiple times)
        sources_to_reassign = list(dict.fromkeys(sources_to_reassign))
        
        # Reassign each problematic source
        # Process in a stable order to ensure deterministic results
        # CRITICAL: Rebuild used_targets for each source to account for previous reassignments
        current_duplicate_targets = {target for target, sources in target_to_sources.items() 
                                    if len(sources) > 1}
        
        # CRITICAL: Process sources one at a time and rebuild state after each reassignment
        # This ensures we're always working with the current state, not stale data
        for source in sorted(sources_to_reassign):
            old_target = unified_map[source]
            
            # Build used_targets: all targets currently used by other sources
            # Exclude the current source from consideration
            # CRITICAL: Rebuild this from the CURRENT state of unified_map (which may have been modified by previous reassignments)
            used_targets = {t for s, t in unified_map.items() if s != source}
            
            # Find an unused target
            # For space: can use any target except space itself
            # For others: can use any target (including space, but not the old_target)
            reassigned = False
            # First try: unused targets without duplicates
            for candidate in UNIFIED_CHARS:
                if source == ' ':
                    # Space cannot map to itself
                    if candidate == ' ':
                        continue
                else:
                    # Other characters cannot map to their old target
                    if candidate == old_target:
                        continue
                
                if candidate not in used_targets and candidate not in current_duplicate_targets:
                    unified_map[source] = candidate
                    reassigned = True
                    break
            
            # Second try: unused targets even if they have duplicates (will create new duplicate, but next iteration fixes)
            if not reassigned:
                for candidate in UNIFIED_CHARS:
                    if source == ' ':
                        # Space cannot map to itself
                        if candidate == ' ':
                            continue
                    else:
                        # Other characters cannot map to their old target
                        if candidate == old_target:
                            continue
                    
                    if candidate not in used_targets:
                        unified_map[source] = candidate
                        reassigned = True
                        break
            
            # If no unused target available, we need to do a swap
            # This happens when all targets are already used
            # Strategy: Swap source with ANY other source to break the duplicate
            if not reassigned:
                # Find any source we can swap with (excluding source itself)
                for swap_source in UNIFIED_CHARS:
                    if swap_source == source:
                        continue
                    
                    swap_source_target = current_state.get(swap_source)
                    if swap_source_target is None:
                        continue
                    
                    # For space: cannot swap to space
                    if source == ' ' and swap_source_target == ' ':
                        continue
                    
                    # For others: cannot swap to old_target
                    if source != ' ' and swap_source_target == old_target:
                        continue
                    
                    # Direct swap: source -> swap_source_target, swap_source -> old_target
                    # This will work as long as swap_source_target != old_target
                    if swap_source_target != old_target:
                        unified_map[source] = swap_source_target
                        unified_map[swap_source] = old_target
                        reassigned = True
                        break
            
            # Last resort: assign to any target (will create duplicate, next iteration fixes it)
            if not reassigned:
                for candidate in UNIFIED_CHARS:
                    if source == ' ':
                        # Space cannot map to itself
                        if candidate == ' ':
                            continue
                    else:
                        # Other characters cannot map to their old target
                        if candidate == old_target:
                            continue
                    
                    unified_map[source] = candidate
                    reassigned = True
                    break
    
    # Split unified_map into upper_map and lower_map for compatibility
    # But they're actually the same unified mapping
    upper_map = {char: unified_map[char] for char in UPPERCASE if char in unified_map}
    lower_map = {char: unified_map[char] for char in LOWERCASE if char in unified_map}
    
    # Special characters (null -> newline) - kept for font display purposes
    space_map = {"\x00": "\n"}
    
    return upper_map, lower_map, space_map

def swap_glyphs_in_font(font, font_mapping_upper, font_mapping_lower, font_mapping_special):
    """
    Apply the encrypted->original permutation at the glyph level.
    We take a snapshot of all source glyphs/metrics first, then rewrite the
    destination glyphs from the snapshot so cycles don't overwrite each other.
    Returns the number of successful swaps.
    """
    cmap = font.getBestCmap()
    char_to_glyph = {chr(unicode_val): glyph_name for unicode_val, glyph_name in cmap.items()}
    glyf_table = font['glyf']
    hmtx = font['hmtx'] if 'hmtx' in font else None

    # DEBUG: Check if space is in character map
    if ' ' in char_to_glyph:
        print(f"  DEBUG: Space found in font character map: ' ' -> glyph '{char_to_glyph[' ']}'")
    else:
        print(f"  ⚠️  WARNING: Space NOT found in font character map!")
        print(f"     Available characters in font: {sorted([c for c in char_to_glyph.keys() if c.isprintable()])[:20]}...")
    
    # Build a unified mapping list (dest_glyph, src_glyph, display strings)
    mappings = []
    dest_glyph_seen = {}  # Track which dest_glyphs we've seen to detect duplicates
    for mapping in (font_mapping_upper, font_mapping_lower, font_mapping_special):
        for encrypted_char, original_char in mapping.items():
            if original_char in char_to_glyph and encrypted_char in char_to_glyph:
                src_glyph = char_to_glyph[original_char]
                dest_glyph = char_to_glyph[encrypted_char]
                # Check for duplicate dest_glyph (shouldn't happen if bijective, but verify)
                if dest_glyph in dest_glyph_seen:
                    prev_enc, prev_orig = dest_glyph_seen[dest_glyph]
                    print(f"  ⚠️  WARNING: Duplicate dest_glyph '{dest_glyph}':")
                    print(f"     Previously: {repr(prev_enc)} -> {repr(prev_orig)}")
                    print(f"     Now: {repr(encrypted_char)} -> {repr(original_char)}")
                    print(f"     This will cause the second mapping to overwrite the first!")
                else:
                    dest_glyph_seen[dest_glyph] = (encrypted_char, original_char)
                mappings.append((dest_glyph, src_glyph, encrypted_char, original_char))
            else:
                missing = []
                if original_char not in char_to_glyph:
                    missing.append(f"original {repr(original_char)}")
                if encrypted_char not in char_to_glyph:
                    missing.append(f"encrypted {repr(encrypted_char)}")
                # Special debug for space
                if encrypted_char == ' ' or original_char == ' ':
                    print(f"  ⚠️  CRITICAL: Space mapping skipped!")
                    print(f"     encrypted_char: {repr(encrypted_char)}, original_char: {repr(original_char)}")
                    print(f"     missing: {', '.join(missing)}")
                    print(f"     char_to_glyph has space: {' ' in char_to_glyph}")
                else:
                    print(f"  Skipped: {repr(encrypted_char)} -> {repr(original_char)} (missing: {', '.join(missing)})")

    # Snapshot source glyphs and metrics so cycles can't clobber later copies
    # Also store original character widths for verification
    glyph_snapshot = {}
    metrics_snapshot = {}
    original_widths = {}  # Store original char -> width mapping for verification
    for _, src_glyph, _, original_char in mappings:
        if src_glyph in glyf_table:
            glyph_snapshot[src_glyph] = copy.deepcopy(glyf_table[src_glyph])
        if hmtx and src_glyph in hmtx.metrics:
            # hmtx.metrics is a dict mapping glyph names to (advanceWidth, leftSideBearing) tuples
            metrics_snapshot[src_glyph] = copy.deepcopy(hmtx.metrics[src_glyph])
            # Store original width for this character (for verification)
            original_widths[original_char] = hmtx.metrics[src_glyph][0]  # advanceWidth
    
    # Pre-calculate fallback metrics once (for efficiency)
    fallback_metrics = {}
    if hmtx:
        # Get actual space metrics if available
        space_glyph = char_to_glyph.get(' ')
        if space_glyph and space_glyph in hmtx.metrics:
            fallback_metrics['space'] = copy.deepcopy(hmtx.metrics[space_glyph])
        
        # Calculate average letter metrics
        letter_glyphs = [char_to_glyph.get(c) for c in UPPERCASE + LOWERCASE 
                        if c in char_to_glyph and char_to_glyph[c] in hmtx.metrics]
        if letter_glyphs:
            letter_widths = [hmtx.metrics[g][0] for g in letter_glyphs]
            letter_lsbs = [hmtx.metrics[g][1] for g in letter_glyphs]
            fallback_metrics['letter'] = (
                sum(letter_widths) // len(letter_widths),
                sum(letter_lsbs) // len(letter_lsbs) if letter_lsbs else 0
            )
        
        # Font defaults as last resort
        units_per_em = font['head'].unitsPerEm if 'head' in font else 1000
        if 'space' not in fallback_metrics:
            fallback_metrics['space'] = (int(units_per_em * 0.2), 0)
        if 'letter' not in fallback_metrics:
            fallback_metrics['letter'] = (int(units_per_em * 0.5), 0)

    swaps_made = 0
    for dest_glyph, src_glyph, encrypted_char, original_char in mappings:
        try:
            if src_glyph in glyph_snapshot and dest_glyph in glyf_table:
                # Copy the glyph outline
                # Directly assign the glyph from snapshot (fontTools handles this correctly)
                src_glyph_obj = glyph_snapshot[src_glyph]
                # Simply assign - fontTools will handle the copy internally
                glyf_table[dest_glyph] = copy.deepcopy(src_glyph_obj)
                # Copy the horizontal metrics (advance width and left side bearing)
                # CRITICAL: Always use source metrics for zero visual change
                # Source metrics = what original text used = what we must preserve exactly
                # This ensures encrypted text has identical layout to original
                if hmtx:
                    source_metrics = None
                    used_fallback = False
                    
                    # CRITICAL: Always use snapshot - never read from hmtx.metrics after modifications
                    # The snapshot was taken BEFORE any modifications, so it's the source of truth
                    if src_glyph in metrics_snapshot:
                        source_metrics = copy.deepcopy(metrics_snapshot[src_glyph])
                    
                    # Fallback only if source glyph wasn't in snapshot (shouldn't happen, but safety)
                    if not source_metrics:
                        used_fallback = True
                        if original_char == ' ':
                            # Use actual space metrics if available, otherwise fallback
                            source_metrics = fallback_metrics.get('space', (500, 0))
                        elif original_char.isalpha():
                            # Use average letter metrics
                            source_metrics = fallback_metrics.get('letter', (500, 0))
                        else:
                            # For other characters, use letter metrics as default
                            source_metrics = fallback_metrics.get('letter', (500, 0))
                    
                    # Always set metrics (never leave glyph without)
                    # This overwrites any existing metrics on dest_glyph with source metrics
                    hmtx.metrics[dest_glyph] = source_metrics
                    
                    # Verify exact width preservation (for zero visual change)
                    if not used_fallback and original_char in original_widths:
                        expected_width = original_widths[original_char]
                        actual_width = source_metrics[0]
                        if expected_width != actual_width:
                            print(f"  ⚠️  Width mismatch: {repr(original_char)} expected {expected_width}, got {actual_width}")
                        # else: Width preserved exactly (silent success)
                    
                    # Warn if we used fallback (helps debug layout issues)
                    if used_fallback:
                        print(f"  Warning: Used fallback metrics for {repr(original_char)} -> {repr(encrypted_char)} "
                              f"(source glyph {src_glyph} had no metrics)")
                swaps_made += 1
                enc_disp = repr(encrypted_char) if encrypted_char in [' ', '\x00', '\n'] else f"'{encrypted_char}'"
                orig_disp = repr(original_char) if original_char in [' ', '\x00', '\n'] else f"'{original_char}'"
                # Special debug for space to check width and glyph outline
                if encrypted_char == ' ':
                    width_info = ""
                    outline_info = ""
                    if hmtx and dest_glyph in hmtx.metrics:
                        width_info = f" (width: {hmtx.metrics[dest_glyph][0]})"
                    # Check if glyph has outline (is not empty)
                    if dest_glyph in glyf_table:
                        glyph_obj = glyf_table[dest_glyph]
                        if hasattr(glyph_obj, 'numberOfContours'):
                            if glyph_obj.numberOfContours > 0:
                                outline_info = f" (has {glyph_obj.numberOfContours} contours)"
                            else:
                                outline_info = " (EMPTY OUTLINE - this will be invisible!)"
                        elif hasattr(glyph_obj, 'data') and glyph_obj.data:
                            outline_info = " (has outline data)"
                        else:
                            outline_info = " (NO OUTLINE DATA - this will be invisible!)"
                    print(f"  Swapped: {enc_disp} now shows {orig_disp} glyph{width_info}{outline_info}")
                else:
                    print(f"  Swapped: {enc_disp} now shows {orig_disp} glyph")
        except Exception as e:
            print(f"  Warning: Could not swap {repr(encrypted_char)} -> {repr(original_char)}: {e}")

    return swaps_made

def create_decryption_font_from_mappings(input_font_path, output_font_path, upper_map, lower_map, space_map):
    """
    Create a decryption font using pre-computed unified mappings.
    This avoids recalculating mappings that were already computed during encryption.
    
    Args:
        input_font_path: Path to the base font file
        output_font_path: Path where the decryption font will be saved
        upper_map: Dictionary mapping original -> encrypted for uppercase (from get_dynamic_mappings)
        lower_map: Dictionary mapping original -> encrypted for lowercase + space (from get_dynamic_mappings)
        space_map: Dictionary mapping original -> encrypted for special chars only (from get_dynamic_mappings)
    """
    print(f"Loading font: {input_font_path}")
    font = TTFont(input_font_path)
    
    # Create unified reverse mapping for the font (encrypted -> original)
    # With unified mapping, we need to combine all mappings into one
    # When encrypted text is displayed, we want to show original glyphs
    # Since we have cross-case mappings, we need a unified font mapping
    # IMPORTANT: Space CAN appear in encrypted text (as a target from other characters).
    # The character that space encrypts to (e.g., 'B') SHOULD be in the font mapping to show the space glyph.
    # When space appears in encrypted text, it should show the glyph of the character that maps to space.
    unified_encryption_map = {**upper_map, **lower_map}
    unified_font_mapping = {v: k for k, v in unified_encryption_map.items()}  # encrypted -> original (unified)
    
    # Split into upper/lower for compatibility with swap_glyphs_in_font
    # But we need to ensure all encrypted characters are covered
    font_mapping_upper = {}
    font_mapping_lower = {}
    
    # Populate font mappings based on the encrypted character's case
    # This ensures cross-case mappings are handled correctly
    # CRITICAL: Space CAN appear in encrypted text (as a target), so we need to handle it
    # If space appears in encrypted text, it should show the glyph of whatever character maps to space
    # CRITICAL: Include period (.) and other non-alphabetic characters from LOWERCASE
    for encrypted_char, original_char in unified_font_mapping.items():
        if encrypted_char.isupper():
            font_mapping_upper[encrypted_char] = original_char
        elif encrypted_char.islower() or encrypted_char in LOWERCASE or encrypted_char == ' ':
            # Include lowercase letters, non-alphabetic chars from LOWERCASE (like period), and space
            font_mapping_lower[encrypted_char] = original_char
    
    # DEBUG: Print space mapping to verify it's included
    if ' ' in font_mapping_lower:
        space_target = font_mapping_lower[' ']
        print(f"  DEBUG: Space in font_mapping_lower: ' ' -> {repr(space_target)}")
        print(f"         This means when space appears in encrypted text, it should show the '{space_target}' glyph")
        # Check if space_target is also in the font mapping (shouldn't be, but verify)
        if space_target in unified_font_mapping:
            print(f"  ⚠️  WARNING: '{space_target}' is also in unified_font_mapping as a key!")
            print(f"         This could cause conflicts. Space should map to a character that doesn't appear in encrypted text.")
    else:
        print(f"  ⚠️  WARNING: Space NOT in font_mapping_lower!")
        print(f"     unified_font_mapping keys: {sorted(unified_font_mapping.keys())}")
        if ' ' in unified_font_mapping:
            print(f"     Space IS in unified_font_mapping: ' ' -> {repr(unified_font_mapping[' '])}")
            print(f"     But it wasn't added to font_mapping_lower - this is a bug!")
    
    font_mapping_special = {v: k for k, v in space_map.items()}  # encrypted -> original
    
    # CRITICAL: Also map non-breaking space (U+00A0) to the same glyph as regular space (U+0020)
    # This allows the client to replace spaces with non-breaking spaces to prevent line breaks
    # while still rendering the correct glyph
    if ' ' in font_mapping_lower:
        # Non-breaking space should show the same glyph as regular space
        font_mapping_lower['\u00A0'] = font_mapping_lower[' ']
        print(f"  DEBUG: Added non-breaking space mapping: '\\u00A0' -> {repr(font_mapping_lower[' '])}")
    
    print("Swapping glyphs...")
    swaps_made = swap_glyphs_in_font(font, font_mapping_upper, font_mapping_lower, font_mapping_special)
    
    print(f"\nMade {swaps_made} glyph swaps")
    
    # Update font family name
    if 'name' in font:
        name_table = font['name']
        for record in name_table.names:
            if record.nameID == 1:  # Family name
                record.string = 'EncryptedFont'  # Must match CONFIG.fontName in encrypt-page.js
        print("Updated font family name to 'EncryptedFont'")
    
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
        print(f"   Will use TTF file instead: {ttf_output}")
        # Return TTF path instead of WOFF2 path
        return ttf_output  # Return TTF path so caller knows to use it

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
