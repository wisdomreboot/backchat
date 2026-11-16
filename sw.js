/* Backchat: start without a connection.

   Everything a reader has is on the device, but the page itself used to come from the network
   each time: with no signal there was no Backchat. This worker keeps the page, its libraries
   and the guide in a cache on the device.

   The network is always asked first, so a new build is used as soon as it is published and two
   devices never run different builds for long. The cache answers only when the network does
   not (no signal, the host is down or failing) or takes more than a few seconds.

   Only the files named in SHELL are its business. Everything else goes to the network as it
   always has: the relay, a book's images, YouTube, and any other file of this site.

   When the page that arrives from the host is not the one kept, the rest of the list is fetched
   again behind it. The copy kept is then one build, never a new page beside an old library.

   To change what is kept, or how: raise the number in CACHE. The old cache is then dropped.
   To retire the worker: publish a sw.js that unregisters itself (self.registration.unregister()
   in its activate handler). Deleting this file is not enough: a browser that cannot fetch a
   newer worker keeps the one it has. */
var CACHE = "backchat-shell-1";
var SLOW_MS = 4000;
var SHELL = [
  "index.html",
  "lib/jszip.min.js", "lib/epub.min.js", "lib/minisearch.js", "lib/codemirror.js", "lib/goatcounter.js",
  "guide/guide.md", "guide/cover.jpg",
  "manifest.webmanifest", "icon.svg", "icon-192.png", "icon-512.png", "favicon.ico", "apple-touch-icon.png"
];
var ROOT = new URL("./", self.location).pathname;
var KEPT = {};
SHELL.forEach(function (path) { KEPT[ROOT + path] = path; });

// A response that came by a redirect cannot answer a page load: keep a plain copy of it.
function plain(res) {
  if (!res.redirected) return Promise.resolve(res);
  return res.blob().then(function (body) {
    return new Response(body, { status: res.status, statusText: res.statusText, headers: res.headers });
  });
}
// Fetch one file of the list from the host, past the browser's own cache, and keep it.
// A file that is missing must not stop the rest from being kept.
function keep(cache, path) {
  return fetch(new Request(path, { cache: "reload" })).then(function (res) {
    if (res && res.ok) return plain(res).then(function (copy) { return cache.put(path, copy); });
  }).catch(function () {});
}
function keepAll(but) {
  return caches.open(CACHE).then(function (cache) {
    return Promise.all(SHELL.filter(function (path) { return path !== but; }).map(function (path) { return keep(cache, path); }));
  });
}
// Which copy of a file this is, as the host tells it.
function stamp(res) {
  return res ? String(res.headers.get("etag") || res.headers.get("last-modified") || "").replace(/^W\//, "") : "";
}

self.addEventListener("install", function (e) {
  e.waitUntil(keepAll().then(function () { return self.skipWaiting(); }));
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k.indexOf("backchat-shell-") === 0 && k !== CACHE; })
      .map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener("fetch", function (e) {
  var req = e.request;
  if (req.method !== "GET") return;
  var url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  // Every way of asking for the page (the bare address, index.html, either with a query) is the page.
  var page = req.mode === "navigate" && (url.pathname === ROOT || url.pathname === ROOT + "index.html");
  var key = page ? "index.html" : KEPT[url.pathname];
  if (!key) return;
  e.respondWith(answer(e, req, key));
});

function answer(e, req, key) {
  return caches.open(CACHE).then(function (cache) {
    var kept = function () { return cache.match(key, { ignoreSearch: true }); };
    var net = fetch(req).then(function (res) {
      if (res && res.ok && res.type === "basic") {
        var copy = res.clone();
        var done = kept().then(function (old) {
          // A page that is not the one kept is a new build: the rest of the list follows it.
          var newer = key === "index.html" && !!old && !!stamp(copy) && stamp(copy) !== stamp(old);
          return cache.put(key, copy).then(function () { if (newer) return keepAll("index.html"); });
        }).catch(function () {});
        try { e.waitUntil(done); } catch (_e) {}     // already answered from the copy kept: the work goes on all the same
      }
      return res;
    });
    // The network's answer, unless it fails, the host is failing, or it is slow and a copy is kept.
    var quick = net.then(function (res) { return (res && res.status < 500) ? res : null; }, function () { return null; });
    var slow = new Promise(function (resolve) { setTimeout(resolve, SLOW_MS); }).then(kept);
    return Promise.race([quick, slow]).then(function (first) {
      if (first) return first;
      return kept().then(function (hit) { return hit || net; });
    });
  });
}
