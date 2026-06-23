import asyncio
from xml.etree import ElementTree as ET
import uuid

import pytest
import httpx


# =============================================================================
# Konfiguracja
# =============================================================================
TARGET_URL = "http://localhost:8001"
SEPA_INSTANT_URL = "http://localhost:8003"
SEPA_BATCH_URL = "http://localhost:8002"

BANK_A = {"bic": "BANKPLPW", "name": "Bank Polski A"}
BANK_B = {"bic": "BANKDEXX", "name": "Bank German B"}
BANK_C = {"bic": "BANKFRPP", "name": "Banque France C"}

IBAN_A = "PL61109010140000071219812874"
IBAN_B = "DE89370400440532013000"
IBAN_C = "FR1420041010050500013M02606"
INVALID_IBAN = "PL99999999999999999999999999"


# =============================================================================
# Helper functions
# =============================================================================

def build_iso20022_xml(sender_iban, receiver_iban, sender_bic, receiver_bic,
                       amount, currency="EUR", description="Test XML transfer"):
    e2e_id = str(uuid.uuid4())[:20]
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03">
  <CstmrCdtTrfInitn>
    <PmtInf>
      <PmtMtd>TRF</PmtMtd>
      <PmtId><EndToEndId>{e2e_id}</EndToEndId></PmtId>
      <InstdAmt Ccy="{currency}">{amount:.2f}</InstdAmt>
      <DbtrAcct><Id><IBAN>{sender_iban}</IBAN></Id></DbtrAcct>
      <DbtrAgt><FinInstnId><BIC>{sender_bic}</BIC></FinInstnId></DbtrAgt>
      <CdtrAcct><Id><IBAN>{receiver_iban}</IBAN></Id></CdtrAcct>
      <CdtrAgt><FinInstnId><BIC>{receiver_bic}</BIC></FinInstnId></CdtrAgt>
      <RmtInf><Ustrd>{description}</Ustrd></RmtInf>
    </PmtInf>
  </CstmrCdtTrfInitn>
</Document>"""


def build_malformed_xml():
    return """<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03">
  <CstmrCdtTrfInitn>
    <PmtInf>
      <InstdAmt Ccy="EUR">100.00</InstdAmt>
    </PmtInf>
  </CstmrCdtTrfInitn>
"""


def build_xml_missing_fields():
    e2e_id = str(uuid.uuid4())[:20]
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03">
  <CstmrCdtTrfInitn>
    <PmtInf>
      <PmtMtd>TRF</PmtMtd>
      <PmtId><EndToEndId>{e2e_id}</EndToEndId></PmtId>
      <InstdAmt Ccy="EUR">100.00</InstdAmt>
    </PmtInf>
  </CstmrCdtTrfInitn>
</Document>"""


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(scope="module")
def event_loop():
    """SelectorEventLoop dla zgodności Windows + httpx."""
    policy = asyncio.WindowsSelectorEventLoopPolicy()
    asyncio.set_event_loop_policy(policy)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def target_client():
    async with httpx.AsyncClient(timeout=30.0) as c:
        yield c


@pytest.fixture(scope="module")
async def instant_client():
    async with httpx.AsyncClient(timeout=30.0) as c:
        yield c


@pytest.fixture(scope="module")
async def batch_client():
    async with httpx.AsyncClient(timeout=30.0) as c:
        yield c


@pytest.fixture(scope="module")
async def setup_banks(target_client):
    """Rejestruje banki w TARGET i wstrzykuje płynność."""
    for bank in (BANK_A, BANK_B, BANK_C):
        resp = await target_client.post(f"{TARGET_URL}/banks", json=bank)
        if resp.status_code == 400:
            detail = resp.json().get("detail", "")
            assert "already" in detail.lower(), \
                f"Bank {bank['bic']}: {resp.status_code} - {detail}"
        else:
            assert resp.status_code in (200, 201), \
                f"Bank {bank['bic']}: {resp.status_code}"

    for bic, amount in [("BANKPLPW", 1_000_000), ("BANKDEXX", 500_000)]:
        resp = await target_client.post(
            f"{TARGET_URL}/liquidity/injection",
            json={"bank_bic": bic, "amount": amount, "currency": "EUR"},
        )
        assert resp.status_code == 200, \
            f"Liquidity injection failed for {bic}: {resp.status_code}"


# =============================================================================
# 1. HEALTH CHECKS
# =============================================================================

@pytest.mark.asyncio(loop_scope="module")
class TestHealth:
    """Podstawowe testy stanu serwisów."""

    async def test_target_health(self, target_client):
        """TARGET service - health check."""
        r = await target_client.get(f"{TARGET_URL}/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

    async def test_instant_health(self, instant_client):
        """SEPA Instant service - health check."""
        r = await instant_client.get(f"{SEPA_INSTANT_URL}/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

    async def test_batch_health(self, batch_client):
        """SEPA Batch service - health check."""
        r = await batch_client.get(f"{SEPA_BATCH_URL}/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"


# =============================================================================
# 2. TARGET RTGS
# =============================================================================

@pytest.mark.asyncio(loop_scope="module")
class TestTargetService:
    """Testy TARGET RTGS - przelewy natychmiastowe."""

    async def test_create_bank(self, target_client, setup_banks):
        """Test 1: Tworzenie banku - pozytywny."""
        for bank in (BANK_A, BANK_B, BANK_C):
            r = await target_client.get(f"{TARGET_URL}/banks/{bank['bic']}")
            assert r.status_code == 200
            d = r.json()
            assert d["bic"] == bank["bic"]

    async def test_create_duplicate_bank(self, target_client):
        """Test 2: Duplikat BIC - 400."""
        r = await target_client.post(f"{TARGET_URL}/banks", json=BANK_A)
        assert r.status_code == 400
        assert "already" in r.json().get("detail", "").lower()

    async def test_inject_liquidity(self, target_client, setup_banks):
        """Test 3: Wstrzyknięcie płynności."""
        r = await target_client.get(f"{TARGET_URL}/banks/{BANK_A['bic']}")
        assert r.status_code == 200
        bal = float(r.json()["settlement_accounts"][0]["balance"])
        assert bal >= 0

    async def test_rtgs_transfer_json(self, target_client, setup_banks):
        """Test 4: Przelew RTGS (JSON) - sukces."""
        r = await target_client.post(f"{TARGET_URL}/transfers", json={
            "sender_iban": IBAN_A, "receiver_iban": IBAN_B,
            "sender_bic": BANK_A["bic"], "receiver_bic": BANK_B["bic"],
            "amount": 100, "currency": "EUR", "description": "RTGS 100 EUR",
        })
        assert r.status_code == 200
        assert r.json()["status"] == "settled"

    async def test_rtgs_transfer_insufficient_funds(self, target_client):
        """Test 5: Brak środków - 400."""
        r = await target_client.post(f"{TARGET_URL}/transfers", json={
            "sender_iban": IBAN_C, "receiver_iban": IBAN_B,
            "sender_bic": BANK_C["bic"], "receiver_bic": BANK_B["bic"],
            "amount": 100, "currency": "EUR",
            "description": "brak środków",
        })
        assert r.status_code == 400
        detail = r.json().get("detail", "").lower()
        assert any(w in detail for w in ("insufficient", "blocked"))

    async def test_rtgs_transfer_blocked_sender(self, target_client):
        """Test 6: Blokada nadawcy - 400."""
        r = await target_client.post(
            f"{TARGET_URL}/banks/block/{BANK_A['bic']}"
        )
        assert r.status_code == 200

        r = await target_client.post(f"{TARGET_URL}/transfers", json={
            "sender_iban": IBAN_A, "receiver_iban": IBAN_B,
            "sender_bic": BANK_A["bic"], "receiver_bic": BANK_B["bic"],
            "amount": 100, "currency": "EUR",
            "description": "nadawca zablokowany",
        })
        assert r.status_code == 400
        assert "blocked" in r.json().get("detail", "").lower()

        await target_client.post(f"{TARGET_URL}/banks/unblock/{BANK_A['bic']}")

    async def test_rtgs_transfer_blocked_receiver(self, target_client):
        """Test 7: Blokada odbiorcy - 400."""
        r = await target_client.post(
            f"{TARGET_URL}/banks/block/{BANK_B['bic']}"
        )
        assert r.status_code == 200

        r = await target_client.post(f"{TARGET_URL}/transfers", json={
            "sender_iban": IBAN_A, "receiver_iban": IBAN_B,
            "sender_bic": BANK_A["bic"], "receiver_bic": BANK_B["bic"],
            "amount": 100, "currency": "EUR",
            "description": "odbiorca zablokowany",
        })
        assert r.status_code == 400
        assert "blocked" in r.json().get("detail", "").lower()

        await target_client.post(f"{TARGET_URL}/banks/unblock/{BANK_B['bic']}")

    async def test_rtgs_transfer_invalid_iban(self, target_client):
        """Test 8: Nieprawidłowy IBAN - 400 (walidacja przed DB)."""
        r = await target_client.post(f"{TARGET_URL}/transfers", json={
            "sender_iban": INVALID_IBAN, "receiver_iban": IBAN_B,
            "sender_bic": BANK_A["bic"], "receiver_bic": BANK_B["bic"],
            "amount": 100, "currency": "EUR",
            "description": "zły IBAN",
        })
        assert r.status_code == 400

    async def test_rtgs_transfer_xml(self, target_client):
        """Test 9: Przelew RTGS przez XML ISO 20022."""
        xml = build_iso20022_xml(
            IBAN_A, IBAN_B, BANK_A["bic"], BANK_B["bic"], 200,
        )
        r = await target_client.post(
            f"{TARGET_URL}/transfers/xml",
            content=xml, headers={"Content-Type": "application/xml"},
        )
        assert r.status_code == 200
        assert ET.fromstring(r.text).find(".//TxSts").text == "ACSC"

    async def test_rtgs_recall_transfer(self, target_client, setup_banks):
        """Test 10: Recall rozliczonego przelewu."""
        r = await target_client.post(f"{TARGET_URL}/transfers", json={
            "sender_iban": IBAN_A, "receiver_iban": IBAN_B,
            "sender_bic": BANK_A["bic"], "receiver_bic": BANK_B["bic"],
            "amount": 100, "currency": "EUR", "description": "do recall",
        })
        assert r.status_code == 200
        tid = r.json()["transfer_id"]

        rc = await target_client.post(f"{TARGET_URL}/transfers/{tid}/recall")
        assert rc.status_code == 200
        assert rc.json()["status"] == "recalled"

    async def test_rtgs_recall_not_found(self, target_client):
        """Test 11: Recall nieistniejącego przelewu - 404."""
        r = await target_client.post(
            f"{TARGET_URL}/transfers/{uuid.uuid4()}/recall"
        )
        assert r.status_code == 404

    async def test_rtgs_transfer_bank_not_found(self, target_client):
        """Test 12: Bank nie istnieje - 404."""
        r = await target_client.post(f"{TARGET_URL}/transfers", json={
            "sender_iban": IBAN_A, "receiver_iban": IBAN_B,
            "sender_bic": "FAKEBICXXXX", "receiver_bic": BANK_B["bic"],
            "amount": 100, "currency": "EUR",
            "description": "fake bank",
        })
        assert r.status_code == 404
        assert "not found" in r.json().get("detail", "").lower()

    async def test_rtgs_block_unblock_flow(self, target_client):
        """Test 13: Blokada i odblokowanie banku."""
        bic = BANK_B["bic"]
        r1 = await target_client.post(f"{TARGET_URL}/banks/block/{bic}")
        assert r1.status_code == 200
        assert r1.json()["status"] == "blocked"

        r2 = await target_client.post(f"{TARGET_URL}/banks/unblock/{bic}")
        assert r2.status_code == 200
        assert r2.json()["status"] == "unblocked"


# =============================================================================
# 3. SEPA INSTANT
# =============================================================================

@pytest.mark.asyncio(loop_scope="module")
class TestSepaInstantService:
    """Testy SEPA Instant - płatności natychmiastowe."""

    async def test_instant_transfer_pending_on_no_liquidity(
        self, instant_client, setup_banks
    ):
        """Test 14: Instant bez środków → pending (kolejka gridlock)."""
        r = await instant_client.post(f"{SEPA_INSTANT_URL}/transfers", json={
            "sender_iban": IBAN_C, "receiver_iban": IBAN_B,
            "sender_bic": BANK_C["bic"], "receiver_bic": BANK_B["bic"],
            "bank_bic": BANK_C["bic"],
            "amount": 100, "currency": "EUR",
            "description": "instant - brak środków",
        })
        assert r.status_code == 200
        assert r.json()["status"] in ("pending", "processing")

    async def test_instant_transfer_xml(self, instant_client, setup_banks):
        """Test 15: Instant przez XML ISO 20022."""
        xml = build_iso20022_xml(
            IBAN_C, IBAN_B, BANK_C["bic"], BANK_B["bic"], 50,
        )
        r = await instant_client.post(
            f"{SEPA_INSTANT_URL}/transfers/xml",
            content=xml, headers={"Content-Type": "application/xml"},
        )
        assert r.status_code == 200
        st = ET.fromstring(r.text).find(".//TxSts").text
        assert st in ("ACSC", "PDNG", "RJCT")

    async def test_instant_transfer_invalid_iban(self, instant_client):
        """Test 16: Instant z nieprawidłowym IBAN - 400."""
        r = await instant_client.post(f"{SEPA_INSTANT_URL}/transfers", json={
            "sender_iban": INVALID_IBAN, "receiver_iban": IBAN_B,
            "sender_bic": BANK_A["bic"], "receiver_bic": BANK_B["bic"],
            "bank_bic": BANK_A["bic"],
            "amount": 100, "currency": "EUR",
        })
        assert r.status_code == 400

    async def test_instant_transfer_list(self, instant_client):
        """Test 17: Lista przelewów instant."""
        r = await instant_client.get(f"{SEPA_INSTANT_URL}/transfers")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        if r.json():
            tid = r.json()[0]["transfer_id"]
            sr = await instant_client.get(
                f"{SEPA_INSTANT_URL}/transfers/{tid}"
            )
            assert sr.status_code == 200
            assert sr.json()["transfer_id"] == tid


# =============================================================================
# 4. SEPA BATCH
# =============================================================================

@pytest.mark.asyncio(loop_scope="module")
class TestSepaBatchService:
    """Testy SEPA Batch - batch clearing z multilateral netting."""

    async def test_batch_queue_single(self, batch_client, setup_banks):
        """Test 18: Kolejkowanie pojedynczego przelewu batch."""
        r = await batch_client.post(f"{SEPA_BATCH_URL}/transfers", json={
            "sender_iban": IBAN_A, "receiver_iban": IBAN_B,
            "sender_bic": BANK_A["bic"], "receiver_bic": BANK_B["bic"],
            "bank_bic": BANK_A["bic"],
            "amount": 500, "currency": "EUR",
            "description": "batch 500 EUR",
        })
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "queued"
        assert d["session_id"]
        assert d["transfer_id"]

    async def test_batch_queue_multiple(self, batch_client):
        """Test 19: Wiele przelewów w jednej sesji."""
        transfers = [
            (IBAN_A, IBAN_B, BANK_A["bic"], BANK_B["bic"], 200),
            (IBAN_B, IBAN_A, BANK_B["bic"], BANK_A["bic"], 150),
            (IBAN_A, IBAN_B, BANK_A["bic"], BANK_B["bic"], 300),
        ]
        sessions = set()
        for si, ri, sb, rb, amt in transfers:
            r = await batch_client.post(f"{SEPA_BATCH_URL}/transfers", json={
                "sender_iban": si, "receiver_iban": ri,
                "sender_bic": sb, "receiver_bic": rb,
                "bank_bic": sb,
                "amount": amt, "currency": "EUR",
            })
            assert r.status_code == 200
            sessions.add(r.json()["session_id"])
        assert len(sessions) == 1, f"Transfery w różnych sesjach: {sessions}"

    async def test_batch_close_and_netting(self, batch_client):
        """Test 20: Zamknięcie sesji i multilateral netting."""
        r = await batch_client.get(f"{SEPA_BATCH_URL}/sessions")
        assert r.status_code == 200
        open_ss = [s for s in r.json() if s["status"] == "open"]
        if not open_ss:
            pytest.skip("Brak otwartej sesji do zamknięcia")
        sid = open_ss[0]["session_id"]

        cr = await batch_client.post(
            f"{SEPA_BATCH_URL}/sessions/close/{sid}"
        )
        assert cr.status_code == 200
        result = cr.json()
        assert result["status"] == "closed"
        netting = result.get("netting", {})
        assert netting.get("transfers_processed", 0) > 0

        pos = netting.get("bank_positions", {})
        assert BANK_A["bic"] in pos
        assert BANK_B["bic"] in pos
        assert pos[BANK_A["bic"]]["net_position"] != 0
        assert pos[BANK_B["bic"]]["net_position"] != 0

    async def test_batch_session_detail(self, batch_client):
        """Test 21: Szczegóły zamkniętej sesji."""
        r = await batch_client.get(f"{SEPA_BATCH_URL}/sessions")
        assert r.status_code == 200
        closed = [s for s in r.json() if s["status"] == "closed"]
        if not closed:
            pytest.skip("Brak zamkniętej sesji")
        dr = await batch_client.get(
            f"{SEPA_BATCH_URL}/sessions/{closed[-1]['session_id']}"
        )
        assert dr.status_code == 200
        assert dr.json()["status"] == "closed"
        assert len(dr.json().get("netting_results", [])) > 0

    async def test_batch_netting_blocks_insolvent(
        self, batch_client, target_client
    ):
        """Test 22: Netting blokuje bank bez środków."""
        r = await batch_client.post(f"{SEPA_BATCH_URL}/transfers", json={
            "sender_iban": IBAN_C, "receiver_iban": IBAN_A,
            "sender_bic": BANK_C["bic"], "receiver_bic": BANK_A["bic"],
            "bank_bic": BANK_C["bic"],
            "amount": 50, "currency": "EUR",
            "description": "C → A - brak środków",
        })
        assert r.status_code == 200
        sid = r.json()["session_id"]

        cr = await batch_client.post(
            f"{SEPA_BATCH_URL}/sessions/close/{sid}"
        )
        assert cr.status_code == 200
        blocked = cr.json().get("netting", {}).get("blocked_banks", [])
        if blocked:
            assert BANK_C["bic"] in blocked
            await target_client.post(
                f"{TARGET_URL}/banks/unblock/{BANK_C['bic']}"
            )


# =============================================================================
# 5. GRIDLOCK RESOLUTION
# =============================================================================

@pytest.mark.asyncio(loop_scope="module")
class TestGridlockResolution:
    """Testy gridlock - kolejkowanie i retry."""

    async def test_gridlock_pending_queue(
        self, instant_client, setup_banks
    ):
        """Test 23: Gridlock - kolejka dla nieudanego przelewu."""
        r = await instant_client.post(f"{SEPA_INSTANT_URL}/transfers", json={
            "sender_iban": IBAN_C, "receiver_iban": IBAN_A,
            "sender_bic": BANK_C["bic"], "receiver_bic": BANK_A["bic"],
            "bank_bic": BANK_C["bic"],
            "amount": 100, "currency": "EUR",
            "description": "gridlock - kolejkuj",
        })
        assert r.status_code == 200
        assert r.json()["status"] == "pending"

    async def test_gridlock_inject_and_resolve(
        self, target_client, instant_client, setup_banks
    ):
        """Test 24: Gridlock - pelny cykl: pending -> inject -> settle."""
        r = await instant_client.post(f"{SEPA_INSTANT_URL}/transfers", json={
            "sender_iban": IBAN_C, "receiver_iban": IBAN_A,
            "sender_bic": BANK_C["bic"], "receiver_bic": BANK_A["bic"],
            "bank_bic": BANK_C["bic"],
            "amount": 100, "currency": "EUR",
            "description": "gridlock - pelny cykl",
        })
        assert r.status_code == 200
        assert r.json()["status"] == "pending"
        tid = r.json()["transfer_id"]

        r = await target_client.post(f"{TARGET_URL}/liquidity/injection", json={
            "bank_bic": BANK_C["bic"], "amount": 1_000_000, "currency": "EUR",
        })
        assert r.status_code == 200

        r = await target_client.post(f"{TARGET_URL}/settle/payment", json={
            "transaction_id": tid,
            "sender_iban": IBAN_C, "receiver_iban": IBAN_A,
            "sender_bic": BANK_C["bic"], "receiver_bic": BANK_A["bic"],
            "amount": 100, "currency": "EUR",
            "description": "gridlock retry",
            "service": "sepa_instant_retry",
        })
        assert r.status_code == 200
        assert r.json()["status"] == "settled"

        r = await target_client.post(f"{TARGET_URL}/settle/payment", json={
            "transaction_id": f"cleanup-{uuid.uuid4()}",
            "sender_iban": IBAN_C, "receiver_iban": IBAN_A,
            "sender_bic": BANK_C["bic"], "receiver_bic": BANK_A["bic"],
            "amount": 999_900, "currency": "EUR",
            "description": "cleanup - drain C back to 0",
            "service": "cleanup",
        })
        assert r.status_code == 200


# =============================================================================
# 6. ISO 20022 XML - NEGATYWNE
# =============================================================================

@pytest.mark.asyncio(loop_scope="module")
class TestXmlIso20022:
    """Testy parsowania XML - scenariusze negatywne."""

    async def test_xml_malformed(self, target_client):
        """Test 25: Zniekształcony XML → 400."""
        r = await target_client.post(
            f"{TARGET_URL}/transfers/xml",
            content=build_malformed_xml(),
            headers={"Content-Type": "application/xml"},
        )
        assert r.status_code == 400

    async def test_xml_missing_fields(self, target_client):
        """Test 26: XML bez IBAN/BIC → 400."""
        r = await target_client.post(
            f"{TARGET_URL}/transfers/xml",
            content=build_xml_missing_fields(),
            headers={"Content-Type": "application/xml"},
        )
        assert r.status_code == 400

    async def test_xml_batch_valid(self, batch_client):
        """Test 27: XML ISO 20022 w SEPA Batch."""
        xml = build_iso20022_xml(
            IBAN_A, IBAN_B, BANK_A["bic"], BANK_B["bic"], 75,
        )
        r = await batch_client.post(
            f"{SEPA_BATCH_URL}/transfers/xml",
            content=xml, headers={"Content-Type": "application/xml"},
        )
        assert r.status_code == 200
        st = ET.fromstring(r.text).find(".//TxSts").text
        assert st == "ACCP"
