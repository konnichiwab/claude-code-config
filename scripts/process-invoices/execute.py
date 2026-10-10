import json
import re
import shutil
import os
import sys

import bank
from graph import Graph

sys.stdout.reconfigure(encoding="utf-8")

DROPBOX_BASE = r"D:\Dropbox\Klootwijk - RAAD\ESC Online"


def get_or_create_subfolder(g, name):
    for folder in g.get_all("/me/mailFolders/inbox/childFolders", params={"$select": "id,displayName", "$top": "100"}):
        if folder["displayName"].upper() == name.upper():
            return folder["id"]
    return g.post("/me/mailFolders/inbox/childFolders", {"displayName": name})["id"]


def main():
    # --bank-quarter YYYYQn: the quarter whose bank statements decide which
    # verkoop invoices count as paid. Required when filing verkoop invoices.
    args = sys.argv[1:]
    bank_quarter = None
    if "--bank-quarter" in args:
        i = args.index("--bank-quarter")
        bank_quarter = args[i + 1]
        del args[i:i + 2]
    if len(args) != 1:
        print("Usage: execute.py <decisions.json> [--bank-quarter 2026Q3]")
        sys.exit(1)

    with open(args[0], encoding="utf-8") as f:
        decisions = json.load(f)

    bank_txns = None
    if any(d.get("action") == "file" and d.get("category") == "verkoop" for d in decisions):
        m = re.fullmatch(r"(\d{4})Q([1-4])", bank_quarter or "")
        if not m:
            print("ERROR: verkoop invoices present; pass --bank-quarter YYYYQn")
            sys.exit(1)
        bank_txns = bank.credits(int(m.group(1)), int(m.group(2)))

    g = Graph()

    for d in decisions:
        subject = d.get("subject", "unknown")

        if d.get("action") != "file":
            print(f"SKIP: {subject}")
            continue

        try:
            vendor = d["vendor"]
            vendor_upper = vendor.upper()
            invoice_date = d["invoice_date"]  # YYYY-MM-DD
            category = d["category"]          # inkoop or verkoop
            pdf_source = d["pdf_source_path"]
            pdf_filename = d["pdf_filename"]
            outlook_folder = d.get("outlook_folder", vendor_upper)

            year = invoice_date[:4]
            month = int(invoice_date[5:7])
            quarter = (month - 1) // 3 + 1

            if category == "verkoop":
                # Only file verkoop invoices once paid within the bank quarter;
                # unpaid ones stay untouched in the inbox for a later quarter.
                ref = d.get("invoice_number") or next(iter(re.findall(r"ESC69\d{7}", f"{pdf_filename} {subject}")), None)
                if not ref:
                    print(f"UNPAID-CHECK FAILED (no invoice number, left in inbox): {subject}")
                    continue
                payment = bank.find_payment(ref, bank_txns)
                if not payment:
                    print(f"UNPAID in {bank_quarter} (left in inbox): {ref}")
                    continue
                print(f"PAID: {ref} on {payment['date']} EUR {payment['amount']:.2f}")
                dest_dir = os.path.join(DROPBOX_BASE, payment["date"][:4], "Verkoop")
            else:
                dest_dir = os.path.join(DROPBOX_BASE, year, "Inkoop", f"Q{quarter}")

            os.makedirs(dest_dir, exist_ok=True)

            dest_filename = f"{vendor_upper} {pdf_filename}"
            dest_path = os.path.join(dest_dir, dest_filename)

            if os.path.exists(dest_path):
                print(f"WARNING: file already exists, skipping copy: {dest_path}")
            else:
                shutil.copy2(pdf_source, dest_path)
                print(f"SAVED: {dest_path}")

            msg_id = d["entry_id"]
            original_subject = g.get(f"/me/messages/{msg_id}", params={"$select": "subject"}).get("subject") or ""
            g.patch(f"/me/messages/{msg_id}", {"subject": f"{vendor_upper} - {original_subject}"})

            target_folder = get_or_create_subfolder(g, outlook_folder)
            g.post(f"/me/messages/{msg_id}/move", {"destinationId": target_folder})
            print(f"MOVED: '{subject}' -> Outlook folder '{outlook_folder}'")

        except Exception as e:
            print(f"ERROR on '{subject}': {e}")
            continue


if __name__ == "__main__":
    main()
