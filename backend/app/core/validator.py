import re
from typing import Tuple


def validate_iban(iban: str) -> Tuple[bool, str]:
    """
    Validates IBAN format using mod-97 algorithm.
    Returns (is_valid, error_message)
    """
    if not iban:
        return False, "IBAN cannot be empty"

    iban_clean = iban.replace(" ", "").upper()

    if not re.match(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]+$", iban_clean):
        return False, "Invalid IBAN format"

    if len(iban_clean) < 15 or len(iban_clean) > 34:
        return False, "IBAN length must be between 15 and 34 characters"

    numeric = ""
    for char in iban_clean[4:] + iban_clean[:4]:
        if char.isdigit():
            numeric += char
        else:
            numeric += str(ord(char) - 55)

    if int(numeric) % 97 != 1:
        return False, "Invalid IBAN checksum"

    return True, ""


def validate_amount(amount: float, payment_type: str) -> Tuple[bool, str]:
    """
    Validates amount based on payment type limits.
    SEPA: no limit
    SEPA_INSTANT: max 100000 EUR
    TARGET: no limit
    """
    if amount <= 0:
        return False, "Amount must be greater than 0"

    if payment_type == "SEPA_INSTANT" and amount > 100000:
        return False, "SEPA Instant maximum amount is 100,000 EUR"

    return True, ""


def validate_currency(currency: str) -> Tuple[bool, str]:
    """Validates that currency is EUR (required for SEPA)"""
    if currency != "EUR":
        return False, "SEPA payments must use EUR currency"
    return True, ""


def check_system_availability(payment_type: str) -> Tuple[bool, str]:
    """
    Checks if the selected payment system is available at the current time.
    
    TARGET2: only business days (Mon-Fri), 7:00-18:00 CET
    SEPA: business days only (Mon-Fri), after 16:00 processes next day
    SEPA_INSTANT: 24/7/365 always available
    """
    from datetime import datetime
    import pytz
    
    cet = pytz.timezone('Europe/Warsaw')
    now = datetime.now(cet)
    weekday = now.weekday()
    hour = now.hour
    
    if payment_type == "SEPA_INSTANT":
        return True, ""
    
    if payment_type == "TARGET":
        if weekday >= 5:
            return False, "TARGET2 is not available on weekends"
        if hour < 7 or hour >= 18:
            return False, "TARGET2 is available only 7:00-18:00 CET on business days"
        return True, ""
    
    if payment_type == "SEPA":
        if weekday >= 5:
            return False, "SEPA is not available on weekends"
        return True, ""
    
    return False, f"Unknown payment type: {payment_type}"