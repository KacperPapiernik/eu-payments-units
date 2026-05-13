import re
from typing import Optional


class IBANValidator:
    IBAN_LENGTHS = {
        "AL": 28, "AD": 24, "AT": 20, "AZ": 28, "BH": 22, "BY": 28,
        "BE": 16, "BA": 20, "BR": 29, "BG": 22, "CR": 22, "HR": 21,
        "CY": 28, "CZ": 24, "DK": 18, "DO": 28, "TL": 23, "EE": 20,
        "FO": 18, "FI": 18, "FR": 27, "GE": 22, "DE": 22, "GI": 23,
        "GR": 27, "GL": 18, "GT": 28, "HU": 28, "IS": 26, "IQ": 23,
        "IE": 22, "IL": 23, "IT": 27, "JO": 30, "KZ": 20, "XK": 20,
        "KW": 30, "LV": 21, "LB": 28, "LI": 21, "LT": 20, "LU": 20,
        "MK": 19, "MT": 31, "MR": 27, "MU": 30, "MC": 27, "MD": 24,
        "ME": 22, "NL": 18, "NO": 15, "PK": 24, "PS": 29, "PL": 28,
        "PT": 25, "QA": 29, "RO": 24, "LC": 32, "SM": 27, "ST": 25,
        "SA": 24, "RS": 22, "SC": 31, "SK": 24, "SI": 19, "ES": 24,
        "SE": 24, "CH": 21, "TN": 24, "TR": 26, "UA": 29, "AE": 23,
        "GB": 22, "VA": 22, "VG": 24
    }

    @classmethod
    def validate(cls, iban: str) -> tuple[bool, Optional[str]]:
        if not iban:
            return False, "IBAN cannot be empty"

        iban_clean = iban.replace(" ", "").replace("-", "").upper()

        if not re.match(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]+$", iban_clean):
            return False, "Invalid IBAN format"

        country_code = iban_clean[:2]
        if country_code not in cls.IBAN_LENGTHS:
            return False, f"Unknown country code: {country_code}"

        if len(iban_clean) != cls.IBAN_LENGTHS[country_code]:
            return False, f"Invalid length for {country_code}. Expected {cls.IBAN_LENGTHS[country_code]}, got {len(iban_clean)}"

        if not cls._validate_mod97(iban_clean):
            return False, "Invalid checksum (MOD-97 validation failed)"

        return True, None

    @classmethod
    def _validate_mod97(cls, iban: str) -> bool:
        rearranged = iban[4:] + iban[:4]
        numeric = ""
        for char in rearranged:
            if char.isdigit():
                numeric += char
            else:
                numeric += str(ord(char) - ord("A") + 10)

        return int(numeric) % 97 == 1

    @classmethod
    def format_iban(cls, iban: str) -> str:
        return iban.replace(" ", "").replace("-", "").upper()

    @classmethod
    def extract_bic_from_iban(cls, iban: str) -> Optional[str]:
        return None


def validate_iban(iban: str) -> tuple[bool, Optional[str]]:
    return IBANValidator.validate(iban)