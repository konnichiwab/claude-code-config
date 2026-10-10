"""Shared Microsoft Graph access for the process-invoices scripts.

Signs in as the ESC Online M365 user (delegated Mail.ReadWrite) via MSAL.
The first run opens a browser for login; after that the token cache is reused
silently. The cache lives in %LOCALAPPDATA% so it never ends up in git.
"""
import json
import os
import sys

import msal
import requests

ACCOUNT_EMAIL = "marc.klootwijk@esconline.nl"
# Microsoft's first-party "Microsoft Graph Command Line Tools" public client,
# so no app registration is needed. Override with PROCESS_INVOICES_CLIENT_ID.
CLIENT_ID = os.environ.get("PROCESS_INVOICES_CLIENT_ID", "14d82eec-204b-4c2f-b7e8-296a70dab67e")
AUTHORITY = "https://login.microsoftonline.com/organizations"
SCOPES = ["Mail.ReadWrite"]
GRAPH = "https://graph.microsoft.com/v1.0"

CACHE_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "process-invoices")
CACHE_PATH = os.path.join(CACHE_DIR, "msal_cache.json")


def _load_cache():
    cache = msal.SerializableTokenCache()
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, encoding="utf-8") as f:
            cache.deserialize(f.read())
    return cache


def _save_cache(cache):
    if cache.has_state_changed:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            f.write(cache.serialize())


def get_token():
    cache = _load_cache()
    app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY, token_cache=cache)

    result = None
    accounts = [a for a in app.get_accounts() if a.get("username", "").lower() == ACCOUNT_EMAIL]
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
    if not result:
        print(f"Opening browser to sign in as {ACCOUNT_EMAIL} ...", file=sys.stderr, flush=True)
        result = app.acquire_token_interactive(SCOPES, login_hint=ACCOUNT_EMAIL, timeout=300)

    _save_cache(cache)
    if "access_token" not in result:
        raise RuntimeError(f"Login failed: {result.get('error')}: {result.get('error_description')}")
    username = (result.get("id_token_claims") or {}).get("preferred_username") or accounts[0]["username"]
    return result["access_token"], username.lower()


class Graph:
    def __init__(self):
        self.session = requests.Session()
        token, signed_in = get_token()
        self.session.headers["Authorization"] = f"Bearer {token}"
        if signed_in != ACCOUNT_EMAIL:
            # Never fall back to some other mailbox
            raise RuntimeError(f"Signed in as {signed_in!r}, expected {ACCOUNT_EMAIL!r}")

    def _url(self, path):
        return path if path.startswith("https://") else GRAPH + path

    def _check(self, r):
        if not r.ok:
            raise RuntimeError(f"Graph {r.request.method} {r.url} -> {r.status_code}: {r.text[:300]}")
        return r

    def get(self, path, params=None):
        return self._check(self.session.get(self._url(path), params=params)).json()

    def get_bytes(self, path):
        return self._check(self.session.get(self._url(path))).content

    def get_all(self, path, params=None):
        data = self.get(path, params)
        items = list(data.get("value", []))
        while data.get("@odata.nextLink"):
            data = self.get(data["@odata.nextLink"])
            items.extend(data.get("value", []))
        return items

    def patch(self, path, body):
        return self._check(self.session.patch(self._url(path), json=body)).json()

    def post(self, path, body):
        return self._check(self.session.post(self._url(path), json=body)).json()


if __name__ == "__main__":
    # `python graph.py` = sign in once and confirm the mailbox
    g = Graph()
    inbox = g.get("/me/mailFolders/inbox", params={"$select": "totalItemCount,unreadItemCount"})
    print(json.dumps({"signed_in_as": ACCOUNT_EMAIL, "inbox": inbox.get("totalItemCount"), "token_cache": CACHE_PATH}))
