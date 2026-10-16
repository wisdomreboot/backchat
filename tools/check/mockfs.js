// In-memory stand-in for the File System Access API, for tools/check/check.py.
// mkDir(name, caseInsensitive) behaves like a folder on a macOS or Windows disk when the flag is set.
window.mkFile=function(name){
  let data=new Blob([]);
  const f={kind:"file", name:name,
    async getFile(){ return new File([data], f.name, {lastModified: 1}); },
    async createWritable(){ const parts=[]; return { async write(c){ parts.push(c); }, async close(){ data=new Blob(parts); }, async abort(){} }; } };
  return f;
};
window.mkDir=function(name, ci){
  const entries=new Map(); const key=n=>ci?n.toLowerCase():n;
  return { kind:"directory", name:name,
    async getDirectoryHandle(n,o){ let e=entries.get(key(n)); if(!e){ if(!(o&&o.create)) throw new DOMException("not found","NotFoundError"); e={name:n,kind:"directory",obj:mkDir(n,ci)}; entries.set(key(n),e); } return e.obj; },
    async getFileHandle(n,o){ let e=entries.get(key(n)); if(!e){ if(!(o&&o.create)) throw new DOMException("not found","NotFoundError"); e={name:n,kind:"file",obj:mkFile(n)}; entries.set(key(n),e); } return e.obj; },
    async removeEntry(n){ if(!entries.delete(key(n))) throw new DOMException("not found","NotFoundError"); },
    async *values(){ for(const e of [...entries.values()]) yield e.obj; },
    async queryPermission(){ return "granted"; }, async requestPermission(){ return "granted"; } };
};
