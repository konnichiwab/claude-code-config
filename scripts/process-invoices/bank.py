"""Read transactions from the bunq MT940 (.sta) statements in Dropbox.

Statements live in D:\\Dropbox\\Klootwijk - RAAD\\ESC Online\\{year}\\Bank\\Q{n}\\*.sta
Usage (inspect): python bank.py 2026 3
"""
import glob
import os
import re
import sys

BANK_BASE = r"D:\Dropbox\Klootwijk - RAAD\ESC Online"

# :61: valuedate(YYMMDD) entrydate(MMDD) C/D/RC/RD amount(1234,56) N + 3-char type ... then :86: details
_TXN = re.compile(r":61:(\d{6})(\d{4})?(R?[CD])([\d,]+)N\w{3}.*?\n:86:(.*?)(?=\n:6[12]|\n:62|\Z)", re.S)


def _field(info, key):
    m = re.search(rf"/{key}/(.*?)(?=/(?:IBAN|BIC|NAME|REMI|EREF|ORDP|BENM)/|$)", info)
    return m.group(1).strip() if m else ""


def transactions(year, quarter):
    """All transactions in the quarter's statements, in statement order.

    amount is signed: positive = money in, negative = money out.
    date is the booking (entry) date; card payments carry a value date of the
    1st of the next month, which is not when they happened.
    """
    folder = os.path.join(BANK_BASE, str(year), "Bank", f"Q{quarter}")
    files = sorted(glob.glob(os.path.join(folder, "*.sta")))
    if not files:
        raise FileNotFoundError(f"No .sta bank statements in {folder}")
    result = []
    for path in files:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        for value, entry, cd, amount, info in _TXN.findall(text):
            info = " ".join(info.split())
            yy, vm = int(value[:2]), int(value[2:4])
            if entry:
                em = int(entry[:2])
                ey = yy - 1 if em > vm else yy  # entry in Dec, value in Jan
                date = f"20{ey:02d}-{entry[:2]}-{entry[2:]}"
            else:
                date = f"20{value[:2]}-{value[2:4]}-{value[4:]}"
            amt = float(amount.replace(",", "."))
            usd = re.search(r"([\d.]+) USD", info)
            result.append({
                "date": date,
                "amount": amt if cd.endswith("C") ^ cd.startswith("R") else -amt,
                "usd": float(usd.group(1)) if usd else None,
                "iban": _field(info, "IBAN"),
                "name": _field(info, "NAME"),
                "remi": _field(info, "REMI"),
                "info": info,
                "statement": os.path.basename(path),
            })
    return result


def credits(year, quarter):
    """Incoming transactions only."""
    return [t for t in transactions(year, quarter) if t["amount"] > 0]


def find_payment(invoice_number, txns):
    """First transaction whose description mentions the invoice number, or None."""
    for t in txns:
        if invoice_number in t["info"]:
            return t
    return None


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for t in transactions(int(sys.argv[1]), int(sys.argv[2])):
        print(t["date"], f"{t['amount']:>10.2f}", t["name"][:30].ljust(30), t["remi"][:70])
