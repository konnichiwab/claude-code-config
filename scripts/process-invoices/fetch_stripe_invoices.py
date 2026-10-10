"""Download Stripe-hosted invoices (e.g. OpenAI API top-ups) into Dropbox.

The vendor portal (behind a login) only has to give us the public
invoice.stripe.com/i/<acct>/<token> links; the PDFs themselves are fetched
here without any login.

Usage: python fetch_stripe_invoices.py <invoices.json> <year> <quarter>

invoices.json: {"vendor": "OPENAI",
                "invoices": [{"number": "162BF096-0007", "date": "2026-08-29",
                              "amount": "$10.00", "url": "https://invoice.stripe.com/i/..."}]}
Only invoices dated in the given quarter are saved, to
D:\\Dropbox\\Klootwijk - RAAD\\ESC Online\\{year}\\Inkoop\\Q{n}\\{VENDOR} Invoice-{number}.pdf
Existing files are never overwritten.
"""
import json
import os
import re
import sys

import requests

sys.stdout.reconfigure(encoding="utf-8")

DROPBOX_BASE = r"D:\Dropbox\Klootwijk - RAAD\ESC Online"


def pdf_bytes(hosted_url):
    m = re.search(r"/i/(acct_\w+)/(live_[\w-]+)", hosted_url)
    if not m:
        raise ValueError(f"not a Stripe hosted invoice URL: {hosted_url}")
    r = requests.get(f"https://invoicedata.stripe.com/invoice_pdf_file_url/{m.group(1)}/{m.group(2)}", timeout=30)
    r.raise_for_status()
    pdf = requests.get(r.json()["file_url"], timeout=60)
    pdf.raise_for_status()
    if not pdf.content.startswith(b"%PDF"):
        raise ValueError("response is not a PDF")
    return pdf.content


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, str):  # browser_evaluate(filename=...) saves a JSON-encoded string
        data = json.loads(data)
    year, quarter = int(sys.argv[2]), int(sys.argv[3])
    vendor = data["vendor"].upper()
    dest_dir = os.path.join(DROPBOX_BASE, str(year), "Inkoop", f"Q{quarter}")

    saved = skipped = 0
    for inv in data["invoices"]:
        y, m = int(inv["date"][:4]), int(inv["date"][5:7])
        if y != year or (m - 1) // 3 + 1 != quarter:
            continue
        dest = os.path.join(dest_dir, f"{vendor} Invoice-{inv['number']}.pdf")
        # also skip if it was already handed to the accountant
        if os.path.exists(dest) or os.path.exists(os.path.join(dest_dir, "Verwerkt door RAAD", os.path.basename(dest))):
            print(f"EXISTS: {os.path.basename(dest)}")
            skipped += 1
            continue
        try:
            content = pdf_bytes(inv["url"])
        except Exception as e:
            print(f"ERROR {inv['number']}: {e}")
            continue
        os.makedirs(dest_dir, exist_ok=True)
        with open(dest, "wb") as f:
            f.write(content)
        print(f"SAVED: {dest}  ({inv['date']}, {inv.get('amount', '')})")
        saved += 1
    print(f"{saved} saved, {skipped} already present")


if __name__ == "__main__":
    main()
