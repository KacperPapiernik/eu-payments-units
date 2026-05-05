from pydantic import BaseModel

class PaymentRequest(BaseModel):
    sender_iban: str
    receiver_iban: str
    amount: float
    currency: str = "EUR"
