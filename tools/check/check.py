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
    sp.evaluate("()=>{ settings.tts=true; saveSettings(); syncTtsControls(); }")
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
        gp.evaluate("()=>{ settings.tts=true; saveSettings(); }")
        gp.evaluate("()=>DB.all('meta').then(ms=>openBook(ms.filter(m=>/Long Landing/.test(m.title))[0].id))"); wait(gp, "rendition && rendition.getContents().length>0"); settle(2.5)
        gp.evaluate("()=>rendition.next()"); settle(0.8)
        paged = ev(gp, INSET)
        gp.evaluate("()=>document.querySelector('#seg-tts [data-tts=off]').click()"); settle(1.5)
        paged_off = ev(gp, INSET)
        expect("a page keeps its margins and spacing when read aloud is switched off", [paged_off.get(k) for k in ("left", "lh", "cut")], [paged.get(k) for k in ("left", "lh", "cut")],
               "the player going away lays the book out again for the taller page; the text's width and spacing must not change with it")
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
            rp.evaluate("(f)=>{ settings.flow=f; settings.tts=true; saveSettings(); }", flow)
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
            expect("after reopening, Back to my spot shows the saved spot is there" + F, ev(rp, "()=>document.querySelector('#tts-mark-go').style.opacity"), "1",
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
    def heard(): return ev(ap, "()=>__speech.log.filter(r=>!r.error).map(r=>r.text.trim())")
    def a_state(): return ev(ap, "()=>tts.state")
    def chapter(i):
        ev(ap, "()=>ttsStop()"); ev(ap, "()=>{ __speech.log=[]; __speech.cancels=0; }")
        # the chapter's first page (display() of the chapter already showing would not move)
        ap.evaluate("(i)=>{ const c=(rendition.getContents()||[]).filter(x=>x.sectionIndex===i)[0]; return c ? rendition.display(c.cfiFromNode(c.document.body)) : rendition.display(book.spine.spineItems[i].href); }", i); settle(1.3)
    VOICE_ON_PAGE = r"""()=>{ const ch=tts.chunks[tts.cidx]; if(!ch) return 'no voice'; return bcRangeSide(tts.contents, ttsRangeAt(ch, tts.lastChar)); }"""
    try:
        ap.goto(URL); wait(ap, "document.querySelectorAll('#home-recent .card').length>0"); settle(1)
        ap.set_input_files("#file-input", [LISTEN]); wait(ap, "DB.count('meta').then(n=>window.__an=n), window.__an>=2", 30000); settle(1)
        ap.evaluate("()=>{ settings.tts=true; saveSettings(); syncTtsControls(); }")
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
        swiped = a_state(); ev(ap, "()=>{ __speech.log=[]; ttsPlayPause(); }"); settle(0.8)
        expect("turning the page yourself pauses the voice; play takes you back to it", [swiped, ev(ap, VOICE_ON_PAGE)], ["paused", 0], "a swipe stopped read aloud and lost its place")
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
        idle_fit = ev(ap, "()=>[!document.querySelector('#audiobar').classList.contains('hidden'), Math.round(document.querySelector('#viewport iframe').getBoundingClientRect().height)===rendition.manager.container.clientHeight]")
        ev(ap, "()=>ttsStart()"); settle(1.0)
        playing_fit = ev(ap, "()=>Math.round(document.querySelector('#viewport iframe').getBoundingClientRect().height)===rendition.manager.container.clientHeight")
        expect("with read aloud on, the player stays and the book always fits the space above it", [idle_fit, playing_fit], [[True, True], True],
               "the player appeared over a book laid out for the taller page, hiding the last lines of every page")
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
