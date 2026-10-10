"""Read incoming payments from the bunq MT940 (.sta) statements in Dropbox.

Statements live in D:\\Dropbox\\Klootwijk - RAAD\\ESC Online\\{year}\\Bank\\Q{n}\\*.sta
Usage (inspect): python bank.py 2026 3
"""
import glob
import os
import re
import sys

BANK_BASE = r"D:\Dropbox\Klootwijk - RAAD\ESC Online"

# :61: valuedate(YYMMDD) [entrydate(MMDD)] C/D [R] amount(1234,56) N + 3-char type ... then :86: details
_TXN = re.compile(r":61:(\d{6})\d{0,4}(R?[CD])([\d,]+)N\w{3}.*?\n:86:(.*?)(?=\n:6[12]|\n:62|\Z)", re.S)


def credits(year, quarter):
    """All incoming (credit) transactions in the quarter's statements."""
    folder = os.path.join(BANK_BASE, str(year), "Bank", f"Q{quarter}")
    files = sorted(glob.glob(os.path.join(folder, "*.sta")))
    if not files:
        raise FileNotFoundError(f"No .sta bank statements in {folder}")
    result = []
    for path in files:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        for date, cd, amount, info in _TXN.findall(text):
            if cd != "C":
                continue
            result.append({
                "date": f"20{date[:2]}-{date[2:4]}-{date[4:]}",
                "amount": float(amount.replace(",", ".")),
                "info": " ".join(info.split()),
            })
    return result


def find_payment(invoice_number, txns):
    """First credit whose description mentions the invoice number, or None."""
    for t in txns:
        if invoice_number in t["info"]:
            return t
    return None


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for t in credits(int(sys.argv[1]), int(sys.argv[2])):
        print(t["date"], f"{t['amount']:>10.2f}", t["info"][:100])
