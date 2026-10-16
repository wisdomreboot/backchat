#!/usr/bin/env python3
"""Backchat regression check.

Drives the real page in headless Chromium and checks the behaviours that have broken
before: data that must never be lost, deletes that must stick, the security policy,
search, exports and folder sync. Run it before merging any change to index.html.

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
def make_epub(path, title, author, ident, chapters):
    z = zipfile.ZipFile(path, "w")
    z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
    z.writestr("META-INF/container.xml", '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
    man = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>']; spine = []; nav = []
    for i, (lab, paras) in enumerate(chapters):
        body = "".join("<p>%s</p>" % p for p in paras)
        z.writestr("OEBPS/c%d.xhtml" % i, '<?xml version="1.0" encoding="utf-8"?><!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml"><head><title>%s</title></head><body><h1>%s</h1>%s</body></html>' % (lab, lab, body))
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
    expect("margins keep numbers and links", ev(page, """(()=>{ const h=scratchHtml('Numbers 42 and 1984 stay. '+bcMakeToken({bookKey:'id:x',kind:'book'})); return /42/.test(h) && /1984/.test(h) && /bc-ref/.test(h); })()"""), True, "the token sentinels must not eat digits")

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
    browser.close()

httpd.shutdown()
expect("no page errors", page_errors, [], "uncaught errors and console errors")
expect("no failed or stray requests", bad_requests, [], "every request the page makes must succeed")

failed = [r for r in results if not r[1]]
for name, ok, got, want, why in results:
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else "\n      expected %s, got %s  (%s)" % (json.dumps(want), json.dumps(got)[:400], why)))
print("\n%d of %d checks passed." % (len(results) - len(failed), len(results)))
sys.exit(1 if failed else 0)
