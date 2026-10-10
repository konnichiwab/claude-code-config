"""File Simyo invoices fetched from mijn.simyo.nl into Dropbox.

Simyo's portal labels each invoice with the *usage* month ("Juni 2026"), but
the PDF's Factuurdatum is ~a week into the next month and it also covers that
next month's subscription. So the portal label is one month behind: always
file by the Factuurdatum printed on the PDF, never by the label.

Usage: python file_simyo.py <simyo.json> <year> <quarter>

simyo.json (written by the browser step, see skill Section F):
  {"list": [{"href": "/factuur/98402997", "text": "Augustus 2026 Betaald € 5,74"}, ...],
   "pdfs": {"98402997": "<base64 PDF>", ...}}
Saves invoices whose Factuurdatum falls in the quarter as
  Inkoop\\Q{n}\\SIMYO Factuur {number}.pdf   (never overwrites)
"""
import base64
import io
import json
import os
import re
import sys

import pdfplumber

sys.stdout.reconfigure(encoding="utf-8")

DROPBOX_BASE = r"D:\Dropbox\Klootwijk - RAAD\ESC Online"


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, str):  # browser_evaluate(filename=...) saves a JSON-encoded string
        data = json.loads(data)
    year, quarter = int(sys.argv[2]), int(sys.argv[3])
    dest_dir = os.path.join(DROPBOX_BASE, str(year), "Inkoop", f"Q{quarter}")
    labels = {i["href"].rsplit("/", 1)[-1]: i["text"] for i in data.get("list", [])}

    for number, b64 in sorted(data["pdfs"].items()):
        content = base64.b64decode(b64)
        if not content.startswith(b"%PDF"):
            print(f"ERROR {number}: not a PDF (session expired?)")
            continue
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            text = " ".join((p.extract_text() or "") for p in pdf.pages)
        m = re.search(r"Factuurdatum\s*:?\s*(\d{2})-(\d{2})-(\d{4})", text)
        if not m:
            print(f"ERROR {number}: no Factuurdatum found, check manually")
            continue
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        label = labels.get(number, "")
        if y != year or (mo - 1) // 3 + 1 != quarter:
            print(f"SKIP {number}: Factuurdatum {y}-{mo:02d}-{d:02d} is not in {year} Q{quarter}  [{label}]")
            continue
        dest = os.path.join(dest_dir, f"SIMYO Factuur {number}.pdf")
        if os.path.exists(dest) or os.path.exists(os.path.join(dest_dir, "Verwerkt door RAAD", os.path.basename(dest))):
            print(f"EXISTS: {os.path.basename(dest)}")
            continue
        os.makedirs(dest_dir, exist_ok=True)
        with open(dest, "wb") as f:
            f.write(content)
        print(f"SAVED: {dest}  (Factuurdatum {y}-{mo:02d}-{d:02d}; portal label '{label}')")


if __name__ == "__main__":
    main()
