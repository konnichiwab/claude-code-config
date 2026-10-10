"""Reconcile a quarter's bank transactions against the filed invoices.

Cash is king: every bank mutation must be explained by an invoice (inkoop or
verkoop) or by a rule (private withdrawal, internal transfer, tax).

Usage: python reconcile.py 2026 3 [--csv out.csv]
Prints a report and writes JSON (and optional CSV) next to the temp output.
"""
import csv
import glob
import json
import os
import re
import sys
import tempfile

import pdfplumber

import bank
from build_decisions import extract_date_from_text

sys.stdout.reconfigure(encoding="utf-8")

BASE = r"D:\Dropbox\Klootwijk - RAAD\ESC Online"
RULES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reconcile_rules.json")
NL_MONTHS = ["januari", "februari", "maart", "april", "mei", "juni", "juli",
             "augustus", "september", "oktober", "november", "december"]


def load_rules():
    with open(RULES, encoding="utf-8") as f:
        return json.load(f)


def classify(t, rules):
    """(kind, vendor): kind is private/internal/tax/vendor/unknown."""
    for kind in ("private", "internal", "tax"):
        r = rules.get(kind, {})
        if t["iban"] and t["iban"] in r.get("iban", []):
            return kind, None
        if any(re.search(p, t["name"], re.I) for p in r.get("name", [])):
            return kind, None
    for pattern, vendor in rules["vendors"].items():
        if not pattern.startswith("_") and re.search(pattern, t["name"], re.I):
            return "vendor", vendor
    return "unknown", None


def _amounts(text):
    """Every money-looking number in the text, as floats (both 1.234,56 and 1,234.56)."""
    found = set()
    for raw in re.findall(r"\d{1,3}(?:[.,]\d{3})*[.,]\d{2}\b", text):
        sep, thousands = raw[-3], "." if raw[-3] == "," else ","
        try:
            found.add(float(raw.replace(thousands, "").replace(sep, ".")))
        except ValueError:  # mixed-up separators, e.g. 23.400.00
            continue
    return found


def _quarter_dirs(year, quarter):
    """The quarter's Inkoop folder plus neighbours (payments can lag a quarter)."""
    qs = [(year, quarter)]
    qs.append((year, quarter - 1) if quarter > 1 else (year - 1, 4))
    qs.append((year, quarter + 1) if quarter < 4 else (year + 1, 1))
    return [os.path.join(BASE, str(y), "Inkoop", f"Q{q}") for y, q in qs]


def load_invoices(year, quarter, vendors):
    prefixes = sorted(set(vendors), key=len, reverse=True)
    paths = []
    for d in _quarter_dirs(year, quarter):
        paths += glob.glob(os.path.join(d, "**", "*.pdf"), recursive=True)
    for y in {year, year + 1 if quarter == 4 else year}:
        paths += glob.glob(os.path.join(BASE, str(y), "Verkoop", "**", "*.pdf"), recursive=True)

    invoices = []
    for path in sorted(set(paths)):
        name = os.path.basename(path)
        vendor = next((p for p in prefixes if name.upper().startswith(p + " ")), name.split(" ")[0].upper())
        try:
            with pdfplumber.open(path) as pdf:
                text = " ".join((p.extract_text() or "") for p in pdf.pages[:4])
        except Exception as e:
            text = ""
            print(f"WARNING: cannot read {path}: {e}", file=sys.stderr)
        date = extract_date_from_text(text)
        if not date:  # fall back to a Dutch month name in the filename (KPN, Dropbox)
            m = re.search(r"_(" + "|".join(NL_MONTHS) + r")_(\d{4})", name)
            if m:
                date = f"{m.group(2)}-{NL_MONTHS.index(m.group(1)) + 1:02d}-15"
        invoices.append({
            "path": path,
            "file": name,
            "folder": os.path.relpath(os.path.dirname(path), BASE),
            "vendor": vendor,
            "date": date,
            "amounts": _amounts(text),
            # digit runs (ESC690000015, 20260732) plus all digits joined (F0000_2607_0004_1459)
            "refs": set(re.findall(r"\d{5,}", name)) | {re.sub(r"\D", "", name)},
            "matched": None,
            "this_quarter": os.path.relpath(path, BASE).split(os.sep)[:3] == [str(year), "Inkoop", f"Q{quarter}"],
        })
    return invoices


def _days(a, b):
    from datetime import date
    if not a or not b:
        return 999
    return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)


def _in_window(inv, t):
    """Card payments (no IBAN) happen on the invoice date; transfers and direct
    debits come after the invoice, within ~5 weeks."""
    if not inv["date"]:
        # undated: only trust it when filed in this quarter's own folder
        return inv["this_quarter"]
    from datetime import date
    delta = (date.fromisoformat(t["date"]) - date.fromisoformat(inv["date"])).days
    return abs(delta) <= 5 if not t["iban"] else -7 <= delta <= 35


def match(t, vendor, invoices, by_reference):
    pool = [i for i in invoices if i["matched"] is None and i["vendor"] == vendor]
    if by_reference:
        # invoice number in the payment description
        digits = re.sub(r"\D", "", t["remi"])
        for inv in pool:
            if any(len(r) >= 6 and r in digits for r in inv["refs"]):
                return inv, "reference"
        return None, None
    # same vendor + amount (EUR, or the original USD for card payments) within the date window
    want = {round(abs(t["amount"]), 2)} | ({round(t["usd"], 2)} if t["usd"] else set())
    hits = [i for i in pool if want & i["amounts"] and _in_window(i, t)]
    if hits:
        # the most recent invoice before the payment (closest preceding date)
        return min(hits, key=lambda i: _days(i["date"], t["date"]) + (0 if (i["date"] or "") <= t["date"] else 0.5)), "amount"
    return None, None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    csv_path = sys.argv[sys.argv.index("--csv") + 1] if "--csv" in sys.argv else None
    if csv_path in args:
        args.remove(csv_path)
    year, quarter = int(args[0]), int(args[1])

    rules = load_rules()
    txns = bank.transactions(year, quarter)
    invoices = load_invoices(year, quarter, rules["vendors"].values())

    # Reference matches first, so an amount match can't take an invoice that a
    # later payment names explicitly.
    kinds = [classify(t, rules) for t in txns]
    # A refund cancels an earlier charge of the same vendor and amount (e.g. card checks)
    refunded = set()
    for n, t in enumerate(txns):
        if t["amount"] > 0 and kinds[n][0] == "vendor" and "refund" in t["info"].lower():
            for m, u in enumerate(txns):
                if (m not in refunded and kinds[m] == kinds[n] and u["amount"] == -t["amount"]
                        and _days(u["date"], t["date"]) <= 14):
                    refunded |= {n, m}
                    break

    found = {}
    for by_reference in (True, False):
        for n, (t, (kind, vendor)) in enumerate(zip(txns, kinds)):
            if kind == "vendor" and n not in found and n not in refunded:
                inv, how = match(t, vendor, invoices, by_reference)
                if inv:
                    inv["matched"] = t
                    found[n] = (inv, how)

    rows = []
    for n, (t, (kind, vendor)) in enumerate(zip(txns, kinds)):
        inv, how = found.get(n, (None, None))
        if inv:
            status = "OK"
        elif n in refunded:
            status = "REFUNDED"
        elif kind in ("private", "internal", "tax"):
            status = kind.upper()
        else:
            status = "MISSING INVOICE" if kind == "vendor" else "UNKNOWN"
        rows.append({
            "date": t["date"], "amount": t["amount"], "usd": t["usd"] or "",
            "counterparty": t["name"], "description": t["remi"], "vendor": vendor or "",
            "status": status, "match": how or "", "invoice": inv["file"] if inv else "",
            "invoice_folder": inv["folder"] if inv else "",
        })

    this_q = {os.path.normcase(os.path.join(BASE, str(year), "Inkoop", f"Q{quarter}"))}
    private_prefixes = tuple(rules.get("paid_privately", {}).get("prefixes", []))
    unpaid = [i for i in invoices if i["matched"] is None and not i["file"].startswith(private_prefixes) and (
        os.path.normcase(os.path.dirname(i["path"])).startswith(next(iter(this_q)))
        or (i["folder"].split(os.sep)[1:2] == ["Verkoop"] and (i["date"] or "")[:4] == str(year)
            and i["date"] and (int(i["date"][5:7]) - 1) // 3 + 1 == quarter))]

    # Report
    order = ["MISSING INVOICE", "UNKNOWN", "OK", "REFUNDED", "PRIVATE", "INTERNAL", "TAX"]
    print(f"Reconciliation {year} Q{quarter}: {len(txns)} bank transactions, {len(invoices)} invoices scanned\n")
    for st in order:
        sel = [r for r in rows if r["status"] == st]
        if not sel:
            continue
        print(f"== {st} ({len(sel)}, total EUR {sum(r['amount'] for r in sel):.2f})")
        if st in ("OK", "PRIVATE", "INTERNAL", "TAX") and "--verbose" not in sys.argv:
            continue
        for r in sel:
            usd = f" (${r['usd']})" if r["usd"] else ""
            other_q = r["invoice_folder"] and not r["invoice_folder"].startswith(os.path.join(str(year), "Inkoop", f"Q{quarter}")) and "Verkoop" not in r["invoice_folder"]
            extra = f" -> {r['invoice']} [{r['match']}]" + (f" (in {r['invoice_folder']})" if other_q else "") if r["invoice"] else ""
            print(f"  {r['date']} {r['amount']:>10.2f}{usd:<10} {r['counterparty'][:28]:<28} {r['description'][:40]}{extra}")
        print()
    paid_privately = [i for i in invoices if i["file"].startswith(private_prefixes) and i["this_quarter"]]
    if paid_privately:
        print(f"== PAID PRIVATELY, business share set by accountant ({len(paid_privately)})")
        for i in paid_privately:
            print(f"  {i['date'] or '?':<10} {i['folder']}\{i['file']}")
        print()
    if unpaid:
        print(f"== INVOICES WITHOUT PAYMENT in this quarter's bank ({len(unpaid)})")
        for i in unpaid:
            print(f"  {i['date'] or '?':<10} {i['folder']}\\{i['file']}")

    out = csv_path or os.path.join(tempfile.gettempdir(), f"reconcile_{year}Q{quarter}.csv")
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
        w.writeheader()
        w.writerows(rows)
    print(f"\nCSV: {out}")


if __name__ == "__main__":
    main()
