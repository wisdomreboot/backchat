# Changelog

What changed in each build of Backchat, newest first. The build number shows at the bottom of **Settings > Advanced**.

## 1.0.56 (13 October 2026)

**Added**
- **Send to margins** in the selection menu (the notebook icon, the same one that opens the margins). Select text, tap it, and the passage goes straight into the book's margins as a quote with a location link back to its paragraph. No highlight is made, so you can collect lines to come back to without colouring them. The quote is kept whole, because the margin entry is the only copy of the words.

**Fixed**
- The **Margins** button under a highlight now carries the highlight's comment into the margins, below the quote and its link. The comment was previously left out. Highlights sent before this fix arrived without their comments; sending one again adds a new entry rather than updating the old one.
- **Copy location** now always links the paragraph you selected. In one edge case, when the selection was not in the first part of the chapter shown on screen, it could link the first paragraph on screen instead.

**Changed**
- The built-in guide book describes the new button, and refreshes itself on first load.

## 1.0.55

**Security**
- The three libraries (JSZip, epub.js, MiniSearch) now load from `lib/` in this repository instead of a public CDN.
- A Content-Security-Policy lets the browser run only this site's scripts and the inline scripts it lists by hash. `tools/csp.py` keeps the hashes current.
- Fixed two ways a crafted folder file, backup or hand-off could inject script: bare web addresses auto-linked in margin notes could break out of a link or image, and book ids were written into the page unescaped.
- Restored settings are copied one by one with their types and ranges checked, and star ratings are clamped.
- A sync setup link now names the relay it points to, and the video player listens only to YouTube's exact addresses.

## 1.0.54

- Runs as a standalone page for GitHub Pages: full page header, mobile viewport, title and icons.
- Closed drawers sit fully off-screen, so their shadow no longer shows at the edge of the page.
- Fixed a character in the as-you-type search that could break the page when the file was copied.

## 1.0.53

- **Remove from this device** on a book's page, for devices without a folder. It frees the EPUB and its search index while the book's record, cover, marks, margins and position stay and keep syncing. The cover dims until the EPUB is added again, and the button becomes "Add the EPUB to read".
- With sync on, **Delete** is labelled "Delete everywhere", and its confirmation says so.

## 1.0.52

- **Sync between devices**, optional, through a relay you own (a free Cloudflare Worker). Each device writes its notes encrypted with a passphrase that never leaves the device, reads the other devices' notes, and merges them. Marks, comments, margins, reading position, tags and deletions stay in step without a manual hand-off. Books themselves do not travel. A setup link fills in the relay details on a second device. See [docs/SYNC-SETUP.md](docs/SYNC-SETUP.md).

## 1.0.51

- Two different files of a book with the same title and author, and no ISBN, are no longer merged into one, so one edition's highlights can no longer land on the other. Book identities and folder filenames are unchanged.

## 1.0.50

- Deleting a highlight or comment now carries across devices and merges, so a deleted mark no longer comes back.
- Removing a tag now sticks across devices instead of being added back.

## 1.0.49

- Deleting a book now also removes it from the search index, so it no longer turns up in search results.
- Opening a book and quickly going back can no longer wipe its marks.
- A failed source lookup can no longer erase a transcript book's saved video link.
- Pulling from the folder while a book is open now updates that book's marks on screen, so the next edit cannot undo what was pulled in.

## 1.0.48

- In the Markdown notes, the Source line for an ordinary book is now an Obsidian link to the book's note and its author, and titles containing `|`, `#` or `:` no longer break it.

## 1.0.47

- A book's source is captured only when its file comes into the app: when added, or with Refresh EPUB from folder. Opening a book does no extra work. The source survives re-importing a book.

## 1.0.46

- Notes name their source. Ordinary books get a "Source: title - author" line; transcript books made from YouTube embed the video, so it plays in Obsidian.

## 1.0.45

- **Connect preview.** Choosing a folder now scans it first, without changing anything, and asks before merging: how many books and notes it holds, how many match your library, some sample titles, and a warning that the merge runs both ways. A wrong folder is caught instead of silently merged.

## 1.0.44

- Removed Trails. Backchat is a reader you mark up; the margins remain the place to write.
