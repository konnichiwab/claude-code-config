---
name: process-invoices
description: Process monthly invoices — Outlook inbox emails, KPN web invoices, and Dropbox subscription invoices — filing all PDFs to Dropbox and tidying Outlook
allowed-tools: Bash, Read, Write, mcp__playwright__browser_navigate, mcp__playwright__browser_click, mcp__playwright__browser_snapshot, mcp__playwright__browser_take_screenshot, mcp__playwright__browser_tabs, mcp__playwright__browser_run_code_unsafe, mcp__playwright__browser_evaluate
---

Process monthly invoices by completing all three sections below in order.

## Step 1 — Check dependencies

Run:
```
pip show msal requests pdfplumber
```
If any package is missing, install it: `pip install msal requests pdfplumber`

## Step 2 — Extract emails from Outlook

Mail is read through **Microsoft Graph**, not Outlook COM. The user runs the *new* Outlook (`olk.exe`), which has no COM API; COM would launch classic Outlook, whose profile holds an old Source for Quality account and prompts for a login. Never use `win32com` for this.

The scripts sign in as marc.klootwijk@esconline.nl (delegated `Mail.ReadWrite`, Microsoft's Graph CLI public client — no app registration). The token cache is at `%LOCALAPPDATA%\process-invoices\msal_cache.json`. If it has expired, the script opens a browser login — run it in the background and ask the user to sign in. To test sign-in alone: `python graph.py`. The scripts refuse to run against any other mailbox.

Run the extraction script (prints `OUTPUT:<path to extract_output.json>`):
```
python "C:/Users/mjjkl/.claude/scripts/process-invoices/extract.py"
```

`build_decisions.py <extract_output.json> <decisions.json>` produces a first-draft decisions file (vendor, date, invoice-vs-receipt PDF). Review it against Step 3 — e.g. it does not skip RAAD's quarterly "Administratie" report pack or GitHub receipts (personal account konnichiwab; ask the user).

Also read the vendor config:
```
C:/Users/mjjkl/.claude/scripts/process-invoices/vendors.json
```

## Step 3 — Analyse each email

For every email in the extracted JSON, determine:

**Category (inkoop vs verkoop)**
- If `sender_email` matches any address in `verkoop_senders` in vendors.json → `verkoop`
- Otherwise → `inkoop`

**Verkoop: only once paid (rule set by the user)**
- A verkoop invoice is filed only when its payment arrived in the quarter being processed. Unpaid ones stay untouched in the inbox and get picked up in a later quarter. No temp copies are needed, because the email keeps the PDF.
- Payments come from the bunq MT940 statements in `D:\Dropbox\Klootwijk - RAAD\ESC Online\{year}\Bank\Q{n}\*.sta`. A payment matches when the invoice number appears in the credit's description. Randstad writes it as `Betalingskenmerk ESC690000012`.
- To preview: `python bank.py 2026 3` lists that quarter's incoming payments. Use `bank.credits()` / `bank.find_payment()` to show paid/unpaid in the Step 4 table.
- If the quarter's `.sta` files aren't in Dropbox yet, ask the user to export them from bunq first.

**Which PDF is the invoice**
- If there is only one PDF, use it.
- If there are multiple PDFs, read the filenames and PDF text to identify the invoice (vs receipt, delivery note, packing slip, etc.). Invoices typically show an invoice number, a total amount due, and a payment date/term.

**Invoice date**
- Extract from the invoice PDF text. Look for labels like "Invoice Date", "Datum", "Date:", "Factuurdatum", "Invoice date:", or a date near the top of the document.
- Target format: YYYY-MM-DD. If only month+year is found, use the last day of that month.
- If the date cannot be extracted with confidence, flag this item for manual review.

**Vendor name**
- Derive a short, clean vendor name from `sender_name` or the PDF content (e.g. "Amazon Web Services EMEA SARL" → "AWS", "Microsoft Ireland Operations Limited" → "Microsoft").
- Check `folder_name_overrides` in vendors.json. If the vendor has an entry there, use that value as the `outlook_folder` (the Outlook subfolder name to move the email into); otherwise use the vendor name itself (not upper-cased — existing folders match case-insensitively, new ones are created with this exact name). Current overrides: RAAD → `_Algemeen`, Randstad (intermediary for ABN) → `ABN Amro`, SuperGarant → `ZZP Nederland`. Add new ones the user gives you.

## Step 4 — Present summary for review

Show a table:

| # | Sender | Vendor | Invoice Date | Category | Destination | Invoice PDF | Notes |
|---|--------|--------|--------------|----------|-------------|-------------|-------|
| 1 | aws@amazon.com | AWS | 2026-05-15 | Inkoop | 2026/Inkoop/Q2 | invoice.pdf | |
| 2 | leverancierbeheer@randstadgroep.nl | Randstad | 2026-09-22 | Verkoop | stays in inbox | INV_…021_1.pdf | unpaid in Q3 |

Use **Notes** to flag: uncertain date, ambiguous PDF selection, unknown vendor, verkoop paid date or "unpaid", or any other issue.

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
    "pdf_filename": "invoice.pdf",
    "invoice_number": "ESC690000012"
  }
]
```

`invoice_number` is only used for verkoop. If it's missing, the script looks for `ESC69xxxxxxx` in the filename or subject.

For skipped or flagged items use `"action": "skip"`.

Write the decisions to a temp file (e.g. `%TEMP%/process_invoices_decisions.json`), then run:
```
python "C:/Users/mjjkl/.claude/scripts/process-invoices/execute.py" "<path_to_decisions_json>" --bank-quarter 2026Q3
```

`--bank-quarter` is the quarter being processed. It's required whenever the decisions include verkoop invoices to file.

## Step 6 — Report results

Show which emails were successfully filed and moved, and list any errors so the user can handle them manually.

---

**What the execute script does per email:**
- For verkoop, checks first for a payment in the `--bank-quarter` bank statements. If there is none, it prints `UNPAID … (left in inbox)` and leaves the email alone. If paid, the PDF goes to `{payment year}\Verkoop\`.
- Copies the invoice PDF to `D:\Dropbox\Klootwijk - RAAD\ESC Online\{year}\{Inkoop\Q{n} or Verkoop}\` with filename `VENDOR originalfilename.pdf`
- Renames the Outlook email subject to `VENDOR - original subject`
- Moves the email from Inbox to the vendor subfolder (creates the subfolder if it doesn't exist yet)

---

## Section B — KPN invoices (mobile + internet)

KPN does not send invoices by email. Download them from MijnKPN each cycle.

### B1 — Navigate and log in

Open: https://www.kpn.com/mijn/facturen

The user must log in manually (requires phone 2FA). Wait for confirmation before proceeding.

### B2 — Determine which invoices to download

Ask the user which quarter is being processed, then determine the date range:
- Q1: Jan–Mar, Q2: Apr–Jun, Q3: Jul–Sep, Q4: Oct–Dec

### B3 — Download invoices

On the Facturen page there are two subscriptions:
- **06-36 59 93 96** — mobile phone
- **Triangelweg 7** — home internet

Each invoice row has a button named `Factuur downloaden {subscription} - {dd maand yyyy}` (e.g. `Factuur downloaden Triangelweg 7 - 09 juli 2026`). The list sits inside an iframe, so a plain `document.querySelectorAll` on the top page finds nothing — use `browser_run_code_unsafe` and search `page.frames()` for `getByRole('button', { name: ... })`. Wrap each click in `page.waitForEvent('download')` and `saveAs()` to a temp folder.

KPN's own filenames (`suggestedFilename()`, as of Q3 2026) look like:
- `KPN_2026_juli_06-36599396.pdf`
- `KPN_2026_juli_Triangelweg 7.pdf`

(Playwright's auto-saved copy in `.playwright-mcp\` additionally replaces spaces/underscores with dashes — ignore that copy.) Don't use these names as-is; rename per B4.

### B4 — Save to Dropbox

Save each file under the established naming convention (matches earlier quarters):
```
D:\Dropbox\Klootwijk - RAAD\ESC Online\{year}\Inkoop\Q{n}\KPN 06-36 59 93 96_{maand}_{year}.pdf
D:\Dropbox\Klootwijk - RAAD\ESC Online\{year}\Inkoop\Q{n}\KPN Triangelweg 7_{maand}_{year}.pdf
```

Month names are Dutch lowercase (`juli`, `augustus`, `september`). Use `cp -n` so existing files are never overwritten, and check `Q{n}\Verwerkt door RAAD\` first — files there have already been handed to the accountant.

---

## Section C — Dropbox subscription invoices

Dropbox Essentials is billed monthly (~€16.52). Download invoices for the processed quarter.

### C1 — Navigate and log in

Open: https://www.dropbox.com/manage/billing

The user must log in manually. Wait for confirmation before proceeding.

### C2 — Download invoices as PDF

The billing table is built from `div[role="row"]` elements, not `<tr>`. Each row has `data-testid="billing-history-table-row-{i}"` (row 0 = most recent), and its description is in `[data-testid="billing-history-table-row-{i}-description"]`, e.g. `Dropbox Essentials (07/19/2026 to 08/19/2026)`. Name the file after the month the period starts in.

For each invoice in the target quarter:
1. Click the `...` (Open menu) button on the row (the last `button` in the row)
2. Click **Invoice** — this opens a new tab with the invoice as a web page
3. Switch to the new tab, wait for `networkidle`, then hide any modals/overlays:
   ```js
   document.querySelectorAll('[class*="modal"], [class*="overlay"], [class*="cookie"], [class*="banner"], [role="dialog"]')
     .forEach(el => el.style.display = 'none');
   ```
4. Generate PDF using `page.pdf({ format: 'A4', printBackground: true })`
5. Close the tab and repeat

### C3 — Save to Dropbox

Save each PDF to:
```
D:\Dropbox\Klootwijk - RAAD\ESC Online\{year}\Inkoop\Q{n}\DROPBOX Dropbox Essentials_{month}_{year}.pdf
```

Example: `DROPBOX Dropbox Essentials_juni_2026.pdf`
