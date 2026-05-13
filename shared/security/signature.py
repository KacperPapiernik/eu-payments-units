import base64
import hashlib
import json
from typing import Optional, Dict, Any
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend


class SignatureHandler:
    def __init__(self, private_key_pem: Optional[str] = None, public_key_pem: Optional[str] = None):
        self._private_key = None
        self._public_key = None
        
        if private_key_pem:
            self._load_private_key(private_key_pem)
        if public_key_pem:
            self._load_public_key(public_key_pem)

    def _load_private_key(self, pem: str):
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        self._private_key = load_pem_private_key(
            pem.encode(),
            password=None,
            backend=default_backend()
        )

    def _load_public_key(self, pem: str):
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        self._public_key = load_pem_public_key(
            pem.encode(),
            backend=default_backend()
        )

    def sign(self, payload: Dict[str, Any]) -> str:
        if not self._private_key:
            raise ValueError("Private key not loaded")
        
        payload_str = json.dumps(payload, sort_keys=True)
        payload_bytes = payload_str.encode("utf-8")
        
        signature = self._private_key.sign(
            payload_bytes,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        
        return base64.b64encode(signature).decode("utf-8")

    def verify(self, payload: Dict[str, Any], signature: str, public_key_pem: str) -> bool:
        try:
            if not self._public_key:
                self._load_public_key(public_key_pem)
            
            payload_str = json.dumps(payload, sort_keys=True)
            payload_bytes = payload_str.encode("utf-8")
            
            signature_bytes = base64.b64decode(signature.encode("utf-8"))
            
            self._public_key.verify(
                signature_bytes,
                payload_bytes,
                padding.PKCS1v15(),
                hashes.SHA256()
            )
            return True
        except Exception:
            return False

    @staticmethod
    def load_public_key_from_file(path: str) -> str:
        with open(path, "r") as f:
            return f.read()

    @staticmethod
    def load_private_key_from_file(path: str) -> str:
        with open(path, "r") as f:
            return f.read()


class SignedRequest:
    def __init__(self, payload: Dict[str, Any], signature: str, bank_bic: str):
        self.payload = payload
        self.signature = signature
        self.bank_bic = bank_bic


def create_signed_request(payload: Dict[str, Any], signature_handler: SignatureHandler) -> Dict[str, Any]:
    return {
        "payload": payload,
        "signature": signature_handler.sign(payload),
        "bank_bic": payload.get("bank_bic", "UNKNOWN")
    }


def verify_signed_request(
    request: Dict[str, Any],
    public_key_pem: str
) -> tuple[bool, Optional[str]]:
    try:
        payload = request.get("payload", {})
        signature = request.get("signature")
        bank_bic = request.get("bank_bic")
        
        if not all([payload, signature, bank_bic]):
            return False, "Missing required fields (payload, signature, bank_bic)"
        
        handler = SignatureHandler()
        if handler.verify(payload, signature, public_key_pem):
            return True, None
        return False, "Signature verification failed"
    except Exception as e:
        return False, f"Verification error: {str(e)}"