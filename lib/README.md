# Libraries

Backchat runs four open-source libraries. They are stored here, in this repository, so the app depends on no outside server for its code and runs only code that has been read and published with it. The page's security policy refuses any script loaded from another site, so a new library must be added here, never linked from a CDN.

| File | Library | Version | Licence |
|---|---|---|---|
| `jszip.min.js` | JSZip | 3.10.1 | MIT or GPL-3.0, at your choice ([LICENSE-jszip.md](LICENSE-jszip.md)) |
| `epub.min.js` | epub.js | 0.3.93 | BSD-2-Clause ([LICENSE-epubjs.txt](LICENSE-epubjs.txt)) |
| `minisearch.js` | MiniSearch | 7.2.0 | MIT ([LICENSE-minisearch.txt](LICENSE-minisearch.txt)) |
| `goatcounter.js` | GoatCounter count.js (page-view count) | v5 | ISC ([LICENSE-goatcounter.txt](LICENSE-goatcounter.txt)) |

The first three are the published builds from the npm registry, unchanged, checked against the registry's integrity hash. `goatcounter.js` is GoatCounter's pinned `count.v5.js`, unchanged, checked against the integrity hash GoatCounter publishes for it (`sha384-atnOLvQb9t+jTSipvd75X2yginT4PjVbqDdlJAmxMm+wYElFmeR6EmLP5bYeoRVQ`).
