"""
Stub para pyotp - funcionalidad básica de 2FA
"""

import secrets
import base64
import hashlib
import hmac
import time
import struct

class TOTP:
    """Time-based One-Time Password stub implementation."""
    
    def __init__(self, secret, digits=6, digest=hashlib.sha1, interval=30):
        self.secret = secret
        self.digits = digits
        self.digest = digest
        self.interval = interval
    
    def now(self):
        """Generate current TOTP."""
        return self.at(time.time())
    
    def at(self, for_time):
        """Generate TOTP for specific time."""
        counter = int(for_time // self.interval)
        return self._generate_otp(counter)
    
    def verify(self, token, for_time=None):
        """Verify TOTP token."""
        if for_time is None:
            for_time = time.time()
        
        # Check current and previous/next intervals
        for offset in [-1, 0, 1]:
            if self.at(for_time + offset * self.interval) == token:
                return True
        return False
    
    def _generate_otp(self, counter):
        """Generate OTP for counter value."""
        # Convert secret from base32
        try:
            key = base64.b32decode(self.secret.upper() + '=' * (8 - len(self.secret) % 8))
        except:
            key = self.secret.encode('utf-8')
        
        # Generate HMAC
        counter_bytes = struct.pack('>Q', counter)
        hmac_hash = hmac.new(key, counter_bytes, self.digest).digest()
        
        # Dynamic truncation
        offset = hmac_hash[-1] & 0xf
        code = struct.unpack('>I', hmac_hash[offset:offset+4])[0] & 0x7fffffff
        
        # Return as string with leading zeros
        return str(code % (10 ** self.digits)).zfill(self.digits)

def random_base32():
    """Generate random base32 secret."""
    return base64.b32encode(secrets.token_bytes(20)).decode('utf-8')