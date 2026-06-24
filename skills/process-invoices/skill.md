---
name: process-invoices
description: Process monthly invoices from Outlook inbox — classify, extract dates from PDFs, file to Dropbox, and move emails to vendor folders
allowed-tools: Bash, Read, Write
---

Process monthly invoices from the Outlook inbox (marc.klootwijk@esconline.nl) by following these steps exactly.

## Step 1 — Check dependencies

Run:
```
pip show pywin32 pdfplumber
```
If either package is missing, install it: `pip install pywin32 pdfplumber`

## Step 2 — Extract emails from Outlook

Run the extraction script and capture its output:
```
python "C:/Users/mjjkl/.claude/scripts/process-invoices/extract.py"
```

Also read the vendor config:
```
C:/Users/mjjkl/.claude/scripts/process-invoices/vendors.json
```

## Step 3 — Analyse each email

For every email in the extracted JSON, determine:

**Category (inkoop vs verkoop)**
- If `sender_email` matches any address in `verkoop_senders` in vendors.json → `verkoop`
- Otherwise → `inkoop`

**Which PDF is the invoice**
- If there is only one PDF, use it.
- If there are multiple PDFs, read the filenames and PDF text to identify the invoice (vs receipt, delivery note, packing slip, etc.). Invoices typically show an invoice number, a total amount due, and a payment date/term.

**Invoice date**
- Extract from the invoice PDF text. Look for labels like "Invoice Date", "Datum", "Date:", "Factuurdatum", "Invoice date:", or a date near the top of the document.
- Target format: YYYY-MM-DD. If only month+year is found, use the last day of that month.
- If the date cannot be extracted with confidence, flag this item for manual review.

**Vendor name**
- Derive a short, clean vendor name from `sender_name` or the PDF content (e.g. "Amazon Web Services EMEA SARL" → "AWS", "Microsoft Ireland Operations Limited" → "Microsoft").
- Check `folder_name_overrides` in vendors.json. If the vendor has an entry there, use that value as the `outlook_folder` (the Outlook subfolder name to move the email into); otherwise use the vendor name itself.

## Step 4 — Present summary for review

Show a table:

| # | Sender | Vendor | Invoice Date | Category | Destination | Invoice PDF | Notes |
|---|--------|--------|--------------|----------|-------------|-------------|-------|
| 1 | aws@amazon.com | AWS | 2026-05-15 | Inkoop | 2026/Inkoop/Q2 | invoice.pdf | |

Use **Notes** to flag: uncertain date, ambiguous PDF selection, unknown vendor, or any other issue.

Ask the user: **"Does this look correct? Reply YES to proceed, or tell me what needs adjusting."**

## Step 5 — Execute after confirmation

Once the user confirms, build a decisions JSON array with one object per email:

```json
[
  {
    "action": "file",
    "entry_id": "...",
    "subject": "...",
    "vendor": "AWS",
    "outlook_folder": "AWS",
    "invoice_date": "2026-05-15",
    "category": "inkoop",
    "pdf_source_path": "C:/...temp path from extract output...",
    "pdf_filename": "invoice.pdf"
  }
]
```

For skipped or flagged items use `"action": "skip"`.

Write the decisions to a temp file (e.g. `%TEMP%/process_invoices_decisions.json`), then run:
```
python "C:/Users/mjjkl/.claude/scripts/process-invoices/execute.py" "<path_to_decisions_json>"
```

## Step 6 — Report results

Show which emails were successfully filed and moved, and list any errors so the user can handle them manually.

---

**What the execute script does per email:**
- Copies the invoice PDF to `D:\Dropbox\Klootwijk - RAAD\ESC Online\{year}\{Inkoop\Q{n} or Verkoop}\` with filename `VENDOR originalfilename.pdf`
- Renames the Outlook email subject to `VENDOR - original subject`
- Moves the email from Inbox to the vendor subfolder (creates the subfolder if it doesn't exist yet)
