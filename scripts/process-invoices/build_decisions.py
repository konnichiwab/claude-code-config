"""
Reads extract_output.json and produces decisions.json.
Run once per session after extract.py, before execute.py.

Usage: python build_decisions.py <extract_output.json> <decisions_output.json>
"""
import json
import re
import sys
import os
from datetime import datetime

VENDORS_JSON = os.path.join(os.path.dirname(__file__), "vendors.json")

# Keywords that identify a non-invoice PDF (case-insensitive filename match)
NON_INVOICE_KEYWORDS = ["receipt", "reçu", "bon de livraison", "belastingdienst", "memo"]

# Keywords that positively identify an invoice PDF
INVOICE_KEYWORDS = ["invoice", "factuur", "rechnung", "order"]


def is_invoice_pdf(filename):
    lower = filename.lower()
    for kw in NON_INVOICE_KEYWORDS:
        if kw in lower:
            return False
    return True


def pick_invoice_pdf(pdfs):
    """Return the best candidate invoice PDF from a list."""
    if len(pdfs) == 1:
        return pdfs[0]
    # Prefer files with invoice keywords
    candidates = [p for p in pdfs if is_invoice_pdf(p["filename"])]
    if candidates:
        return candidates[0]
    # Fall back to first
    return pdfs[0]


NL_MONTHS = {
    "jan": 1, "feb": 2, "mrt": 3, "mar": 3, "apr": 4, "mei": 5, "may": 5,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9, "okt": 10, "oct": 10,
    "nov": 11, "dec": 12,
}

EN_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def extract_date_from_text(text):
    """Try to extract an invoice date from PDF text. Returns YYYY-MM-DD or ''."""
    t = text.replace("\x00", " ")

    # Pattern: "Date of issue June 23, 2026" or "Date due ..."
    m = re.search(r"Date of issue\s+([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", t, re.IGNORECASE)
    if m:
        month = EN_MONTHS.get(m.group(1).lower())
        if month:
            return f"{m.group(3)}-{month:02d}-{int(m.group(2)):02d}"

    # Pattern: "Invoice Date: 01-Jun-2026"
    m = re.search(r"Invoice Date:\s*(\d{1,2})-([A-Za-z]{3})-(\d{4})", t, re.IGNORECASE)
    if m:
        month = EN_MONTHS.get(m.group(2).lower())
        if month:
            return f"{m.group(3)}-{month:02d}-{int(m.group(1)):02d}"

    # Pattern: "Factuurdatum: 16-06-2026" or "Factuurdatum : 1-6-2026"
    m = re.search(r"Factuurdatum\s*:\s*(\d{1,2})-(\d{1,2})-(\d{4})", t, re.IGNORECASE)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"

    # Pattern: "Factuurdatum 27-MEI-2026" (Dutch month abbreviation)
    m = re.search(r"Factuurdatum\s+(\d{1,2})-([A-Za-z]{3,4})-(\d{4})", t, re.IGNORECASE)
    if m:
        month = NL_MONTHS.get(m.group(2).lower()[:3])
        if month:
            return f"{m.group(3)}-{month:02d}-{int(m.group(1)):02d}"

    # Pattern: ISO "2026-06-03" near top of document
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", t)
    if m and 2020 <= int(m.group(1)) <= 2030:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    # Pattern: city + date "Leidschendam, 22 mei 2026"
    m = re.search(r",\s*(\d{1,2})\s+([a-z]+)\s+(\d{4})", t, re.IGNORECASE)
    if m:
        month = NL_MONTHS.get(m.group(2).lower()[:3])
        if month:
            return f"{m.group(3)}-{month:02d}-{int(m.group(1)):02d}"

    # Pattern: "Nieuwegein, 10-04-2026"
    m = re.search(r",\s*(\d{1,2})-(\d{1,2})-(\d{4})", t)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"

    # Pattern: "Datum: 09/05/2026" or "Datum: 09.05.2026"
    m = re.search(r"Datum:\s*(\d{1,2})[/.](\d{1,2})[/.](\d{4})", t, re.IGNORECASE)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"

    return ""


def vendor_from_sender(sender_name, sender_email):
    """Derive a clean short vendor name."""
    name = sender_name.strip()
    # Clean up common noise
    replacements = {
        "Anthropic, PBC": "Anthropic",
        "Vercel Inc.": "Vercel",
        "Noreply SuperGarant": "SuperGarant",
        "TransIP Facturen": "TransIP",
        "facturen-RAAD@RAADNootdorp.nl": "RAAD Nootdorp",
        "RAAD Nootdorp - Peter Schingenga": "RAAD Nootdorp",
        "leverancierbeheer@randstadgroep.nl": "Randstad",
        "servicenl@magnitglobal.com": "Magnit",
    }
    # Also fall back on sender_email domain → name mapping
    result = replacements.get(name)
    if not result:
        result = replacements.get(sender_email, name)
    return result


def main():
    if len(sys.argv) < 3:
        print("Usage: build_decisions.py <extract_output.json> <decisions_output.json>")
        sys.exit(1)

    extract_path = sys.argv[1]
    decisions_path = sys.argv[2]

    with open(VENDORS_JSON, encoding="utf-8") as f:
        vendor_config = json.load(f)

    verkoop_senders = {e.lower() for e in vendor_config.get("verkoop_senders", [])}
    folder_overrides = vendor_config.get("folder_name_overrides", {})

    with open(extract_path, encoding="utf-8") as f:
        data = json.load(f)

    decisions = []

    for email in data["emails"]:
        entry_id = email["entry_id"]
        sender_email = email["sender_email"].lower()
        sender_name = email["sender_name"]
        subject = email["subject"]
        pdfs = email["pdfs"]

        # Determine category
        category = "verkoop" if sender_email in verkoop_senders else "inkoop"

        # Pick invoice PDF
        pdf = pick_invoice_pdf(pdfs)

        # Check if this looks like a non-invoice email (e.g. info memo)
        all_non_invoice = all(not is_invoice_pdf(p["filename"]) for p in pdfs)

        vendor = vendor_from_sender(sender_name, sender_email)
        outlook_folder = folder_overrides.get(vendor, vendor.upper())

        invoice_date = extract_date_from_text(pdf["text"]) if not all_non_invoice else ""
        note = ""
        if all_non_invoice:
            note = "auto-skipped: no invoice PDF found"
        elif not invoice_date:
            note = "⚠️ date not found — needs manual entry"

        decisions.append({
            "action": "skip" if all_non_invoice else "file",
            "entry_id": entry_id,
            "subject": subject,
            "vendor": vendor,
            "outlook_folder": outlook_folder,
            "invoice_date": invoice_date,
            "category": category,
            "pdf_source_path": pdf["temp_path"],
            "pdf_filename": pdf["filename"],
            "_note": note,
        })

    with open(decisions_path, "w", encoding="utf-8") as f:
        json.dump(decisions, f, indent=2, ensure_ascii=False)

    print(f"Written {len(decisions)} decisions to {decisions_path}")
    skipped = sum(1 for d in decisions if d["action"] == "skip")
    filed = len(decisions) - skipped
    print(f"  {filed} to file, {skipped} to skip")


if __name__ == "__main__":
    main()
