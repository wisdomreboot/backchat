// In-memory stand-in for the File System Access API, for tools/check/check.py.
// It behaves like a real disk where sync depends on it: real modification times, case-insensitive
// names when mkDir(name, true) (macOS and Windows disks), permission that can lapse (__fs.perm), a
// folder that can vanish (__fs.gone), and a log of every create, write and remove (__fs.log).
// B holds helpers for checks: B.init() connects a fresh folder, B.put/putB64/rm/text/ls handle
// files by path, B.mark() and B.log() count what a sync wrote, B.dump()/B.load() hand a whole
// folder to another browser, as a cloud client would.
(function(){
  const S = window.__fs = { log: [], perm: "granted", permReq: "granted", gone: false };
  function gate(){ if(S.gone) throw new DOMException("The folder is gone", "NotFoundError"); }
  function canWrite(){ if(S.perm !== "granted") throw new DOMException("Permission withdrawn", "NotAllowedError"); }
  window.mkFile = function(name, path){
    let data = new Blob([]), mtime = Date.now();
    const f = { kind: "file", name: name, _path: path,
      async getFile(){ gate(); return new File([data], f.name, { lastModified: mtime }); },
      async createWritable(){ gate(); canWrite(); const parts = [];
        return { async write(c){ parts.push(c); }, async close(){ data = new Blob(parts); mtime = Date.now(); S.log.push(["w", path]); }, async abort(){} }; },
      _set(bytes, mt){ data = new Blob([bytes]); mtime = mt || Date.now(); } };
    return f;
  };
  window.mkDir = function(name, ci, path){
    path = path || name;
    const entries = new Map(); const key = n => ci ? n.toLowerCase() : n;
    return { kind: "directory", name: name, _path: path, _entries: entries,
      async getDirectoryHandle(n, o){ gate(); let e = entries.get(key(n));
        if(!e){ if(!(o && o.create)) throw new DOMException("not found", "NotFoundError"); e = { name: n, kind: "directory", obj: mkDir(n, ci, path + "/" + n) }; entries.set(key(n), e); }
        if(e.kind !== "directory") throw new DOMException("not a folder", "TypeMismatchError"); return e.obj; },
      async getFileHandle(n, o){ gate(); let e = entries.get(key(n));
        if(!e){ if(!(o && o.create)) throw new DOMException("not found", "NotFoundError"); canWrite(); e = { name: n, kind: "file", obj: mkFile(n, path + "/" + n) }; entries.set(key(n), e); S.log.push(["c", path + "/" + n]); }
        if(e.kind !== "file") throw new DOMException("not a file", "TypeMismatchError"); return e.obj; },
      async removeEntry(n){ gate(); canWrite(); if(!entries.delete(key(n))) throw new DOMException("not found", "NotFoundError"); S.log.push(["r", path + "/" + n]); },
      async *values(){ gate(); for(const e of [...entries.values()]) yield e.obj; },
      async queryPermission(){ return S.perm; }, async requestPermission(){ return S.permReq; } };
  };
  // Bench helpers.
  window.B = {
    root: null,
    init(){ this.root = mkDir("root", true, "root"); vault.handle = this.root; vault.connected = true; vault.needsReauth = false; S.log.length = 0; return true; },
    async dir(p){ let d = this.root; for(const s of p.split("/").filter(Boolean)) d = await d.getDirectoryHandle(s, { create: true }); return d; },
    async put(p, data, mtime){ const parts = p.split("/"), name = parts.pop(), d = await this.dir(parts.join("/")); const fh = await d.getFileHandle(name, { create: true }); fh._set(data, mtime); return true; },
    async putB64(p, b64, mtime){ return this.put(p, Uint8Array.from(atob(b64), c => c.charCodeAt(0)), mtime); },
    async rm(p){ const parts = p.split("/"), name = parts.pop(), d = await this.dir(parts.join("/")); await d.removeEntry(name); return true; },
    async text(p){ const parts = p.split("/"), name = parts.pop(), d = await this.dir(parts.join("/")); return await (await (await d.getFileHandle(name)).getFile()).text(); },
    async ls(sub){ const out = {}; async function walk(d, pre){ for await (const e of d.values()){ if(e.kind === "directory") await walk(e, pre + e.name + "/"); else out[pre + e.name] = (await e.getFile()).size; } } await walk(sub ? await this.dir(sub) : this.root, sub ? sub + "/" : ""); return out; },
    mark(){ S.log.length = 0; return true; },
    log(kind){ return S.log.filter(x => !kind || x[0] === kind).map(x => x[1].replace(/^root\//, "")); },
    async quiet(ms){ ms = ms || 900; let n = -1, still = 0; for(let i = 0; i < 400; i++){ await new Promise(r => setTimeout(r, 100)); if(S.log.length === n){ still += 100; if(still >= ms) break; } else { n = S.log.length; still = 0; } } return S.log.length; },
    async lib(){ const m = await DB.all("meta"), h = await DB.all("highlights"), bl = await DB.keys("blob"), hm = {}; h.forEach(x => hm[x.id] = x); const has = {}; bl.forEach(k => has[k] = 1);
      return m.map(x => ({ id: x.id, title: x.title, key: bookKeyOf(x), marks: ((hm[x.id] || {}).items || []).filter(i => !i.deleted).length, blob: !!has[x.id] })); },
    async tomb(){ return await loadTombstones(); },
    // the whole folder as {path: base64}, and back: two browsers sharing one cloud-synced folder
    async dump(){ const out={}; async function walk(d, pre){ for await (const e of d.values()){ if(e.kind==="directory") await walk(e, pre+e.name+"/"); else { const b=new Uint8Array(await (await e.getFile()).arrayBuffer()); let s=""; for(let i=0;i<b.length;i+=8192) s+=String.fromCharCode.apply(null, b.subarray(i, i+8192)); out[pre+e.name]=btoa(s); } } } await walk(this.root, ""); return out; },
    async load(map){ this.root._entries.clear(); for(const p of Object.keys(map)) await this.putB64(p, map[p]); vault.handle=this.root; S.log.length=0; return Object.keys(map).length; }
  };
})();
