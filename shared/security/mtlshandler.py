import ssl
import httpx
from typing import Optional
from pathlib import Path


class mTLSConfig:
    def __init__(
        self,
        ca_cert_path: str,
        service_cert_path: str,
        service_key_path: str
    ):
        self.ca_cert_path = ca_cert_path
        self.service_cert_path = service_cert_path
        self.service_key_path = service_key_path

    def create_ssl_context(self, verify_client: bool = True) -> ssl.SSLContext:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        
        context.load_cert_chain(
            certfile=self.service_cert_path,
            keyfile=self.service_key_path
        )
        
        if verify_client:
            context.verify_mode = ssl.CERT_REQUIRED
            context.load_verify_locations(cafile=self.ca_cert_path)
        
        return context

    def create_client_ssl_context(self) -> ssl.SSLContext:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        
        context.load_cert_chain(
            certfile=self.service_cert_path,
            keyfile=self.service_key_path
        )
        
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(cafile=self.ca_cert_path)
        
        return context


def create_mtls_client(
    ca_cert: str,
    client_cert: str,
    client_key: str
) -> httpx.AsyncClient:
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.load_cert_chain(certfile=client_cert, keyfile=client_key)
    ssl_context.verify_mode = ssl.CERT_REQUIRED
    ssl_context.load_verify_locations(cafile=ca_cert)
    
    return httpx.AsyncClient(verify=ssl_context)