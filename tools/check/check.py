#!/usr/bin/env python3
"""Backchat regression check.

Drives the real page in headless Chromium and checks the behaviours that have broken
before: data that must never be lost, deletes that must stick, the security policy,
search, exports, folder sync, and every way back to a place in a book landing on it.
Run it before merging any change to index.html.

    pip install playwright && python3 -m playwright install chromium
    python3 tools/check/check.py            # checks the copy in this repository
    python3 tools/check/check.py path/to/site

Exit code 0 means every check passed. Each failure is printed with what was expected.
"""
import base64, functools, http.server, json, os, re, socket, socketserver, sys, tempfile, threading, time, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", ".."))

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("Playwright is missing. Run: pip install playwright && python3 -m playwright install chromium")


# ---------- test books ----------
def make_epub(path, title, author, ident, chapters, style=""):
    z = zipfile.ZipFile(path, "w")
    z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
    z.writestr("META-INF/container.xml", '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
    man = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>']; spine = []; nav = []
    for i, (lab, paras) in enumerate(chapters):
        body = "".join("<p>%s</p>" % p for p in paras)
        z.writestr("OEBPS/c%d.xhtml" % i, '<?xml version="1.0" encoding="utf-8"?><!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml"><head><title>%s</title>%s</head><body><h1>%s</h1>%s</body></html>' % (lab, ("<style>%s</style>" % style) if style else "", lab, body))
        man.append('<item id="c%d" href="c%d.xhtml" media-type="application/xhtml+xml"/>' % (i, i)); spine.append('<itemref idref="c%d"/>' % i); nav.append('<li><a href="c%d.xhtml">%s</a></li>' % (i, lab))
    z.writestr("OEBPS/nav.xhtml", '<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><head><title>Nav</title></head><body><nav epub:type="toc"><ol>%s</ol></nav></body></html>' % "".join(nav))
    z.writestr("OEBPS/content.opf", '<?xml version="1.0" encoding="utf-8"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="bookid">%s</dc:identifier><dc:title>%s</dc:title><dc:creator>%s</dc:creator><dc:language>en</dc:language></metadata><manifest>%s</manifest><spine>%s</spine></package>' % (ident, title, author, "".join(man), "".join(spine)))
    z.close()

def make_transcript_epub(path, title, vid):
    """A book as the Video Book builder writes it: the video id in the OPF and a media
    element in each chapter, a data-t time on every caption line and timestamp button."""
    z = zipfile.ZipFile(path, "w")
    z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
    z.writestr("META-INF/container.xml", '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
    rows = "".join('<div class="transcript-entry" id="e-%d"><button class="ts timestamp" type="button" data-t="%d">0:%02d</button><p><span class="c" id="t-%d" data-t="%d">Line %d of the talk, spoken at second %d.</span></p></div>' % (t, t, t, t, t, i, t) for i, t in enumerate(range(0, 60, 6)))
    z.writestr("OEBPS/ch01.xhtml", '<?xml version="1.0" encoding="utf-8"?><!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml"><head><title>Talk</title></head><body><div id="backchat-media" data-provider="youtube" data-id="%s" data-duration="60" data-next="" hidden="hidden"></div><h1 class="ch" id="c1" data-t="0">Talk</h1>%s</body></html>' % (vid, rows))
    z.writestr("OEBPS/nav.xhtml", '<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><head><title>Nav</title></head><body><nav epub:type="toc"><ol><li><a href="ch01.xhtml">Talk</a></li></ol></nav></body></html>')
    z.writestr("OEBPS/content.opf", '<?xml version="1.0" encoding="utf-8"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="bookid">urn:uuid:video-%s</dc:identifier><dc:title>%s</dc:title><dc:creator>Speaker</dc:creator><dc:language>en</dc:language><dc:source>https://www.youtube.com/watch?v=%s</dc:source><meta property="backchat:media">youtube:%s</meta><meta property="backchat:duration">60</meta></metadata><manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/><item id="c1" href="ch01.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="c1"/></spine></package>' % (vid, title, vid, vid))
    z.close()

def make_long_epub(path):
    """Four chapters long enough to run many pages each, so a jump that lands on the wrong page
    is caught. One quote is unique; another appears twice in one chapter, and the second copy
    is the one marked, so a jump must tell the two apart."""
    words = "river stone lantern harbor meadow copper window orchard thunder pencil garden mirror candle valley silver forest compass ladder ribbon anchor".split()
    chapters = []
    for c in range(4):
        ps = ["Paragraph %d of chapter %d: %s." % (i, c, " ".join(words[(c * 7 + i * 3 + k) % len(words)] for k in range(38))) for i in range(80)]
        if c == 1:
            ps[5] = ps[55] = "The process comes in three stages, and each one asks something different."
        if c == 2:
            ps[60] = "Become who you are by learning who you are, as the Greek poet Pindar wrote."
        chapters.append(("Chapter %d" % (c + 1), ps))
    make_epub(path, "Long Landing Book", "Test Author", "urn:isbn:9780000000777", chapters)

TMP = tempfile.mkdtemp(prefix="backchat-check-")
ALPHA, BETA = os.path.join(TMP, "alpha.epub"), os.path.join(TMP, "beta.epub")
GONE, LIVE = os.path.join(TMP, "gone.epub"), os.path.join(TMP, "live.epub")
make_transcript_epub(GONE, "Removed Talk", "deadvideo01")
make_transcript_epub(LIVE, "Playing Talk", "livevideo01")
make_epub(ALPHA, "Alpha Testing Book", "Ann Author", "urn:isbn:9780000000001", [
    ("Chapter One", ["The quick brown fox jumps over the lazy dog near the riverbank.",
                     "Call me Ishmael. Some years ago, never mind how long precisely, I went to sea.",
                     "A rare word appears here: zygomorphic flowers bloom in spring."]),
    ("Chapter Two", ["It was the best of times, it was the worst of times, it was the age of wisdom.",
                     "The lord is my shepherd, I shall not want. He maketh me to lie down.",
                     "Numbers like 42 and 1984 should survive the margins renderer intact."])])
make_epub(BETA, "Beta Second Book", "Bob Writer", "urn:isbn:9780000000002", [
    ("Opening", ["Another quick brown fox appears in a second book to test rhymes across books.",
                 "Zygomorphic symmetry is a botanical term used by careful readers."])])
# The same book (same identifier) as a corrected file with different contents, and a third book.
ALPHA2, GAMMA = os.path.join(TMP, "alpha2.epub"), os.path.join(TMP, "gamma.epub")
make_epub(ALPHA2, "Alpha Testing Book", "Ann Author", "urn:isbn:9780000000001", [
    ("Chapter One", ["The quick brown fox jumps over the lazy dog near the riverbank, corrected.",
                     "A rare word appears here: zygomorphic flowers bloom in spring and summer."])])
make_epub(GAMMA, "Gamma Third Book", "Cy Writer", "urn:isbn:9780000000003", [
    ("Only", ["A third book, so a library has more than one shelf mate."])])
# A book whose title and identifier read fine but which the reader refuses to add (more files
# inside than an EPUB has any reason to hold).
CROWDED = os.path.join(TMP, "crowded.epub")
make_epub(CROWDED, "Crowded Book", "Di Packer", "urn:isbn:9780000000004", [("Only", ["Too many files ride along with this one."])])
with zipfile.ZipFile(CROWDED, "a") as _z:
    for _i in range(5001): _z.writestr("OEBPS/extra/%d.txt" % _i, "")
LONG = os.path.join(TMP, "long.epub")
make_long_epub(LONG)
# A book that sets its own tight line spacing and side margins, as many do.
STYLED = os.path.join(TMP, "styled.epub")
make_epub(STYLED, "Styled Spacing Book", "Test Author", "urn:isbn:9780000000999",
          [("Tight", ["Tight paragraph %d sets its own spacing: %s." % (i, " ".join("river stone lantern harbor meadow copper window orchard".split()[(i + k) % 8] for k in range(30))) for i in range(40)])],
          style="p{line-height:1.1;margin:0 0 .4em 0} body{line-height:1.1}")

def make_listen_epub(path):
    """A book for read aloud: a plain chapter long enough to turn pages; a chapter of awkward
    structure (a note marker, a block quote, list items holding paragraphs, a nested list, a div used
    as a paragraph, a table, hidden text, a footnote); a chapter that ends in a picture filling its
    last page; and a short last chapter."""
    z = zipfile.ZipFile(path, "w")
    z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
    z.writestr("META-INF/container.xml", '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
    head = '<?xml version="1.0" encoding="utf-8"?><!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><head><title>%s</title></head><body>'
    w = "river stone lantern harbor meadow copper window orchard thunder pencil garden mirror candle valley silver forest".split()
    def para(n):
        a = " ".join(w[(n + k) % len(w)] for k in range(9)); b = " ".join(w[(n * 3 + k) % len(w)] for k in range(10)); c = " ".join(w[(n * 5 + k) % len(w)] for k in range(8))
        return "Paragraph %d opens with %s. Its second sentence %d carries %s. The third sentence %d ends on %s." % (n, a, n, b, n, c)
    ch = [("Plain", "<h1>Plain</h1>" + "".join("<p>%s</p>" % para(i) for i in range(30))),
          ("Structure", "<h1>Structure</h1>"
           '<p>Opening line with a note marker<sup><a href="#fn1" epub:type="noteref">1</a></sup> right here.</p>'
           "<blockquote><p>Quoted first paragraph.</p><p>Quoted second paragraph.</p></blockquote>"
           "<ul><li><p>List item paragraph.</p></li><li>Plain list item<ul><li>Nested item.</li></ul></li></ul>"
           '<div class="para">A paragraph written as a div.</div>'
           "<table><tr><td>Table cell one.</td><td>Table cell two.</td></tr></table>"
           '<p style="display:none">Hidden words never shown.</p>'
           "<p>A line of verse<br/>broken by a line break.</p>"
           "<p>Closing line of structure.</p>"
           '<aside epub:type="footnote" id="fn1"><p>The footnote text itself.</p></aside>'),
          ("Trailing image", "<h1>Trailing image</h1>" + "".join("<p>Image chapter paragraph %d says something about %s.</p>" % (i, w[i]) for i in range(6))
           + '<div><img src="tall.png" alt="" style="height:90vh;width:auto"/></div>'),
          ("Short end", "<h1>Short end</h1><p>The final chapter begins here.</p><p>And the book ends here.</p>")]
    man = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>', '<item id="img" href="tall.png" media-type="image/png"/>']; spine = []; nav = []
    for i, (lab, body) in enumerate(ch):
        z.writestr("OEBPS/c%d.xhtml" % i, (head % lab) + body + "</body></html>")
        man.append('<item id="c%d" href="c%d.xhtml" media-type="application/xhtml+xml"/>' % (i, i)); spine.append('<itemref idref="c%d"/>' % i); nav.append('<li><a href="c%d.xhtml">%s</a></li>' % (i, lab))
    # a 1x1 grey PNG; the page stretches it to fill most of the screen
    z.writestr("OEBPS/tall.png", base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGOYNm0aAAOIAcMdATx8AAAAAElFTkSuQmCC"))
    z.writestr("OEBPS/nav.xhtml", '<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><head><title>Nav</title></head><body><nav epub:type="toc"><ol>%s</ol></nav></body></html>' % "".join(nav))
    z.writestr("OEBPS/content.opf", '<?xml version="1.0" encoding="utf-8"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="bookid">urn:isbn:9780000000888</dc:identifier><dc:title>Listening Book</dc:title><dc:creator>Test Author</dc:creator><dc:language>en</dc:language></metadata><manifest>%s</manifest><spine>%s</spine></package>' % ("".join(man), "".join(spine)))
    z.close()
LISTEN = os.path.join(TMP, "listen.epub")
make_listen_epub(LISTEN)


# ---------- local server ----------
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass

def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p

PORT = free_port()
socketserver.ThreadingTCPServer.allow_reuse_address = True
httpd = socketserver.ThreadingTCPServer(("127.0.0.1", PORT), functools.partial(Quiet, directory=SITE))
threading.Thread(target=httpd.serve_forever, daemon=True).start()
URL = "http://127.0.0.1:%d/index.html" % PORT


# ---------- results ----------
results = []
def expect(name, got, want, why):
    try:
        ok = bool(want(got)) if callable(want) else got == want
    except Exception:
        ok = False
    results.append((name, ok, got, want if not callable(want) else "(condition)", why))

page_errors, bad_requests = [], []
def watch(page, label):
    page.on("pageerror", lambda e: page_errors.append("%s: %s" % (label, e)))
    page.on("console", lambda m: page_errors.append("%s console: %s" % (label, m.text)) if m.type == "error" else None)
    page.on("requestfailed", lambda r: bad_requests.append("%s: failed %s" % (label, r.url[:120])) if "127.0.0.1" in r.url else None)
    page.on("response", lambda r: bad_requests.append("%s: HTTP %d %s" % (label, r.status, r.url[:120])) if r.status >= 400 else None)
    page.on("dialog", lambda d: d.accept())

def wait(page, js, timeout=20000):
    page.wait_for_function(js, timeout=timeout)

def ev(pg, js, *args):
    """Evaluate in the page; an exception becomes a failed check, not a crashed run."""
    try:
        return pg.evaluate(js, *args)
    except Exception as e:
        return "ERROR: " + str(e).splitlines()[0][:200]

def settle(seconds=0.6):
    time.sleep(seconds)

# Is the nth copy of a quote on the page now showing (and, when asked, is it the passage the
# landing flashed)? Answers true or a short reason.
LANDED_JS = r"""(args)=>{ const [quote, nth, flash] = args;
  if(!rendition || $('#reader').classList.contains('hidden')) return 'reader not showing';
  for(const c of rendition.getContents()){
    const tm=secTextMap(c), re=quoteRegex(quote); let m, hits=[]; while((m=re.exec(tm.full))) hits.push(m.index);
    if(hits.length<=nth) continue;
    const i=hits[nth], a=mapLocate(tm.map,i), b=mapLocate(tm.map,i+10);
    const r=c.document.createRange(); r.setStart(a.node,a.offset); r.setEnd(b.node,b.offset);
    if(bcRangeSide(c, r)!==0) return 'the words are on another page';
    if(flash){
      const g=c.window.CSS.highlights.get('goto'); if(!g) return 'nothing flashed';
      const fr=[...g][0], sp=rangeSpan(tm, fr);
      if(sp.start!==i) return 'flashed the wrong copy of the words';
    }
    return true;
  }
  return 'the words are not in the section showing ('+((rendition.currentLocation()||{}).start||{}).href+')';
}"""

# Is the saved reading position (a CFI) on the page now showing? True or a short reason.
ON_PAGE_JS = r"""(cfi)=>{
  if(!rendition || $('#reader').classList.contains('hidden')) return 'reader not showing';
  const idx=bcSectionIndex({cfi:cfi}), c=bcContentsFor(idx); if(!c) return 'its section is not showing';
  const r=bcRangeAt(c, {cfi:cfi}); if(!r) return 'position not found';
  return bcRangeSide(c, r)===0 ? true : 'the position is on another page';
}"""

def on_page(pg, cfi, timeout=8.0):
    end, got = time.time() + timeout, None
    while time.time() < end:
        got = ev(pg, ON_PAGE_JS, cfi)
        if got is True: break
        time.sleep(0.15)
    if got is not True: return got
    time.sleep(1.2)
    return ev(pg, ON_PAGE_JS, cfi)

def landed(pg, quote, nth=0, flash=True, timeout=8.0):
    """Wait for a jump to land on the nth copy of quote; then confirm it stays there once the
    section has finished laying out."""
    end, got = time.time() + timeout, None
    while time.time() < end:
        got = ev(pg, LANDED_JS, [quote, nth, flash])
        if got is True: break
        time.sleep(0.15)
    if got is not True: return got
    time.sleep(1.2)
    return ev(pg, LANDED_JS, [quote, nth, False])


# 0. Every script the page loads is a file in this repository. The security policy refuses
#    anything else, so a script linked from another site (a CDN, an analytics snippet pasted
#    as given) silently never runs on the live site.
_html = open(os.path.join(SITE, "index.html"), encoding="utf-8").read()
_srcs = re.findall(r'<script\b[^>]*\bsrc\s*=\s*["\']([^"\']+)', _html, re.I)
expect("every script is kept in this repository", [s for s in _srcs if re.match(r"^(?:[a-z]+:)?//", s, re.I) or not os.path.isfile(os.path.join(SITE, s))], [],
       "the security policy runs only this site's files: save the library in lib/ and load it from there (see lib/README.md)")

# The page-view counter announces that it skips local addresses; that note is expected here.
_GC_LOCAL = "goatcounter: not counting because of: localhost"

with sync_playwright() as p:
    browser = p.chromium.launch()

    # 1. The real security policy is enforced: boot must run with no violation, no error,
    #    and no stray request (a look-ahead fetch of a URL half-written in a script).
    gc_local = {"notes": 0, "sent": []}
    for i in range(6):
        ctx = browser.new_context(); pg = ctx.new_page()
        notes = []
        def _note(m, notes=notes):
            if m.text == _GC_LOCAL: gc_local["notes"] += 1
            elif m.type in ("error", "warning"): notes.append(m.text)
        pg.on("console", _note)
        pg.on("pageerror", lambda e: notes.append(str(e)))
        pg.on("request", lambda r: notes.append("stray request " + r.url) if "'" in r.url else None)
        pg.on("request", lambda r: gc_local["sent"].append(r.url) if "goatcounter.com" in r.url else None)
        pg.goto(URL); pg.wait_for_selector("#home-recent .card", timeout=20000); settle(0.5)
        if notes or i == 0:
            expect("boot under the security policy, run %d" % (i + 1), notes, [], "the page must boot cleanly with its Content-Security-Policy on")
        ctx.close()
    expect("no page view is counted from a local address", gc_local, lambda g: g["notes"] >= 1 and not g["sent"],
           "test runs and local copies must never reach the live count")

    # 1b. The page-view count under a real-looking address, with the security policy on. The
    #     counting service is intercepted, so nothing reaches the live dashboard. One count goes
    #     out, and nothing after # (where a sync setup link carries the relay token) is in it.
    gbrowser = p.chromium.launch(args=["--host-resolver-rules=MAP backchat.test 127.0.0.1"])
    gctx = gbrowser.new_context(); gp = gctx.new_page()
    sent, gnotes = [], []
    def _gc_stub(route):
        sent.append(route.request.url); route.fulfill(status=204, body="")
    gp.route(re.compile(r"^https://backchat\.goatcounter\.com/"), _gc_stub)
    gp.on("console", lambda m: gnotes.append(m.text) if m.type == "error" or "Content Security Policy" in m.text else None)
    gp.on("pageerror", lambda e: gnotes.append(str(e)))
    gp.on("dialog", lambda d: d.dismiss())
    gp.goto("http://backchat.test:%d/index.html#bcsync=SETUPTOKEN-must-not-leave" % PORT)
    gp.wait_for_selector("#home-recent .card", timeout=20000)
    for _ in range(40):
        if sent: break
        time.sleep(0.25)
    settle(0.5)
    expect("a page view is counted once on a real address", len(sent), 1, "the counter runs under the security policy and sends one count per page load")
    expect("the count never carries the address after #", [u for u in sent if "SETUPTOKEN" in u or "bcsync" in u or "%23" in u or "#" in u], [],
           "a sync setup link puts the relay token after #; it must never be sent")
    expect("the counter causes no errors or policy refusals", gnotes, [], "the counter must run cleanly with the policy on")
    gctx.close(); gbrowser.close()

    # 2. Drive the app's own functions. The policy is bypassed here only so the test can evaluate.
    ctx = browser.new_context(bypass_csp=True); page = ctx.new_page(); watch(page, "app")
    page.goto(URL)
    wait(page, "typeof DB!=='undefined' && typeof renderHome==='function'")
    wait(page, "DB.count('meta').then(n=>window.__n=n), window.__n>=1")
    settle(1.2)

    page.set_input_files("#file-input", [ALPHA, BETA])
    wait(page, "DB.count('meta').then(n=>window.__n=n), window.__n>=3")
    wait(page, "DB.keys('app').then(k=>window.__ft=k.filter(x=>String(x).indexOf('ftbook:')===0).length), window.__ft>=3", 40000)
    ids = page.evaluate("DB.all('meta').then(ms=>Object.fromEntries(ms.map(m=>[m.title,m.id])))")
    alpha, beta = ids["Alpha Testing Book"], ids["Beta Second Book"]

    page.evaluate("openSearch('zygomorphic')")
    wait(page, "/Inside books/.test((document.querySelector('#search-results')||{}).textContent||'')")
    expect("inside-book search finds both books", ev(page, "document.querySelectorAll('#ft-group .res').length"), 2, "cross-book search inside text")
    expect("exact phrase search", ev(page, """searchFullText('"the lord is my shepherd"',60,{},parseSearch('"the lord is my shepherd"')).then(r=>r.length)"""), 1, "quoted phrases match exactly")

    page.evaluate("()=>{ openBook('%s'); }" % alpha)
    wait(page, "rendition && rendition.getContents().length && /quick brown fox/.test(rendition.getContents()[0].document.body.textContent)")
    settle(0.8)
    expect("highlight is saved", ev(page, """(()=>{ const c=rendition.getContents()[0]; const r=findQuoteRange(c,secTextMap(c),'quick brown fox'); lastSelection={cfiRange:c.cfiFromRange(r),text:'quick brown fox',contents:c}; return createHighlight('yellow').then(()=>DB.get('highlights', currentBook.id)).then(h=>hlLive(h.items).length); })()"""), 1, "a highlight lands in storage")
    hid = page.evaluate("highlights.filter(h=>!h.deleted)[0].id")
    page.evaluate("()=>{ deleteHighlight('%s'); }" % hid); settle()
    expect("deleted highlight is a tombstone", ev(page, "DB.get('highlights', currentBook.id).then(h=>[hlLive(h.items).length, h.items.length])"), [0, 1], "a delete is kept as deleted:true so it propagates")

    page.evaluate("""()=>{ const c=rendition.getContents()[0]; const r=findQuoteRange(c,secTextMap(c),'Call me Ishmael'); lastSelection={cfiRange:c.cfiFromRange(r),text:'Call me Ishmael',contents:c}; pushSelectionToMargins(); }""")
    wait(page, "/> Call me Ishmael/.test(currentBook.scratch||'')")
    expect("send to margins writes quote and link", ev(page, "/\\[\\[bc\\|/.test(currentBook.scratch||'')"), True, "the margins entry carries a location link")
    expect("margins show pipe tables", ev(page, r"""(()=>{
      const md=['Before the table.','','| Western Efficacy | Chinese Efficacy |','|:---|---:|','| Means / Ends | Conditions / Consequences |',
        '| Actions / Heroic (loud, direct) | **Transformation** (quiet) |','| a \\| pipe | '+bcMakeToken({bookKey:'id:x',kind:'book'})+' |','After the table.','','a | line with a pipe but no table'].join('\n');
      const d=document.createElement('div'); d.innerHTML=scratchHtml(md); const t=d.querySelector('table');
      if(!t) return 'no table';
      const cell=(r,c)=>t.rows[r].cells[c];
      return { rows:t.rows.length, cols:t.rows[0].cells.length, head:cell(0,0).tagName+':'+cell(0,0).textContent, right:cell(1,1).style.textAlign, left:cell(1,0).style.textAlign,
        bold:!!cell(2,1).querySelector('strong'), pipe:cell(3,0).textContent, link:!!cell(3,1).querySelector('.bc-ref'),
        after:[...d.querySelectorAll('p')].map(p=>p.textContent) };
    })()"""), {"rows": 4, "cols": 2, "head": "TH:Western Efficacy", "right": "right", "left": "left", "bold": True, "pipe": "a | pipe", "link": True,
                "after": ["Before the table.", "After the table.", "a | line with a pipe but no table"]},
           "rows, alignment, formatting and links inside cells; a stray pipe is not a table")
    expect("a link inside an exported table keeps the table whole", ev(page, r"""(()=>{
      const tok=bcMakeToken({bookKey:'id:o',kind:'book'}), ctx={title:()=>'Other Book', file:()=>'other-book-1', quote:()=>'', currentKey:'id:me'};
      return notesToMarkdown(['| A | B |','|---|---|','| x | '+tok+' |','','Outside '+tok].join('\n'), ctx).split('\n'); })()"""),
           ["| A | B |", "|---|---|", "| x | see [[other-book-1\\|Other Book]] |", "", "Outside see [[other-book-1|Other Book]]"],
           "Obsidian splits a table cell at an unescaped pipe, so a wikilink's pipe is written as \\| inside a table")
    expect("margins keep numbers and links",ev(page, """(()=>{ const h=scratchHtml('Numbers 42 and 1984 stay. '+bcMakeToken({bookKey:'id:x',kind:'book'})); return /42/.test(h) && /1984/.test(h) && /bc-ref/.test(h); })()"""), True, "the token sentinels must not eat digits")

    page.evaluate("""DB.put('meta',{id:'ghost1',title:'Ghost Book',author:'Nobody',bookKey:'id:ghost',addedAt:Date.now(),progress:0,tags:[]})""")
    page.evaluate("()=>{ openBookAt('ghost1', null); }"); settle(1)
    expect("opening an unavailable book leaves the open one alone", ev(page, "currentBook && currentBook.id"), alpha, "an unopenable book must not take over currentBook")

    page.evaluate("""()=>{ window.__ib=0; window.__origIB=indexBook; DB.del('fulltext', currentBook.id); indexBook=function(){ window.__ib++; return Promise.resolve(null); }; doFind('fox'); }"""); settle(1.5)
    expect("find in book does not loop", ev(page, "window.__ib"), lambda n: 1 <= n < 10, "an unreadable book must not be re-indexed in a loop (the old loop made thousands of calls)")
    page.evaluate("()=>{ indexBook=window.__origIB; }")

    expect("margins save only to their own book", ev(page, """(async()=>{
      openScratch(); toggleScratchEdit();
      const ta=document.querySelector('#scratch-edit-area'); ta.value='ALPHA MARGINS TEXT'; ta.dispatchEvent(new Event('input'));
      const bytes=(await DB.get('blob','%s')).data;
      await DB.put('meta',{id:'mg2',title:'Margins Two',author:'M',bookKey:'id:mg2',addedAt:1,progress:0,tags:[],scratch:'KEEP ME'});
      await DB.put('blob',{id:'mg2',data:bytes});
      closePanels();
      await openBookAt('mg2', null); await new Promise(r=>setTimeout(r,1800));
      return [(await DB.get('meta','mg2')).scratch, (await DB.get('meta','%s')).scratch];
    })()""" % (alpha, alpha)), ["KEEP ME", "ALPHA MARGINS TEXT"], "a late margins save must never land on another book")
    page.evaluate("()=>{ closeBook(); }"); settle()

    expect("concurrent tombstone clears all apply", ev(page, """(async()=>{
      for(const id of ['t1','t2','t3']) await addTombstone(id,'id:'+id);
      await Promise.all([clearTombstone('t1','id:t1'),clearTombstone('t2','id:t2'),clearTombstone('t3','id:t3')]);
      const t=await loadTombstones(); return ['t1','t2','t3'].filter(k=>t.ids[k]).length; })()"""), 0, "parallel tombstone writes must not overwrite each other")
    expect("a delete racing a sync merge is kept", ev(page, """Promise.all([addTombstone('r1','id:r1'), mutateTombstones(t=>{ t.ids['r2']=Date.now(); return true; })]).then(()=>loadTombstones()).then(t=>!!t.ids.r1 && !!t.ids.r2)"""), True, "both tombstones survive")
    expect("restoring a notes file brings back every deleted book in it", ev(page, """(async()=>{
      const mk=(id)=>({meta:{id:id,title:'Restored '+id,author:'R',bookKey:'id:'+id,addedAt:1,progress:0,tags:[]},highlights:[{id:'h'+id,text:'quote '+id,color:'yellow',created:1,updated:1}],updatedAt:1});
      for(const id of ['rs1','rs2','rs3']) await addTombstone(id,'id:'+id);
      importNotesFile(new File([JSON.stringify({app:'epub-reader',format:'wr-notes',version:1,books:[mk('rs1'),mk('rs2'),mk('rs3')]})],'n.json',{type:'application/json'}));
      await new Promise(r=>setTimeout(r,2000));
      const t=await loadTombstones(); return ['rs1','rs2','rs3'].filter(id=>!t.ids[id]).length; })()"""), 3, "an explicit restore un-deletes every book it carries")
    expect("automatic notes import skips a deleted book", ev(page, """(async()=>{
      await addTombstone('ad1','id:ad1');
      await importNotesBundle({format:'wr-notes',books:[{meta:{id:'ad1',title:'Deleted',bookKey:'id:ad1',tags:[]},highlights:[],updatedAt:1}]});
      return !(await DB.get('meta','ad1')); })()"""), True, "an old notes file must not resurrect a deleted book")
    expect("an aborted storage transaction rejects", ev(page, """(async()=>{
      const db=await DB.open(); const t=db.transaction('app','readwrite');
      const p=new Promise(res=>txSettle(t,()=>res('completed'),()=>res('rejected')));
      t.objectStore('app').put({key:'abort-test',val:1}); t.abort();
      return await Promise.race([p, new Promise(r=>setTimeout(()=>r('hung'),2000))]); })()"""), "rejected", "a full disk must fail loudly, not hang")

    page.evaluate("()=>{ openDetails('%s'); }" % beta); settle()
    page.evaluate("()=>{ detailsDelete(); }")
    wait(page, "DB.get('meta','%s').then(m=>window.__gone=!m), window.__gone===true" % beta)
    settle(1)
    expect("a deleted book leaves no search index", ev(page, """DB.open().then(db=>new Promise(res=>{ const r=db.transaction('ftseg').objectStore('ftseg').count(IDBKeyRange.bound(['%s'],['%s',[]])); r.onsuccess=()=>res(r.result); }))""" % (beta, beta)), 0, "delete clears the disk index")
    expect("a deleted book no longer answers search", ev(page, "searchFullText('zygomorphic',60,{},parseSearch('zygomorphic')).then(r=>r.map(x=>x.bookId))"), lambda ids: beta not in ids and alpha in ids, "the deleted book is gone from results, the kept one remains")

    expect("a dropped file never replaces the app", ev(page, """(()=>{ openSearch(''); const dt=new DataTransfer(); dt.items.add(new File(['x'],'x.epub')); const ev=new DragEvent('drop',{dataTransfer:dt,cancelable:true,bubbles:true}); document.body.dispatchEvent(ev); const r=ev.defaultPrevented; goHome(); return r; })()"""), True, "drops are always handled by the page")

    with page.expect_download() as dl:
        page.evaluate("()=>{ exportLibraryMarkdown(); }")
    zf = zipfile.ZipFile(dl.value.path()); names = set(n[:-3] for n in zf.namelist()); dangling = []
    for n in zf.namelist():
        m = re.search(r"Source: \[\[([^\]|]+)", zf.read(n).decode("utf-8"))
        if m and m.group(1) not in names: dangling.append(n)
    expect("Markdown export links resolve", dangling, [], "each Source link points at a note inside the zip")

    page.evaluate("(async()=>{ for(const id of ['%s','bcguide001','%s']){ await openBook(id); await new Promise(r=>setTimeout(r,700)); } closeBook(); })()" % (alpha, alpha))
    settle(1)

    page.evaluate("()=>purgeEverything().then(()=>1)"); settle(1)
    expect("delete everything clears the search index", ev(page, "Promise.all([DB.count('ftseg'),DB.count('ftblk')])"), [0, 0], "no derived index outlives the books")
    ctx.close()

    # 3. A transcript book whose video YouTube refuses. YouTube is stubbed: the embed for
    #    "deadvideo01" answers with onError 150, as YouTube does for a removed video or one
    #    its owner keeps on YouTube only. The player must say so, stay quiet, and leave the book alone.
    vctx = browser.new_context(bypass_csp=True); vp = vctx.new_page(); watch(vp, "video")
    def youtube_stub(route):
        dead = "deadvideo01" in route.request.url
        body = ("<!doctype html><title>player</title><script>"
                "var say=function(m){parent.postMessage(JSON.stringify(m),'*');};"
                "say({event:'onReady'});" + ("setTimeout(function(){say({event:'onError',info:150});},300);" if dead else "") +
                "</script>")
        route.fulfill(status=200, content_type="text/html", body=body)
    vctx.route(re.compile(r"https://www\.youtube\.com/embed/.*"), youtube_stub)
    vp.goto(URL)
    wait(vp, "typeof DB!=='undefined' && typeof openBook==='function'"); settle(1.2)
    vp.set_input_files("#file-input", [GONE, LIVE])
    wait(vp, "DB.all('meta').then(ms=>window.__v=ms.filter(m=>m.videoId).length), window.__v>=2")
    vids = vp.evaluate("DB.all('meta').then(ms=>Object.fromEntries(ms.filter(m=>m.videoId).map(m=>[m.videoId,m.id])))")
    vp.evaluate("(id)=>openBook(id)", vids["deadvideo01"])
    wait(vp, "!!document.querySelector('.bcp.bcp-dead')")
    note = ev(vp, "document.querySelector('.bcp-gone').textContent")
    expect("a refused video says so", note, lambda t: "The video is unavailable." in t and "your marks are all still here" in t, "the reader is told the book is unaffected")
    expect("the refused video links to YouTube", ev(vp, "document.querySelector('.bcp-gone a').href"), "https://www.youtube.com/watch?v=deadvideo01", "a way to check on YouTube itself")
    expect("the dead player is folded away", ev(vp, "getComputedStyle(document.querySelector('.bcp-stage')).display"), "none", "no black box where the video was")
    vp.evaluate("()=>{ const d=rendition.getContents()[0].document; d.querySelector('button.ts[data-t=\"18\"]').click(); }"); settle(1.5)
    expect("tapping a time does not fake playback", ev(vp, "[BackchatPlayer.isPlaying, Math.round(BackchatPlayer.time)]"), [False, 18], "no clock running against a video that cannot play")
    vp.evaluate("()=>{ closeBook(); }"); settle(0.5)
    vp.evaluate("(id)=>openBook(id)", vids["livevideo01"]); settle(2.5)
    expect("a playable video after a refused one is not marked unavailable", ev(vp, "[!!document.querySelector('.bcp.bcp-dead'), !!document.querySelector('.bcp:not(.bcp-idle)')]"), [False, True], "the refused state belongs to one video, not the player")
    vctx.close()

    # 4. Folder sync against an in-memory, case-insensitive folder (how macOS and Windows disks behave).
    fctx = browser.new_context(bypass_csp=True); fp = fctx.new_page(); watch(fp, "folder")
    fp.goto(URL); wait(fp, "typeof vaultPull==='function'"); settle(1.5)
    fp.evaluate(open(os.path.join(HERE, "mockfs.js"), encoding="utf-8").read())
    res = fp.evaluate("""async (b64)=>{
      const bytes=Uint8Array.from(atob(b64),c=>c.charCodeAt(0));
      const root=mkDir('root',true), books=await root.getDirectoryHandle('books',{create:true});
      const fh=await books.getFileHandle('alpha-testing-book-'+hashTag('id:urn:isbn:9780000000001')+'.epub',{create:true});
      const w=await fh.createWritable(); await w.write(bytes); await w.close();
      vault.handle=root; vault.connected=true; vault.needsReauth=false;
      await vaultPull();
      const a=(await DB.all('meta')).find(m=>m.title==='Alpha Testing Book');
      const files=[]; for await (const e of books.values()) files.push(e.name);
      return {id: a&&a.id, files: files.length};
    }""", base64.b64encode(open(ALPHA, "rb").read()).decode())
    expect("folder import keeps the book file (case-insensitive disk)", res, lambda r: bool(r["id"]) and r["files"] == 1, "renaming must never delete the only copy")
    if res.get("id"):
        wait(fp, "DB.get('app','ftbook:%s').then(v=>window.__done=!!v), window.__done===true" % res["id"], 30000)
        expect("a delete arriving through the folder clears the book and its index", ev(fp, """async (id)=>{
          const m=await DB.get('meta',id), data=await vault.handle.getDirectoryHandle('.reader',{create:true});
          let fh=await data.getFileHandle(id+'.json',{create:true}), w=await fh.createWritable(); await w.write(JSON.stringify({meta:m,highlights:[],updatedAt:1})); await w.close();
          const t={ids:{},keys:{}}; t.ids[id]=Date.now(); t.keys[m.bookKey]=Date.now();
          fh=await data.getFileHandle('_tombstones.json',{create:true}); w=await fh.createWritable(); await w.write(JSON.stringify(t)); await w.close();
          await vaultPull(); await new Promise(r=>setTimeout(r,800));
          return [!(await DB.get('meta',id)), (await searchFullText('zygomorphic',60,{},parseSearch('zygomorphic'))).length];
        }""", res["id"]), [True, 0], "a remote delete removes the record and its search rows")
    fctx.close()

    # 4b. The folder as people really use it: books added, deleted and added back, files dropped in
    #     by hand, cloud clients leaving conflict copies, two browsers on one folder. The mock folder
    #     logs every write, so "nothing to do" can be checked as "nothing written".
    B64 = {k: base64.b64encode(open(v, "rb").read()).decode() for k, v in (("alpha", ALPHA), ("alpha2", ALPHA2), ("beta", BETA), ("gamma", GAMMA), ("crowded", CROWDED))}
    MOCKFS = open(os.path.join(HERE, "mockfs.js"), encoding="utf-8").read()
    def folder_page(label):
        c = browser.new_context(bypass_csp=True); pg = c.new_page(); watch(pg, label)
        pg.goto(URL); wait(pg, "typeof vaultPull==='function'"); settle(1.5)
        pg.evaluate(MOCKFS); pg.evaluate("()=>B.init()")
        pg.evaluate("()=>{ window.__toasts=[]; const t=window.toast; window.toast=function(m){ __toasts.push(String(m)); return t.apply(this, arguments); }; }")
        return c, pg
    SYNC = "async()=>{ B.mark(); const r=await Promise.race([vaultPull().then(()=>vaultPushAll()).then(()=>'done'), new Promise(r=>setTimeout(()=>r('stuck'),25000))]); await B.quiet(600); return [r, B.log('w').length, B.log('r')]; }"
    ALPHA_ID = "async()=>((await DB.all('meta')).find(x=>x.title==='Alpha Testing Book')||{}).id"
    def drop(pg, name, key): ev(pg, "([n,b])=>B.putB64('books/'+n, b)", [name, B64[key]])
    def add_in_app(pg, key, name):
        return ev(pg, "async([b,n])=>{ const u=Uint8Array.from(atob(b),c=>c.charCodeAt(0)); await importFiles([new File([u], n)]); await B.quiet(); return true; }", [B64[key], name])
    def mark_book(pg, title, n, tag):
        return ev(pg, """async([t,n,g])=>{ const m=(await DB.all('meta')).find(x=>x.title===t); const h=(await DB.get('highlights',m.id))||{id:m.id,items:[]}; const now=Date.now();
          for(let i=0;i<n;i++) h.items.push({id:g+i+'-'+now, text:g+' '+i, color:'yellow', note:'', created:now+i, updated:now+i}); await DB.put('highlights',h); await vaultPushBook(m.id,false); await B.quiet(); return h.items.length; }""", [title, n, tag])
    def delete_book(pg, title):
        return ev(pg, """async(t)=>{ const m=(await DB.all('meta')).find(x=>x.title===t); detailsBook=m; detailsItems=((await DB.get('highlights',m.id))||{}).items||[]; detailsDelete(); await B.quiet(1200); return !(await DB.get('meta', m.id)); }""", title)

    gctx, gp = folder_page("folder-robust-1")
    for nm, k in (("a.epub", "alpha"), ("b.epub", "beta"), ("g.epub", "gamma")): drop(gp, nm, k)
    expect("two syncs at once keep every book and its file", ev(gp, """async()=>{ await Promise.all([vaultPull(), vaultPull()]); await B.quiet();
        return [(await DB.all('meta')).filter(m=>m.kind!=='text').length, Object.keys(await B.ls('books')).filter(n=>!/talk-back/i.test(n)).length]; }"""), [3, 3],
        "a second sync started while one runs joins it; two at once imported a book twice, and folding the twins removed the book file")
    ev(gp, SYNC)
    ev(gp, "async()=>{ const s=JSON.stringify(await buildNotesBundle()); await B.put('notes/latest.json', s); await B.put('notes/latest [conflicted].json', s); await B.put('notes/latest (conflicted 1).json', s); return true; }")
    first = ev(gp, SYNC)
    expect("a notes snapshot's cloud conflict copies are merged once, then removed", [first[0], sorted(ev(gp, "async()=>Object.keys(await B.ls('notes'))"))] if isinstance(first, list) else first, ["done", ["notes/latest.json"]],
           "they piled up beside latest.json, and every sync merged every one of them")
    ev(gp, "async()=>{ for(const m of await DB.all('meta')) if(m.kind!=='text') await DB.del('blob', m.id); window.__bp=0; const p=DB.put; DB.put=function(s){ if(s==='blob') __bp++; return p.apply(DB, arguments); }; return true; }")
    again = ev(gp, SYNC)
    expect("a sync with nothing new writes nothing to the folder", again[:2] if isinstance(again, list) else again, ["done", 0],
           "each sync rewrote every book's record once per notes file: thousands of writes for a cloud client to collide over")
    expect("a sync reads no book file into the browser", ev(gp, "()=>window.__bp"), 0,
           "every sync read each book the browser had let go of, only for the cache to let it go again")
    reopened = ev(gp, "async()=>{ _vaultLastWrite={}; _vaultIndexHash=''; return true; }") and ev(gp, SYNC)   # what reopening Backchat forgets
    expect("reopening Backchat rewrites no unchanged file", reopened[:2] if isinstance(reopened, list) else reopened, ["done", 0],
           "the first sync after opening wrote every record and note file again, since the browser no longer knew it had")
    nextday = ev(gp, "()=>{ const D=Date, s=864e5; window.Date=class extends D{ constructor(...a){ a.length ? super(...a) : super(D.now()+s); } static now(){ return D.now()+s; } }; _vaultLastWrite={}; _vaultIndexHash=''; return true; }") and ev(gp, SYNC)
    expect("opening Backchat the next day rewrites no unchanged file", nextday[:2] if isinstance(nextday, list) else nextday, ["done", 0],
           "each notes file carried the day it was written, so the first sync of every day rewrote all of them")
    ev(gp, "async()=>{ await B.put('books/empty.epub', new Uint8Array([])); await B.put('books/broken.epub', new Uint8Array([80,75,3,4,9,9,9])); __toasts.length=0; return true; }")
    stuck = ev(gp, SYNC)
    expect("an unreadable file in books/ does not stop the sync", [stuck[0] if isinstance(stuck, list) else stuck, any("left 2 files" in t for t in ev(gp, "()=>__toasts"))], ["done", True],
           "an empty or half-downloaded .epub made the reader wait forever, so every sync stopped there, silently")
    expect("the next sync passes the unreadable files by quietly", ev(gp, "async()=>{ __toasts.length=0; const r=await Promise.race([vaultPull().then(()=>'done'), new Promise(r=>setTimeout(()=>r('stuck'),25000))]); return r==='done' ? __toasts.filter(t=>/alone/.test(t)).length : r; }"), 0, "said once, not on every sync")
    gctx.close()

    gctx, gp = folder_page("folder-robust-2")
    drop(gp, "alpha.epub", "alpha"); ev(gp, SYNC); mark_book(gp, "Alpha Testing Book", 2, "keep")
    canon = ev(gp, "async()=>{ const m=(await DB.all('meta')).find(x=>x.title==='Alpha Testing Book'); return vaultPathName(m); }")
    ev(gp, """async()=>{ const m=(await DB.all('meta')).find(x=>x.title==='Alpha Testing Book'); const t=Object.assign({}, m, {id:'zz0twin0000000'}); delete t.cover;
        await B.put('.reader/zz0twin0000000.json', JSON.stringify({meta:t, highlights:[], updatedAt:1})); return true; }""")
    folded = ev(gp, SYNC)
    files = ev(gp, "()=>B.ls()")
    expect("folding a second record of a book keeps the book's file and notes", [("books/%s.epub" % canon) in files, ("highlights/%s.md" % canon) in files, ".reader/zz0twin0000000.json" in files, folded[2] if isinstance(folded, list) else folded],
           [True, True, False, [".reader/zz0twin0000000.json"]], "the duplicate shares the book's file names, and removing it removed the surviving book's EPUB and notes")
    drop(gp, "Alpha corrected.epub", "alpha2"); ev(gp, SYNC)
    expect("a copy of a book with different contents is kept, not tidied away", "books/Alpha corrected.epub" in ev(gp, "()=>B.ls('books')"), True,
           "a corrected edition dropped into books/ was deleted as a stray copy of the book")
    expect("Refresh EPUB from folder reads from that copy and keeps the marks", ev(gp, """async()=>{ const m=(await DB.all('meta')).find(x=>x.title==='Alpha Testing Book'); await refreshBookFromFolder(m); await B.quiet();
        const f=await B.ls('books'), bl=await DB.get('blob', m.id), h=await DB.get('highlights', m.id); return [f['books/'+vaultPathName(m)+'.epub']===bl.data.byteLength, bl.data.byteLength, !!f['books/Alpha corrected.epub'], h.items.length]; }"""),
           [True, os.path.getsize(ALPHA2), False, 2], "the refresh is the deliberate way to switch a book to a new file")
    ev(gp, "async(b)=>{ const m=(await DB.all('meta')).find(x=>x.title==='Alpha Testing Book'); const u=Uint8Array.from(atob(b),c=>c.charCodeAt(0)); await B.put('books/'+vaultPathName(m)+'.epub', u); await DB.put('blob', {id:m.id, data:u.buffer}); return true; }", B64["alpha2"])   # the book reads from the corrected file, here and in the folder
    add_in_app(gp, "alpha", "alpha-original.epub")
    expect("adding a changed EPUB in the app replaces the folder's copy", ev(gp, "async()=>{ const m=(await DB.all('meta')).find(x=>x.title==='Alpha Testing Book'); return (await B.ls('books'))['books/'+vaultPathName(m)+'.epub']; }"), os.path.getsize(ALPHA),
           "Updated the book file left the old file in the folder, and it came back once the browser let go of its copy")
    gctx.close()

    gctx, gp = folder_page("folder-robust-3")
    add_in_app(gp, "alpha", "alpha.epub"); mark_book(gp, "Alpha Testing Book", 5, "first")
    delete_book(gp, "Alpha Testing Book"); add_in_app(gp, "alpha", "alpha.epub"); delete_book(gp, "Alpha Testing Book")
    expect("deleting a book again keeps its first backup, marks and all", ev(gp, """async()=>{ const out=[]; for(const n of Object.keys(await B.ls('backups')).sort()){ if(!/Alpha-Testing-Book-backup/.test(n)) continue; const j=JSON.parse(await B.text(n)); out.push(((j.highlights||[])[0]||{items:[]}).items.length); } return out.sort(); }"""), [0, 5],
           "the second delete overwrote the first backup, the one holding the marks")
    stale = ev(gp, "()=>B.text('.reader/_tombstones.json')")
    add_in_app(gp, "alpha", "alpha.epub"); mark_book(gp, "Alpha Testing Book", 2, "back")
    ev(gp, "(t)=>B.put('.reader/_tombstones.json', t)", stale)
    ev(gp, SYNC)
    key = ev(gp, "async()=>bookKeyOf((await DB.all('meta')).find(x=>x.title==='Alpha Testing Book')||{})")
    ev(gp, "async(k)=>{ const t={ids:{}, keys:{}}; t.keys[k]=Date.now()-60000; await cloudApplyBundle({app:'backchat-sync', v:1, name:'phone', tombstones:t, books:[]}); await B.quiet(); return true; }", key)
    expect("a book added back stays when an older delete comes back from another copy", ev(gp, "async()=>{ const m=(await DB.all('meta')).find(x=>x.title==='Alpha Testing Book'); return m ? ((await DB.get('highlights', m.id)).items||[]).length : 'deleted again'; }"), 2,
           "another browser's tombstones in the folder, or the phone's through the relay, deleted the re-added book again")
    drop(gp, "g.epub", "gamma"); ev(gp, SYNC); delete_book(gp, "Gamma Third Book")
    drop(gp, "Gamma again.epub", "gamma"); ev(gp, "()=>{ __toasts.length=0; return true; }"); ev(gp, SYNC)
    expect("a deleted book's file dropped back into books/ is left alone, and said so", [ev(gp, "async()=>!!(await DB.all('meta')).find(x=>x.title==='Gamma Third Book')"), any("you deleted" in t for t in ev(gp, "()=>__toasts"))], [False, True],
           "it was ignored without a word, and Check folder promised it would import on the next sync")
    report = ev(gp, "async()=>{ await folderCheck(); return [document.querySelector('#folder-check-info').textContent, !document.querySelector('#folder-readd-field').classList.contains('hidden')]; }")
    expect("Check folder names the deleted book's file and offers Add back", [("you deleted: Gamma Third Book" in report[0]) if isinstance(report, list) else report, report[1] if isinstance(report, list) else None], [True, True], "the way to bring a deleted book back from its file")
    expect("Add back returns the deleted book", ev(gp, "async()=>{ document.getElementById('folder-readd-btn').click(); await B.quiet(1500); return !!(await DB.all('meta')).find(x=>x.title==='Gamma Third Book'); }"), True, "an explicit add-back clears the delete")
    drop(gp, "crowded.epub", "crowded"); ev(gp, SYNC)
    report = ev(gp, "async()=>{ await folderCheck(); return document.querySelector('#folder-check-info').textContent; }")
    expect("Check folder does not promise to add a file sync could not add, and says why", [("crowded.epub (too many files inside" in report), ("new book file" in report)] if isinstance(report, str) else report, [True, False],
           "it listed the file as new, to be added on the next sync, though sync had stopped trying it")
    gctx.close()

    # Two browsers on one folder, a cloud client carrying it between them.
    actx, ap_ = folder_page("folder-browser-a"); bctx, bp_ = folder_page("folder-browser-b")
    def hand(src, dst): ev(dst, "(m)=>B.load(m)", ev(src, "()=>B.dump()"))
    drop(ap_, "alpha.epub", "alpha"); ev(ap_, SYNC); mark_book(ap_, "Alpha Testing Book", 3, "a")
    ev(bp_, "()=>{ vault.handle=null; vault.connected=false; return true; }"); add_in_app(bp_, "alpha", "alpha.epub"); ev(bp_, "()=>{ vault.handle=B.root; vault.connected=true; return true; }")
    hand(ap_, bp_); ev(bp_, SYNC)
    quiet = []
    for r in range(2):
        hand(bp_, ap_); w = ev(ap_, SYNC); quiet.append(w[1] if isinstance(w, list) else w)
        hand(ap_, bp_); w = ev(bp_, SYNC); quiet.append(w[1] if isinstance(w, list) else w)
    expect("two browsers sharing a folder settle on one record of a book", [ev(ap_, ALPHA_ID) == ev(bp_, ALPHA_ID), quiet[1:]], [True, [0, 0, 0]],
           "each kept its own record of the same book and removed the other's on every sync")
    actx.close(); bctx.close()
    # The same marks merged in another order, or with another time of last change (each browser
    # folds a duplicate at its own moment), are the same notes. Backchat opened in turn on each.
    actx, ap_ = folder_page("folder-same-a"); bctx, bp_ = folder_page("folder-same-b")
    drop(ap_, "alpha.epub", "alpha"); ev(ap_, SYNC); hand(ap_, bp_); ev(bp_, SYNC)
    mark_book(ap_, "Alpha Testing Book", 2, "a"); mark_book(bp_, "Alpha Testing Book", 2, "b")   # marked on both before either saw the other's
    hand(ap_, bp_); ev(bp_, SYNC); hand(bp_, ap_); ev(ap_, SYNC)
    STAMP = "async(d)=>{ const m=(await DB.all('meta')).find(x=>x.title==='Alpha Testing Book'); const h=await DB.get('highlights', m.id); h.updatedAt=Date.now()+d; await DB.put('highlights', h); return [h.items.map(i=>i.id.slice(0,1)).join(''), h.items.length]; }"
    REOPEN = "()=>{ _vaultLastWrite={}; _vaultIndexHash=''; return true; }"
    orders = [ev(ap_, STAMP, 1000), ev(bp_, STAMP, 2000)]
    starts = []
    for r in range(3):
        for src, dst in ((bp_, ap_), (ap_, bp_)):
            hand(src, dst); ev(dst, REOPEN); w = ev(dst, SYNC); starts.append(w[1] if isinstance(w, list) else w)
    expect("the same notes in another order, or with another time of change, are not rewritten", [orders[0] != orders[1], starts[2:]], [True, [0, 0, 0, 0]],
           "each browser wrote its own copy of the book's record back every time Backchat opened, one more collision for the cloud client")
    actx.close(); bctx.close()

    # 4c. The open book keeps what arrives while it is open. Seven paths carry a record into the
    #     library: the folder, a notes file, a hand-off, a cloud conflict copy, a restore, device sync
    #     and the start-up tidy-up. Each delivers a mark for the book on screen, and the reader's next
    #     save must keep it. One rule for every path, so a path that forgets the open book is caught.
    octx, op_ = folder_page("open-book")
    add_in_app(op_, "alpha", "alpha.epub"); ev(op_, SYNC)
    oid = ev(op_, ALPHA_ID)
    ev(op_, "(id)=>{ openBook(id); return true; }", oid)
    wait(op_, "rendition && rendition.getContents().length && /quick brown fox/.test(rendition.getContents()[0].document.body.textContent)")
    settle(0.8)
    ev(op_, """()=>{ const c=rendition.getContents()[0]; const r=findQuoteRange(c,secTextMap(c),'quick brown fox');
      lastSelection={cfiRange:c.cfiFromRange(r),text:'quick brown fox',contents:c}; return createHighlight('yellow').then(()=>true); }""")
    ARRIVE = r"""async([id, path])=>{
      const now=Date.now(), mark={ id:'arrived-'+path.replace(/\W+/g,'-'), text:'a mark that arrived by '+path, color:'green', created:now, updated:now };
      const meta=Object.assign({}, await DB.get('meta', id)), had=((await DB.get('highlights', id))||{}).items||[];
      const rec={ meta:meta, highlights:had.concat([mark]), updatedAt:now };
      if(path==='folder'){ await B.put('.reader/'+id+'.json', JSON.stringify(rec)); await vaultPull(); }
      else if(path==='notes file'){ await B.put('notes/WR-notes-phone.json', JSON.stringify({ app:'epub-reader', format:'wr-notes', version:1, device:'another-device', exportedAt:new Date().toISOString(), books:[rec] })); await vaultPull(); }
      else if(path==='hand-off'){ await B.put('handoff-'+now+'.json', JSON.stringify({ app:'backchat-handoff', exportedAt:new Date().toISOString(), books:[{ meta:meta, highlights:[mark], updatedAt:now }] })); await vaultPull(); }
      else if(path==='conflict copy'){ await B.put('.reader/'+id+' (conflicted copy).json', JSON.stringify(rec)); await vaultPull(); }
      else if(path==='restore'){ await restoreFromObject({ app:'epub-reader', version:2, books:[meta], highlights:[{ id:id, items:[mark], updatedAt:now }], tombstones:{ids:{},keys:{}} }); }
      else if(path==='device sync'){ await cloudApplyBundle({ app:'backchat-sync', v:1, device:'phone', name:'Phone', at:now, tombstones:{ids:{},keys:{},undo:{ids:{},keys:{}}}, books:[{ meta:meta, highlights:[mark], updatedAt:now }] }); }
      else if(path==='tidy-up'){ const dup=Object.assign({}, meta, { id:'zz'+id }); await DB.put('meta', dup); await DB.put('highlights', { id:dup.id, items:[mark], updatedAt:now }); await reconcileLibrary(); }
      await B.quiet(400);
      const mine=highlights.filter(h=>!h.deleted && !/^arrived-/.test(h.id))[0];
      toggleFav(mine.id);   // the reader's next save: any edit of a mark made here
      await new Promise(r=>setTimeout(r,700)); await B.quiet(400);
      return hlLive(((await DB.get('highlights', id))||{}).items).some(h=>h.id===mark.id);
    }"""
    PATHS = ("folder", "notes file", "hand-off", "conflict copy", "restore", "device sync", "tidy-up")
    expect("a mark that arrives while its book is open survives the reader's next save, by every path", [pth for pth in PATHS if ev(op_, ARRIVE, [oid, pth]) is not True], [],
           "the open book saved its own copy of the marks over the ones that had just arrived")
    expect("what you change on the page of the book you are reading stays when you go back to it", ev(op_, r"""async(id)=>{
      await openDetails(id); await new Promise(r=>setTimeout(r,300));
      detailsNotesEdit(); document.querySelector('#det-notes-area').value='Written on the book page.'; detailsNotesSave();
      addDetTag('kept-tag'); const was=!!(await DB.get('meta', id)).fav; await bcToggleFav(id, null);
      await new Promise(r=>setTimeout(r,500));
      await openBookAt(id); await new Promise(r=>setTimeout(r,300));      // Continue: back to the reader, which never closed
      await rendition.next(); await new Promise(r=>setTimeout(r,1200));   // a page turn saves the reader's copy of the record
      const m=await DB.get('meta', id), lost=[];
      if(!/Written on the book page/.test(m.scratch||'')) lost.push('margins');
      if((m.tags||[]).indexOf('kept-tag')<0) lost.push('tag');
      if(!!m.fav===was) lost.push('favourite');
      return lost; }""", oid), [],
           "the page and the reader each held a copy of the book's record, and the reader's next save wrote its older copy back")
    expect("refreshing a closed book from the folder leaves you on its page", ev(op_, r"""async(id)=>{
      closeBook(); await new Promise(r=>setTimeout(r,500));
      await openDetails(id); await new Promise(r=>setTimeout(r,300));
      await refreshBookFromFolder(await DB.get('meta', id)); await new Promise(r=>setTimeout(r,2000));
      return bcScreen(); }""", oid), "details",
           "a closed book still counted as the open one, so the refresh opened it in the reader")
    expect("the start-up tidy-up reads the library a fixed number of times, however many books have no file here", ev(op_, r"""async()=>{
      const now=Date.now();
      for(let i=0;i<40;i++){ const id='ghost'+i; await DB.put('meta', { id, title:'Ghost Book '+i, author:'Nobody', bookKey:'id:urn:ghost:'+i, addedAt:now, updated:now, tags:[] }); await DB.put('highlights', { id, items:[], updatedAt:now }); }
      let n=0; const all=DB.all; DB.all=function(s){ if(s==='meta') n++; return all.apply(DB, arguments); };
      try{ await reconcileLibrary(); } finally { DB.all=all; }
      for(let i=0;i<40;i++){ await DB.del('meta','ghost'+i); await DB.del('highlights','ghost'+i); }
      return n; }"""), lambda n: isinstance(n, int) and n <= 3,
           "it read the whole library again for every book without its file here: on a phone that holds most books that way, seconds at every start")
    octx.close()

    # 4d. A phone keeps its books, and with device sync on it uses the folder as a bookshelf. A phone
    #     reaches the folder only at home, so it never lets a book go for being in the folder. With
    #     device sync carrying its marks, it reads book files from the folder and adds the ones you
    #     add, and writes nothing else there, so each notes file has one writer: the computer.
    PHONE_B64 = []
    for i in range(22):
        pth = os.path.join(TMP, "phone%02d.epub" % i)
        make_epub(pth, "Phone Book %02d" % i, "Pat Reader", "urn:isbn:978111100%04d" % i, [("One", ["The words of phone book %d, kept for the train." % i])])
        PHONE_B64.append(base64.b64encode(open(pth, "rb").read()).decode())
    def phone_page(label, synced):
        c = browser.new_context(viewport={"width": 360, "height": 740}, device_scale_factor=2, is_mobile=True, has_touch=True, bypass_csp=True)
        pg = c.new_page(); watch(pg, label); pg.on("dialog", lambda d: d.accept())
        pg.goto(URL); wait(pg, "typeof vaultPull==='function'"); settle(1.5)
        if synced: pg.evaluate("()=>{ cloud.cfg={ url:'https://relay.invalid', token:'t', name:'Phone' }; return true; }")   # device sync set up; locked, so nothing goes out
        pg.evaluate(MOCKFS); pg.evaluate("()=>B.init()")
        return c, pg
    ADD_PHONE = "async(bs)=>{ await importFiles(bs.map((b,i)=>new File([Uint8Array.from(atob(b),c=>c.charCodeAt(0))], 'phone'+i+'.epub'))); await B.quiet(600); return true; }"
    pctx, pp = phone_page("phone-keeps", False)
    ev(pp, ADD_PHONE, PHONE_B64)
    expect("a phone keeps every book it holds when its folder is connected", ev(pp, r"""async()=>{
      await vaultPull(); await vaultPushAll(); await enforceBlobCache(); await B.quiet(400);
      const ms=(await DB.all('meta')).filter(m=>/^Phone Book/.test(m.title)), have=new Set(await DB.keys('blob'));
      return ms.length+' books, '+ms.filter(m=>have.has(m.id)).length+' with their file'; }"""), "22 books, 22 with their file",
           "the computer's rule ran on the phone: keep the twenty books opened last and let the rest go, because the folder has them")
    expect("a phone with a folder offers Remove from this device", ev(pp, r"""async()=>{
      const m=(await DB.all('meta')).find(x=>x.title==='Phone Book 03'); await openDetails(m.id); await new Promise(r=>setTimeout(r,500));
      return !document.querySelector('#det-remove-local').classList.contains('hidden'); }"""), True,
           "the button appeared only without a folder, the one place the phone could not free its space")
    pctx.close()
    sctx, sp = phone_page("phone-shelf", True)
    expect("with device sync on, a phone writes nothing to the folder but the book files it adds", ev(sp, r"""async(bs)=>{
      B.mark();
      await vaultPull(); await vaultPushAll();                                  // what connecting and reconnecting run
      await importFiles([new File([Uint8Array.from(atob(bs[0]),c=>c.charCodeAt(0))], 'one.epub')]); await B.quiet(600);
      const m=(await DB.all('meta')).find(x=>x.title==='Phone Book 00');
      await saveProgress(m, {immediate:true}); await maybeAutoBackup(); await vaultPushTombstones(); await B.quiet(600);
      const w=B.log('w'), others=w.filter(p=>!/^books\/[^/]+\.epub$/.test(p));
      await DB.del('blob', m.id);                                              // a dimmed book: its file comes from the folder
      await openBookAt(m.id); await new Promise(r=>setTimeout(r,2500));
      const opens=!!(rendition && rendition.getContents().length && /phone book 0/.test(rendition.getContents()[0].document.body.textContent));
      return { others:others, bookFile:w.some(p=>/^books\/.+\.epub$/.test(p)), opens:opens }; }""", PHONE_B64), {"others": [], "bookFile": True, "opens": True},
           "the phone wrote its own records, notes and backups into the folder the computer keeps, a second writer for every notes file")
    sctx.close()
    nctx, np_ = folder_page("no-snapshot")
    add_in_app(np_, "alpha", "alpha.epub"); ev(np_, SYNC)
    expect("no notes snapshot is written to the folder, and Export notes writes only its own file", ev(np_, r"""async()=>{
      B.mark(); const m=(await DB.all('meta')).find(x=>x.title==='Alpha Testing Book');
      m.scratch='A margin note.'; m.updated=Date.now(); await saveProgress(m, {immediate:true});
      await new Promise(r=>setTimeout(r,6800)); await exportNotes(); await B.quiet(600);
      const w=B.log('w').filter(p=>/^notes\//.test(p));
      return { latest:w.filter(p=>/latest\.json$/.test(p)).length, exports:w.filter(p=>/^notes\/WR-notes-/.test(p)).length }; }"""), {"latest": 0, "exports": 1},
           "every change rewrote notes/latest.json, a full copy of the notes the per-book records already hold")
    expect("Settings counts storage without reading a single book file", ev(np_, r"""async()=>{
      let reads=0; const get=DB.get; DB.get=function(s){ if(s==='blob') reads++; return get.apply(DB, arguments); };
      try{ updateStorageInfo(); await new Promise(r=>setTimeout(r,800)); } finally { DB.get=get; }
      return [reads, /^\d+ books?, \d+ with (its|their) file here/.test(document.querySelector('#storage-info').textContent)]; }"""), [0, True],
           "it read every book file in the browser to add up their sizes")
    ev(np_, "async()=>{ const id=((await DB.all('meta')).find(x=>x.title==='Alpha Testing Book')||{}).id; openBook(id); return true; }")
    wait(np_, "rendition && rendition.getContents().length && /quick brown fox/.test(rendition.getContents()[0].document.body.textContent)")
    settle(0.8)
    expect("reading counts its time without rewriting the book's record every ten seconds", ev(np_, r"""async()=>{
      const si=window.setInterval; let tick=null;
      window.setInterval=function(f, ms){ if(ms===10000){ tick=f; return 0; } return si.apply(window, arguments); };
      try{ startReadTimer(); } finally { window.setInterval=si; }
      let puts=0; const put=DB.put; DB.put=function(s){ if(s==='meta') puts++; return put.apply(DB, arguments); };
      const before=currentBook.readMs||0;
      try{ tick(); tick(); } finally { DB.put=put; }
      const counted=(currentBook.readMs||0)-before;
      cloudAdoptOpen(currentBook.id, Object.assign({}, await DB.get('meta', currentBook.id)), null);   // a sync arriving meanwhile
      const kept=(currentBook.readMs||0)-before;
      await saveProgress(currentBook); const stored=((await DB.get('meta', currentBook.id)).readMs||0)-before;
      startReadTimer();
      return { puts:puts, counted:counted, kept:kept, stored:stored }; }"""), {"puts": 0, "counted": 20000, "kept": 20000, "stored": 20000},
           "every ten seconds of reading rewrote the whole record, and woke device sync to check it")
    nctx.close()

    # 4e. Highlighting over a highlight. A plain highlight inside the new one is replaced, and kept
    #     as a deletion, as every deletion is, so no merge with a stored or synced copy brings it
    #     back. One that carries a note or a star stays.
    wctx = browser.new_context(bypass_csp=True); wp = wctx.new_page(); watch(wp, "widen")
    wp.goto(URL); wait(wp, "typeof DB!=='undefined' && typeof renderHome==='function'")
    wait(wp, "DB.count('meta').then(n=>window.__n=n), window.__n>=1"); settle(1.2)
    wp.set_input_files("#file-input", [ALPHA])
    wait(wp, "DB.all('meta').then(ms=>window.__a=ms.find(m=>m.title==='Alpha Testing Book')), !!window.__a")
    ev(wp, "()=>{ openBook(window.__a.id); }")
    wait(wp, "rendition && rendition.getContents().length && /quick brown fox/.test(rendition.getContents()[0].document.body.textContent)")
    settle(0.8)
    widen_want = ["lazy dog", "near the riverbank", "quick brown fox jumps", "riverbank", "the lazy dog near"]
    expect("highlighting over a highlight replaces a plain one for good, and keeps one that carries a note or a star",
           ev(wp, r"""async()=>{
      const c=rendition.getContents()[0], id=currentBook.id, t=a=>a.map(h=>h.text).sort();
      const mark=(q, note)=>{ const r=findQuoteRange(c,secTextMap(c),q); lastSelection={cfiRange:c.cfiFromRange(r),text:q,contents:c}; return createHighlight('yellow', note); };
      await mark('brown fox'); await mark('lazy dog', 'keep this'); await mark('riverbank');
      toggleFav(highlights.find(h=>h.text==='riverbank').id);
      for(let i=0;i<50;i++){ const r=await DB.get('highlights', id); if(r.items.some(h=>h.text==='riverbank' && h.fav)) break; await new Promise(z=>setTimeout(z,100)); }
      const before=JSON.parse(JSON.stringify((await DB.get('highlights', id)).items));   // what another device still holds
      await mark('quick brown fox jumps'); await mark('the lazy dog near'); await mark('near the riverbank');
      const stored=(await DB.get('highlights', id)).items, g=c.window.CSS.highlights.get('hl-yellow');
      return { onScreen:t(hlLive(highlights)), stored:t(hlLive(stored)), deleted:t(stored.filter(h=>h.deleted)),
               merged:[t(hlLive(mergeHighlights(before, stored))), t(hlLive(mergeHighlights(stored, before)))], painted:g ? g.size : 0 };
    }"""),
           {"onScreen": widen_want, "stored": widen_want, "deleted": ["brown fox"], "merged": [widen_want, widen_want], "painted": 5},
           "a plain highlight inside a new one was dropped without a tombstone, so the next save (since 1.0.72) or the next sync brought it back; one carrying a note was dropped with its note")
    wctx.close()

    # 4f. One merge. Seven paths carry a record into the library: the folder, a notes file, a
    #     hand-off, a cloud conflict copy, a restore, device sync and the tidy-up's fold. Each rule
    #     below is checked on every path, so a path that keeps its own copy of the merge is caught.
    mctx, mp_ = folder_page("one-merge")
    add_in_app(mp_, "alpha", "alpha.epub")
    mid = ev(mp_, ALPHA_ID)
    orig = ev(mp_, "async(id)=>JSON.parse(JSON.stringify(await DB.get('meta', id)))", mid)   # as the import made it: never opened, never merged
    ev(mp_, SYNC)
    ev(mp_, r"""()=>{
      window.__deliver=async(path, rec)=>{
        const now=Date.now(), id=rec.meta.id, n=Math.random().toString(36).slice(2,7);
        if(path==='folder'){ await B.put('.reader/'+id+'.json', JSON.stringify(rec)); await vaultPull(); }
        else if(path==='notes file'){ await B.put('notes/WR-notes-elsewhere-'+n+'.json', JSON.stringify({ app:'epub-reader', format:'wr-notes', version:1, device:'another-device', exportedAt:new Date().toISOString(), books:[rec] })); await vaultPull(); }
        else if(path==='hand-off'){ await B.put('handoff-'+n+'.json', JSON.stringify({ app:'backchat-handoff', exportedAt:new Date().toISOString(), books:[rec] })); await vaultPull(); }
        else if(path==='conflict copy'){ await B.put('.reader/'+id+' (conflicted copy '+n+').json', JSON.stringify(rec)); await vaultPull(); }
        else if(path==='restore'){ await restoreFromObject({ app:'epub-reader', version:2, books:[Object.assign({}, rec.meta)], highlights:[{ id:id, items:rec.highlights, updatedAt:rec.updatedAt }], tombstones:{ids:{},keys:{}} }); }
        else if(path==='device sync'){ await cloudApplyBundle({ app:'backchat-sync', v:1, device:'phone', name:'Phone', at:now, tombstones:{ids:{},keys:{},undo:{ids:{},keys:{}}}, books:[rec] }); }
        else if(path==='tidy-up'){ const dup=Object.assign({}, rec.meta, { id:'zz'+id }); await DB.put('meta', dup); await DB.put('highlights', { id:dup.id, items:rec.highlights, updatedAt:rec.updatedAt }); await reconcileLibrary(); }
        await B.quiet(300);
      };
      window.__rec=async(id)=>{ const m=await DB.get('meta', id), h=await DB.get('highlights', id); return JSON.parse(JSON.stringify({ meta:m, highlights:(h&&h.items)||[], updatedAt:(h&&h.updatedAt)||0 })); };
      window.__put=async(rec)=>{ await DB.put('meta', rec.meta); await DB.put('highlights', { id:rec.meta.id, items:rec.highlights, updatedAt:rec.updatedAt }); _vaultLastWrite={}; await vaultPushBook(rec.meta.id, false);
        for(const p of Object.keys(await B.ls('.reader'))) if(/conflict/i.test(p)) await B.rm(p); await B.quiet(200); };
      return true; }""")
    MERGE_PATHS = ("folder", "notes file", "hand-off", "conflict copy", "restore", "device sync", "tidy-up")
    def each_path(js, paths=MERGE_PATHS):   # the paths that break the rule, with what each did
        def held(r): return r is True or (isinstance(r, list) and not r) or (type(r) is int and r == 0)
        return [[p, r] for p in paths for r in [ev(mp_, js, [mid, p])] if not held(r)]

    expect("merging any record with itself changes nothing", ev(mp_, r"""()=>{
      const shapes=[
        { id:'s1', title:'Never Opened', author:'A', lastOpened:null, progress:0, lastCfi:null, readMs:0, tags:[], finished:false, addedAt:1700000000000 },
        { id:'s2', title:'An Old Record', author:'B', addedAt:1700000000000 },
        { id:'s3', title:'Read and Marked', author:'C', lastOpened:1700000500000, posAt:1700000500000, lastCfi:'epubcfi(/6/4!/4/2/1:0)', progress:0.25, readMs:60000, tags:['x','y'], tagsUpdated:1700000400000, updated:1700000300000, addedAt:1700000000000, scratch:'notes', fav:true },
        { id:'s4', title:'Tagged Once', author:'D', tagsUpdated:1700000400000 } ];
      const bad=shapes.filter(s=>cloudCanon(mergeMeta(JSON.parse(JSON.stringify(s)), JSON.parse(JSON.stringify(s))))!==cloudCanon(s)).map(s=>s.title);
      const items=[{ id:'h1', text:'a', created:1, updated:2 }, { id:'h2', text:'b', created:3, updated:4, deleted:true }, { id:'h3', text:'c', created:5 }];
      if(cloudCanon(mergeHighlights(JSON.parse(JSON.stringify(items)), JSON.parse(JSON.stringify(items))).sort(cloudById))!==cloudCanon(items)) bad.push('marks');
      return bad; }"""), [],
           "a book never opened came out with its last-opened time changed from none to 0, so the record looked changed and was written again")
    expect("a record that brings nothing new writes nothing, by every path", each_path(r"""async([id, path])=>{
      await __put({ meta:%s, highlights:((await DB.get('highlights', id))||{}).items||[], updatedAt:((await DB.get('highlights', id))||{}).updatedAt||0 });
      const rec=await __rec(id), p=DB.put, log=[];
      DB.put=function(s, v){ if((s==='meta'||s==='highlights') && v && v.id===id) log.push(s); return p.apply(DB, arguments); };
      try{ await __deliver(path, rec); } finally { DB.put=p; }
      return log.length; }""" % json.dumps(orig)), [],
           "the same record, arriving again, was written again: every connect rewrote each book never opened, and some paths wrote whatever arrived")
    expect("a record whose id names a different book here changes nothing, by every path", each_path(r"""async([id, path])=>{
      const before=await __rec(id), now=Date.now();
      const other={ meta:Object.assign({}, before.meta, { bookKey:'id:urn:another-book', title:'Another Book Entirely', author:'Someone Else', scratch:'margins of another book', updated:now+5000 }),
        highlights:[{ id:'other-'+path.replace(/\W+/g,'-'), text:'a mark in another book', color:'yellow', created:now, updated:now }], updatedAt:now };
      await __deliver(path, other);
      const after=await __rec(id), changed=[];
      if(after.meta.title!==before.meta.title) changed.push('title');
      if((after.meta.scratch||'')!==(before.meta.scratch||'')) changed.push('margins');
      if(after.highlights.some(h=>/^other-/.test(h.id))) changed.push('marks');
      await __put(before);
      return changed; }""", MERGE_PATHS[:-1]), [],
           "a hand-off or a restore carrying the same id for another book wrote that book's title, margins or marks over this one")
    expect("the newest version of each mark wins, and a mark deleted here stays deleted, by every path", each_path(r"""async([id, path])=>{
      const now=Date.now(), tag=path.replace(/\W+/g,'-'), h=await DB.get('highlights', id);
      const gone={ id:'gone-'+tag, text:'deleted here', color:'yellow', note:'', created:now-9000, updated:now-9000 };
      const kept={ id:'edit-'+tag, text:'edited here', color:'yellow', note:'older', created:now-9000, updated:now-9000 };
      const older=await __rec(id); older.highlights=older.highlights.concat([gone, kept]);   // the copy another device still holds
      h.items.push(Object.assign({}, gone, { deleted:true, updated:now-5000 }), Object.assign({}, kept, { note:'newer here', updated:now-5000 }));
      await DB.put('highlights', h);
      await __deliver(path, older);
      let a=(await DB.get('highlights', id)).items; const g=a.find(x=>x.id===gone.id), k=a.find(x=>x.id===kept.id);
      const newer=await __rec(id); newer.highlights=newer.highlights.map(x=>x.id===kept.id ? Object.assign({}, x, { note:'newer elsewhere', updated:now+1000 }) : x);
      await __deliver(path, newer);
      const k2=(await DB.get('highlights', id)).items.find(x=>x.id===kept.id);
      return (g && g.deleted && k && k.note==='newer here' && k2 && k2.note==='newer elsewhere') ? true : { deletedStays:!!(g && g.deleted), editHere:k && k.note, editElsewhere:k2 && k2.note }; }"""), [],
           "an older copy brought a deleted mark back, or undid an edit, or a newer edit from another device was lost")
    expect("a record of a book held here under another id joins that book, by every path", each_path(r"""async([id, path])=>{
      const now=Date.now(), tag=path.replace(/\W+/g,'-'), rec=await __rec(id);
      rec.meta=Object.assign({}, rec.meta, { id:'zy'+tag+'-'+id }); rec.highlights=[{ id:'twin-'+tag, text:'marked under another id', color:'yellow', created:now, updated:now }]; rec.updatedAt=now;
      await __deliver(path, rec);
      const key=bookKeyOf(rec.meta), all=(await DB.all('meta')).filter(m=>bookKeyOf(m)===key);
      const marks=all.length===1 && (((await DB.get('highlights', all[0].id))||{}).items||[]).some(h=>h.id==='twin-'+tag);
      return (all.length===1 && marks) ? true : { copies:all.length, marks:marks }; }"""), [],
           "the same book arriving under another browser's id became a second book")
    expect("every file that carries notes between devices carries the same record of a book", ev(mp_, r"""async(id)=>{
      const m=await DB.get('meta', id); m.updated=Date.now(); await DB.put('meta', m);           // touched since the last hand-off
      const h=await DB.get('highlights', id); delete h.updatedAt; await DB.put('highlights', h);   // a marks record from before Backchat kept a time of change
      const pick=b=>b.books.find(x=>x.meta.id===id), notes=pick(await buildNotesBundle()), hand=await buildHandoffBundle(0), sync=pick(await cloudBuildBundle());
      const same=[cloudCanon(notes)===cloudCanon(sync), cloudCanon(pick(hand))===cloudCanon(sync), hand.format];
      h.updatedAt=Date.now(); await DB.put('highlights', h); _vaultLastWrite={}; await vaultPushBook(id, false); await B.quiet(200);
      return same; }""", mid), [True, True, "wr-notes"],
           "each kind of file built its own copy of the record: the hand-off stamped a record that had no time of change with the moment it was made, and kept fields the others drop")
    expect("a hand-off file made today merges, and is cleared from the folder", ev(mp_, r"""async(id)=>{
      const b=await buildHandoffBundle(0), rec=b.books.find(x=>x.meta.id===id), now=Date.now();
      rec.highlights=rec.highlights.concat([{ id:'handed-new', text:'handed off', color:'yellow', created:now, updated:now }]);
      await B.put('handoff-made-today.json', JSON.stringify(b)); await vaultPull(); await B.quiet(300);
      return [(((await DB.get('highlights', id))||{}).items||[]).some(x=>x.id==='handed-new'), !('handoff-made-today.json' in (await B.ls()))]; }""", mid), [True, True],
           "the hand-off becomes a notes file; the computer still takes it from the top of the folder")
    expect("Check folder lists every book the sync message says has notes but no EPUB", ev(mp_, r"""async()=>{
      const now=Date.now(), ghost={ id:'ghost-nofile-1', title:'A Book Read Elsewhere', author:'Far Away', bookKey:'id:urn:elsewhere:1', addedAt:now, updated:now, tags:[] };
      const was=vault.connected; vault.connected=false;   // it arrived while the folder could not be written
      await cloudApplyBundle({ app:'backchat-sync', v:1, device:'phone', name:'Phone', at:now, tombstones:{ids:{},keys:{},undo:{ids:{},keys:{}}}, books:[{ meta:ghost, highlights:[{ id:'g1', text:'read elsewhere', color:'yellow', created:now, updated:now }], updatedAt:now }] });
      vault.connected=was;
      const counted=(await bcBooksWithoutFile(await vaultDirs())).map(m=>m.title);
      await folderCheck(); const report=document.querySelector('#folder-check-info').textContent, m=/notes but no EPUB[^:]*: ([^\n]*)/.exec(report);
      return [counted.indexOf(ghost.title)>=0, !!m && m[1].indexOf(ghost.title)>=0]; }"""), [True, True],
           "the message said Check folder lists them, and Check folder listed this one as a book the next sync would write, which no sync could give a file")
    ev(mp_, "async()=>{ for(const m of await DB.all('meta')) if(m.id==='ghost-nofile-1') await removeBookEverywhere(m); return true; }")
    expect("a book's backup brings the book back and leaves your settings alone", ev(mp_, r"""async(id)=>{
      const was=settings.fs||100; detailsBook=await DB.get('meta', id); detailsItems=hlLive(((await DB.get('highlights', id))||{}).items);
      detailsBackup(); await B.quiet(600);
      const name=Object.keys(await B.ls('backups')).filter(n=>/Alpha-Testing-Book-backup/.test(n)).sort().pop(), j=JSON.parse(await B.text(name));
      settings.fs=was+7; saveSettings();   // changed since the backup was made
      await restoreFromObject(j); const kept=settings.fs===was+7;
      settings.fs=was; saveSettings(); detailsBook=null;
      return [j.books.length===1 && !!j.books[0].data, kept]; }""", mid), [True, True],
           "a book's backup carried the whole app's settings, so restoring one book put back your type size, theme and voice as they were that day")
    expect("a mark the guide's new edition no longer has is deleted as every mark is, so another device's copy cannot bring it back", ev(mp_, r"""async()=>{
      const src=await fetchGuide(), m=await DB.get('meta', GUIDE_ID), now=Date.now(), phrase=(/[A-Z][a-z]+(?: [a-z,']+){6,12}/.exec(src.body.slice(1500))||[''])[0];
      const h=await DB.get('highlights', GUIDE_ID); h.items.push({ id:'guide-gone', text:phrase, color:'yellow', note:'', created:now, updated:now }); await DB.put('highlights', h);
      const older=JSON.parse(JSON.stringify(h.items));   // the copy another device still holds
      _guideSrc=Object.assign({}, src, { rev:(m.guideRev||0)+1, body:src.body.split(phrase).join('words this edition changed') });
      try{ await refreshGuideIfNewer(); } finally { _guideSrc=src; }
      const after=(await DB.get('highlights', GUIDE_ID)).items, g=after.find(x=>x.id==='guide-gone');
      return [phrase.length>20, !!(g && g.deleted), hlLive(mergeHighlights(older, after)).some(x=>x.id==='guide-gone')]; }"""), [True, True, False],
           "a new edition of the guide dropped the marks whose words it no longer has without a tombstone, so any device still holding one brought it back")
    ev(mp_, SYNC); add_in_app(mp_, "beta", "beta.epub"); add_in_app(mp_, "gamma", "gamma.epub")   # two books added here: the folder holds their records as the import made them
    ev(mp_, "async()=>{ await vaultWriteIndex(await vaultDirs()); await B.quiet(200); return true; }")   # and the library's index lists them
    expect("connecting a folder that already holds this library's records rewrites none of them", ev(mp_, r"""async()=>{
      await B.quiet(300); B.mark(); let n=0; const p=DB.put; DB.put=function(s){ if(s==='meta') n++; return p.apply(DB, arguments); };
      try{ vault.handle=null; vault.connected=false; vault.handle=B.root; vault.connected=true; _vaultLastWrite={}; await vaultPull(); await vaultPushAll(); await B.quiet(600); } finally { DB.put=p; }
      return [n, B.log('w')]; }"""), [0, []],
           "a record merged with itself came out different (last opened: none became 0), so connecting rewrote every book never opened, here and in the folder")
    ev(mp_, "(id)=>{ openBook(id); return true; }", mid)
    wait(mp_, "rendition && rendition.getContents().length && /quick brown fox/.test(rendition.getContents()[0].document.body.textContent)")
    settle(0.8)
    expect("margins that arrive while their book is open survive the reader's next save, by every path", each_path(r"""async([id, path])=>{
      const text='Margins that arrived by '+path+'.', rec=await __rec(id);
      rec.meta=Object.assign({}, rec.meta, { scratch:text, updated:Date.now()+1000 });
      await __deliver(path, rec);
      await saveProgress(currentBook);   // the reader's next save: a page turn writes its copy of the record
      return ((await DB.get('meta', id)).scratch||'')===text; }"""), [],
           "the open book kept its own copy of the record, so the reader's next page turn wrote the old margins back")
    mctx.close()

    # 4g. One EPUB reader. Every way a book file comes in (Add EPUB, books/ in the folder, Refresh,
    #     the folder's verdict, the tidy-up's key backfill, the cover from the book) reads it with one
    #     function, by one set of rules, as few times as it can.
    import struct, zlib
    def png_bytes(rgb):
        raw = b"".join(b"\x00" + bytes(rgb) * 24 for _ in range(36))
        def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
        return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 24, 36, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    def raw_epub(name, meta, manifest="", files=None, nav=True):
        path = os.path.join(TMP, name)
        z = zipfile.ZipFile(path, "w")
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        z.writestr("OEBPS/content.opf", '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">' + meta +
                   '</metadata><manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/><item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>' + manifest + '</manifest><spine><itemref idref="ch1"/></spine></package>')
        if nav: z.writestr("OEBPS/nav.xhtml", '<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><head><title>Nav</title></head><body><nav epub:type="toc"><ol><li><a href="ch1.xhtml">One</a></li></ol></nav></body></html>')
        z.writestr("OEBPS/ch1.xhtml", '<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml"><head><title>One</title></head><body><p>A chapter with a few words in it.</p></body></html>')
        for pth, data in (files or {}).items(): z.writestr(pth, data)
        z.close()
        return base64.b64encode(open(path, "rb").read()).decode()
    TRICKY = raw_epub("tricky.epub", '<dc:identifier id="uid">\n   urn:uuid:tricky-1  \n</dc:identifier><dc:title>  Tricky   Title </dc:title><dc:creator>Ann Author</dc:creator><dc:date>2021-03-04</dc:date><dc:publisher>Small Press</dc:publisher>')
    NAMED = raw_epub("named-cover.epub", '<dc:identifier id="uid">urn:uuid:named-cover</dc:identifier><dc:title>Named Cover</dc:title><dc:creator>Cy Painter</dc:creator>',
                     '<item id="front" href="images/front.png" media-type="image/png" properties="cover-image"/><item id="old" href="images/cover-old.png" media-type="image/png"/>',
                     {"OEBPS/images/front.png": png_bytes((30, 60, 200)), "OEBPS/images/cover-old.png": png_bytes((200, 30, 30))})
    PLAIN = raw_epub("plain.epub", '<dc:identifier id="uid">urn:uuid:plain-1</dc:identifier><dc:title>No Pictures</dc:title><dc:creator>Di Words</dc:creator>')
    NEVER = raw_epub("never-opens.epub", '<dc:identifier id="uid">urn:uuid:never-opens</dc:identifier><dc:title>Never Opens</dc:title><dc:creator>Ed Missing</dc:creator>', nav=False)
    COUNT = r"""async([b64, name, how, key])=>{
      const u8=Uint8Array.from(atob(b64), c=>c.charCodeAt(0)); let zips=0, opens=0; const lz=JSZip.loadAsync, ep=window.ePub, ix=indexBook;
      JSZip.loadAsync=function(){ zips++; return lz.apply(JSZip, arguments); }; window.ePub=function(){ opens++; return ep.apply(this, arguments); };
      indexBook=function(){ return Promise.resolve(); };   // reading the pages for search is the indexer's own read
      try{ if(how==='app') await importFiles([new File([u8], name)]); else { await B.put('books/'+name, u8); await vaultPull(); await B.quiet(300); } }
      finally { JSZip.loadAsync=lz; window.ePub=ep; indexBook=ix; }
      return [zips, opens, !!(await DB.all('meta')).find(m=>bookKeyOf(m)===key)]; }"""
    rctx, rp = folder_page("one-reader")
    expect("adding a book in the app reads its file once", ev(rp, COUNT, [NAMED, "named-cover.epub", "app", "id:urn:uuid:named-cover"]), [1, 0, True],
           "the file was unzipped once to check it, again by epub.js for its metadata and cover, and again for its video source")
    rctx.close(); rctx, rp = folder_page("one-reader-folder")
    expect("a book dropped into books/ is read twice on its way in: once to know what it is, once to add it", ev(rp, COUNT, [NAMED, "dropped.epub", "folder", "id:urn:uuid:named-cover"]), [2, 0, True],
           "it was unzipped six times on its way in, two of them by epub.js")
    expect("every way a book file comes in names it the same: the same key, title and author", ev(rp, r"""async(b64)=>{
      const u8=Uint8Array.from(atob(b64), c=>c.charCodeAt(0)); await B.put('books/tricky.epub', u8); await vaultPull(); await B.quiet(300);   // by the folder
      const m=(await DB.all('meta')).find(x=>bookKeyOf(x)==='id:urn:uuid:tricky-1');
      const v=await bcInspectEpub(u8.slice().buffer, { name:'tricky' }), k=await computeBookKey({ title:'Stored', author:'Stored' }, u8.slice().buffer);
      await DB.del('meta', m.id); await DB.del('blob', m.id); await importFiles([new File([u8], 'tricky.epub')]);
      const a=(await DB.all('meta')).find(x=>bookKeyOf(x)==='id:urn:uuid:tricky-1');
      return [m.bookKey, a.bookKey, v.key, k, m.title===a.title && a.title===v.title, m.author===a.author, m.year, m.publisher]; }""", TRICKY),
           ["id:urn:uuid:tricky-1"] * 4 + [True, True, "2021", "Small Press"], "each way in kept its own reader, and their rules could drift apart")
    rctx.close(); rctx, rp = folder_page("one-reader-refresh")
    add_in_app(rp, "alpha", "alpha.epub")
    expect("Refresh EPUB from folder refuses a damaged file and keeps the book's own copy", ev(rp, r"""async()=>{
      const m=(await DB.all('meta')).find(x=>x.title==='Alpha Testing Book'), was=(await DB.get('blob', m.id)).data.byteLength;
      await B.put('books/'+vaultPathName(m)+'.epub', new Uint8Array([80,75,3,4,1,2,3,4,5,6,7,8])); __toasts.length=0;
      await refreshBookFromFolder(m); await new Promise(r=>setTimeout(r,800));
      return [(await DB.get('blob', m.id)).data.byteLength===was, __toasts.some(t=>/Could not use/.test(t))]; }"""), [True, True],
           "a half-downloaded or damaged file in the folder took the place of the book's good copy, and the book no longer opened")
    rctx.close(); rctx, rp = folder_page("one-reader-covers")
    expect("a file the reader could never open is refused at once, not after a minute", ev(rp, r"""async(b64)=>{
      const u8=Uint8Array.from(atob(b64), c=>c.charCodeAt(0)), t0=Date.now(); __toasts.length=0;
      await importFiles([new File([u8], 'never-opens.epub')]);
      return [Date.now()-t0<5000, !(await DB.all('meta')).find(x=>x.title==='Never Opens'), __toasts.some(t=>/never-opens.epub/.test(t) && /could not be read/.test(t))]; }""", NEVER), [True, True, True],
           "a book naming a table of contents it does not hold kept epub.js waiting a minute before it was refused, and a sync with it in books/ waited too")
    expect("the cover from the book is the cover the book names, at import, on its page and on the shelf", ev(rp, r"""async(b64)=>{
      const u8=Uint8Array.from(atob(b64), c=>c.charCodeAt(0)); await importFiles([new File([u8], 'named-cover.epub')]);
      const m=(await DB.all('meta')).find(x=>x.title==='Named Cover'), atImport=await getCoverSrc(m.id);
      detailsBook=m; metaDraftCover=null; document.getElementById('meta-frombook').onclick(); for(let i=0;i<50 && !metaDraftCover;i++) await new Promise(r=>setTimeout(r,100));
      const onPage=metaDraftCover; detailsBook=null;
      await delCover(m.id); const ph=document.createElement('div'); ph.className='ph'; ph.setAttribute('data-cover', m.id); document.body.appendChild(ph);
      hydrateCovers(document.body); for(let i=0;i<50 && !(await getCoverSrc(m.id));i++) await new Promise(r=>setTimeout(r,100));
      const onShelf=await getCoverSrc(m.id); ph.remove();
      return [!!atImport, onPage===atImport, onShelf===atImport]; }""", NAMED), [True, True, True],
           "on its page and on the shelf the cover came from the first image with cover in its name, not from the cover the book names, so the two could differ")
    expect("a book with no picture for a cover is not read again at every paint", ev(rp, r"""async(b64)=>{
      const u8=Uint8Array.from(atob(b64), c=>c.charCodeAt(0)); await importFiles([new File([u8], 'plain.epub')]);
      const m=(await DB.all('meta')).find(x=>x.title==='No Pictures'), paint=async()=>{ const ph=document.createElement('div'); ph.className='ph'; ph.setAttribute('data-cover', m.id); document.body.appendChild(ph); hydrateCovers(document.body); await new Promise(r=>setTimeout(r,500)); ph.remove(); };
      await paint();   // the first paint looks for a cover in the file
      let zips=0; const lz=JSZip.loadAsync; JSZip.loadAsync=function(){ zips++; return lz.apply(JSZip, arguments); };
      try{ await paint(); await paint(); await paint(); } finally { JSZip.loadAsync=lz; }
      return [!(await getCoverSrc(m.id)), zips]; }""", PLAIN), [True, 0],
           "each paint of Home or the Library unzipped every book without a cover again, looking for one that is not there")
    rctx.close()

    # 4h. One identity. A book is known by its key and by every identifier its files have carried:
    #     an ISBN however it is written, ten digits or thirteen; an ASIN; a UUID; several, in any
    #     order. One rule decides, on every path, whether a file or a record is a book already here.
    #     Title and author alone never make two files one book: you are asked, or the file is held.
    def isbn13(p12): return p12 + str((10 - sum((1 if i % 2 == 0 else 3) * int(c) for i, c in enumerate(p12)) % 10) % 10)
    def isbn10(p9):
        d = (11 - sum((10 - i) * int(c) for i, c in enumerate(p9)) % 11) % 11
        return p9 + ("X" if d == 10 else str(d))
    P9 = "190276435"; I10, I13 = isbn10(P9), isbn13("978" + P9)
    def hyph(i): return "%s-%s-%s-%s-%s" % (i[:3], i[3], i[4:9], i[9:12], i[12])
    ASIN, CAL, REB = "B0HRBRLT42", "5f0c2a9e-7b1d-4c3e-9a8f-2d6b4e1c0a77", "3c9e1f5a-2b7d-5e4f-8a1c-6d0b9e2f4a13"
    OPFNS = ' xmlns:opf="http://www.idpf.org/2007/opf"'
    def ident(text, scheme="", uid=False): return '<dc:identifier%s%s%s>%s</dc:identifier>' % (' id="uid"' if uid else "", OPFNS if scheme else "", (' opf:scheme="%s"' % scheme) if scheme else "", text)
    def book(name, title, author, ids):
        return raw_epub(name, "".join(ids) + "<dc:title>%s</dc:title>" % title + ("<dc:creator>%s</dc:creator>" % author if author else ""))
    B64.update({
      "h-store": book("h-store.epub", "Harbour Lights", "Ada Lantern", [ident("urn:isbn:" + hyph(I13), uid=True)]),
      "h-isbn10": book("h-isbn10.epub", "Harbour Lights", "Ada Lantern", [ident("ISBN " + I10[:1] + "-" + I10[1:6] + "-" + I10[6:9] + "-" + I10[9:], uid=True)]),
      "h-calibre": book("h-calibre.epub", "Harbour Lights: A Novel", "Ada Lantern", [ident(CAL, "uuid", uid=True), ident("17", "calibre"), ident(I13, "ISBN"), ident(ASIN, "AMAZON")]),
      "h-kindle": book("h-kindle.epub", "Harbour Lights", "Ada Lantern", [ident(ASIN, "MOBI-ASIN", uid=True)]),
      "h-rebuilt": book("h-rebuilt.epub", "Harbour Lights", "", [ident("urn:uuid:" + REB, uid=True)]),
      "h-other": book("h-other.epub", "Harbour Lights", "Ada Lantern", [ident(isbn13("978190276451"), "ISBN", uid=True)]),
      "box": book("box.epub", "Complete Collection", "Various", [ident("urn:uuid:aa11bb22-cc33-4d44-8e55-ff6677889900", uid=True), ident(I13, "ISBN")]),
      "q-store": book("q-store.epub", "Quiet Rooms", "Bo Stillwell", [ident(isbn13("978190276443"), uid=True)]),
      "q-calibre": book("q-calibre.epub", "Quiet Rooms", "Bo Stillwell", [ident("0b1c2d3e-4f50-4a6b-8c7d-9e0f1a2b3c4d", "uuid", uid=True), ident(isbn13("978190276443"), "ISBN")]),
    })
    SIZE = {k: len(base64.b64decode(B64[k])) for k in ("h-store", "h-kindle", "h-rebuilt")}
    ANSWER = "(a)=>{ window.__answers=a.slice(); window.__asked=[]; window.confirm=function(q){ __asked.push(String(q)); return !!__answers.shift(); }; return true; }"
    HL = "async()=>(await DB.all('meta')).filter(m=>m.title && /^Harbour Lights/.test(m.title))"
    COUNT_H = "async()=>(await DB.all('meta')).filter(m=>m.title && /^Harbour Lights/.test(m.title)).length"
    ictx, ip = folder_page("identity-add")
    ev(ip, "()=>{ vault.handle=null; vault.connected=false; return true; }")   # added in the app, no folder
    add_in_app(ip, "h-store", "harbour.epub")
    ev(ip, ANSWER, [True]); ev(ip, "()=>{ __toasts.length=0; return true; }"); add_in_app(ip, "h-isbn10", "harbour-10.epub")
    expect("a book is known by its ISBN however a file writes it, ten digits or thirteen", [ev(ip, COUNT_H), any("Updated the book file" in t for t in ev(ip, "()=>__toasts")), len(ev(ip, "()=>__asked"))], [1, True, 1],
           "a copy whose ISBN was written as ten digits, or without the urn:isbn: prefix, came in as a second book, its marks apart from the first")
    ev(ip, ANSWER, [True, True]); add_in_app(ip, "h-calibre", "harbour-calibre.epub"); add_in_app(ip, "h-kindle", "harbour-kindle.epub")
    expect("a book with an ISBN and an ASIN is known by both, so a copy carrying either one is the same book", ev(ip, r"""async(sz)=>{ const ms=(await DB.all('meta')).filter(m=>/^Harbour Lights/.test(m.title||'')), m=ms[0];
        return [ms.length, (m.ids||[]).filter(t=>/^(asin|uuid):/.test(t)).length, ((await DB.get('blob', m.id))||{data:{byteLength:0}}).data.byteLength===sz, __asked.length===2 && /same ASIN/.test(__asked[1])]; }""", SIZE["h-kindle"]),
           [1, 2, True, True], "Backchat read only a file's first identifier, so a Kindle copy carrying just the ASIN was a stranger to the book a file with ISBN and ASIN had made")
    ictx.close()

    ictx, ip = folder_page("identity-lookalike")
    ev(ip, "()=>{ vault.handle=null; vault.connected=false; return true; }")
    add_in_app(ip, "h-store", "harbour.epub"); mark_book(ip, "Harbour Lights", 2, "keep")
    ev(ip, ANSWER, [False, False]); ev(ip, "()=>{ __toasts.length=0; return true; }"); add_in_app(ip, "h-rebuilt", "Harbour-Lights.epub")
    first = [ev(ip, COUNT_H), any("Did not add" in t for t in ev(ip, "()=>__toasts")), len(ev(ip, "()=>__asked"))]
    ev(ip, ANSWER, [True]); add_in_app(ip, "h-rebuilt", "Harbour-Lights.epub")
    expect("a file with only the title of a book here is never taken for it unasked; asked, it becomes the book's file and the marks stay", [first, ev(ip, r"""async(a)=>{ const [sz, reb]=a, ms=(await DB.all('meta')).filter(m=>/^Harbour Lights/.test(m.title||'')), m=ms[0];
        return [ms.length, hlLive(((await DB.get('highlights', m.id))||{}).items||[]).length, (await DB.get('blob', m.id)).data.byteLength===sz, (m.ids||[]).indexOf('uuid:'+reb)>=0]; }""", [SIZE["h-rebuilt"], REB])],
           [[1, True, 2], [1, 2, True, True]], "a rebuilt copy with no identifier in common became a second book with none of the marks, or, for a book added before 1.0.51, silently replaced the book's file")
    ev(ip, ANSWER, [False, True]); add_in_app(ip, "h-other", "harbour-other.epub")
    TWO = "async(k)=>{ const ms=await DB.all('meta'), a=ms.find(m=>m.bookKey===k[0]), b=ms.find(m=>m.bookKey===k[1]); return !!a && !!b && a.id!==b.id; }"
    keys2 = ["id:urn:isbn:" + hyph(I13), "id:" + isbn13("978190276451")]
    expect("a book with the same title and author but another ISBN can be added as a book of its own, and stays one", [ev(ip, TWO, keys2), ev(ip, "async()=>{ await reconcileLibrary(); return true; }") and ev(ip, TWO, keys2)], [True, True],
           "two editions with different ISBNs are two books when you say so")
    ev(ip, ANSWER, []); add_in_app(ip, "box", "box.epub")
    expect("an ISBN shared with a book whose title has nothing in common with it does not make them one book", [ev(ip, "async()=>(await DB.all('meta')).filter(m=>m.title==='Complete Collection').length"), len(ev(ip, "()=>__asked"))], [1, 0],
           "a boxed set carrying one volume's ISBN would have taken that volume's place")
    ictx.close()

    ictx, ip = folder_page("identity-folder")
    drop(ip, "harbour.epub", "h-store"); ev(ip, SYNC); mark_book(ip, "Harbour Lights", 2, "f")
    drop(ip, "Harbour (calibre).epub", "h-calibre"); ev(ip, "()=>{ __toasts.length=0; return true; }"); ev(ip, SYNC)
    rep_ = ev(ip, "async()=>{ await folderCheck(); return document.querySelector('#folder-check-info').textContent; }")
    expect("the folder knows a book by any identifier its file carries: a copy under another first identifier is kept as another copy, not added", [ev(ip, COUNT_H), "books/Harbour (calibre).epub" in ev(ip, "()=>B.ls('books')"), ("other cop" in rep_ and "Harbour (calibre).epub" in rep_) if isinstance(rep_, str) else rep_],
           [1, True, True], "a Calibre copy, whose first identifier is Calibre's own, came in as a second book")
    add_in_app(ip, "q-store", "quiet.epub"); ev(ip, SYNC); delete_book(ip, "Quiet Rooms")
    drop(ip, "Quiet Rooms (calibre).epub", "q-calibre"); ev(ip, "()=>{ __toasts.length=0; return true; }"); ev(ip, SYNC)
    expect("a deleted book stays deleted whichever identifier a copy of it carries first", [ev(ip, "async()=>!!(await DB.all('meta')).find(x=>x.title==='Quiet Rooms')"), any("you deleted" in t for t in ev(ip, "()=>__toasts"))], [False, True],
           "a copy of a deleted book with another first identifier brought it back")
    ictx.close()

    ictx, ip = folder_page("identity-held")
    drop(ip, "harbour.epub", "h-store"); ev(ip, SYNC); mark_book(ip, "Harbour Lights", 2, "f")
    drop(ip, "Harbour-Lights.epub", "h-rebuilt"); ev(ip, "()=>{ __toasts.length=0; return true; }"); ev(ip, SYNC)
    rep_ = ev(ip, "async()=>{ await folderCheck(); return document.querySelector('#folder-check-info').textContent; }")
    held = [ev(ip, COUNT_H), any("has the same title" in t and "not added" in t for t in ev(ip, "()=>__toasts")), ("no identifier in common" in rep_ and "Harbour-Lights.epub" in rep_) if isinstance(rep_, str) else rep_]
    ev(ip, ANSWER, [False]); kept = ev(ip, r"""async(sz)=>{ const m=(await DB.all('meta')).find(x=>x.title==='Harbour Lights'); await refreshBookFromFolder(m); await B.quiet(); return [(await DB.get('blob', m.id)).data.byteLength===sz, __asked.length]; }""", SIZE["h-store"])
    ev(ip, ANSWER, [True])
    expect("a look-alike in books/ is held and named, and Refresh reads from it only when you say so", [held, kept, ev(ip, r"""async(sz)=>{ const m=(await DB.all('meta')).find(x=>x.title==='Harbour Lights'); await refreshBookFromFolder(m); await B.quiet();
        return [(await DB.get('blob', m.id)).data.byteLength===sz, !(await B.ls('books'))['books/Harbour-Lights.epub'], hlLive((await DB.get('highlights', m.id)).items).length]; }""", SIZE["h-rebuilt"])],
           [[1, True, True], [True, 1], [True, True, 2]], "a rebuilt copy with the book's title but a new identifier came in as a second book, or a refresh took it unasked")
    ictx.close()

    ictx, ip = folder_page("identity-learn")
    drop(ip, "harbour-calibre.epub", "h-calibre"); ev(ip, SYNC)
    ev(ip, "async()=>{ const m=(await DB.all('meta')).find(x=>/^Harbour Lights/.test(x.title||'')); delete m.ids; await DB.put('meta', m); await DB.del('app','idsread'); return true; }")   # a book added before this build
    ev(ip, SYNC)
    learned = ev(ip, "async()=>((await DB.all('meta')).find(x=>/^Harbour Lights/.test(x.title||''))||{}).ids||[]")
    reads = ev(ip, "async()=>{ let n=0; const f=bcInspectEpub; window.bcInspectEpub=function(){ n++; return f.apply(this, arguments); }; try{ await vaultPull(); await B.quiet(300); } finally { window.bcInspectEpub=f; } return n; }")
    drop(ip, "harbour-kindle.epub", "h-kindle"); ev(ip, SYNC)
    expect("a book added before this build learns its file's identifiers once, and a copy carrying any of them is the same book", [("asin:" + ASIN) in learned, reads, ev(ip, COUNT_H)], [True, 0, 1],
           "only the key's identifier was known, so a copy carrying the book's ASIN was a stranger to it; or every sync read every book's file again")
    ictx.close()

    actx, ap_ = folder_page("identity-browser-a"); bctx, bp_ = folder_page("identity-browser-b")
    drop(ap_, "harbour.epub", "h-store"); ev(ap_, SYNC); mark_book(ap_, "Harbour Lights", 2, "a")
    ev(bp_, "()=>{ vault.handle=null; vault.connected=false; return true; }"); add_in_app(bp_, "h-calibre", "harbour-calibre.epub"); mark_book(bp_, "Harbour Lights: A Novel", 1, "b")
    ev(bp_, "()=>{ vault.handle=B.root; vault.connected=true; return true; }")
    hand(ap_, bp_); ev(bp_, SYNC)
    quiet = []
    for r in range(2):
        hand(bp_, ap_); w = ev(ap_, SYNC); quiet.append(w[1] if isinstance(w, list) else w)
        hand(ap_, bp_); w = ev(bp_, SYNC); quiet.append(w[1] if isinstance(w, list) else w)
    SEEN = "async()=>{ const ms=(await DB.all('meta')).filter(m=>/^Harbour Lights/.test(m.title||'')); return [ms.length, ms[0] && ms[0].id, ms[0] ? hlLive(((await DB.get('highlights', ms[0].id))||{}).items||[]).length : 0]; }"
    sa, sb = ev(ap_, SEEN), ev(bp_, SEEN)
    expect("two browsers that each added a different copy of one book settle on one record with every mark", [sa[0], sb[0], sa[1] == sb[1], sa[2], sb[2], quiet[1:], ev(bp_, "async(c)=>(bcFindBook(await DB.all('meta'), 'id:'+c)||{}).title||''", CAL)],
           [1, 1, True, 3, 3, [0, 0, 0], "Harbour Lights"], "each kept its own record of the book under its own key, so the marks made on one never reached the other")
    actx.close(); bctx.close()

    # 4i. One database, one margins editor, one clock for the video. Every write reaches the same
    #     hooks; the library snapshot shows only what was saved, in every tab; the margins are
    #     saved alone, from the reader's drawer and from the book's page; the chapter follows the
    #     sound on the player's own tick, and nothing polls while no video plays.
    dctx = browser.new_context(bypass_csp=True); dp = dctx.new_page(); watch(dp, "one-db")
    dp.goto(URL); wait(dp, "typeof DB!=='undefined' && typeof renderHome==='function'"); settle(1.2)
    expect("every write reaches device sync through one list of hooks, a one-step update included", ev(dp, r"""async()=>{
      let n=0; const f=window.cloudScheduleCheck; window.cloudScheduleCheck=function(){ n++; };
      const out=[], step=async(fn)=>{ const a=n; await fn(); await new Promise(r=>setTimeout(r,30)); out.push(n-a); };
      const tomb=(await DB.get('app', TOMB_KEY)) || { key:TOMB_KEY, val:{ ids:{}, keys:{} } };
      try{
        await step(()=>DB.put('meta', { id:'hook1', title:'Hook', bookKey:'id:hook1', tags:[] }));
        await step(()=>DB.put('highlights', { id:'hook1', items:[], updatedAt:1 }));
        await step(()=>DB.put('app', tomb));
        await step(()=>DB.put('app', { key:'hook-other', val:1 }));
        await step(()=>DB.update('meta', 'hook1', r=>{ r.title='Hooked'; return r; }));
        await step(()=>DB.del('meta', 'hook1'));
      } finally { window.cloudScheduleCheck=f; }
      return out; }"""), [1, 1, 1, 0, 1, 1], "device sync wrapped the database from inside its own code, a second wrapper at the end of the page wrapped that, and a write made any other way reached neither")
    expect("the library snapshot shows what was saved, never a change still in memory", ev(dp, r"""async()=>{
      const m={ id:'snap1', title:'Saved title', bookKey:'id:snap1', tags:[] }; await DB.put('meta', m); await DB.snapshot('meta');
      m.title='Changed in memory, not saved';
      const a=(await DB.snapshot('meta')).find(x=>x.id==='snap1').title;
      await DB.put('meta', m); const b=(await DB.snapshot('meta')).find(x=>x.id==='snap1').title;
      await DB.del('meta', 'snap1'); const c=!(await DB.snapshot('meta')).find(x=>x.id==='snap1');
      return [a, b, c]; }"""), ["Saved title", "Changed in memory, not saved", True],
           "the cache held the very objects callers saved, so a change made after a save showed in search, links and exports as if it were saved")
    dp2 = dctx.new_page(); watch(dp2, "one-db-tab-2"); dp2.goto(URL); wait(dp2, "typeof DB!=='undefined' && typeof renderHome==='function'"); settle(1.0)
    ev(dp, "async()=>{ await DB.snapshot('meta'); return true; }")
    ev(dp2, "async()=>{ await DB.put('meta', { id:'tab2', title:'Written in another tab', bookKey:'id:tab2', tags:[] }); return true; }"); settle(0.5)
    expect("a book written in another tab reaches this tab's library snapshot", ev(dp, "async()=>!!(await DB.snapshot('meta')).find(x=>x.id==='tab2')"), True,
           "the cache was filled once and never heard of another tab's writes, so search there missed new books until a reload")
    dp2.close()
    expect("a write the disk refuses is said at once", ev(dp, r"""async()=>{
      const op=IDBObjectStore.prototype.put; IDBObjectStore.prototype.put=function(){ throw new DOMException('The disk is full', 'QuotaExceededError'); };
      let failed=false; try{ await DB.put('meta', { id:'full1', title:'x' }); }catch(e){ failed=true; } finally { IDBObjectStore.prototype.put=op; }
      const b=document.getElementById('bc-storage-warn'), t=b ? b.textContent : ''; if(b) b.remove();
      return [failed, /Storage is full/.test(t)]; }"""), [True, True], "a full disk aborted the save without a word")
    dctx.close()

    mctx = browser.new_context(bypass_csp=True); mp = mctx.new_page(); watch(mp, "one-margins")
    mp.goto(URL); wait(mp, "typeof DB!=='undefined' && typeof renderHome==='function'"); settle(1.2)
    mp.set_input_files("#file-input", [ALPHA])
    wait(mp, "DB.all('meta').then(ms=>window.__a=ms.find(m=>m.title==='Alpha Testing Book')), !!window.__a")
    mp.evaluate("()=>{ openBook(window.__a.id); }")
    wait(mp, "rendition && rendition.getContents().length>0"); settle(1.0)
    BEHIND = "async(v)=>{ const r=await DB.get('meta', currentBook.id); Object.assign(r, v); await DB.put('meta', r); return true; }"   # another device's sync, say, landing behind the reader's back
    ev(mp, BEHIND, {"rating": 5, "summary": "Written elsewhere"})
    expect("the reader's margins save the margins and nothing else into the book's record", ev(mp, r"""async()=>{
      openScratch(); toggleScratchEdit(); const ta=document.querySelector('#scratch-edit-area'); ta.value='Typed in the drawer.'; ta.dispatchEvent(new Event('input'));
      await new Promise(r=>setTimeout(r,1300)); toggleScratchEdit(); closePanels(); await new Promise(r=>setTimeout(r,300));
      const m=await DB.get('meta', currentBook.id); return [m.scratch, m.rating, m.summary]; }"""), ["Typed in the drawer.", 5, "Written elsewhere"],
           "a margins save wrote the reader's whole copy of the record, so what had reached the stored record since the book opened was written over")
    ev(mp, BEHIND, {"rating": 4})
    expect("the book's page saves the margins and nothing else into the book's record", ev(mp, r"""async()=>{
      await openDetails(currentBook.id); await new Promise(r=>setTimeout(r,300));
      detailsNotesEdit(); document.querySelector('#det-notes-area').value='Written on the book page.'; detailsNotesSave(); await new Promise(r=>setTimeout(r,500));
      const m=await DB.get('meta', currentBook.id); return [m.scratch, m.rating]; }"""), ["Written on the book page.", 4],
           "the book page's save wrote its whole copy of the record over what had reached it since")
    expect("location links in the reader's margins carry their book's title, as on the book's page", ev(mp, r"""async()=>{
      const other=(await DB.all('meta')).find(m=>m.id!==currentBook.id && m.title);
      appendToMargins(bcMakeToken({ bookKey:bookKeyOf(other), kind:'book', highlightId:'', cfi:'', anchorId:'' })+'\n');
      openScratch(); await new Promise(r=>setTimeout(r,500));
      const t=document.querySelector('#scratch-view .bc-ref-title'); return t ? t.textContent===' ('+other.title+')' : 'no title'; }"""), True,
           "the drawer drew the margins with its own renderer, which never named the book a link points to")
    mctx.close()

    # The video's clock. A two-chapter transcript book: the first chapter's part of the video ends at
    # 30 s, where the second begins. YouTube is stubbed to report it is playing at 29.4 s.
    def transcript_two(path, vid):
        z = zipfile.ZipFile(path, "w")
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        for n, (t0, nxt) in enumerate(((0, "30"), (30, ""))):
            rows = "".join('<div class="transcript-entry"><button class="ts timestamp" type="button" data-t="%d">0:%02d</button><p><span class="c" data-t="%d">Line at second %d.</span></p></div>' % (t, t, t, t) for t in range(t0, t0 + 30, 5))
            z.writestr("OEBPS/ch%d.xhtml" % (n + 1), '<?xml version="1.0" encoding="utf-8"?><!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml"><head><title>Part %d</title></head><body><div id="backchat-media" data-provider="youtube" data-id="%s" data-duration="60" data-next="%s" hidden="hidden"></div><h1 class="ch" data-t="%d">Part %d</h1>%s</body></html>' % (n + 1, vid, nxt, t0, n + 1, rows))
        z.writestr("OEBPS/nav.xhtml", '<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><head><title>Nav</title></head><body><nav epub:type="toc"><ol><li><a href="ch1.xhtml">Part 1</a></li><li><a href="ch2.xhtml">Part 2</a></li></ol></nav></body></html>')
        z.writestr("OEBPS/content.opf", '<?xml version="1.0" encoding="utf-8"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="bookid">urn:uuid:video-%s</dc:identifier><dc:title>Two Parts</dc:title><dc:creator>Speaker</dc:creator><dc:language>en</dc:language><meta property="backchat:media">youtube:%s</meta></metadata><manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/><item id="c1" href="ch1.xhtml" media-type="application/xhtml+xml"/><item id="c2" href="ch2.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="c1"/><itemref idref="c2"/></spine></package>' % (vid, vid))
        z.close()
    TWOPART = os.path.join(TMP, "two-parts.epub"); transcript_two(TWOPART, "followvid01")
    pctx = browser.new_context(bypass_csp=True)
    pctx.add_init_script("(()=>{ const si=window.setInterval; window.__every=[]; window.setInterval=function(fn, ms){ window.__every.push(ms); return si.apply(this, arguments); }; })()")
    pctx.route(re.compile(r"https://www\.youtube\.com/embed/.*"), lambda route: route.fulfill(status=200, content_type="text/html", body=(
        "<!doctype html><title>player</title><script>var say=function(m){parent.postMessage(JSON.stringify(m),'*');};"
        "say({event:'onReady'});setTimeout(function(){say({event:'infoDelivery',info:{playerState:1,currentTime:29.4,duration:60}});},400);</script>")))
    pp = pctx.new_page(); watch(pp, "player-clock")
    pp.goto(URL); wait(pp, "typeof DB!=='undefined' && typeof renderHome==='function'"); settle(1.5)
    expect("nothing polls the video player while no video plays", ev(pp, "()=>window.__every.filter(ms=>ms===400).length"), 0,
           "a patch at the end of the page asked the player every 400 ms, from the moment the page loaded, video or not")
    pp.set_input_files("#file-input", [TWOPART])
    wait(pp, "DB.all('meta').then(ms=>window.__v=ms.find(m=>m.title==='Two Parts')), !!window.__v")
    pp.evaluate("()=>{ openBook(window.__v.id); }")
    wait(pp, "rendition && rendition.getContents().length>0"); settle(4.0)
    expect("the sound carries the book on to the next chapter, on the player's own clock", ev(pp, "()=>{ const l=rendition.currentLocation(); return [BackchatPlayer.isPlaying, l && l.start && l.start.index]; }"), [True, 1],
           "at the end of a chapter's part of the video, the book stayed where it was while the sound went on")
    pctx.close()

    # 5. Every way back to a place lands on it: the page showing holds the words, and the words
    #    flashed are the ones that were marked (the second of two identical sentences, when that
    #    is the one marked). Run in pages and in scroll mode.
    for flow in ("paginated", "scrolled"):
        nctx = browser.new_context(bypass_csp=True, viewport={"width": 1280, "height": 860}); np_ = nctx.new_page(); watch(np_, "landing-" + flow)
        np_.goto(URL); wait(np_, "typeof DB!=='undefined' && typeof renderHome==='function'"); settle(1.2)
        np_.evaluate("(f)=>{ settings.flow=f; saveSettings(); }", flow)
        np_.set_input_files("#file-input", [LONG])
        wait(np_, "DB.all('meta').then(ms=>window.__lb=ms.find(m=>m.title==='Long Landing Book')), !!window.__lb")
        lid = np_.evaluate("window.__lb.id")
        wait(np_, "DB.get('app','ftbook:%s').then(v=>window.__lx=!!v), window.__lx===true" % lid, 40000)
        np_.evaluate("(id)=>openBook(id)", lid); settle(1.5)
        def mark_nth(href, quote, nth, note=None):
            np_.evaluate("(h)=>bcGoTo(currentBook.id,{href:h,flash:false})", href); settle(1.2)
            return np_.evaluate(r"""(a)=>{ const [quote,nth,note]=a; const c=bcContentsFor(bcSectionIndex({href:currentBook && rendition.currentLocation().start.href})); const tm=secTextMap(c), re=quoteRegex(quote); let m, hits=[]; while((m=re.exec(tm.full))) hits.push(m.index);
              const s=mapLocate(tm.map,hits[nth]), e=mapLocate(tm.map,hits[nth]+quote.length-1), r=c.document.createRange(); r.setStart(s.node,s.offset); r.setEnd(e.node,e.offset+1);
              lastSelection={cfiRange:c.cfiFromRange(r), text:quote, contents:c};
              return createHighlight('yellow', note||undefined).then(()=>highlights.filter(h=>!h.deleted).slice(-1)[0].id); }""", [quote, nth, note])
        BECOME, STAGES = "Become who you are by learning who you are", "The process comes in three stages"
        h1 = mark_nth("c2.xhtml", BECOME, 0, "Greek poet Pindar wrote")
        h2 = mark_nth("c1.xhtml", STAGES, 1)
        key = np_.evaluate("bookKeyOf(currentBook)")
        def home():
            np_.evaluate("()=>{ closeBook(); return goHome(); }"); settle(0.4)
        def click_result(box, q, group, has):
            np_.evaluate("(a)=>a[0]==='#search-results' ? openSearch(a[1]) : openReaderSearch(a[1])", [box, q])
            wait(np_, "/Inside books \\(|No in-text/.test(document.querySelector('%s').textContent)" % box)
            return ev(np_, """(a)=>{ const [box,g,has]=a; const grp=[...document.querySelectorAll(box+' .res-group')].find(x=>x.querySelector('h3').textContent.startsWith(g));
              const el=grp && [...grp.querySelectorAll('.res')].find(e=>e.textContent.toLowerCase().includes(has.toLowerCase())); if(!el) return 'no such result'; el.click(); return true; }""", [box, group, has])
        F = " (%s)" % flow

        home(); click_result("#search-results", "becom", "Highlights", BECOME)
        expect("search: a highlight opens the book on it" + F, landed(np_, BECOME), True, "the reported bug: the result opened the right chapter on the wrong page")
        np_.evaluate("()=>bcGoTo(currentBook.id,{href:'c0.xhtml',flash:false})"); settle(1)
        click_result("#rs-results", "becom", "Highlights", BECOME)
        expect("search over the open book lands on the highlight" + F, landed(np_, BECOME), True, "searching from inside the reader, the book already open elsewhere")
        home(); click_result("#search-results", "three stages", "Highlights", "three stages")
        expect("search: the marked copy of a repeated sentence" + F, landed(np_, STAGES, 1), True, "the same words appear twice; the jump goes to the one that was marked")
        home(); click_result("#search-results", "pindar wrote", "Notes", "pindar")
        expect("search: a comment opens its passage" + F, landed(np_, BECOME), True, "a comment result lands on the words it comments on")
        home(); click_result("#search-results", '"paragraph 70 of chapter 3"', "Inside books", "paragraph 70")
        expect("search: an inside-book match lands on the words" + F, landed(np_, "Paragraph 70 of chapter 3"), True, "the found passage, not its chapter's first page")

        np_.evaluate("()=>bcGoTo(currentBook.id,{href:'c3.xhtml',flash:false})"); settle(1)
        np_.evaluate("(id)=>{ renderHlControls(); renderHighlightList(); openPanel($('#hl-panel')); [...document.querySelectorAll('#hl-list .hl-item .txt')].find(e=>/three stages/.test(e.textContent)).click(); }", h2)
        expect("highlights panel lands on the marked copy" + F, landed(np_, STAGES, 1), True, "tapping a mark in the panel")
        home(); np_.evaluate("()=>openMarks()"); settle(0.8)
        np_.evaluate("(id)=>document.querySelector('#marks-list .mark-row[data-id=\"'+id+'\"]').click()", h2)
        expect("all marks lands on the marked copy" + F, landed(np_, STAGES, 1), True, "the all-marks view")
        home(); np_.evaluate("(a)=>{ dailyMmap[a[0]]=window.__lb; return DB.get('highlights',a[0]).then(r=>{ showDailyPick({bookId:a[0], h:r.items.find(h=>h.id===a[1])}); document.querySelector('#home-daily .m').click(); }); }", [lid, h1])
        expect("the daily highlight opens on its passage" + F, landed(np_, BECOME), True, "the home page highlight")
        home(); np_.evaluate("(a)=>openMarkById(a[0], a[1], '', '')", [lid, h2])
        expect("a rhyme opens on its mark" + F, landed(np_, STAGES, 1), True, "rhymes jump by mark id")
        home(); np_.evaluate("(a)=>followBcRef({bookKey:a[0],kind:'highlight',highlightId:a[1]})", [key, h2]); settle(0.6)
        np_.evaluate("()=>document.querySelector('#bc-peek .bc-peek-open').click()")
        expect("a highlight link opens on the marked copy" + F, landed(np_, STAGES, 1), True, "a [[bc|...]] highlight link, then Open in book")

        # A location link copied from a paragraph, and a raw position link.
        np_.evaluate("()=>bcGoTo(currentBook.id,{href:'c3.xhtml',quote:'Paragraph 40 of chapter 3',flash:false})"); settle(1.5)
        ref = np_.evaluate(r"""()=>{ const c=bcContentsFor(bcSectionIndex({href:'c3.xhtml'})); const r=findQuoteRange(c,secTextMap(c),'Paragraph 40 of chapter 3'); lastSelection={cfiRange:c.cfiFromRange(r), text:'Paragraph 40 of chapter 3', contents:c}; return bcPassageRef(bookKeyOf(currentBook), lastSelection.cfiRange, lastSelection); }""")
        home(); np_.evaluate("(r)=>followBcRef(bcParseAny(bcMakeToken(r)))", ref)
        expect("a location link lands on its paragraph" + F, [ref and ref.get("kind"), landed(np_, "Paragraph 40 of chapter 3")], ["anchor", True], "Copy location, pasted, followed later")
        np_.evaluate("()=>bcGoTo(currentBook.id,{href:'c0.xhtml',quote:'Paragraph 50 of chapter 0',flash:false})"); settle(1.5)
        pcfi = np_.evaluate(r"""()=>{ const c=bcContentsFor(0); const r=findQuoteRange(c,secTextMap(c),'Paragraph 50 of chapter 0'); return c.cfiFromRange(r); }""")
        home(); np_.evaluate("(a)=>followBcRef({bookKey:a[0],kind:'passage',cfi:a[1]})", [key, pcfi])
        expect("a position link lands on its passage" + F, landed(np_, "Paragraph 50 of chapter 0"), True, "a raw position (CFI) link")

        np_.evaluate("()=>bcGoTo(currentBook.id,{href:'c3.xhtml',flash:false})"); settle(1)
        np_.evaluate("()=>{ openFind(); $('#find-input').value='three stages'; doFind('three stages'); }"); settle(1.2)
        np_.evaluate("()=>document.querySelectorAll('#find-results .fr')[1].click()")
        expect("find in book: the second match lands on the second copy" + F, landed(np_, "three stages", 1), True, "each match lands on its own occurrence")
        np_.evaluate("()=>closeFind()"); settle(0.8)

        np_.evaluate("(c)=>{ currentBook.bookmarkCfi=c; ttsBookmarkGo(); }", pcfi)
        expect("the saved listening spot returns to its sentence" + F, landed(np_, "Paragraph 50 of chapter 0"), True, "Go to saved spot")

        # Where you were reading: closing and reopening, and the Return button after a link.
        bad = []
        for n in (1, 3, 6):
            np_.evaluate("()=>bcGoTo(currentBook.id,{href:'c3.xhtml',flash:false})"); settle(1)
            for _ in range(n):
                if flow == "paginated": np_.evaluate("()=>rendition.next()")
                else: np_.evaluate("()=>{ rendition.manager.container.scrollTop += 500; }")
                settle(0.35)
            settle(0.5)
            at, page = np_.evaluate("()=>{ const s=rendition.currentLocation().start; return [s.cfi, s.displayed.page]; }")
            np_.evaluate("()=>closeBook()"); settle(0.3); np_.evaluate("(id)=>openBook(id)", lid)
            got = on_page(np_, at)
            if got is True and flow == "paginated":
                now = np_.evaluate("()=>rendition.currentLocation().start.displayed.page")
                if now != page: got = "page %s, left on page %s" % (now, page)
            if got is not True: bad.append([n, at, got])
        expect("reopening a book returns to the same page" + F, bad, [], "the first words of the page you left are on the page you come back to")
        # Closing a book with the find bar still open: the bar closes on the way out, and the place
        # saved must be the page you saw, not one measured against the taller page left behind.
        np_.evaluate("()=>bcGoTo(currentBook.id,{href:'c1.xhtml',flash:false})"); settle(1)
        np_.evaluate("()=>bcGoTo(currentBook.id,{href:'c3.xhtml',flash:false})"); settle(1)
        np_.evaluate("()=>openFind()"); settle(0.8)
        for _ in range(3):
            if flow == "paginated": np_.evaluate("()=>rendition.next()")
            else: np_.evaluate("()=>{ rendition.manager.container.scrollTop += 500; }")
            settle(0.35)
        settle(0.5)
        at = np_.evaluate("()=>rendition.currentLocation().start.cfi")
        np_.evaluate("()=>closeBook()"); settle(0.3); np_.evaluate("(id)=>openBook(id)", lid)
        expect("closing a book with find open keeps the words you were reading" + F, on_page(np_, at), True,
               "find closed before the place was read, and the page measured against the taller area began a page or so later")
        # Changing how the page is laid out keeps you on the words you were reading.
        def font_to(v):
            return "()=>{ const b=s=>document.querySelector('#fs-step [data-step=\"'+s+'\"]'); let n=0; while(settings.fs<%d && n++<20) b('1').click(); while(settings.fs>%d && n++<40) b('-1').click(); }" % (v, v)
        changes = [("a bigger font", font_to(140)), ("a smaller font", font_to(90)), ("a smaller window", "resize"),
                   ("the font family", "()=>document.querySelector('#seg-font [data-font]:not(.active)').click()")]
        if flow == "paginated": changes += [("switching to scroll", "()=>setReadFlow('scrolled')"), ("switching back to pages", "()=>setReadFlow('paginated')")]
        bad = []
        for what, how in changes:
            if what != "switching back to pages":
                np_.evaluate("()=>bcGoTo(currentBook.id,{href:'c3.xhtml',quote:'Paragraph 37 of chapter 3',flash:false})"); settle(1.5)
            else: settle(2)   # read a while in scroll mode first; the page you return to holds the top line you left
            at = np_.evaluate("()=>rendition.currentLocation().start.cfi")
            if how == "resize": np_.set_viewport_size({"width": 1000, "height": 760})
            else: np_.evaluate(how)
            got = on_page(np_, at)
            if got is not True: bad.append([what, got])
            if how == "resize": np_.set_viewport_size({"width": 1280, "height": 860}); settle(1.5)
        np_.evaluate("()=>{ settings.fs=100; settings.font='serif'; saveSettings(); syncSettingsUI(); applyTheme(); }"); settle(1)
        expect("changing the layout keeps your place" + F, bad, [], "font size (which on a wide screen also moves the margins), font, window size and scroll mode all reflow the book; the words you were reading stay on screen")

        np_.evaluate("()=>bcGoTo(currentBook.id,{href:'c1.xhtml',quote:'Paragraph 30 of chapter 1',flash:false})"); settle(1.5)
        at = np_.evaluate("()=>{ const s=rendition.currentLocation().start; _bcReadJump.push(s.cfi); return s.cfi; }")
        np_.evaluate("()=>bcGoTo(currentBook.id,{href:'c3.xhtml'})"); settle(1.5)
        np_.evaluate("()=>_bcJumpBack()")
        expect("Return goes back to the page you left" + F, on_page(np_, at), True, "after following a link inside a book")

        # Places that moved or were never pinned down, and a newer jump overtaking an older one.
        np_.evaluate("(a)=>DB.get('highlights',a[0]).then(r=>{ r.items.push({id:'stale1',text:'Become who you are by learning',color:'blue',created:1,updated:1,href:'c0.xhtml',cfiRange:'epubcfi(/6/2!/4/10/1:0)'}, {id:'bare1',text:'The process comes in three stages',color:'blue',created:1,updated:1}); return DB.put('highlights',r); })", [lid])
        home(); np_.evaluate("(id)=>openMarkById(id,'stale1','','')", lid)
        expect("a mark whose saved place went stale still lands on its words" + F, landed(np_, BECOME), True, "an EPUB edited after marking: the words are found in their new section")
        home(); np_.evaluate("(id)=>openMarkById(id,'bare1','','')", lid)
        expect("a mark saved without a position lands on its words" + F, landed(np_, STAGES), True, "imported marks carry only their words")
        np_.evaluate("()=>{ bcGoTo(currentBook.id,{href:'c3.xhtml',quote:'Paragraph 75 of chapter 3'}); bcGoTo(currentBook.id,{href:'c0.xhtml',quote:'Paragraph 20 of chapter 0'}); }")
        expect("the latest jump wins" + F, landed(np_, "Paragraph 20 of chapter 0"), True, "two quick taps: the reader ends on the second")

        # A mark kept under an older copy's id (the book was deleted and added again).
        if flow == "paginated":
            np_.evaluate("(a)=>DB.put('meta',{id:'oldcopy',title:'Long Landing Book',author:'Test Author',bookKey:a[0],addedAt:1,progress:0,tags:[]}).then(()=>DB.put('highlights',{id:'oldcopy',items:[{id:'old1',text:'Paragraph 66 of chapter 2',color:'green',created:1,updated:1,href:'c2.xhtml'}]}))", [key])
            home(); click_result("#search-results", '"paragraph 66 of chapter 2"', "Highlights", "paragraph 66")
            expect("a mark from an older copy of the book opens the current copy on it", landed(np_, "Paragraph 66 of chapter 2"), True, "ids change when a book is added again")
        nctx.close()

    # 6. The built-in guide lives in guide/, is fetched only when needed, arrives whole, and updates
    #    itself when guide.md's revision rises. Web links inside a book open in a new tab.
    gctx = browser.new_context(bypass_csp=True); gp = gctx.new_page(); watch(gp, "guide")
    guide_reqs = []
    gctx.on("request", lambda r: guide_reqs.append(r.url) if "/guide/" in r.url else None)
    gp.goto(URL); wait(gp, "typeof DB!=='undefined' && typeof seedGuide==='function'")
    wait(gp, "DB.get('meta','bcguide001').then(m=>window.__g=m), !!window.__g")
    settle(1.5)
    expect("a first run adds the guide from guide/ with its sample marks", ev(gp, """(async()=>{
      const m=await DB.get('meta','bcguide001'), h=await DB.get('highlights','bcguide001'), b=await DB.get('blob','bcguide001');
      return [m.guideRev===GUIDE_SRC.rev, /^data:image\\/jpeg/.test(m.cover||''), !!(b&&b.data), hlLive(h.items).length===GUIDE_SRC.marks.length]; })()""".replace("GUIDE_SRC", "(await fetchGuide())")),
           [True, True, True, True], "the book, its cover and every sample mark")
    expect("every icon the guide names is drawn", ev(gp, """(async()=>{ const src=await fetchGuide(); const names=[...new Set([...src.body.matchAll(/\\{\\{icon:([a-z-]+)\\}\\}/g)].map(m=>m[1]))]; return names.filter(n=>!guideIcon(n)); })()"""), [],
           "an unknown icon name would leave a gap in the sentence")
    expect("every sample mark is in the guide's text", ev(gp, """(async()=>{ const src=await fetchGuide(), flat=src.body.replace(/\\s+/g,' '); return src.marks.filter(m=>flat.indexOf(m.text.replace(/\\s+/g,' '))<0).map(m=>m.text); })()"""), [],
           "a mark whose words are missing could never be shown")
    gp.evaluate("()=>openBook('bcguide001')")
    wait(gp, "rendition && rendition.getContents().length>0"); settle(2)
    gp.evaluate("async ()=>{ const src=await fetchGuide(); await bcGoTo(currentBook.id,{quote:src.marks[0].text,flash:false}); }"); settle(1.5)
    expect("the guide's sample marks are painted", ev(gp, "(()=>{ const c=rendition.getContents()[0]; return Object.keys(c._hlRanges||{}).length; })()"), lambda n: n >= 2,
           "the chapter holding the first sample marks paints them")
    gp.evaluate("()=>closeBook()"); settle(0.5)
    guide_reqs.clear()
    gp.reload(); wait(gp, "typeof DB!=='undefined' && typeof renderHome==='function'"); wait(gp, "document.querySelectorAll('#home-recent .card').length>0"); settle(2)
    expect("an ordinary page load never fetches the guide", guide_reqs, [], "the guide is fetched on a first run, on request, or when it is opened")
    # A newer guide.md: opening the guide rebuilds it, keeps the reader's own marks, adds the new text.
    gp.evaluate("""async ()=>{ const r=await DB.get('highlights','bcguide001'); r.items.push({id:'mine1',text:'Most reading apps store books.',color:'green',note:'my own note',created:1,updated:1,cfiRange:''}); await DB.put('highlights',r); }""")
    gtext = open(os.path.join(SITE, "guide", "guide.md"), encoding="utf-8").read()
    newer = re.sub(r"revision:\s*(\d+)", lambda m: "revision: %d" % (int(m.group(1)) + 1), gtext, count=1).replace("## The bargain", "## A brand new chapter\n\nThis chapter arrived with a newer revision.\n\n## The bargain")
    gp.route(re.compile(r".*/guide/guide\.md$"), lambda route: route.fulfill(status=200, content_type="text/markdown; charset=utf-8", body=newer))
    gp.reload(); wait(gp, "typeof DB!=='undefined' && typeof renderHome==='function'"); settle(1.5)
    gp.evaluate("()=>openBook('bcguide001')"); wait(gp, "rendition && rendition.getContents().length>0"); settle(2)
    expect("a newer guide.md updates the guide when it is opened, keeping your own marks", ev(gp, """(async()=>{
      const m=await DB.get('meta','bcguide001'), h=await DB.get('highlights','bcguide001'), ft=await indexBook('bcguide001',{force:true}).then(()=>DB.get('fulltext','bcguide001'));
      const text=recSectionTexts(ft).map(s=>s.text).join(' ');
      return [m.guideRev, /arrived with a newer revision/.test(text), hlLive(h.items).some(x=>x.id==='mine1' && x.note==='my own note')]; })()"""),
           [int(re.search(r"revision:\s*(\d+)", gtext).group(1)) + 1, True, True], "revision rises, new text in, the reader's mark kept")
    gp.unroute(re.compile(r".*/guide/guide\.md$"))
    # Web links inside a book open in a new tab (the book's frame cannot open one itself).
    gctx.route(re.compile(r"^https://github\.com/.*"), lambda route: route.fulfill(status=200, content_type="text/html", body="<title>ok</title>"))
    gp.evaluate("()=>bcGoTo(currentBook.id,{quote:'Its code is public on GitHub',flash:false})"); settle(2)
    fr = [f for f in gp.frames if f != gp.main_frame]
    try:
        with gctx.expect_page(timeout=5000) as newtab:
            fr[0].click('a[href^="https://github.com"]')
        opened = newtab.value.url
    except Exception as e:
        opened = "no new tab: " + str(e).splitlines()[0][:120]
    expect("a web link in a book opens in a new tab", opened, lambda u: u.startswith("https://github.com/wisdomreboot/backchat"), "the guide's GitHub link, and any link in a book")
    # A guide that cannot be fetched says so instead of failing silently.
    gp.evaluate("()=>{ closeBook(); }"); settle(0.5)
    gp.route(re.compile(r".*/guide/guide\.md$"), lambda route: route.fulfill(status=200, content_type="text/html", body="<html>a captive portal page, not the guide</html>"))
    expect("a guide that cannot be fetched says so", ev(gp, """(async()=>{ _guideSrc=null; await DB.del('meta','bcguide001'); let msg='';
      const t=window.toast; window.toast=function(m){ msg=m; t(m); }; document.querySelector('#guide-btn').click(); await new Promise(r=>setTimeout(r,1200)); window.toast=t; return msg; })()"""),
           lambda m: "could not be fetched" in m, "a toast, not a silent failure")
    gctx.close()

    # 7. Phones: real touch input on a phone-sized screen. Pages turn by swipe and by a tap on either
    #    edge; text boxes are large enough that an iPhone never zooms; the phone's Back steps back
    #    inside Backchat; scroll mode never strands you at a chapter's end; nothing hides under the
    #    notch or the home bar.
    phone = dict(p.devices["iPhone 13"]); phone.pop("default_browser_type", None)
    PW, PH = phone["viewport"]["width"], phone["viewport"]["height"]
    mctx = browser.new_context(**phone, bypass_csp=True); mp = mctx.new_page(); watch(mp, "phone")
    cdp = mctx.new_cdp_session(mp)
    def touch(kind, pts): cdp.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": [{"x": x, "y": y} for x, y in pts]})
    def swipe(x0, y0, x1, y1, steps=6, dur=0.08):
        touch("touchStart", [(x0, y0)])
        for i in range(1, steps + 1):
            touch("touchMove", [(x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps)]); time.sleep(dur / steps)
        touch("touchEnd", [])
    def tap_at(x, y): touch("touchStart", [(x, y)]); time.sleep(0.05); touch("touchEnd", [])
    def tap(sel):
        try: mp.tap(sel, timeout=4000); return True
        except Exception: return False
    def page_no(): return ev(mp, "()=>{ const l=rendition.currentLocation(); return l&&l.start ? [l.start.index,(l.start.displayed||{}).page] : null }")
    def back_state(): return ev(mp, "()=>[bcScreen(), bcLayers(), bcBackDepth()]")
    def back():
        """The phone's Back. True while Backchat is still the page showing; otherwise it reopens it."""
        mp.go_back(); settle(0.7)
        if mp.url.split("#")[0] == URL: return True
        mp.goto(URL); wait(mp, "document.querySelectorAll('#home-recent .card').length>0"); settle(1)
        return False
    try:
        mp.goto(URL); wait(mp, "document.querySelectorAll('#home-recent .card').length>0"); settle(1.5)
        expect("the Handoff count leaves out the guide's sample marks", ev(mp, "()=>document.querySelector('#home-handoff-count').textContent"), "",
               "a first visit has nothing of the reader's own to hand off")
        mp.set_input_files("#file-input", [LONG, ALPHA])
        wait(mp, "DB.count('meta').then(n=>window.__pn=n), window.__pn>=3", 30000); settle(1.5)
        mp.evaluate("()=>goHome()"); settle(0.8)
        expect("on a phone no text box is under 16px, so an iPhone never zooms in", ev(mp, r"""()=>[...document.querySelectorAll('input,textarea,select')]
            .filter(e=>!['range','checkbox','radio','file','hidden'].includes((e.type||'').toLowerCase()))
            .map(e=>[e.id||e.className, parseFloat(getComputedStyle(e).fontSize)]).filter(x=>x[1]<16)"""), [], "Safari zooms the page into any text box under 16px")
        mp.evaluate("()=>window.scrollTo(0, 400)"); settle(0.3)
        expect("the home header scrolls away on a phone", ev(mp, "()=>Math.round(document.querySelector('#home .topbar').getBoundingClientRect().bottom)"), lambda b: b <= 0,
               "pinned, the search and Add rows cover a third of a small screen")
        mp.evaluate("()=>window.scrollTo(0, 0)")
        tap("#home-settings"); settle(0.5)
        for _ in range(10): swipe(PW * 0.7, PH * 0.8, PW * 0.7, PH * 0.2); time.sleep(0.12)
        settle(0.6)
        expect("a panel scrolled to its end leaves the page behind it still", ev(mp, "()=>[document.querySelector('#lib-panel .panel-body').scrollTop>0, window.scrollY]"), [True, 0],
               "overscroll-behavior: contain on panels")
        tap("#lib-panel [data-close]"); settle(1.0)
        expect("closing a panel with its own button uses up Back's step", [ev(mp, "()=>document.querySelector('#lib-panel').classList.contains('open')"), back_state()], [False, ["home", 0, 0]],
               "otherwise the next Back would do nothing")
        tap("#home-settings"); settle(0.4); stayed = back()
        expect("the phone's Back closes a panel instead of leaving", [stayed, ev(mp, "()=>document.querySelector('#lib-panel').classList.contains('open')"), back_state()], [True, False, ["home", 0, 0]],
               "Android's Back and an iPhone's edge swipe used to leave the site")
        long_id = ev(mp, "DB.all('meta').then(ms=>ms.filter(m=>/Long Landing/.test(m.title))[0].id)")
        mp.evaluate("(id)=>openDetails(id)", long_id); settle(1.0)
        tap(".det-cta"); wait(mp, "rendition && rendition.getContents().length>0"); settle(2.5)
        a = page_no(); swipe(PW * 0.8, PH * 0.5, PW * 0.2, PH * 0.5); settle(0.9); b = page_no()
        swipe(PW * 0.2, PH * 0.5, PW * 0.8, PH * 0.5); settle(0.9); c = page_no()
        expect("a swipe turns the page on a phone", [b[1] - a[1], c[1] - b[1]] if a and b and c else [a, b, c], [1, -1], "swipe left for the next page, right for the one before")
        a = page_no(); tap_at(PW - 14, PH * 0.5); settle(0.9); b = page_no(); tap_at(14, PH * 0.5); settle(0.9); c = page_no()
        expect("a tap on the right or left edge turns the page on a phone", [b[1] - a[1], c[1] - b[1]] if a and b and c else [a, b, c], [1, -1],
               "the guide and the help both promise it; below 600px there are no side arrows")
        settle(0.6); a = page_no(); mp.mouse.click(PW - 14, PH * 0.5); settle(0.9); b = page_no()
        expect("a mouse click at the edge does not turn the page", b, a, "edge taps are for fingers; a click there may just be setting the caret or closing a menu")
        tap("#find-btn"); settle(0.4)
        bs2 = [ev(mp, "()=>document.activeElement && document.activeElement.id"), back_state()]
        stayed = back(); bs3 = [stayed, ev(mp, "()=>document.querySelector('#findbar').classList.contains('hidden')"), back_state()]
        expect("the phone's Back closes the find bar, then the book", [bs2, bs3], [["find-input", ["reader", 2, 2]], [True, True, ["reader", 1, 1]]],
               "each open thing takes one Back; Find opens with the keyboard up")
        # The selection menu stays clear of the phone's own Copy menu above and the handles below.
        mp.evaluate(r"""()=>{ const c=rendition.getContents()[0]; const r=findQuoteRange(c,secTextMap(c),'Paragraph 3 of chapter 0'); const s=c.window.getSelection(); s.removeAllRanges(); s.addRange(r); }"""); settle(1.0)
        MENU_CLEAR = r"""()=>{ const c=rendition.getContents()[0], r=c.window.getSelection().getRangeAt(0).getBoundingClientRect(), f=c.document.defaultView.frameElement.getBoundingClientRect(), p=document.querySelector('#sel-pop').getBoundingClientRect();
            return selPopOpen() && (p.top>=f.top+r.bottom+20 || p.bottom<=f.top+r.top-40) && p.bottom<=innerHeight*0.8; }"""
        clear_mid = ev(mp, MENU_CLEAR)
        # words low on the screen, where a menu below them would sit under Chrome's Touch to Search bar
        mp.evaluate(r"""()=>{ const c=rendition.getContents()[0], doc=c.document, fr=doc.defaultView.frameElement.getBoundingClientRect(), box=rendition.manager.container.getBoundingClientRect();
            const a=doc.caretRangeFromPoint(box.left-fr.left+30, box.top-fr.top+box.height*0.8), b=doc.caretRangeFromPoint(box.left-fr.left+200, box.top-fr.top+box.height*0.8);
            c.window.getSelection().setBaseAndExtent(a.startContainer, a.startOffset, b.startContainer, b.startOffset); }"""); settle(1.0)
        clear_low = ev(mp, MENU_CLEAR)
        mp.evaluate(r"""()=>{ const c=rendition.getContents()[0]; const r=findQuoteRange(c,secTextMap(c),'Paragraph 3 of chapter 0'); const s=c.window.getSelection(); s.removeAllRanges(); s.addRange(r); }"""); settle(1.0)
        expect("the selection menu sits clear of the selection and of the bottom of the screen", [clear_mid, clear_low], [True, True],
               "a phone draws Copy above a selection and drag handles below it, and Chrome's Touch to Search bar covers the bottom of the screen")
        tap("#sel-pop button.act[title='Comment']"); settle(0.4)
        mp.keyboard.type("Typed on a phone"); stayed = back()
        expect("Back on a comment being typed keeps it", [stayed, ev(mp, "()=>highlights.filter(h=>!h.deleted && h.note==='Typed on a phone').length"), back_state()], [True, 1, ["reader", 1, 1]],
               "Back closes the box; the words are not thrown away")
        stayed = back(); settle(0.8)
        expect("the phone's Back then closes the book", [stayed, back_state()], [True, ["home", 0, 0]], "the last open thing")
        # Scroll mode: the end of a chapter offers the next; a pull down at the start offers the one before.
        mp.evaluate("(id)=>openBook(id)", long_id); wait(mp, "rendition && rendition.getContents().length>0"); settle(2)
        mp.evaluate("()=>setReadFlow('scrolled')"); settle(2)
        mp.evaluate("()=>bcGoTo(currentBook.id,{href:book.spine.spineItems[0].href,flash:false})"); settle(1.5)
        for _ in range(45): swipe(PW * 0.5, PH * 0.75, PW * 0.5, PH * 0.15); time.sleep(0.1)
        settle(0.8)
        shown = ev(mp, "()=>document.querySelector('#bc-chap-next').classList.contains('show')")
        tap("#bc-chap-next"); settle(1.5)
        expect("scroll mode: a chapter's end offers the next chapter", [shown, (page_no() or [None])[0]], [True, 1], "scrolling stops at a chapter's end, and phones have no side arrows")
        swipe(PW * 0.5, PH * 0.3, PW * 0.5, PH * 0.8); settle(0.6)
        shown = ev(mp, "()=>document.querySelector('#bc-chap-prev').classList.contains('show')")
        tap("#bc-chap-prev"); settle(1.8)
        expect("scroll mode: a pull down at a chapter's start offers the one before, at its end", [shown, (page_no() or [None])[0], ev(mp, "()=>{ const c=rendition.manager.container; return c.scrollTop+c.clientHeight>=c.scrollHeight-4; }")],
               [True, 0, True], "reading on backwards arrives at the end of the chapter before")
        mp.evaluate("()=>setReadFlow('paginated')"); settle(1.2)
    except Exception as e:
        expect("the phone checks run to the end", str(e).splitlines()[0][:200], None, "a step above could not continue")
    mctx.close()
    # A small phone: the find bar fits, and its matches sit above it, where the keyboard cannot cover them.
    small = dict(p.devices["iPhone SE"]); small.pop("default_browser_type", None)
    sctx = browser.new_context(**small, bypass_csp=True); sp = sctx.new_page(); watch(sp, "small-phone")
    sp.goto(URL); wait(sp, "document.querySelectorAll('#home-recent .card').length>0"); settle(1)
    sp.set_input_files("#file-input", [LONG]); wait(sp, "DB.count('meta').then(n=>window.__sn=n), window.__sn>=2", 30000); settle(1)
    sp.evaluate("()=>DB.all('meta').then(ms=>openBook(ms.filter(m=>/Long Landing/.test(m.title))[0].id))"); wait(sp, "rendition && rendition.getContents().length>0"); settle(2)
    expect("the reader's top bar is one row on a small phone, read aloud included", ev(sp, "()=>Math.round(document.querySelector('#reader .topbar').getBoundingClientRect().height)"), lambda h: isinstance(h, int) and h < 70,
           "with read aloud on, the buttons wrapped to a second row and took the page's height")
    # Dragging a selection handle past the edge of the page scrolls the book sideways by part of a page.
    sp.evaluate("()=>rendition.next()"); settle(0.8)
    sp.evaluate(r"""()=>{ const c=rendition.getContents()[0], m=rendition.manager, d=m.layout.delta, doc=c.document;
      const fr=doc.defaultView.frameElement.getBoundingClientRect(), box=m.container.getBoundingClientRect();
      const a=doc.caretRangeFromPoint(box.right-fr.left-50, box.bottom-fr.top-60), b=doc.caretRangeFromPoint(box.right-fr.left+50, box.top-fr.top+100);
      c.window.getSelection().setBaseAndExtent(a.startContainer, a.startOffset, b.startContainer, b.startOffset);
      m.container.scrollLeft = m.container.scrollLeft + Math.round(d*0.55); }""")
    settle(1.5)
    snapped = ev(sp, r"""()=>{ const c=rendition.getContents()[0], m=rendition.manager, d=m.layout.delta, sl=m.container.scrollLeft, s=c.window.getSelection();
        const r=c.document.createRange(); r.setStart(s.focusNode, Math.max(0, s.focusOffset-1)); r.setEnd(s.focusNode, s.focusOffset);
        return [Math.abs(sl-Math.round(sl/d)*d)<2, bcRangeSide(c, r)===0, !s.isCollapsed, selPopOpen()]; }""")
    sp.evaluate("()=>{ hideSelPop(); rendition.getContents()[0].window.getSelection().removeAllRanges(); rendition.next(); }"); settle(0.8)
    expect("a selection dragged onto the next page settles on a whole page, and pages stay whole after", [snapped, ev(sp, "()=>{ const m=rendition.manager, d=m.layout.delta, sl=m.container.scrollLeft; return Math.abs(sl-Math.round(sl/d)*d)<2; }")],
           [[True, True, True, True], True], "half of two pages stayed on screen, and every page turn after kept the offset until the book was reopened")
    sp.tap("#find-btn"); sp.keyboard.type("river"); settle(1.2)
    expect("find in book fits a 320px phone, with its matches above the box", ev(sp, """()=>{ const x=document.querySelector('#find-close').getBoundingClientRect(), b=document.querySelector('#findbar').getBoundingClientRect(), r=document.querySelector('#find-results').getBoundingClientRect();
        return [x.right<=innerWidth, r.height>0 && r.bottom<=b.top+1]; }"""), [True, True], "the close button was pushed off screen, and the keyboard covered the matches")
    sctx.close()
    # The notch and the home bar (landscape, or a home-screen app): nothing sits under them.
    land = dict(p.devices["iPhone 13 landscape"]); land.pop("default_browser_type", None)
    lctx = browser.new_context(**land, bypass_csp=True); lp = lctx.new_page(); watch(lp, "notch")
    lctx.new_cdp_session(lp).send("Emulation.setSafeAreaInsetsOverride", {"insets": {"left": 47, "right": 47, "top": 0, "bottom": 21}})
    lp.goto(URL); wait(lp, "document.querySelectorAll('#home-recent .card').length>0"); settle(1)
    lp.evaluate("()=>openBook('bcguide001')"); wait(lp, "rendition && rendition.getContents().length>0"); settle(2)
    LW, LH = land["viewport"]["width"], land["viewport"]["height"]
    expect("nothing sits under the notch or the home bar", ev(lp, """(a)=>{ const r=s=>document.querySelector(s).getBoundingClientRect();
        return [r('#back-btn').left>=47, r('#set-btn').right<=a[0]-47, r('#viewport').left>=47, r('#prev .nav-arrow').left>=47, r('#pct-label').bottom<=a[1]-21]; }""", [LW, LH]), [True, True, True, True, True],
           "with the page drawn edge to edge, the safe-area insets keep controls and text clear")
    lctx.close()

    # 7b. Margins and line spacing, on an Android-sized phone and on a wide screen. They are set by the
    #     reader, alike in pages and in scroll mode, and hold steady as the player comes and goes. Font
    #     size moves by buttons, so a swipe that scrolls the Reading panel cannot change it.
    # Every line on screen: the nearest any comes to each side, how many cross the reading area's edge,
    # and the line spacing of the first paragraph showing, as a multiple of its font size.
    INSET = r"""()=>{ const c=rendition.getContents()[0], d=c.document, fr=d.defaultView.frameElement.getBoundingClientRect(), box=rendition.manager.container.getBoundingClientRect();
        let L=1e9, R=1e9, cut=0, n=0; const w=d.createTreeWalker(d.body, NodeFilter.SHOW_TEXT); let t;
        while((t=w.nextNode())){ if(!t.textContent.trim()) continue; const r=d.createRange(); r.selectNodeContents(t);
          for(const q of r.getClientRects()){ const a=fr.left+q.left, b=fr.left+q.right, y=fr.top+(q.top+q.bottom)/2;
            if(b<=box.left || a>=box.right || y<box.top || y>box.bottom) continue; n++;
            if(a<box.left-0.5 || b>box.right+0.5) cut++; L=Math.min(L, a-box.left); R=Math.min(R, box.right-b); } }
        const p=[...d.querySelectorAll('p')].find(e=>{ const r=e.getBoundingClientRect(), y=fr.top+r.top; return fr.left+r.left>=box.left-1 && fr.left+r.left<box.right && y>=box.top && y<box.bottom; });
        const cs=p && getComputedStyle(p);
        return { left:Math.round(L), right:Math.round(R), cut:cut, lines:n, lh: cs ? +(parseFloat(cs.lineHeight)/parseFloat(cs.fontSize)).toFixed(2) : null, font: cs ? parseFloat(cs.fontSize) : null, col: Math.round(box.width-2*L) }; }"""
    try:
        gctx = browser.new_context(viewport={"width": 360, "height": 740}, device_scale_factor=2, is_mobile=True, has_touch=True, bypass_csp=True)
        gp = gctx.new_page(); watch(gp, "margins"); gcdp = gctx.new_cdp_session(gp)
        def gtouch(kind, pts): gcdp.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": [{"x": x, "y": y} for x, y in pts]})
        gp.goto(URL); wait(gp, "document.querySelectorAll('#home-recent .card').length>0"); settle(1)
        gp.set_input_files("#file-input", [LONG, STYLED]); wait(gp, "DB.count('meta').then(n=>window.__gn=n), window.__gn>=3", 30000); settle(1)
        gp.evaluate("()=>DB.all('meta').then(ms=>openBook(ms.filter(m=>/Long Landing/.test(m.title))[0].id))"); wait(gp, "rendition && rendition.getContents().length>0"); settle(2.5)
        gp.evaluate("()=>rendition.next()"); settle(0.8)
        gp.evaluate("()=>{ tts.on=true; ttsSetUI(); }"); settle(1.5)   # the player showing, without a voice to speak
        paged = ev(gp, INSET)
        gp.evaluate("()=>ttsTurnOff()"); settle(1.5)
        paged_off = ev(gp, INSET)
        expect("a page keeps its margins and spacing when read aloud is switched off", [paged_off.get(k) for k in ("left", "lh", "cut")], [paged.get(k) for k in ("left", "lh", "cut")],
               "the player going away must not change the text's width or spacing")
        gp.evaluate("()=>setReadFlow('scrolled')"); settle(2.5)
        scrolled = ev(gp, INSET)
        expect("pages and scroll mode have the same margins and line spacing on a phone", [scrolled["left"], scrolled["lh"], abs(scrolled["right"] - scrolled["left"]) <= 30],
               [paged["left"], paged["lh"], True], "scroll mode had twice the side margin of a page, a cramped column of wide-spaced words")
        expect("a phone's margins leave most of the screen to the words", [paged["left"] <= 24, paged["lh"]], [True, 1.35],
               "on a short line every pixel of margin costs words; the spacing suits a short line")
        gp.evaluate("()=>setReadFlow('paginated')"); settle(2)
        # The Reading panel: swipe up from the font size control to reach Read aloud at the bottom.
        gp.evaluate("()=>openPanel(document.querySelector('#settings-panel'))"); settle(0.8)
        fs0 = ev(gp, "()=>settings.fs")
        x, y = ev(gp, "()=>{ const e=document.querySelector('#fs-step')||document.querySelector('#fs'), r=e.getBoundingClientRect(); return [r.left+r.width*0.78, r.top+r.height/2]; }")
        gtouch("touchStart", [(x, y)])
        for i in range(1, 13): time.sleep(0.016); gtouch("touchMove", [(x, y - 220 * i / 12)])
        gtouch("touchEnd", []); settle(0.8)
        expect("a swipe that scrolls the Reading panel leaves the font size alone", [ev(gp, "()=>document.querySelector('#settings-panel .panel-body').scrollTop>0"), ev(gp, "()=>settings.fs"), ev(gp, "()=>!!document.querySelector('#lh,#mg')")],
               [True, fs0, False], "the swipe that reaches Read aloud started on a slider and dragged it: font size and margins changed on their own")
        gp.evaluate("()=>document.querySelector('#settings-panel .panel-body').scrollTop=0"); settle(0.3)
        try: gp.tap("#fs-step [data-step='1']", timeout=4000)
        except Exception: pass
        settle(1.5)
        gp.evaluate("()=>closePanels()"); settle(0.5)
        for _ in range(4): gp.evaluate("()=>rendition.next()"); settle(0.4)
        bigger = ev(gp, INSET)
        expect("a tap on the larger button makes the text 10% bigger, and every line stays inside its page", [ev(gp, "()=>settings.fs"), bigger["font"], bigger["cut"], bigger["left"]],
               [fs0 + 10, round((fs0 + 10) * 19 / 100), 0, paged["left"]], "font size is yours; margins follow the screen")
        gp.evaluate("()=>{ settings.fs=100; saveSettings(); syncSettingsUI(); }")
        # A book with its own tight spacing reads with the reader's.
        gp.evaluate("()=>DB.all('meta').then(ms=>openBook(ms.filter(m=>/Styled Spacing/.test(m.title))[0].id))"); wait(gp, "rendition && rendition.getContents().length>0 && /Styled/.test(currentBook.title)"); settle(2.5)
        own = ev(gp, INSET)
        expect("a book's own line spacing gives way to the reader's", [own["lh"], own["left"]], [1.35, paged["left"]], "line spacing is set for every book alike")
        gctx.close()
        # A wide screen: the margins grow to hold a line to a readable length, in pages and in scroll mode.
        wctx = browser.new_context(viewport={"width": 1280, "height": 860}, bypass_csp=True); wp = wctx.new_page(); watch(wp, "wide")
        wp.goto(URL); wait(wp, "document.querySelectorAll('#home-recent .card').length>0"); settle(1)
        wp.set_input_files("#file-input", [LONG]); wait(wp, "DB.count('meta').then(n=>window.__wn=n), window.__wn>=2", 30000); settle(1)
        wp.evaluate("()=>DB.all('meta').then(ms=>openBook(ms.filter(m=>/Long Landing/.test(m.title))[0].id))"); wait(wp, "rendition && rendition.getContents().length>0"); settle(2.5)
        wpg = ev(wp, INSET)
        wp.evaluate("()=>setReadFlow('scrolled')"); settle(2.5)
        wsc = ev(wp, INSET)
        wp.evaluate("()=>setReadFlow('paginated')"); settle(1.5)
        cpl = lambda m: round(m["col"] / (0.5 * m["font"])) if m.get("font") else None
        expect("on a wide screen a line holds about 66 characters, in pages and in scroll mode", [cpl(wpg) <= 70, abs(wsc["left"] - wpg["left"]) <= 1, wpg["lh"], wpg["cut"]], [True, True, 1.45, 0],
               "lines ran to 80 characters and more, too long for the eye to find the next one; longer lines get a little more space between them")
        wctx.close()
    except Exception as e:
        expect("the margin checks run to the end", str(e).splitlines()[0][:200], None, "a step above could not continue")

    # 7c. Where you were, on a phone. A book open when Backchat went away (the phone dropped the tab, a
    #     reload) opens again on its page; a book closed first does not. The saved listening spot shows
    #     as there. Across devices the place read last wins, the newest saved spot wins, and a book
    #     sitting open and untouched moves to a place read since on another device.
    # Another device's copy of this book's record, changed as given, arriving as a relay pull delivers it.
    OTHER = r"""(a)=>DB.get('meta', a.id).then(m=>{ const o=Object.assign({}, m, a.change); return cloudApplyBundle({app:'backchat-sync', v:1, device:'desk', name:'Desktop', at:Date.now(), tombstones:{ids:{},keys:{}}, books:[{meta:o, highlights:[], updatedAt:0}]}); })"""
    def now_ms(): return int(time.time() * 1000)
    try:
        for flow in ("paginated", "scrolled"):
            F = " (%s)" % flow
            rctx = browser.new_context(viewport={"width": 360, "height": 740}, device_scale_factor=2, is_mobile=True, has_touch=True, bypass_csp=True)
            rp = rctx.new_page(); watch(rp, "place-" + flow)
            rp.goto(URL); wait(rp, "document.querySelectorAll('#home-recent .card').length>0"); settle(1)
            rp.set_input_files("#file-input", [LONG]); wait(rp, "DB.count('meta').then(n=>window.__rn=n), window.__rn>=2", 30000); settle(1)
            rp.evaluate("(f)=>{ settings.flow=f; saveSettings(); }", flow)
            rid = rp.evaluate("()=>DB.all('meta').then(ms=>ms.filter(m=>/Long Landing/.test(m.title))[0].id)")
            rp.evaluate("(id)=>openBook(id)", rid); wait(rp, "rendition && rendition.getContents().length>0"); settle(2.5)
            def read_on(n):
                for _ in range(n):
                    rp.evaluate("()=>{ _bcInputAt=Date.now(); " + ("rendition.next(); }" if flow == "paginated" else "rendition.manager.container.scrollTop += 400; }")); settle(0.4)
            def reopened():
                try: wait(rp, "bcScreen()==='reader' && rendition && rendition.getContents().length>0", 12000); return True
                except Exception: return ev(rp, "()=>bcScreen()")
            rp.evaluate("()=>{ _bcInputAt=Date.now(); return bcGoTo(currentBook.id,{href:'c2.xhtml',flash:false}); }"); settle(1.5)
            read_on(3); settle(0.6)
            at = rp.evaluate("()=>rendition.currentLocation().start.cfi")
            rp.evaluate("()=>{ _bcInputAt=Date.now(); ttsBookmarkSet(); }"); settle(0.5)
            rp.reload(); came = reopened(); settle(1.5)
            expect("a book open when Backchat went away opens again on its page" + F, [came, on_page(rp, at)], [True, True],
                   "a phone drops a tab in the background to save memory; coming back showed Home, not the book")
            expect("after reopening, Back to my spot shows the saved spot is there" + F, ev(rp, "()=>{ tts.on=true; ttsSetUI(); const o=document.querySelector('#tts-mark-go').style.opacity; ttsTurnOff(); return o; }"), "1",
                   "the button stayed dimmed as if nothing were saved until a spot was saved again")
            rp.evaluate("()=>closeBook()"); settle(0.4); rp.reload(); wait(rp, "document.querySelectorAll('#home-recent .card').length>0"); settle(4)
            expect("a book closed before leaving does not open again" + F, ev(rp, "()=>bcScreen()"), "home", "going back to Home is a choice the next start keeps")
            rp.evaluate("(id)=>{ localStorage.setItem('reader-last-book', id); localStorage.setItem('reader-reopen-try', '1'); }", rid)
            rp.reload(); wait(rp, "document.querySelectorAll('#home-recent .card').length>0"); settle(4)
            expect("a reopening that never finished is not tried again" + F, ev(rp, "()=>[bcScreen(), localStorage.getItem('reader-last-book')]"), ["home", None],
                   "a book that brings the tab down as it opens must not do so on every start")
            # Across devices. Read far on, then go back to reread: the desktop's sync must not undo the going back.
            rp.evaluate("(id)=>openBook(id)", rid); wait(rp, "rendition && rendition.getContents().length>0"); settle(2.5)
            rp.evaluate("()=>{ _bcInputAt=Date.now(); return bcGoTo(currentBook.id,{href:'c3.xhtml',flash:false}); }"); settle(1.5)
            far = rp.evaluate("()=>rendition.currentLocation().start.cfi")
            rp.evaluate("()=>{ _bcInputAt=Date.now(); return bcGoTo(currentBook.id,{href:'c1.xhtml',flash:false}); }"); settle(1.5); read_on(1); settle(0.6)
            back_at = rp.evaluate("()=>rendition.currentLocation().start.cfi")
            rp.evaluate("()=>closeBook()"); settle(0.4)
            rp.evaluate(OTHER, {"id": rid, "change": {"lastCfi": far, "progress": 0.9, "posAt": now_ms() - 3600000, "updated": now_ms()}}); settle(0.5)
            expect("going back to reread keeps that place when another device syncs" + F, rp.evaluate("(id)=>DB.get('meta',id).then(m=>m.lastCfi)", rid) == back_at, True,
                   "the furthest point always won, so another device's sync put the place back where it had read furthest")
            # The saved listening spot: the newest save wins, not the device that last edited anything about the book.
            spot = rp.evaluate("(id)=>DB.get('meta',id).then(m=>m.bookmarkCfi)", rid)
            rp.evaluate(OTHER, {"id": rid, "change": {"bookmarkCfi": far, "bookmarkAt": now_ms() - 7200000, "scratch": "Written on the desktop.", "updated": now_ms() + 1000}}); settle(0.5)
            expect("the newest saved listening spot wins over a device that edited the book since" + F, rp.evaluate("(id)=>DB.get('meta',id).then(m=>[m.bookmarkCfi===a, m.scratch])".replace("===a", "===" + json.dumps(spot)), rid), [True, "Written on the desktop."],
                   "a margin edit on the desktop brought back the desktop's older spot")
            # A book sitting open and untouched follows a place read since on another device; Return goes back.
            p0 = rp.evaluate("(id)=>DB.get('meta',id).then(m=>m.posAt||0)", rid)
            rp.evaluate("(id)=>openBook(id)", rid); wait(rp, "rendition && rendition.getContents().length>0"); settle(5)
            expect("opening a book does not make its place the newest" + F, [rp.evaluate("()=>currentBook.posAt||0"), rp.evaluate("(id)=>DB.get('meta',id).then(m=>m.posAt||0)", rid)], [p0, p0],
                   "only reading moves the place's time; a book opened on a device that is behind cannot outrank a newer place")
            rp.evaluate(OTHER, {"id": rid, "change": {"lastCfi": far, "progress": 0.9, "posAt": now_ms(), "updated": now_ms()}}); settle(3)
            expect("an open book untouched here moves to the place read since on another device, with Return to go back" + F,
                   [on_page(rp, far), ev(rp, "()=>{ const p=document.getElementById('bc-jumpback'); return _bcReadJump.length>0 && !!p && getComputedStyle(p).display!=='none'; }")], [True, True],
                   "the screen stayed on the old page, and turning it then made the old place the newest everywhere")
            # Reading here a moment ago: another device's place does not pull the page away.
            read_on(1); settle(0.3); mine = rp.evaluate("()=>rendition.currentLocation().start.cfi")
            rp.evaluate("()=>{ _bcInputAt=Date.now(); }")
            rp.evaluate(OTHER, {"id": rid, "change": {"lastCfi": back_at, "progress": 0.2, "posAt": now_ms() + 5000, "updated": now_ms()}}); settle(2.5)
            expect("a book being read here keeps its page when another device syncs" + F, on_page(rp, mine), True, "a page pulled away mid-read is worse than a place a moment out of date")
            if flow == "paginated":
                expect("records from before the place had a time keep the old rule, and a timed place outranks them", rp.evaluate(r"""()=>[
                    mergeMeta({progress:.2,lastCfi:'a'},{progress:.5,lastCfi:'b'}).lastCfi,
                    mergeMeta({progress:.2,lastCfi:'a',posAt:5},{progress:.5,lastCfi:'b'}).lastCfi,
                    mergeMeta({progress:.5,lastCfi:'a',posAt:5},{progress:.2,lastCfi:'b',posAt:9}).lastCfi,
                    mergeMeta({bookmarkCfi:'x',updated:1},{bookmarkCfi:'y',updated:2}).bookmarkCfi ]"""), ["b", "a", "b", "y"],
                    "furthest read between two records with no time; a device still on an older build cannot pull a timed place back; spots saved before they had a time follow the newer record")
            rctx.close()
    except Exception as e:
        expect("the place checks run to the end", str(e).splitlines()[0][:200], None, "a step above could not continue")

    # 8. Read aloud, on a phone, with a scripted voice in place of the browser's (speech_stub.js). It
    #    reads each passage once and in order, follows the voice page by page, survives pausing to mark
    #    a passage, and recovers from the ways real speech engines fail.
    actx = browser.new_context(**phone, bypass_csp=True); actx.add_init_script(path=os.path.join(HERE, "speech_stub.js"))
    ap = actx.new_page(); watch(ap, "read-aloud"); acdp = actx.new_cdp_session(ap)
    def a_swipe(x0, y0, x1, y1, steps=6, dur=0.1):
        acdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x0, "y": y0}]})
        for i in range(1, steps + 1):
            acdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x0 + (x1 - x0) * i / steps, "y": y0 + (y1 - y0) * i / steps}]}); time.sleep(dur / steps)
        acdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    def voice(**kw): ev(ap, "(o)=>Object.assign(window.__speech, o)", kw)
    def heard(): return ev(ap, "()=>__speech.log.filter(r=>!r.error && r.text.trim()).map(r=>r.text.trim())")
    def a_state(): return ev(ap, "()=>tts.state")
    def chapter(i):
        ev(ap, "()=>ttsStop()"); ev(ap, "()=>{ __speech.log=[]; __speech.cancels=0; }")
        # the chapter's first page (display() of the chapter already showing would not move)
        ap.evaluate("(i)=>{ const c=(rendition.getContents()||[]).filter(x=>x.sectionIndex===i)[0]; return c ? rendition.display(c.cfiFromNode(c.document.body)) : rendition.display(book.spine.spineItems[i].href); }", i); settle(1.3)
    VOICE_ON_PAGE = r"""()=>{ const ch=tts.chunks[tts.cidx]; if(!ch) return 'no voice'; return bcRangeSide(tts.contents, ttsRangeAt(ch, tts.lastChar)); }"""
    try:
        ap.goto(URL); wait(ap, "document.querySelectorAll('#home-recent .card').length>0"); settle(1)
        ap.set_input_files("#file-input", [LISTEN]); wait(ap, "DB.count('meta').then(n=>window.__an=n), window.__an>=2", 30000); settle(1)
        ap.evaluate("()=>DB.all('meta').then(ms=>openBook(ms.filter(m=>/Listening/.test(m.title))[0].id))"); wait(ap, "rendition && rendition.getContents().length>0"); settle(2)

        voice(cps=900, mode="boundary"); chapter(1); ev(ap, "()=>ttsStart()"); settle(2.5)
        got = heard(); got = got[:got.index("Trailing image")] if "Trailing image" in got else got
        expect("read aloud reads each passage once, in order", got,
               ["Structure", "Opening line with a note marker right here.", "Quoted first paragraph.", "Quoted second paragraph.", "List item paragraph.", "Plain list item", "Nested item.",
                "A paragraph written as a div.", "Table cell one.", "Table cell two.", "A line of verse\nbroken by a line break.", "Closing line of structure.", "The footnote text itself."],
               "a quote or a list item was read twice, text in divs and tables was skipped, hidden text and note numbers were read, verse lines ran together")
        voice(cps=900); chapter(2); ev(ap, "()=>ttsStart()"); settle(3)
        got = heard()
        expect("a chapter that ends in a picture carries on into the next chapter", [got.count("Image chapter paragraph 0 says something about river."), "The final chapter begins here." in got], [1, True],
               "a page turn at the end landed on the picture and the chapter was read again from the top, for ever")
        voice(cps=150); chapter(0); ap.evaluate("()=>rendition.next()"); settle(0.8)
        first = ev(ap, r"""()=>{ const c=rendition.getContents()[0]; for(const k of buildChunks(c)) for(const s of k.sentences) if(bcRangeSide(c,s.range)===0) return s.range.toString().slice(0,40); return null; }""")
        ev(ap, "()=>ttsStart()"); settle(0.6)
        expect("play starts with the first sentence on the page you see", ((heard() or [""])[0])[:40], first, "it started with the paragraph begun on the page before, so you heard words you could not see")
        for mode in ["boundary", "none"]:
            voice(cps=200, mode=mode); chapter(0)
            ev(ap, r"""()=>{ window.__lag={on:0,off:0}; clearInterval(window.__lagT); window.__lagT=setInterval(()=>{ try{ if(tts.state!=='playing'||!speechSynthesis.speaking) return; const s=bcRangeSide(tts.contents, ttsRangeAt(tts.chunks[tts.cidx], tts.lastChar)); if(s===0) __lag.on++; else __lag.off++; }catch(e){} },50); }""")
            ev(ap, "()=>ttsStart()"); settle(5)
            lag = ev(ap, "()=>{ clearInterval(window.__lagT); return [__lag.off, __lag.on>40, (rendition.currentLocation().start.displayed||{}).page>1]; }")
            expect("the page turns with the voice, word by word (%s)" % ("a voice that reports words" if mode == "boundary" else "a voice that reports none"), lag, [0, True, True],
                   "the word being spoken was off the page; voices that report no words turned the page late")
        voice(cps=60, mode="boundary"); chapter(0); ev(ap, "()=>ttsStart()"); settle(2.6)
        ev(ap, "()=>ttsPlayPause()"); settle(0.3)
        was = ev(ap, "()=>{ const ch=tts.chunks[tts.cidx]; return ch.text.slice(ch.sentences[tts.curSentIdx].cStart, ch.sentences[tts.curSentIdx].cEnd).trim().slice(0,40); }")
        awake = ev(ap, "()=>__speech.wake.held")
        ev(ap, r"""()=>{ const c=rendition.getContents()[0]; const r=findQuoteRange(c,secTextMap(c),'Paragraph 0 opens'); const s=c.window.getSelection(); s.removeAllRanges(); s.addRange(r); }"""); settle(0.8)
        ev(ap, "()=>document.querySelector('#sel-pop .sw').click()"); settle(0.5)
        ev(ap, "()=>{ const h=highlights.filter(x=>!x.deleted).slice(-1)[0]; editExistingNote(h.id); }"); settle(0.3)
        ap.keyboard.type("Noted while listening"); ev(ap, "()=>document.querySelector('#note-save').click()"); settle(0.5)
        ev(ap, "()=>{ __speech.log=[]; ttsPlayPause(); }"); settle(0.4)
        expect("pause, highlight and comment, then play picks up at the start of the sentence", [awake, ((heard() or [""])[0])[:40], ev(ap, "()=>highlights.some(h=>h.note==='Noted while listening')")], [True, was, True],
               "the screen may not sleep during a pause, and play must not restart mid-sentence or mid-word")
        voice(cps=80); chapter(0)
        ev(ap, r"""()=>{ const c=rendition.getContents()[0]; tts.contents=c; tts.chunks=buildChunks(c); let k=0; for(let i=0;i<tts.chunks.length;i++) if(bcRangeSide(c,tts.chunks[i].range)===0) k=i; tts.cidx=k; tts.state='playing'; ensureAudioBar(); ttsSetUI(); speakChunk(0); }""")
        settle(0.5)
        ev(ap, r"""()=>{ const c=rendition.getContents()[0]; const r=findQuoteRange(c,secTextMap(c),'Paragraph 0 opens'); const s=c.window.getSelection(); s.removeAllRanges(); s.addRange(r); }"""); settle(4)
        held = [ev(ap, "()=>selPopOpen()"), ev(ap, "()=>(rendition.currentLocation().start.displayed||{}).page")]
        ev(ap, "()=>{ hideSelPop(); rendition.getContents()[0].window.getSelection().removeAllRanges(); }"); settle(1.2)
        expect("selecting words while it reads keeps the page and the menu still, then the page catches up", [held, ev(ap, VOICE_ON_PAGE)], [[True, 1], 0],
               "the voice turned the page under your finger and the highlight menu vanished")
        voice(cps=60); chapter(0); ev(ap, "()=>ttsStart()"); settle(1.2)
        a_swipe(PW * 0.8, PH * 0.5, PW * 0.2, PH * 0.5); settle(0.8)
        swiped = a_state(); turned_to = ev(ap, "()=>(rendition.currentLocation().start.displayed||{}).page")
        first_there = ev(ap, r"""()=>{ const c=rendition.getContents()[0]; for(const k of buildChunks(c)) for(const s of k.sentences) if(bcRangeSide(c,s.range)===0) return s.range.toString().trim().slice(0,40); return null; }""")
        ev(ap, "()=>{ __speech.log=[]; ttsPlayPause(); }"); settle(0.8)
        expect("turning the page yourself pauses the voice; play reads from the page you turned to", [swiped, ((heard() or [""])[0])[:40], ev(ap, "()=>(rendition.currentLocation().start.displayed||{}).page")], ["paused", first_there, turned_to],
               "the voice is to start where you are reading; play used to turn back to the page where it had stopped")
        ev(ap, "()=>ttsPlayPause()"); settle(0.2); chapter_to = 3
        ap.evaluate("(i)=>bcGoTo(currentBook.id,{href:book.spine.spineItems[i].href,flash:false})", chapter_to); settle(1.3)
        ev(ap, "()=>{ __speech.log=[]; ttsPlayPause(); }"); settle(0.6)
        expect("after going to another chapter, play reads the chapter on screen", ((heard() or [""])[0])[:20], "Short end", "it read the old chapter's words aloud, unseen, while showing the new one")
        voice(cps=60, failAll=True); chapter(0); ev(ap, "()=>ttsStart()"); settle(2.5)
        expect("a voice that keeps failing pauses instead of racing through the book", [ev(ap, "()=>__speech.log.length"), a_state()], [3, "paused"], "an offline online voice flew through every paragraph")
        voice(failAll=False, swallowAfterCancelMs=40); chapter(0); ev(ap, "()=>ttsStart()"); settle(1)
        for v in [1.1, 1.2, 1.3, 1.4, 1.5, 1.4, 1.3]:
            ev(ap, "(v)=>{ const r=document.querySelector('#tts-rate'); r.value=v; r.dispatchEvent(new Event('input',{bubbles:true})); }", v); time.sleep(0.03)
        settle(0.8)
        expect("dragging the speed slider changes the voice once, without a silence", [ev(ap, "()=>__speech.cancels"), ev(ap, "()=>speechSynthesis.speaking")], [1, True],
               "every step of the drag restarted the voice, and Chrome can lose speech started right after a cancel")
        # Marking up while it reads, by touch.
        def a_touch(kind, pts): acdp.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": [{"x": x, "y": y} for x, y in pts]})
        def a_page(): return ev(ap, "()=>(rendition.currentLocation().start.displayed||{}).page")
        START_LAST_SENTENCE = r"""()=>{ const c=rendition.getContents()[0]; tts.contents=c; tts.chunks=buildChunks(c); let k=0, at=0;
            tts.chunks.forEach((ch,i)=>ch.sentences.forEach(s=>{ if(bcRangeSide(c,s.range)===0){ k=i; at=s.cStart; } })); tts.cidx=k; tts.state='playing'; ttsSetUI(); speakChunk(at); }"""
        expect("while a book is open the page itself cannot scroll", ev(ap, "()=>[getComputedStyle(document.documentElement).overflowY, getComputedStyle(document.body).overflowY]"), ["hidden", "hidden"],
               "on a phone a swipe or a selection slid the address bar away, the window resized, and the book laid itself out again mid-gesture")
        voice(cps=120, mode="boundary"); chapter(0); ev(ap, "()=>ttsStop()"); settle(0.3)
        FIT = "()=>[rendition.manager.container.clientHeight, Math.round(document.querySelector('#viewport iframe').getBoundingClientRect().height)===rendition.manager.container.clientHeight]"
        idle_fit = ev(ap, FIT)
        ev(ap, "()=>ttsStart()"); settle(1.0)
        playing_fit = ev(ap, FIT)
        ev(ap, "()=>ttsTurnOff()"); settle(1.0)
        off_fit = ev(ap, FIT)
        expect("read aloud on or off, the page keeps its size and the book fits it", [playing_fit, off_fit], [idle_fit, idle_fit],
               "the player appeared over a book laid out for the taller page, hiding the last lines; and a page laid out again for a new height moves the words you were reading")
        ev(ap, "()=>{ tts.on=true; ttsSetUI(); }")
        ev(ap, "()=>ttsStop()"); ev(ap, START_LAST_SENTENCE); settle(0.3)
        f0 = a_page(); a_touch("touchStart", [(PW * 0.5, PH * 0.5)]); settle(3.5); f1 = a_page(); a_touch("touchCancel", []); settle(0.2)
        expect("a finger on the page keeps read aloud from turning it", [f0, f1], lambda v: v[0] == v[1], "the voice turned the page while you were pressing to select")
        ev(ap, "()=>ttsStop()"); settle(0.3)
        ev(ap, r"""()=>{ const c=rendition.getContents()[0]; for(const k of buildChunks(c)) for(const s of k.sentences) if(bcRangeSide(c,s.range)===0){ const sel=c.window.getSelection(); sel.removeAllRanges(); sel.addRange(s.range); return; } }"""); settle(0.8)
        ev(ap, "()=>{ hideSelPop(); rendition.getContents()[0].window.getSelection().removeAllRanges(); }")   # a phone clears the selection as the tap begins
        d0 = a_page(); a_touch("touchStart", [(PW - 12, PH * 0.5)]); time.sleep(0.05); a_touch("touchEnd", []); settle(0.8)
        expect("a tap that dismisses a selection does not turn the page", [d0, a_page()], lambda v: v[0] == v[1], "the tap that cleared a selection near the edge also turned the page")
        settle(1.2); t0 = a_page(); a_touch("touchStart", [(PW * 0.78, PH * 0.5)]); time.sleep(0.05); a_touch("touchEnd", []); settle(0.8)
        expect("a tap on the words near the edge does not turn the page", [t0, a_page()], lambda v: v[0] == v[1], "a quarter of the text on each side turned the page, so a tap meant for the words moved on")
        ev(ap, "()=>openFind()"); settle(0.8); fh0 = ev(ap, "()=>rendition.manager.container.clientHeight")
        ev(ap, "()=>{ document.querySelector('#find-input').value='river'; doFind('river'); }"); settle(1.0)
        expect("find's matches open over the page without changing its size", [ev(ap, "()=>rendition.manager.container.clientHeight") == fh0, ev(ap, "()=>Math.round(document.querySelector('#viewport iframe').getBoundingClientRect().height)===rendition.manager.container.clientHeight")], [True, True],
               "the list of matches pushed the page up and hid its last lines")
        ev(ap, "()=>closeFind()"); settle(0.8)
        # start mid-page, so carrying on cannot be mistaken for starting again at the top of the page
        voice(cps=30); ev(ap, r"""()=>{ const c=rendition.getContents()[0]; tts.contents=c; tts.chunks=buildChunks(c); const on=[];
            tts.chunks.forEach((ch,i)=>ch.sentences.forEach(s=>{ if(bcRangeSide(c,s.range)===0) on.push([i,s.cStart]); })); const m=on[Math.min(on.length-1, 3)];
            tts.cidx=m[0]; tts.state='playing'; ttsSetUI(); speakChunk(m[1]); }"""); settle(1.5)
        said = ev(ap, "()=>{ const ch=tts.chunks[tts.cidx]; return ch.text.slice(ch.sentences[tts.curSentIdx].cStart).trim().slice(0,30); }")
        ev(ap, "()=>{ __speech.log=[]; }"); ap.set_viewport_size({"width": PW, "height": PH + 56}); settle(2.0)
        expect("when the book is laid out again while it reads, the voice carries on in its sentence", [said, ev(ap, "()=>(__speech.log.filter(r=>!r.error)[0]||{text:''}).text.trim().slice(0,30)")], lambda v: v[0] and v[0] == v[1],
               "a new layout left the voice on a page that no longer existed, so it restarted elsewhere or fell silent")
        ap.set_viewport_size({"width": PW, "height": PH}); settle(1.2); ev(ap, "()=>ttsStop()")
        voice(swallowAfterCancelMs=0, cps=40, mode="none", stallAfterMs=700); chapter(0); ev(ap, "()=>{ tts.cps=40; ttsStart(); }")
        # the heading is over before the engine stalls; the first paragraph is not
        stall = None; t_end = time.time() + 20
        while time.time() < t_end:
            log = ev(ap, "()=>__speech.log.map(r=>[r.text.slice(0,30), r.t])") or []
            k = next((i for i, r in enumerate(log) if len(r[0]) >= 30), None)
            if k is not None and len(log) > k + 1:
                stall = [log[k + 1][0] == log[k][0], round((log[k + 1][1] - log[k][1]) / 1000)]; break
            time.sleep(0.25)
        voice(stallAfterMs=0)
        expect("an engine that goes silent mid-sentence is noticed, and the voice repeats that sentence", [stall and stall[0], stall and stall[1] <= 12], [True, True],
               "Chrome's online voices can stop with no end and no error; the watchdog only looked for a stopped engine (got %s)" % stall)
        ev(ap, "()=>ttsStop()")

        # 8b. The read aloud switch: the speaker in the top bar. Off when a book opens. On reads from
        #     where you are, and the player takes the progress row's place; off pauses, keeps the
        #     voice's place, and nothing on the page moves. The voice always starts where you are reading.
        FIRST_ON_PAGE = r"""()=>{ const c=rendition.getContents()[0]; for(const k of buildChunks(c)) for(const s of k.sentences) if(bcRangeSide(c,s.range)===0) return s.range.toString().trim().slice(0,40); return null; }"""
        SWITCH = r"""()=>{ const b=document.querySelector('#tts-btn'), on=b.querySelector('.ic-on'); return [getComputedStyle(b).display!=='none', b.getAttribute('aria-pressed'), on ? getComputedStyle(on).display : 'no on-icon',
            !document.querySelector('#audiobar').classList.contains('hidden'), getComputedStyle(document.querySelector('.botbar')).display!=='none']; }"""
        HEIGHT = "()=>rendition.manager.container.clientHeight"
        def flip(): ap.tap("#tts-btn", timeout=4000)
        def voice_at(): return ev(ap, "()=>{ const ch=tts.chunks[tts.cidx]; return ch ? ch.text.slice(tts.resumeAt||0).trim().slice(0,40) : null; }")
        def select_on_page(k):
            return ev(ap, r"""(k)=>{ const c=rendition.getContents()[0]; const on=[]; for(const x of buildChunks(c)) for(const s of x.sentences) if(bcRangeSide(c,s.range)===0) on.push(s.range);
                const r=on[Math.max(0, Math.min(on.length-1, k<0 ? on.length+k : k))]; const sel=c.window.getSelection(); sel.removeAllRanges(); sel.addRange(r); return r.toString().trim().slice(0,40); }""", k)
        def a_page(): return ev(ap, "()=>(rendition.currentLocation().start.displayed||{}).page")
        voice(cps=40, mode="boundary", stallAfterMs=0, failAll=False, swallowAfterCancelMs=0)
        ev(ap, "()=>closeBook()"); settle(0.4)
        ap.evaluate("()=>DB.all('meta').then(ms=>openBook(ms.filter(m=>/Listening/.test(m.title))[0].id))"); wait(ap, "rendition && rendition.getContents().length>0"); settle(2)
        chapter(0)
        ev(ap, "()=>{ delete currentBook.voiceCfi; delete currentBook.voiceAt; }")   # a book never listened to: the earlier checks read this one
        expect("the speaker in the top bar is the read aloud switch: there from the start, off, and no switch in Display", ev(ap, SWITCH) + [ev(ap, "()=>!!document.querySelector('#seg-tts')")], [True, "false", "none", False, True, False],
               "read aloud was switched on in Display, below the bottom of the panel on a phone, and the speaker only started and stopped it")
        h0 = ev(ap, HEIGHT); first = ev(ap, FIRST_ON_PAGE)
        ev(ap, "()=>{ __speech.log=[]; }"); flip(); settle(2.0)
        expect("switched on, it reads from the top of the page, and the player takes the progress row's place", [((heard() or [""])[0])[:40], ev(ap, SWITCH)[1:], ev(ap, HEIGHT)], [first, ["true", "block", True, False], h0],
               "on is shown by shape (sound waves on a solid button), and the page must keep its size")
        top = ev(ap, FIRST_ON_PAGE); flip(); settle(0.8); said = voice_at(); n = len(heard() or []); settle(1.2)
        expect("switched off, the voice pauses, the player goes, and nothing on the page moves", [a_state(), len(heard() or []) == n, ev(ap, SWITCH)[1:], ev(ap, FIRST_ON_PAGE), ev(ap, HEIGHT)], ["paused", True, ["false", "none", False, True], top, h0],
               "a page laid out again for a new height re-flows the chapter, so the passage you meant to mark could move or slip to another page")
        select_on_page(0); settle(0.8)
        ev(ap, "()=>document.querySelector('#sel-pop .sw').click()"); settle(0.5)
        ev(ap, "()=>{ const h=highlights.filter(x=>!x.deleted).slice(-1)[0]; editExistingNote(h.id); }"); settle(0.3)
        ap.keyboard.type("Marked with read aloud off"); ev(ap, "()=>document.querySelector('#note-save').click()"); settle(0.5)
        ev(ap, "()=>{ __speech.log=[]; }"); flip(); settle(1.5)
        expect("off, highlight and comment, on: the voice carries on from the sentence where it stopped", [((heard() or [""])[0])[:40], ev(ap, "()=>highlights.some(h=>h.note==='Marked with read aloud off')")], [said, True],
               "stopping forgot the voice's place, so it started again at the top of the page")
        flip(); settle(0.8)
        a_swipe(PW * 0.8, PH * 0.5, PW * 0.2, PH * 0.5); settle(1.0)
        p_on = a_page(); first = ev(ap, FIRST_ON_PAGE); ev(ap, "()=>{ __speech.log=[]; }"); flip(); settle(1.5)
        expect("off, read on a page, on: the voice starts at the top of the page you are on", [((heard() or [""])[0])[:40], a_page()], [first, p_on],
               "where you are reading is where the voice goes on from, not back where it stopped")
        flip(); settle(0.8)
        marked = select_on_page(-2); settle(0.8); ev(ap, "()=>document.querySelector('#sel-pop .sw').click()"); settle(0.6)
        ev(ap, "()=>{ __speech.log=[]; }"); flip(); settle(1.5)
        expect("off, mark a passage further down the page, on: the voice starts at the passage you marked", ((heard() or [""])[0])[:40], marked,
               "you read on to the passage you marked; going back to where the voice stopped repeats what you have read")
        flip(); settle(0.8); ev(ap, "()=>{ __speech.log=[]; }")
        a_touch("touchStart", [(PW * 0.5, PH * 0.45)]); time.sleep(0.05); a_touch("touchEnd", []); settle(1.2)
        expect("with read aloud off, a tap on the words never starts the voice", [a_state(), heard()], ["paused", []], "a tap meant for marking moved the voice and set it talking")
        flip(); settle(2.0); flip(); settle(0.8); said = voice_at()
        ev(ap, "()=>closeBook()"); settle(0.4)
        ap.evaluate("()=>DB.all('meta').then(ms=>openBook(ms.filter(m=>/Listening/.test(m.title))[0].id))"); wait(ap, "rendition && rendition.getContents().length>0"); settle(2.5)
        ev(ap, "()=>{ __speech.log=[]; }"); flip(); settle(1.5)
        expect("the voice's place stays with the book: reopened and switched on, it carries on from its sentence", [ev(ap, SWITCH)[1], ((heard() or [""])[0])[:40]], ["true", said],
               "the place lived only while the book was open, so tomorrow's listening started again at the top of the page")
        flip(); settle(0.5)
        ev(ap, "()=>setReadFlow('scrolled')"); settle(3)
        for _ in range(3): a_swipe(PW * 0.5, PH * 0.75, PW * 0.5, PH * 0.3); settle(0.3)   # read on by finger, as a reader scrolls
        settle(1.2)
        h1 = ev(ap, HEIGHT); first = ev(ap, FIRST_ON_PAGE)
        ev(ap, "()=>{ __speech.log=[]; }"); flip(); settle(1.5); playing_h = ev(ap, HEIGHT); how = ev(ap, "()=>[tts.state, __speech.log.length]"); said_first = ((heard() or [""])[0])[:40]
        flip(); settle(0.8)
        expect("scroll mode: switched on, it reads from the first sentence in view, and the view keeps its size", [said_first, playing_h, ev(ap, HEIGHT), how[0] if isinstance(how, list) else how], [first, h1, h1, "playing"],
               "the voice starts where you are reading in scroll mode too (voice state, utterances: %s)" % (how,))
        ev(ap, "()=>setReadFlow('paginated')"); settle(1.5)
        expect("the voice's place syncs, the newest wins", ev(ap, r"""()=>[mergeMeta({voiceCfi:'a',voiceAt:5},{voiceCfi:'b',voiceAt:9}).voiceCfi, mergeMeta({voiceCfi:'a',voiceAt:9},{voiceCfi:'b',voiceAt:5}).voiceCfi]"""), ["b", "a"],
               "switch on at the desktop and carry on from where the phone stopped, when the desktop shows that page")
    except Exception as e:
        expect("the read-aloud checks run to the end", str(e).splitlines()[0][:200], None, "a step above could not continue")
    actx.close()
    browser.close()

httpd.shutdown()
expect("no page errors", page_errors, [], "uncaught errors and console errors")
expect("no failed or stray requests", bad_requests, [], "every request the page makes must succeed")

failed = [r for r in results if not r[1]]
for name, ok, got, want, why in results:
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else "\n      expected %s, got %s  (%s)" % (json.dumps(want), json.dumps(got)[:400], why)))
print("\n%d of %d checks passed." % (len(results) - len(failed), len(results)))
sys.exit(1 if failed else 0)
