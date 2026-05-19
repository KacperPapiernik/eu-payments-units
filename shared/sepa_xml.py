from decimal import Decimal
from xml.etree import ElementTree as ET


def _namespace(root):
    if root.tag.startswith("{"):
        return {"ns": root.tag.split("}")[0].strip("{")}
    return {}


def _find_text(root, path, ns):
    element = root.find(path, ns)
    return element.text if element is not None else None


def parse_iso20022_payment_xml(xml_body: str) -> dict:
    root = ET.fromstring(xml_body)
    ns = _namespace(root)

    if ns:
        amount_el = root.find(".//ns:InstdAmt", ns)
        transfer_id = _find_text(root, ".//ns:PmtId/ns:EndToEndId", ns)
        sender_iban = _find_text(root, ".//ns:DbtrAcct/ns:Id/ns:IBAN", ns)
        receiver_iban = _find_text(root, ".//ns:CdtrAcct/ns:Id/ns:IBAN", ns)
        sender_bic = _find_text(root, ".//ns:DbtrAgt/ns:FinInstnId/ns:BIC", ns)
        receiver_bic = _find_text(root, ".//ns:CdtrAgt/ns:FinInstnId/ns:BIC", ns)
        description = _find_text(root, ".//ns:RmtInf/ns:Ustrd", ns)
    else:
        amount_el = root.find(".//InstdAmt")
        transfer_id = _find_text(root, ".//PmtId/EndToEndId", ns)
        sender_iban = _find_text(root, ".//DbtrAcct/Id/IBAN", ns)
        receiver_iban = _find_text(root, ".//CdtrAcct/Id/IBAN", ns)
        sender_bic = _find_text(root, ".//DbtrAgt/FinInstnId/BIC", ns)
        receiver_bic = _find_text(root, ".//CdtrAgt/FinInstnId/BIC", ns)
        description = _find_text(root, ".//RmtInf/Ustrd", ns)

    if amount_el is None or amount_el.text is None:
        raise ValueError("Missing amount: InstdAmt")

    return {
        "external_reference": transfer_id,
        "sender_iban": sender_iban,
        "receiver_iban": receiver_iban,
        "sender_bic": sender_bic,
        "receiver_bic": receiver_bic,
        "amount": Decimal(amount_el.text),
        "currency": amount_el.attrib.get("Ccy", "EUR"),
        "description": description,
    }


def build_payment_status_xml(status: str, transfer_id: str, session_id: str | None = None) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Document>
  <CstmrPmtStsRpt>
    <OrgnlPmtInfAndSts>
      <OrgnlEndToEndId>{transfer_id}</OrgnlEndToEndId>
      <TxSts>{status}</TxSts>
      <SplmtryData>
        <Envlp>
          <SessionId>{session_id or ""}</SessionId>
        </Envlp>
      </SplmtryData>
    </OrgnlPmtInfAndSts>
  </CstmrPmtStsRpt>
</Document>
"""