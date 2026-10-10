import pdfplumber
import json
import os
import sys
import tempfile
from datetime import datetime

from graph import Graph

sys.stdout.reconfigure(encoding="utf-8")

TEMP_BASE = os.path.join(os.environ.get("TEMP", tempfile.gettempdir()), "process_invoices")


def extract_pdf_text(path):
    try:
        with pdfplumber.open(path) as pdf:
            text = ""
            for page in pdf.pages[:4]:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text[:1500]
    except Exception as e:
        return f"[PDF read error: {e}]"


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_dir = os.path.join(TEMP_BASE, timestamp)
    os.makedirs(temp_dir, exist_ok=True)

    g = Graph()
    results = []
    errors = []

    messages = g.get_all("/me/mailFolders/inbox/messages", params={
        "$filter": "hasAttachments eq true",
        "$select": "id,subject,from,receivedDateTime,bodyPreview",
        "$top": "50",
    })

    for i, msg in enumerate(messages, 1):
        try:
            attachments = g.get_all(f"/me/messages/{msg['id']}/attachments",
                                    params={"$select": "id,name,contentType"})
            pdfs = []
            for j, att in enumerate(attachments, 1):
                name = att.get("name") or ""
                if att.get("@odata.type") != "#microsoft.graph.fileAttachment" or not name.lower().endswith(".pdf"):
                    continue
                safe_name = name.replace("/", "_").replace("\\", "_")
                temp_path = os.path.join(temp_dir, f"{i}_{j}_{safe_name}")
                with open(temp_path, "wb") as f:
                    f.write(g.get_bytes(f"/me/messages/{msg['id']}/attachments/{att['id']}/$value"))
                pdfs.append({
                    "filename": name,
                    "temp_path": temp_path,
                    "text": extract_pdf_text(temp_path),
                })

            if not pdfs:
                continue

            sender = (msg.get("from") or {}).get("emailAddress", {})
            results.append({
                "entry_id": msg["id"],
                "sender_email": (sender.get("address") or "").lower(),
                "sender_name": sender.get("name") or "",
                "subject": msg.get("subject") or "",
                "received_time": msg.get("receivedDateTime") or "",
                "body": (msg.get("bodyPreview") or "")[:600],
                "pdfs": pdfs,
            })
        except Exception as e:
            errors.append(f"{msg.get('subject')!r}: {e}")
            continue

    output_path = os.path.join(temp_dir, "extract_output.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"temp_dir": temp_dir, "emails": results, "errors": errors},
                  f, indent=2, ensure_ascii=False)
    print(f"OUTPUT:{output_path}")
    print(f"Inbox messages with attachments: {len(messages)}, with PDFs: {len(results)}, errors: {len(errors)}")


if __name__ == "__main__":
    main()
