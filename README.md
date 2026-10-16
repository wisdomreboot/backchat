# Backchat

**Talk back to your books.** A local-first EPUB reader for highlights, comments, margins and reading position, with your library kept in a folder you own.

Open it at **https://backchat.jonathandutoit.com**

## What it is

Backchat is one HTML page and four open-source libraries, all served from this repository. Everything runs in your browser: there is no server, no account and no cookies. The page talks to the outside world only to count a page view (see below), to play a video in a transcript book (from YouTube), to show a cover or image that a book or note links to on the web, and, if you turn it on, to sync with your own relay. Your books and notes live in your browser's storage and, if you connect one, in a folder on your computer as ordinary EPUB and Markdown files, which works well with Obsidian.

- Highlight, comment and write in the margins of any EPUB
- Search across every book, your marks, and the full text inside books
- Copy links to an exact passage
- Read aloud
- Hand off notes between devices by file, or sync them automatically through a relay you own (see below)

What changed in each build: [CHANGELOG.md](CHANGELOG.md).

## Page-view count

Each time the page opens, it tells [GoatCounter](https://www.goatcounter.com), a cookie-free counting service, that it was opened. It sends the page address (never anything after `#`, where location links and sync setup links live), the site you came from, the page title and your screen size. Nothing about your books, notes, folder or sync is sent, and nothing is stored on your device to recognise you. GoatCounter receives your IP address and browser name with the request, as every website does; it says it holds them only in memory, for up to 8 hours, to tell one visit from the next, and never writes them to disk.

The count does not run on your own computer's addresses (localhost and the like), and you can switch it off in any browser by opening the page once with `#toggle-goatcounter` at the end of its address.

## Sync between devices (optional)

Backchat can keep your phone and computer in step through a small relay you set up yourself: a free Cloudflare Worker. Your notes are encrypted on your device with a passphrase that never leaves it, so the relay only stores scrambled data. Each person runs their own relay; nothing is shared with anyone else, including the author.

Setup takes about 15 minutes in a browser: [docs/SYNC-SETUP.md](docs/SYNC-SETUP.md). The relay code is in [worker/](worker/).

## Host your own copy

Fork this repository and turn on GitHub Pages, or copy its files to any static host, keeping `lib/` beside `index.html`. Nothing else is needed. If you change any inline script in `index.html`, run `python3 tools/csp.py index.html` to refresh the security policy, or the browser will refuse to run the edited script. Before merging any change, run `python3 tools/check/check.py`: it drives the page in a headless browser and checks the behaviours that must never break, such as marks and margins that must not be lost and deletes that must stick. The same check runs on every pull request. If you host it elsewhere, change the address in the page's `canonical`, `og:url` and `og:image` tags, and in `robots.txt` and `sitemap.xml`, and change or remove the `data-goatcounter` address in `index.html`, or your visitors are counted on mine.

## Security

The page runs only code published in this repository. A security policy in the page tells the browser to refuse any other script, and book content is shown in a sandbox with its scripts stripped. See [SECURITY.md](SECURITY.md) for what Backchat can and cannot reach, and how to report a problem.

## The deal

I built Backchat for my own reading and share it as is. There is no support, no roadmap and no promise of anything. Keep your folder backed up. Issues and suggestions may be read, and may not be answered.

I write about reading, decisions and building tools like this at [jonathandutoit.com](https://jonathandutoit.com).

## Licence

MIT, see [LICENSE](LICENSE). The libraries in [lib/](lib/) keep their own licences: JSZip (MIT or GPL-3.0, used under MIT), epub.js (BSD), MiniSearch (MIT), GoatCounter's count.js (ISC).
