# Backchat

**Talk back to your books.** A local-first EPUB reader for highlights, comments, margins and reading position, with your library kept in a folder you own.

Open it at **https://backchat.jonathandutoit.com**

## What it is

Backchat is one HTML file. Everything runs in your browser: there is no server, no account and no tracking. The only outside requests fetch three open-source libraries from the jsDelivr CDN (listed under Licence) and, when you play a video in a transcript book, the video from YouTube. Your books and notes live in your browser's storage and, if you connect one, in a folder on your computer as ordinary EPUB and Markdown files, which works well with Obsidian.

- Highlight, comment and write in the margins of any EPUB
- Search across every book, your marks, and the full text inside books
- Copy links to an exact passage
- Read aloud
- Hand off notes between devices by file, or sync them automatically through a relay you own (see below)

## Sync between devices (optional)

Backchat can keep your phone and computer in step through a small relay you set up yourself: a free Cloudflare Worker. Your notes are encrypted on your device with a passphrase that never leaves it, so the relay only stores scrambled data. Each person runs their own relay; nothing is shared with anyone else, including the author.

Setup takes about 15 minutes in a browser: [docs/SYNC-SETUP.md](docs/SYNC-SETUP.md). The relay code is in [worker/](worker/).

## Host your own copy

Download `index.html`, `icon.svg` and `apple-touch-icon.png` and serve them from any static host, or fork this repository and turn on GitHub Pages. Nothing else is needed.

## The deal

I built Backchat for my own reading and share it as is. There is no support, no roadmap and no promise of anything. Keep your folder backed up. Issues and suggestions may be read, and may not be answered.

I write about reading, decisions and building tools like this at [jonathandutoit.com](https://jonathandutoit.com).

## Licence

MIT, see [LICENSE](LICENSE). Bundled libraries keep their own licences: JSZip (MIT or GPL-3.0, used under MIT), epub.js (BSD), MiniSearch (MIT).
