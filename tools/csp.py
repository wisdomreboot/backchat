#!/usr/bin/env python3
"""Refresh the script hashes in index.html's Content-Security-Policy.

The policy lets the browser run only scripts it recognises: files from this site,
plus the inline <script> blocks whose exact text is hashed in the policy. Any edit
to an inline script changes its hash, so run this after every edit, or the app
stops running (the browser blocks the edited script).

    python3 tools/csp.py index.html          rewrite the hashes in place
    python3 tools/csp.py index.html --check  exit 1 if they are out of date
"""
import base64, hashlib, re, sys

def inline_hashes(html):
    out = []
    for m in re.finditer(r'<script(?P<attrs>[^>]*)>(?P<body>.*?)</script>', html, re.S | re.I):
        attrs = m.group('attrs')
        if re.search(r'\bsrc\s*=', attrs, re.I):
            continue
        if re.search(r'type\s*=\s*["\']application/(ld\+)?json', attrs, re.I):
            continue  # data blocks never run, so they need no hash
        digest = hashlib.sha256(m.group('body').encode('utf-8')).digest()
        out.append("'sha256-%s'" % base64.b64encode(digest).decode())
    return out

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'index.html'
    check = '--check' in sys.argv
    html = open(path, encoding='utf-8').read()
    want = "script-src 'self' " + ' '.join(inline_hashes(html))
    pat = re.compile(r"script-src 'self'(?: 'sha256-[A-Za-z0-9+/=]+')*")
    if not pat.search(html):
        sys.exit("No script-src 'self' ... found in the Content-Security-Policy of " + path)
    new = pat.sub(want, html, count=1)
    if check:
        if new != html:
            sys.exit(path + ": script hashes are out of date. Run: python3 tools/csp.py " + path)
        print(path + ": script hashes match")
        return
    if new != html:
        open(path, 'w', encoding='utf-8').write(new)
        print(path + ": script hashes updated")
    else:
        print(path + ": already up to date")

main()
