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

TMP = tempfile.mkdtemp(prefix="backchat-check-")
ALPHA, BETA = os.path.join(TMP, "alpha.epub"), os.path.join(TMP, "beta.epub")
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


with sync_playwright() as p:
    browser = p.chromium.launch()

    # 1. The real security policy is enforced: boot must run with no violation, no error,
    #    and no stray request (a look-ahead fetch of a URL half-written in a script).
    for i in range(6):
        ctx = browser.new_context(); pg = ctx.new_page()
        notes = []
        pg.on("console", lambda m: notes.append(m.text) if m.type in ("error", "warning") else None)
        pg.on("pageerror", lambda e: notes.append(str(e)))
        pg.on("request", lambda r: notes.append("stray request " + r.url) if "'" in r.url else None)
        pg.goto(URL); pg.wait_for_selector("#home-recent .card", timeout=20000); settle(0.5)
        if notes or i == 0:
            expect("boot under the security policy, run %d" % (i + 1), notes, [], "the page must boot cleanly with its Content-Security-Policy on")
        ctx.close()

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

    # 3. Folder sync against an in-memory, case-insensitive folder (how macOS and Windows disks behave).
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
