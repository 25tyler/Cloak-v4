
# ============================================================================
# This code takes the secret key, nonce, and a single character and runs it through the Fiestal cipher
# to return a single character in [0..25]. It essentially is a reversible pseudo-random number generator.
# With the same secret key and nonce, the same character will always produce the same output.
# Additionally, the output can be ran back through the cipher to get the original character (with the
# same secret key and nonce). Does all characters and " " (space).
# ============================================================================

import hashlib

def _to_bytes(x):
    """Convert int/str/bytes to bytes."""
    if isinstance(x, bytes):
        return x
    if isinstance(x, str):
        return x.encode('utf-8')
    if isinstance(x, int):
        # at least 1 byte
        length = max(1, (x.bit_length() + 7) // 8)
        return x.to_bytes(length, 'big')
    raise TypeError("Key/nonce must be int, str, or bytes")

def _sha256_int(data: bytes) -> int:
    """SHA256(data) as big integer."""
    return int.from_bytes(hashlib.sha256(data).digest(), 'big')

def enc(sk, nonce, x):
    """
    Encrypt x in [0..26] with secret key sk and nonce.
    Returns y in [0..26].
    Supports 27 values: 0-25 for letters, 26 for space.
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

def dec(sk, nonce, y):
    """
    Decrypt y in [0..26] with secret key sk and nonce.
    Returns x in [0..26].
    Supports 27 values: 0-25 for letters, 26 for space.
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
    x  = 9 * q0 + r0
    return x

print(enc(29202, 348596, 21))