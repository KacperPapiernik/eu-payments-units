# Symulator Europejskiej Infrastruktury Płatności

Symulacja europejskiej infrastruktury płatności obejmującej TARGET (RTGS), SEPA Batch (clearing + netting) oraz SEPA Instant (płatności w czasie rzeczywistym).

## Pierwsze kroki

### 1. Generowanie certyfikatów

```bash
python -m pip install cryptography
python certs/generate_certs.py
```

### 2. Uruchomienie serwisów

```bash
docker-compose up --build
```

### 3. Dostęp do serwisów i dokumentacji api

- TARGET: http://localhost:8001
- SEPA Batch: http://localhost:8002
- SEPA Instant: http://localhost:8003

Api:

- http://localhost:8001/docs
- http://localhost:8002/docs
- http://localhost:8003/docs

### 4. Workery (uruchamiane automatycznie w Docker)

- SEPA Batch Worker: zamyka sesje co 5 min, wykonuje netting
- SEPA Instant Worker: rozwiązuje zatory co 1 min, monitoruje płynność

Możliwe opcje pracy workera:

{
"mode": "fixed_times",
"times": [
"05:30",
"08:15",
"10:45",
"13:15",
"15:15"
]
}

{
"mode": "interval",
"interval_minutes": 5
}

---

## Pełny scenariusz testowy

Ten przewodnik pokazuje jak przetestować cały system SEPA od zera.

### Wymagania wstępne

1. Uruchom wszystkie serwisy:

   ```bash
   docker-compose up
   ```

   Poczekaj aż zobaczysz "ready" dla wszystkich serwisów (5-10 sekund).

2. Przygotuj dwa banki ( BANKPLPW i BANKDEXX ) - zarejestruj je według kroków poniżej.

---

### Krok 1: Utworzenie banków

```bash
# Bank Polski
curl -X POST http://localhost:8001/banks \
  -H "Content-Type: application/json" \
  -d '{"bic": "BANKPLPW", "name": "Bank Polski"}'

# Deutsche Bank
curl -X POST http://localhost:8001/banks \
  -H "Content-Type: application/json" \
  -d '{"bic": "BANKDEXX", "name": "Deutsche Bank"}'
```

**Co się dzieje:** TARGET tworzy bank i automatycznie zakłada mu konto rozliczeniowe z saldem 0.

**Weryfikacja:**

```bash
curl http://localhost:8001/banks
```

---

### Krok 2: Wstrzyknięcie płynności

Bez tego kroku żaden transfer się nie powiedzie - bank musi mieć środki na koncie!

```bash
# 1 000 000 EUR dla Banku Polskiego
curl -X POST http://localhost:8001/liquidity/injection \
  -H "Content-Type: application/json" \
  -d '{"bank_bic": "BANKPLPW", "amount": 1000000.00, "currency": "EUR"}'

# 500 000 EUR dla Deutsche Bank
curl -X POST http://localhost:8001/liquidity/injection \
  -H "Content-Type: application/json" \
  -d '{"bank_bic": "BANKDEXX", "amount": 500000.00, "currency": "EUR"}'
```

**Co się dzieje:** Operator (centralny bank) dodaje środki na konta rozliczeniowe banków.

**Weryfikacja:**

```bash
curl http://localhost:8001/banks/BANKPLPW
# Sprawdź pole "balance" - powinno być 1000000.00
```

---

### Krok 3: RTGS Transfer przez TARGET (bank → bank)

Bezpośredni przelew między bankami przez system TARGET (RTGS). W przeciwieństwie do SEPA, transfer jest rozliczany natychmiast i bezpośrednio na kontach rozliczeniowych banków.

```bash
curl -X POST http://localhost:8001/transfers \
  -H "Content-Type: application/json" \
  -d '{
    "sender_iban": "PL61109010140000071219812874",
    "receiver_iban": "DE89370400440532013000",
    "sender_bic": "BANKPLPW",
    "receiver_bic": "BANKDEXX",
    "amount": 500.00,
    "currency": "EUR",
    "description": "Direct RTGS transfer"
  }'
```

**Co się dzieje:**

- TARGET natychmiast sprawdza saldo Banku Polskiego
- Obciąża konto BANKPLPW, uznaje konto BANKDEXX
- Transfer rejestrowany w historii RTGS
- Wszystko w jednym kroku, bez pośredników

**Możliwe odpowiedzi:**

- `{"status": "settled", "transfer_id": "...", "created_at": "..."}` - przelew wykonany
- `{"detail": "Insufficient funds..."}` - brak środków (powtórz Krok 2)
- `{"detail": "Sender bank is blocked: ..."}` - bank zablokowany

**Weryfikacja:**

```bash
# Sprawdź salda po przelewie
curl http://localhost:8001/banks/BANKPLPW
curl http://localhost:8001/banks/BANKDEXX

# Sprawdź historię przelewów RTGS
curl http://localhost:8001/transfers
```

**Również w formacie XML (ISO 20022):**

```bash
curl -X POST http://localhost:8001/transfers/xml \
  -H "Content-Type: application/xml" \
  -d '
<Document>
  <CstmrCdtTrfInitn>

    <PmtId>
      <EndToEndId>RTGS-1001</EndToEndId>
    </PmtId>

    <Amt>
      <InstdAmt Ccy="EUR">250.00</InstdAmt>
    </Amt>

    <DbtrAcct>
      <Id>
        <IBAN>PL61109010140000071219812874</IBAN>
      </Id>
    </DbtrAcct>

    <CdtrAcct>
      <Id>
        <IBAN>DE89370400440532013000</IBAN>
      </Id>
    </CdtrAcct>

    <DbtrAgt>
      <FinInstnId>
        <BIC>BANKPLPW</BIC>
      </FinInstnId>
    </DbtrAgt>

    <CdtrAgt>
      <FinInstnId>
        <BIC>BANKDEXX</BIC>
      </FinInstnId>
    </CdtrAgt>

    <RmtInf>
      <Ustrd>XML RTGS transfer</Ustrd>
    </RmtInf>

  </CstmrCdtTrfInitn>
</Document>'
```

**Weryfikacja XML:** Odpowiedź XML zawiera `transfer_id` (UUID) w polu `OrgnlEndToEndId` — użyj go do sprawdzenia statusu:

```bash
# Podmień {transfer_id} na UUID z odpowiedzi XML
curl http://localhost:8001/transfers/{transfer_id}
```

---

### Krok 4: SEPA Instant Transfer (rozliczenie natychmiastowe)

```bash
curl -X POST http://localhost:8003/transfers/xml \
  -H "Content-Type: application/xml" \
  -d '
<Document>
  <CstmrCdtTrfInitn>

    <PmtId>
      <EndToEndId>INST-1001</EndToEndId>
    </PmtId>

    <Amt>
      <InstdAmt Ccy="EUR">100.00</InstdAmt>
    </Amt>

    <DbtrAcct>
      <Id>
        <IBAN>PL61109010140000071219812874</IBAN>
      </Id>
    </DbtrAcct>

    <CdtrAcct>
      <Id>
        <IBAN>DE89370400440532013000</IBAN>
      </Id>
    </CdtrAcct>

    <DbtrAgt>
      <FinInstnId>
        <BIC>BANKPLPW</BIC>
      </FinInstnId>
    </DbtrAgt>

    <CdtrAgt>
      <FinInstnId>
        <BIC>BANKDEXX</BIC>
      </FinInstnId>
    </CdtrAgt>

    <RmtInf>
      <Ustrd>Instant transfer</Ustrd>
    </RmtInf>

  </CstmrCdtTrfInitn>
</Document>'
```

**Co się dzieje:**

- SEPA Instant NATYCHMIAST wysyła żądanie do TARGET `/settle/payment`
- Rozliczenie trwa ~1-2 sekundy
- Salda obu banków aktualizują się automatycznie

**Możliwe odpowiedzi:**

- ✅ `{"status": "settled", ...}` - transfer wykonany
- ❌ `{"detail": "Insufficient funds"}` - brak środków (powtórz Krok 2)

**Weryfikacja salda:**

```bash
curl http://localhost:8001/banks/BANKPLPW
curl http://localhost:8001/banks/BANKDEXX
```

---

### Krok 5: SEPA Batch Transfer (kolejkowanie)

```bash
curl -X POST http://localhost:8003/transfers/xml \
  -H "Content-Type: application/xml" \
  -d '
<Document>
  <CstmrCdtTrfInitn>

    <PmtId>
      <EndToEndId>INST-1001</EndToEndId>
    </PmtId>

    <Amt>
      <InstdAmt Ccy="EUR">100.00</InstdAmt>
    </Amt>

    <DbtrAcct>
      <Id>
        <IBAN>PL61109010140000071219812874</IBAN>
      </Id>
    </DbtrAcct>

    <CdtrAcct>
      <Id>
        <IBAN>DE89370400440532013000</IBAN>
      </Id>
    </CdtrAcct>

    <DbtrAgt>
      <FinInstnId>
        <BIC>BANKPLPW</BIC>
      </FinInstnId>
    </DbtrAgt>

    <CdtrAgt>
      <FinInstnId>
        <BIC>BANKDEXX</BIC>
      </FinInstnId>
    </CdtrAgt>

    <RmtInf>
      <Ustrd>Instant transfer</Ustrd>
    </RmtInf>

  </CstmrCdtTrfInitn>
</Document>'
```

**Co się dzieje:**

- Transfer NIE jest od razu rozliczany
- Idzie do kolejki z statusem `QUEUED`
- Czeka na zamknięcie sesji

**Weryfikacja - sprawdź sesję:**

```bash
curl http://localhost:8002/sessions
```

Odpowiedź zawiera `session_id` - zapamiętaj go.

---

### Krok 6: Batch Transfer - wiele transakcji + netting

Dodaj więcej transferów (w obie strony dla demonstracji nettingu):

```bash
# Transfer A → B
curl -X POST http://localhost:8002/transfers/xml \
  -H "Content-Type: application/xml" \
  -d '
<Document>
  <CstmrCdtTrfInitn>

    <PmtId>
      <EndToEndId>BATCH-5001</EndToEndId>
    </PmtId>

    <Amt>
      <InstdAmt Ccy="EUR">500.00</InstdAmt>
    </Amt>

    <DbtrAcct>
      <Id>
        <IBAN>PL61109010140000071219812874</IBAN>
      </Id>
    </DbtrAcct>

    <CdtrAcct>
      <Id>
        <IBAN>DE89370400440532013000</IBAN>
      </Id>
    </CdtrAcct>

    <DbtrAgt>
      <FinInstnId>
        <BIC>BANKPLPW</BIC>
      </FinInstnId>
    </DbtrAgt>

    <CdtrAgt>
      <FinInstnId>
        <BIC>BANKDEXX</BIC>
      </FinInstnId>
    </CdtrAgt>

  </CstmrCdtTrfInitn>
</Document>'

# Transfer B → A
curl -X POST http://localhost:8002/transfers/xml \
  -H "Content-Type: application/xml" \
  -d '
<Document>
  <CstmrCdtTrfInitn>

    <PmtId>
      <EndToEndId>BATCH-5002</EndToEndId>
    </PmtId>

    <Amt>
      <InstdAmt Ccy="EUR">200.00</InstdAmt>
    </Amt>

    <DbtrAcct>
      <Id>
        <IBAN>DE89370400440532013000</IBAN>
      </Id>
    </DbtrAcct>

    <CdtrAcct>
      <Id>
        <IBAN>PL61109010140000071219812874</IBAN>
      </Id>
    </CdtrAcct>

    <DbtrAgt>
      <FinInstnId>
        <BIC>BANKDEXX</BIC>
      </FinInstnId>
    </DbtrAgt>

    <CdtrAgt>
      <FinInstnId>
        <BIC>BANKPLPW</BIC>
      </FinInstnId>
    </CdtrAgt>

  </CstmrCdtTrfInitn>
</Document>'
```

**Co to jest netting?**
Zamiast 2 osobnych rozliczeń (1000 + 200), system policzy NETTO:

- BankPLPW płaci BankDEXX: 500 - 200 = **300 EUR** (tylko jedno rozliczenie)

---

### Krok 7: Zamknięcie sesji i rozliczenie

**Opcja A - Ręcznie (natychmiast):**

```bash
curl -X POST http://localhost:8002/sessions/close/{session_id}
```

Zamień `{session_id}` na ID z Kroku 4.

**Opcja B - Automatycznie (po 5 minutach):**
Celem nie jest ręczne zamykanie - **worker robi to automatycznie** co 5 minut (SESSION_CLOSE_INTERVAL=300).

**Co się dzieje przy zamknięciu:**

1. Worker pobiera wszystkie transfery z sesji
2. Liczy netting (sumuje credits/debits per bank)
3. Wysyła do TARGET TYLKO jedno rozliczenie netto
4. Status sesji zmienia się na `CLOSED`
5. Status transferów zmienia się na `PROCESSED`

**Weryfikacja:**

```bash
# Stan sesji
curl http://localhost:8002/sessions/{session_id}

# Stan kont po rozliczeniu
curl http://localhost:8001/banks/BANKPLPW
curl http://localhost:8001/banks/BANKDEXX
```

---

### Krok 8: Automatyczne retry (SEPA Instant)

Jeśli przelew instant nie mógł być wykonany (brak środków), worker automatycznie:

1. Co **1 minutę** sprawdza kolejkę `PendingTransferQueue`
2. Retry do TARGET `/settle/payment`
3. Jeśli środki już są → transfer się wykonuje

**Jak sprawdzić pending transfery:**

```bash
curl http://localhost:8003/transfers
```

---

## Serwisy

### TARGET Service (Port 8001)

- **Rola**: Centralny Bank - Rozliczenia RTGS
- **Funkcje**:
  - Rachunki rozliczeniowe dla banków
  - Rozliczenia brutto w czasie rzeczywistym (RTGS)
  - Blokowanie/odblokowywanie banków
  - Wstrzykiwanie płynności (liquidity injection)
  - Przelewy RTGS bank → bank
- **Endpointy**:
  - `GET /banks` - Lista wszystkich banków
  - `POST /banks` - Utworzenie nowego banku
  - `POST /banks/block/{bic}` - Zablokowanie banku
  - `POST /banks/unblock/{bic}` - Odblokowanie banku
  - `POST /settle/payment` - Rozliczenie płatności
  - `POST /liquidity/injection` - Wstrzyknięcie płynności
  - `POST /transfers` - Przelew RTGS bank → bank (JSON)
  - `POST /transfers/xml` - Przelew RTGS bank → bank (XML ISO 20022)
  - `GET /transfers` - Lista przelewów RTGS
  - `GET /transfers/{id}` - Status przelewu RTGS

### SEPA Batch Service (Port 8002)

- **Rola**: Batch clearing z multilateral netting
- **Funkcje**:
  - Przyjmowanie paczek przelewów
  - Sesyjny clearing
  - Multilateral netting (netowanie wielostronne)
  - Okresowe rozliczenia z TARGET
- **Endpointy**:
  - `POST /transfers/xml` - Złożenie pojedynczego przelewu
  - `POST /transfers/batch` - Złożenie paczki przelewów
  - `GET /sessions` - Lista sesji
  - `POST /sessions/close/{session_id}` - Zamknięcie sesji
- **Workery**: Celery worker zamyka sesje i wykonuje netting

### SEPA Instant Service (Port 8003)

- **Rola**: Płatności w czasie rzeczywistym (24/7)
- **Funkcje**:
  - Natychmiastowe przetwarzanie płatności
  - Gridlock resolution (rozwiązywanie zatorów)
  - Monitoring płynności
  - Auto-blokada po 2h braku płynności
- **Endpointy**:
  - `POST /transfers/xml` - Złożenie przelewu instant
  - `GET /transfers/{id}` - Status przelewu
  - `GET /transfers` - Lista przelewów
- **Workery**: Celery worker rozwiązuje zaległe transfery i monitoruje alerty

---

## Zabezpieczenia

### 1. mTLS (Mutual TLS) - Szyfrowana komunikacja dwukierunkowa

#### Co to jest mTLS?

Mutual TLS to protokół, w którym **obie strony się uwierzytelniają**:

- Serwer prezentuje swój certyfikat klientowi
- Klient prezentuje swój certyfikat serwerowi
- Oba certyfikaty muszą być podpisane przez zaufane CA (Certification Authority)

#### Co to daje?

- **Szyfrowanie**: Cała komunikacja jest szyfrowana (TLS 1.3)
- **Uwierzytelnienie**: Obie strony mają pewność, że rozmawiają z właściwym serwisem
- **Integralność**: Dane nie mogą być zmodyfikowane podczas transmisji

Implementacja:

- **Serwer**: Uvicorn startuje z `--ssl-keyfile` i `--ssl-certfile`
- **Certyfikaty**: Przechowywane w `/certs/`
- **Weryfikacja**: Każdy serwis sprawdza czy certyfikat klienta jest podpisany przez nasze CA

#### Generowanie certyfikatów

Proces generowania (szczegóły w `certs/generate_certs.py`):

1. **Tworzenie Root CA**:
   - Generowanie klucza prywatnego RSA 2048-bit
   - Tworzenie self-signed certificate (CA = Certificate Authority)
   - Zapis: `ca.pem`, `ca.key`

2. **Generowanie certyfikatów serwisów**:
   - Dla każdego serwisu: `target`, `sepa_batch`, `sepa_instant`
   - Generowanie własnego klucza prywatnego RSA
   - Tworzenie CSR (Certificate Signing Request)
   - Podpisanie przez Root CA
   - Zapis: `{serwis}.pem`, `{serwis}.key`

3. **Generowanie certyfikatów przykładowych banków**:
   - Dla `BANKA`, `BANKB` (do testów)
   - Ten sam proces co wyżej

Lokalizacja certyfikatów w projekcie:

```
certs/
├── ca.pem / ca.key           # Root CA (ufamy temu certyfikatowi)
├── target.pem / target.key   # Certyfikat TARGET service
├── sepa_batch.pem / key      # Certyfikat SEPA Batch
├── sepa_instant.pem / key    # Certyfikat SEPA Instant
├── banka.pem / banka.key     # Przykładowy bank A
└── bankb.pem / bankb.key     # Przykładowy bank B
```

Uruchomienie generowania:

```bash
python certs/generate_certs.py
```

---

### 2. RSA Podpisy Cyfrowe

#### Co to jest?

Podpis cyfrowy to mechanizm pozwalający zweryfikować:

- **Tożsamość**: Kto podpisał wiadomość (klucz prywatny = tożsamość)
- **Integralność**: Wiadomość nie została zmodyfikowana
- **Niezaprzeczalność**: Twórca nie może zaprzeczyć że podpisał

#### Jak to działa w projekcie?

Każdy request od banku zawiera podpis:

```json
{
  "payload": {
    "sender_iban": "PL83109010140000000101987008",
    "receiver_iban": "PL83109010140000000101987009",
    "amount": 100.0,
    "currency": "EUR"
  },
  "signature": "base64_encoded_rsa_signature",
  "bank_bic": "BANKPLPW"
}
```

Implementacja w `shared/security/signature.py`:

- `SignatureHandler.sign(payload)` - podpisywanie kluczem prywatnym
- `SignatureHandler.verify(payload, signature, public_key_pem)` - weryfikacja

---

### 3. Walidacja IBAN

#### Co to jest IBAN?

IBAN (International Bank Account Number) to międzynarodowy standard numeracji kont bankowych.

#### Struktura IBAN:

```
PL 82 1090 1014 0000 0001 0198 7008
│  │  │                              │
│  │  │                              └─── BBAN (Basic Bank Account Number)
│  │  └── Kod kontrolny (2 cyfry)
└── Kod kraju (2 litery)
```

#### Walidacje implementowane:

1. **Długość IBAN** (per kraj):

   ```python
   IBAN_LENGTHS = {
       "PL": 28, "DE": 22, "FR": 27, "IT": 27, "ES": 24, ...
   }
   ```

2. **Format** (regex):

   ```python
   ^[A-Z]{2}[0-9]{2}[A-Z0-9]+$
   ```

   - 2 litery (kod kraju)
   - 2 cyfry (checksum)
   - reszta (BBAN - litery/cyfry)

3. **MOD-97 (ISO 7064)** - suma kontrolna:
   ```python
   # Algorytm:
   # 1. Przesuń pierwsze 4 znaki na koniec
   # 2. Zamień litery na liczby (A=10, B=11, ..., Z=35)
   # 3. Oblicz MOD 97
   # 4. Wynik musi być równy 1
   ```

Implementacja w `shared/security/iban_validator.py`:

```python
valid, error = validate_iban("PL82109010140000000101987008")
# valid=True, error=None
```

Każdy przelew przed przyjęciem przechodzi walidację IBAN.

---

### 4. Walidacja EUR

System SEPA obsługuje wyłącznie walutę EUR. Walidacja na poziomie Pydantic schemas:

```python
@field_validator('currency')
@classmethod
def validate_eur_only(cls, v: str) -> str:
    if v != "EUR":
        raise ValueError('SEPA transfers only support EUR currency')
    return v
```

Dotyczy:

- `SettlementRequest` (TARGET)
- `TransferRequest` (SEPA Batch)
- `InstantTransferRequest` (SEPA Instant)
- `LiquidityInjectionRequest` (TARGET)
- `RtgsTransferRequest` (TARGET)

---

## Tabela: Czasy i automatyzacja

| Akcja                  | Czas oczekiwania        | Co robi system automatycznie             |
| ---------------------- | ----------------------- | ---------------------------------------- |
| RTGS Transfer (TARGET) | ~1-2 sekundy            | NATYCHMIAST - bezpośrednie rozliczenie   |
| SEPA Instant           | ~1-2 sekundy            | NATYCHMIAST wysyła do TARGET             |
| SEPA Batch do kolejki  | ~1 sekunda              | Transfer przyjęty, czeka na sesję        |
| SEPA Batch rozliczenie | **5 minut** LUB ręcznie | Worker liczy netting, wysyła do TARGET   |
| SEPA Instant retry     | **1 minuta**            | Worker sprawdza pending, retry do TARGET |
| Liquidity alert        | **1 minuta**            | Worker sprawdza brak płynności > 2h      |

---

## Rozwiązywanie problemów

### "Insufficient funds"

Wykonaj Krok 2 ponownie - wstrzyknij więcej płynności.

### Transfer w statusie "pending" (SEPA Instant)

- Worker automatycznie spróbuje ponownie za 1 minutę
- Sprawdź logi: `docker-compose logs sepa_instant_worker`

### Sesja batch nie zamyka się

1. Sprawdź czy worker działa: `docker-compose logs sepa_batch_worker`
2. Zameluj ręcznie: `curl -X POST http://localhost:8002/sessions/close/{id}`

---

## Zmienne środowiskowe

| Zmienna                | Opis                                | Domyślna wartość         |
| ---------------------- | ----------------------------------- | ------------------------ |
| DATABASE_URL           | PostgreSQL connection string        | postgresql+asyncpg://... |
| REDIS_URL              | Redis connection string             | redis://localhost:6379/0 |
| TARGET_URL             | TARGET service URL                  | http://localhost:8001    |
| SESSION_CLOSE_INTERVAL | Interwał zamknięcia sesji (sekundy) | 300                      |

---

## Technologie

- Python 3.12
- FastAPI
- PostgreSQL
- Redis
- Celery
- SQLAlchemy
- cryptography (RSA)
- PyJWT
- Docker

---
