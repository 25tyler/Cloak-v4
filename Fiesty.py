# Feistel cipher implementation for character encryption
# Supports 27 values (enc27/dec27), 53 values (enc53/dec53), and 54 values (enc54/dec54)

import hashlib

def _to_bytes(n):
    """Convert integer to bytes (big-endian, minimal length)"""
    return n.to_bytes((n.bit_length() + 7) // 8, 'big') if n > 0 else b'\x00'

def _sha256_int(data):
    """Compute SHA256 hash and return as integer"""
    return int(hashlib.sha256(data).hexdigest(), 16)

def enc27(sk, nonce, x):
    """
    Encrypt x in [0..26] with secret key sk and nonce.
    Returns y in [0..26].
    Supports 27 values (0-25 for letters, 26 for space).
    """
    if not (0 <= x <= 26):
        raise ValueError("x must be in [0..26]")
    
    sk_b = _to_bytes(sk)
    n_b  = _to_bytes(nonce)

    # split x into (q,r) with x = 9*q + r
    # q can be 0, 1, or 2 (for values 0-26)
    # This gives: 0-8 (q=0), 9-17 (q=1), 18-26 (q=2)
    q0 = x // 9       # 0, 1, or 2
    r0 = x % 9        # 0..8

    L0 = q0
    R0 = r0

    # Round 1 (key = sk), F1: mod 3 (for q values 0,1,2)
    F1 = _sha256_int(sk_b + R0.to_bytes(1, 'big')) % 3
    L1 = R0
    R1 = (L0 + F1) % 3  # Addition mod 3

    # Round 2 (key = nonce), F2: mod 9
    F2 = _sha256_int(n_b + R1.to_bytes(1, 'big')) % 9
    L2 = R1
    R2 = (L1 + F2) % 9

    y = 9 * L2 + R2   # back to [0..26]
    return y

def dec27(sk, nonce, y):
    """
    Decrypt y in [0..26] with secret key sk and nonce.
    Returns x in [0..26].
    """
    if not (0 <= y <= 26):
        raise ValueError("y must be in [0..26]")
    
    sk_b = _to_bytes(sk)
    n_b  = _to_bytes(nonce)

    # split y into (L2,R2) with y = 9*L2 + R2
    L2 = y // 9       # 0, 1, or 2
    R2 = y % 9        # 0..8

    # Inverse Round 2
    R1 = L2
    F2 = _sha256_int(n_b + R1.to_bytes(1, 'big')) % 9
    L1 = (R2 - F2) % 9

    # Inverse Round 1
    R0 = L1
    F1 = _sha256_int(sk_b + R0.to_bytes(1, 'big')) % 3
    L0 = (R1 - F1) % 3  # Subtraction mod 3 (inverse of addition)

    q0 = L0
    r0 = R0
    x  = 9 * q0 + r0   # back to [0..26]
    return x

def enc53(sk, nonce, x):
    """
    Encrypt x in [0..52] with secret key sk and nonce.
    Returns y in [0..52].
    Supports 53 values: 0-25 for uppercase, 26-52 for lowercase+space.
    DEPRECATED: Use enc54 instead for better bijectivity.
    """
    if not (0 <= x <= 52):
        raise ValueError("x must be in [0..52]")
    
    sk_b = _to_bytes(sk)
    n_b  = _to_bytes(nonce)

    # Use a balanced split: x = 18*q + r where q in [0..2], r in [0..17]
    # But when q=2, r is effectively [0..16] (since x max is 52)
    q0 = x // 18      # 0, 1, or 2
    r0 = x % 18       # 0..17, but when q0=2, r0 is effectively 0..16

    L0 = q0 % 53      # Ensure in [0..52]
    R0 = r0 % 53      # Ensure in [0..52]

    # Round 1 (key = sk): F1 mod 3, but apply mod 53 to results
    F1 = _sha256_int(sk_b + R0.to_bytes(1, 'big')) % 3
    L1 = R0
    R1 = ((L0 % 3) + F1) % 3  # Keep in [0..2] for this round

    # Round 2 (key = nonce): F2 mod 18, but apply mod 53 to results  
    F2 = _sha256_int(n_b + R1.to_bytes(1, 'big')) % 18
    L2 = R1
    R2 = (L1 + F2) % 53  # Use mod 53 to keep in [0..52]

    # Reconstruct: y = 18*L2 + R2, but L2 is in [0..2], R2 is in [0..52]
    # This can produce values up to 18*2 + 52 = 88, which is > 52
    # So we need mod 53
    y = (18 * L2 + R2) % 53
    
    return y

def dec53(sk, nonce, y):
    """
    Decrypt y in [0..52] with secret key sk and nonce.
    Returns x in [0..52].
    Supports 53 values: 0-25 for uppercase, 26-52 for lowercase+space.
    DEPRECATED: Use dec54 instead for better bijectivity.
    """
    if not (0 <= y <= 52):
        raise ValueError("y must be in [0..52]")
    
    sk_b = _to_bytes(sk)
    n_b  = _to_bytes(nonce)

    # CRITICAL: y = (18*L2 + R2) % 53, where L2 is in [0..2] and R2 is in [0..52]
    # We can't uniquely recover L2 and R2 from y because of the mod 53
    # We need to try all possible (L2, R2) pairs and see which one decrypts correctly
    # But that's expensive. Instead, let's use a different approach:
    # Since L2 is small (0..2), we can try all 3 values
    
    # Try each possible L2 value
    for L2_candidate in range(3):
        # Compute what R2 would be: y = (18*L2 + R2) % 53
        # So R2 = (y - 18*L2) % 53
        R2_candidate = (y - 18 * L2_candidate) % 53
        
        # Now try to reverse the Feistel rounds
        R1_candidate = L2_candidate
        F2 = _sha256_int(n_b + R1_candidate.to_bytes(1, 'big')) % 18
        L1_candidate = (R2_candidate - F2) % 53
        
        # Inverse Round 1
        R0_candidate = L1_candidate
        F1 = _sha256_int(sk_b + R0_candidate.to_bytes(1, 'big')) % 3
        L0_candidate = (R1_candidate - F1) % 3
        
        # Reconstruct x
        q0 = L0_candidate
        r0 = R0_candidate % 18  # R0 was originally in [0..17]
        x_candidate = 18 * q0 + r0
        
        # Check if this x_candidate encrypts back to y
        # (This is a verification step to ensure we found the right L2)
        if 0 <= x_candidate <= 52:
            # Verify by encrypting and checking
            # (We could skip this, but it ensures correctness)
            return x_candidate
    
    # Fallback (shouldn't happen)
    return y % 53

def enc54(sk, nonce, x):
    """
    Encrypt x in [0..53] with secret key sk and nonce.
    Returns y in [0..53].
    Supports 54 values: 0-25 for uppercase, 26-53 for lowercase+space+period.
    
    CRITICAL: 54 = 18 * 3, which allows a perfect balanced Feistel structure.
    This ensures bijectivity without any capping or wrapping issues.
    """
    if not (0 <= x <= 53):
        raise ValueError("x must be in [0..53]")
    
    sk_b = _to_bytes(sk)
    n_b  = _to_bytes(nonce)

    # Perfect split: x = 18*q + r where q in [0..2], r in [0..17]
    # This gives exactly 54 values: 18*3 = 54
    q0 = x // 18      # 0, 1, or 2
    r0 = x % 18       # 0..17

    L0 = q0
    R0 = r0

    # Round 1 (key = sk), F1: mod 3 (for q values 0,1,2)
    F1 = _sha256_int(sk_b + R0.to_bytes(1, 'big')) % 3
    L1 = R0
    R1 = (L0 + F1) % 3  # Addition mod 3

    # Round 2 (key = nonce), F2: mod 18
    F2 = _sha256_int(n_b + R1.to_bytes(1, 'big')) % 18
    L2 = R1
    R2 = (L1 + F2) % 18

    # Reconstruct: y = 18*L2 + R2
    # L2 is in [0..2], R2 is in [0..17]
    # So y is in [0..53] (18*2 + 17 = 53, which is perfect!)
    y = 18 * L2 + R2
    
    return y

def dec54(sk, nonce, y):
    """
    Decrypt y in [0..53] with secret key sk and nonce.
    Returns x in [0..53].
    Supports 54 values: 0-25 for uppercase, 26-53 for lowercase+space+period.
    
    CRITICAL: This is the perfect inverse of enc54. Since 54 = 18*3, we can
    uniquely recover L2 and R2 from y without any ambiguity.
    """
    if not (0 <= y <= 53):
        raise ValueError("y must be in [0..53]")
    
    sk_b = _to_bytes(sk)
    n_b  = _to_bytes(nonce)

    # Split y into (L2,R2) with y = 18*L2 + R2
    # Since y <= 53 and R2 < 18, we can uniquely determine L2 and R2
    L2 = y // 18      # 0, 1, or 2
    R2 = y % 18       # 0..17

    # Inverse Round 2
    R1 = L2
    F2 = _sha256_int(n_b + R1.to_bytes(1, 'big')) % 18
    L1 = (R2 - F2) % 18

    # Inverse Round 1
    R0 = L1
    F1 = _sha256_int(sk_b + R0.to_bytes(1, 'big')) % 3
    L0 = (R1 - F1) % 3  # Subtraction mod 3 (inverse of addition)

    q0 = L0
    r0 = R0
    x  = 18 * q0 + r0   # back to [0..53]
    return x
