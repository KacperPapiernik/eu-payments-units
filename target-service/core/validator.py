import re

def validate_iban(iban: str):
    pattern = r"^[A-Z]{2}[0-9A-Z]{13,30}$"
    if not re.match(pattern, iban):
        raise ValueError("Invalid IBAN")
