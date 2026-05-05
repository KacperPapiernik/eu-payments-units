from fastapi import APIRouter, HTTPException
from app.schemas.payment import PaymentRequest, PaymentResponse, PaymentType
from app.core.validator import validate_iban, validate_amount, validate_currency
from app.services import sepa, sepa_instant, target

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok", "service": "payments-api"}


@router.get("/types")
def payment_types():
    return {
        "types": [
            {"name": "SEPA", "description": "Standard SEPA Credit Transfer (D+1)"},
            {"name": "SEPA_INSTANT", "description": "SEPA Instant (<10s, max 100k EUR)"},
            {"name": "TARGET", "description": "TARGET2 RTGS for large values"}
        ]
    }


@router.post("/transfer", response_model=PaymentResponse)
async def transfer(req: PaymentRequest):
    # Validate currency (must be EUR)
    is_valid, error = validate_currency(req.currency)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)

    # Validate sender IBAN
    is_valid, error = validate_iban(req.sender_iban)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid sender IBAN: {error}")

    # Validate receiver IBAN
    is_valid, error = validate_iban(req.receiver_iban)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid receiver IBAN: {error}")

    # Validate amount limits for selected payment type
    is_valid, error = validate_amount(req.amount, req.type.value)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)

    # Route to appropriate service - service will decide whether to process immediately
    # or schedule based on system availability (business hours, weekend, etc.)
    if req.type == PaymentType.SEPA:
        return await sepa.process(req)
    elif req.type == PaymentType.SEPA_INSTANT:
        return await sepa_instant.process(req)
    elif req.type == PaymentType.TARGET:
        return await target.process(req)