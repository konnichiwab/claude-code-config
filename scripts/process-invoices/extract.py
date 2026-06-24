import win32com.client
import pdfplumber
import json
import os
import sys
import tempfile
from datetime import datetime

ACCOUNT_EMAIL = "marc.klootwijk@esconline.nl"
TEMP_BASE = os.path.join(os.environ.get("TEMP", tempfile.gettempdir()), "process_invoices")


def get_inbox():
    outlook = win32com.client.Dispatch("Outlook.Application")
    ns = outlook.GetNamespace("MAPI")
    for account in ns.Accounts:
        if account.SmtpAddress.lower() == ACCOUNT_EMAIL:
            return ns, account.DeliveryStore.GetDefaultFolder(6)
    return ns, ns.GetDefaultFolder(6)


def extract_pdf_text(path):
    try:
        with pdfplumber.open(path) as pdf:
            text = ""
            for page in pdf.pages[:4]:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text[:3000]
    except Exception as e:
        return f"[PDF read error: {e}]"


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_dir = os.path.join(TEMP_BASE, timestamp)
    os.makedirs(temp_dir, exist_ok=True)

    ns, inbox = get_inbox()
    results = []
    errors = []

    for i, item in enumerate(inbox.Items):
        try:
            if item.Class != 43:
                continue

            pdfs = []
            for j, att in enumerate(item.Attachments):
                if not att.FileName.lower().endswith(".pdf"):
                    continue
                safe_name = att.FileName.replace("/", "_").replace("\\", "_")
                temp_path = os.path.join(temp_dir, f"{i}_{j}_{safe_name}")
                att.SaveAsFile(temp_path)
                text = extract_pdf_text(temp_path)
                pdfs.append({
                    "filename": att.FileName,
                    "temp_path": temp_path,
                    "text": text,
                })

            if not pdfs:
                continue

            results.append({
                "entry_id": item.EntryID,
                "sender_email": (item.SenderEmailAddress or "").lower(),
                "sender_name": item.SenderName or "",
                "subject": item.Subject or "",
                "received_time": str(item.ReceivedTime),
                "body": (item.Body or "")[:600],
                "pdfs": pdfs,
            })
        except Exception as e:
            errors.append(f"Item {i}: {e}")
            continue

    print(json.dumps({"temp_dir": temp_dir, "emails": results, "errors": errors},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
