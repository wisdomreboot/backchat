# Changelog

What changed in each build of Backchat, newest first. The build number shows at the bottom of **Settings > Advanced**.

## 1.0.59 (17 October 2026)

**Added**
- **A page-view count**, through GoatCounter, which uses no cookies and stores nothing on your device. Each time the page opens it sends the page address (never anything after `#`, where location links and sync setup links live), the referring site, the page title and the screen size. Nothing about your books, notes, folder or sync is sent. The count skips your own computer's addresses, and `#toggle-goatcounter` at the end of the address switches it off in that browser. The README and SECURITY.md now say all of this, in place of the old "no tracking" line.

**Fixed**
- The first attempt loaded GoatCounter's script from its own server, which the page's security policy refuses, so nothing was counted. The script now lives in `lib/` beside the other libraries: GoatCounter's pinned version 5, unchanged, checked against the fingerprint GoatCounter publishes.

**Changed**
- The regression check now fails with a plain message when a script is linked from another site, checks that local runs never count, and checks that a real page load sends exactly one count with nothing from after the `#` in it.

## 1.0.58 (16 October 2026)

**Added**
- **A transcript book whose video has gone now says so.** When YouTube refuses to play a book's video (removed, made private, or kept on YouTube only by its owner), the player folds away and a short note takes its place: the video is unavailable, and the book, its times and your marks are all still here. The note links to the video on YouTube, so you can see YouTube's own reason, and offers Try again. Before, the player showed YouTube's black error box, and tapping a time started a clock that ran against a video that could not play; it no longer does.

**Changed**
- The player now listens only to the YouTube frame it created, so another YouTube embed on the page, such as a video card in the margins, can never move or stop it.
- The regression check covers a refused video and a playable one opened after it.

## 1.0.57 (16 October 2026)

A durability pass, with no new features. Each fix below was reproduced in a real browser first, then checked again after the change.

**Fixed**
- **Margins could be overwritten by another book's.** If you typed in a book's margins and opened a different book within a second, the second book's margins were replaced with the first book's text. The margins editor now saves only to the book it was opened for.
- **A book file could be deleted from the folder.** On a Mac or Windows disk, where file names ignore capital letters, a book file whose name differed from Backchat's own name for it only in capitals could be removed while being renamed, leaving no copy in the folder. It is now left in place.
- **Restoring several deleted books brought back only one.** A backup or notes file holding several books you had deleted restored just one of them. Every book in the file now comes back. The same fix stops a sync that arrives while you delete a book from forgetting the delete.
- **A deleted book could come back from an old notes file** in the folder's notes directory. Automatic imports now skip deleted books; a restore you choose still brings them back.
- **A book deleted on another device kept turning up in inside-book search** on this one when the delete arrived through the folder. Its search index is now removed with it.
- **Delete everything in this browser** now also clears the inside-book search index, which it left behind.
- Opening a book whose file is not on this device, while another book was open, could make the open book save its reading position under the wrong book.
- **Find in book** no longer retries without end, keeping the processor busy, on a book that cannot be read for indexing. It says so instead.
- When storage is full, a save now fails with the storage-full warning instead of waiting forever.
- Dropping a file on the reader or the search screen no longer opens the file in the tab in place of Backchat.
- On about one page load in six, Chrome's look-ahead read part of the code as page markup and requested a nonsense image address, which failed. That request no longer happens.
- In **Export to Markdown** and a book's own export, the Source link now points to the note inside the export rather than to the folder's file name, so it resolves in Obsidian.
- The margins renderer relied on invisible control characters written into the code. An editor that stripped them would have made every number in your margins vanish from view. They, and the accent-folding characters in inside-book search, are now written so they cannot be lost.

**Changed**
- Removed code that no longer ran: the in-memory search the disk index replaced in 1.0.35, the paste-to-book builder, an unused drop box, a theme switch and a layout button that no longer appeared, debug stubs, and styles left from Trails and other retired features. The page is about 28 KB smaller.
- A full push to the folder reads the library once instead of once per book.
- **A regression check** now lives in `tools/check/check.py` and runs on every pull request. It drives the page in a headless browser and fails if any of the problems fixed here, or the earlier ones it covers, come back.
- Comments throughout the code now describe how it works today, and messages that pointed at old buttons name the current ones.

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
