#!/usr/bin/env python3

import os
from datetime import datetime, timedelta
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend


CERT_DIR = os.path.dirname(os.path.abspath(__file__))
DAYS_VALID = 365
KEY_SIZE = 2048


def generate_ca():
    print("Generating CA...")
    
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=KEY_SIZE,
        backend=default_backend()
    )
    
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "EU"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Poland"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Payment Infrastructure CA"),
        x509.NameAttribute(NameOID.COMMON_NAME, "Payment Infrastructure Root CA"),
    ])
    
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow())
        .not_valid_after(datetime.utcnow() + timedelta(days=DAYS_VALID * 5))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_cert_sign=True,
                crl_sign=True,
                key_encipherment=False,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(private_key, hashes.SHA256(), default_backend())
    )
    
    with open(os.path.join(CERT_DIR, "ca.key"), "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))
    
    with open(os.path.join(CERT_DIR, "ca.pem"), "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    
    print(f"  CA generated: ca.key, ca.pem")
    return private_key, cert


def generate_service_cert(service_name: str, ca_key, ca_cert):
    print(f"Generating {service_name} certificate...")
    
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=KEY_SIZE,
        backend=default_backend()
    )
    
    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "EU"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Payment Infrastructure"),
        x509.NameAttribute(NameOID.COMMON_NAME, service_name.upper()),
    ])
    
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow())
        .not_valid_after(datetime.utcnow() + timedelta(days=DAYS_VALID))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(f"{service_name}"),
                x509.DNSName("localhost"),
                x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
            ]),
            critical=False,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                key_cert_sign=False,
                crl_sign=False,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256(), default_backend())
    )
    
    with open(os.path.join(CERT_DIR, f"{service_name}.key"), "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))
    
    with open(os.path.join(CERT_DIR, f"{service_name}.pem"), "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    
    print(f"  {service_name}: {service_name}.key, {service_name}.pem")
    return private_key, cert


def generate_bank_cert(bank_bic: str, ca_key, ca_cert):
    print(f"Generating {bank_bic} certificate...")
    
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=KEY_SIZE,
        backend=default_backend()
    )
    
    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "EU"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, f"Bank {bank_bic}"),
        x509.NameAttribute(NameOID.COMMON_NAME, bank_bic),
    ])
    
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow())
        .not_valid_after(datetime.utcnow() + timedelta(days=DAYS_VALID))
        .sign(ca_key, hashes.SHA256(), default_backend())
    )
    
    with open(os.path.join(CERT_DIR, f"{bank_bic.lower()}.key"), "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))
    
    with open(os.path.join(CERT_DIR, f"{bank_bic.lower()}.pem"), "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    
    print(f"  {bank_bic}: {bank_bic.lower()}.key, {bank_bic.lower()}.pem")
    return private_key, cert


import ipaddress


def main():
    print("=" * 60)
    print("Payment Infrastructure Certificate Generator")
    print("=" * 60)
    
    if os.path.exists(os.path.join(CERT_DIR, "ca.pem")):
        print("\nCA already exists. Skipping...")
        with open(os.path.join(CERT_DIR, "ca.key"), "rb") as f:
            from cryptography.hazmat.primitives.serialization import load_pem_private_key
            ca_key = load_pem_private_key(f.read(), password=None, backend=default_backend())
        with open(os.path.join(CERT_DIR, "ca.pem"), "rb") as f:
            ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())
    else:
        ca_key, ca_cert = generate_ca()
    
    print("\n--- Service Certificates ---")
    for service in ["target", "sepa_batch", "sepa_instant"]:
        generate_service_cert(service, ca_key, ca_cert)
    
    print("\n--- Bank Certificates ---")
    for bank in ["BANKA", "BANKB"]:
        generate_bank_cert(bank, ca_key, ca_cert)
    
    print("\n" + "=" * 60)
    print("Certificate generation complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()