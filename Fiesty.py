# Feistel cipher implementation for character encryption
# Supports 54 values (enc54/dec54) for unified character mapping

import hashlib

def _to_bytes(n):
    """Convert integer to bytes (big-endian, minimal length)"""
    return n.to_bytes((n.bit_length() + 7) // 8, 'big') if n > 0 else b'\x00'

def _sha256_int(data):
    """Compute SHA256 hash and return as integer"""
    return int(hashlib.sha256(data).hexdigest(), 16)

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
