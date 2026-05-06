# eu-payments-units
SEPA + SEPA instant + TARGET

## Uruchomienie
 
```bash
docker-compose up --build
```
## Przykładowe zapytania
 
### Health check
```bash
curl http://localhost:8000/api/v1/health
```
 
### Dostępne typy płatności
```bash
curl http://localhost:8000/api/v1/types
```
 
### Przelew SEPA (standardowy)
```bash
curl -X POST http://localhost:8000/api/v1/transfer \
  -H "Content-Type: application/json" \
  -d '{
    "sender_iban": "DE89370400440532013000",
    "receiver_iban": "FR7630006000011234567890189",
    "amount": 1000.00,
    "currency": "EUR",
    "type": "SEPA"
  }'
```
 
### Przelew SEPA Instant (do 100k EUR, 24/7)
```bash
curl -X POST http://localhost:8000/api/v1/transfer \
  -H "Content-Type: application/json" \
  -d '{
    "sender_iban": "DE89370400440532013000",
    "receiver_iban": "PL61109010140000001234567890",
    "amount": 5000.00,
    "currency": "EUR",
    "type": "SEPA_INSTANT"
  }'
```
 
### Przelew TARGET2 (duże kwoty, RTGS)
```bash
curl -X POST http://localhost:8000/api/v1/transfer \
  -H "Content-Type: application/json" \
  -d '{
    "sender_iban": "DE89370400440532013000",
    "receiver_iban": "GB82WEST12345698765432",
    "amount": 150000.00,
    "currency": "EUR",
    "type": "TARGET"
  }'
```
 
## Przykładowe odpowiedzi
 
### Transfer w godzinach pracy:
```json
{
  "transaction_id": "abc-123-def-456",
  "status": "RECEIVED",
  "payment_type": "SEPA",
  "created_at": "2026-05-05T14:30:00Z",
  "message": "SEPA transfer received, awaiting processing"
}
```
 
### Transfer poza godzinami pracy (zaplanowany):
```json
{
  "transaction_id": "xyz-789-uvw-012",
  "status": "SCHEDULED",
  "payment_type": "TARGET",
  "created_at": "2026-05-05T20:00:00Z",
  "message": "TARGET transfer scheduled for 2026-05-06 07:00 CET"
}
```
 
## Logika systemu
 
| Typ           | Godziny dostępności  | Limit |
| SEPA          | Pon-Pt 7:00-16:00    | Brak |
| SEPA_INSTANT  | 24/7/365             | 100,000 EUR |
| TARGET        | Pon-Pt 7:00-18:00    | Brak |
 
Transfery wysłane poza oknem czasowym są planowane
