import win32com.client
import json
import shutil
import os
import sys

ACCOUNT_EMAIL = "marc.klootwijk@esconline.nl"
DROPBOX_BASE = r"D:\Dropbox\Klootwijk - RAAD\ESC Online"


def get_inbox():
    outlook = win32com.client.Dispatch("Outlook.Application")
    ns = outlook.GetNamespace("MAPI")
    for account in ns.Accounts:
        if account.SmtpAddress.lower() == ACCOUNT_EMAIL:
            return ns, account.DeliveryStore.GetDefaultFolder(6)
    return ns, ns.GetDefaultFolder(6)


def get_or_create_subfolder(inbox, name):
    for folder in inbox.Folders:
        if folder.Name.upper() == name.upper():
            return folder
    return inbox.Folders.Add(name)


def main():
    if len(sys.argv) < 2:
        print("Usage: execute.py <decisions.json>")
        sys.exit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        decisions = json.load(f)

    ns, inbox = get_inbox()

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
                dest_dir = os.path.join(DROPBOX_BASE, year, "Verkoop")
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

            item = ns.GetItemFromID(d["entry_id"])
            original_subject = item.Subject or ""
            item.Subject = f"{vendor_upper} - {original_subject}"
            item.Save()

            target_folder = get_or_create_subfolder(inbox, outlook_folder)
            item.Move(target_folder)
            print(f"MOVED: '{subject}' → Outlook folder '{outlook_folder}'")

        except Exception as e:
            print(f"ERROR on '{subject}': {e}")
            continue


if __name__ == "__main__":
    main()
