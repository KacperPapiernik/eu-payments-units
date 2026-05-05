from fastapi import APIRouter
from app.schemas.payment import PaymentRequest
from app.services.service import process

router = APIRouter()

@router.post("/")
def handle_payment(req: PaymentRequest):
    return process(req)
