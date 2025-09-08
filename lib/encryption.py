import hashlib
import hmac
import os
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding


class EncryptionHandler:
    """
    Encryption utilities for secure communication with update server
    """
    
    def __init__(self, auth_token, encryption_iterations=100000):
        self.auth_token = auth_token
        self.encryption_iterations = encryption_iterations
        self.current_channel_key = None
    
    def negotiate_secure_layer(self, client_nonce_b64, server_nonce_b64):
        """
        Negotiate secure transmission layer using client and server nonces
        
        Args:
            client_nonce_b64 (str): Client nonce in base64
            server_nonce_b64 (str): Server nonce in base64
        
        Returns:
            bool: Success status
        """
        if not client_nonce_b64 or not server_nonce_b64:
            return False
        
        try:
            # Add padding if needed
            client_nonce_padded = client_nonce_b64 + '=='
            server_nonce_padded = server_nonce_b64 + '=='
            
            # Decode nonces using urlsafe base64
            client_marker_bytes = base64.urlsafe_b64decode(client_nonce_padded)
            server_marker_bytes = base64.urlsafe_b64decode(server_nonce_padded)
            
            # Combine for salt
            kdf_salt_material = client_marker_bytes + server_marker_bytes
            
            # Derive key using PBKDF2
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=kdf_salt_material,
                iterations=self.encryption_iterations,
                backend=default_backend()
            )
            
            self.current_channel_key = kdf.derive(self.auth_token.encode('utf-8'))
            
            return True
        except Exception as e:
            print(f"Error negotiating secure layer: {e}")
            self.current_channel_key = None
            return False
    
    def encrypt_payload(self, raw_data_bytes):
        """
        Encrypt outgoing payload
        
        Args:
            raw_data_bytes (bytes): Data to encrypt
        
        Returns:
            str or None: Base64 encoded encrypted data or None on error
        """
        if not self.current_channel_key:
            return None
        
        try:
            # Generate random IV
            iv = os.urandom(16)
            
            # Create cipher
            cipher = Cipher(
                algorithms.AES(self.current_channel_key),
                modes.CBC(iv),
                backend=default_backend()
            )
            encryptor = cipher.encryptor()
            
            # Add PKCS7 padding
            padder = padding.PKCS7(128).padder()
            padded_data = padder.update(raw_data_bytes) + padder.finalize()
            
            # Encrypt data
            encrypted = encryptor.update(padded_data) + encryptor.finalize()
            
            # Combine IV and ciphertext
            combined = iv + encrypted
            
            # Return base64 encoded
            return base64.b64encode(combined).decode('ascii')
        except Exception as e:
            print(f"Encryption error: {e}")
            return None
    
    def decrypt_payload(self, encrypted_data_b64):
        """
        Decrypt incoming payload
        
        Args:
            encrypted_data_b64 (str): Base64 encoded encrypted data
        
        Returns:
            bytes or None: Decrypted data or None on error
        """
        if not self.current_channel_key:
            return None
        
        try:
            # Decode from base64
            combined = base64.b64decode(encrypted_data_b64)
            
            # Extract IV and ciphertext
            iv = combined[:16]
            ciphertext = combined[16:]
            
            # Create cipher
            cipher = Cipher(
                algorithms.AES(self.current_channel_key),
                modes.CBC(iv),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            
            # Decrypt data
            padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            
            # Remove PKCS7 padding
            unpadder = padding.PKCS7(128).unpadder()
            plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()
            
            return plaintext
        except Exception as e:
            print(f"Decryption error: {e}")
            return None
    
    def sign_data(self, data):
        """
        Sign data with HMAC-SHA256
        
        Args:
            data (str or bytes): Data to sign
        
        Returns:
            str: Hex encoded signature
        """
        if isinstance(data, str):
            data_bytes = data.encode('utf-8')
        elif isinstance(data, bytes):
            data_bytes = data
        else:
            raise TypeError('Data for HMAC signing must be string or bytes')
        
        signature = hmac.new(
            self.auth_token.encode('utf-8'),
            data_bytes,
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def verify_signature(self, data, signature):
        """
        Verify data signature
        
        Args:
            data (str or bytes): Data to verify
            signature (str): Expected signature
        
        Returns:
            bool: Verification result
        """
        computed_signature = self.sign_data(data)
        return hmac.compare_digest(computed_signature, signature)
    
    def generate_nonce(self):
        """
        Generate random nonce
        
        Returns:
            str: Base64url encoded nonce without padding
        """
        nonce = os.urandom(16)
        return base64.urlsafe_b64encode(nonce).decode('ascii').rstrip('=')
    
    def compute_hash(self, data):
        """
        Compute SHA256 hash
        
        Args:
            data (bytes): Data to hash
        
        Returns:
            str: Hex encoded hash
        """
        return hashlib.sha256(data).hexdigest()