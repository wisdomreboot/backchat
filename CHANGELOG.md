# Changelog

What changed in each build of Backchat, newest first. The build number shows at the bottom of **Settings > Advanced**.

## 1.0.65 (19 October 2026)

Selecting on an Android phone, in page mode.

**Fixed**
- **Half of two pages stuck on screen.** Dragging a selection handle past the edge of a page makes the browser scroll the book sideways by however far your finger went. The screen was left showing the right half of one page and the left half of the next, and every page turn after that kept the same offset until the book was closed and opened again. Once you stop dragging, the book now settles on a whole page: the one where your selection ends, so the words you reached stay in view. The selection and its colour menu stay up, ready to highlight.
- **The selection menu could hide under Chrome's Touch to Search bar.** On Android, Chrome raises a "Tap to see search results" bar over the bottom of the screen whenever words are selected, and the menu placed below words low on the page sat right under it. On a touch screen the menu now docks at the top of the reader, clear of the phone's own Copy menu, the drag handles and that bar, and drops just under the words only when they are at the very top of the page.
- **The reader's buttons wrapped onto a second row** on a phone with read aloud switched on, taking about 45px of height from the page. They now fit one row even at 320px.

**Checks**
- The phone checks add a selection dragged onto the next page (it settles on a whole page, keeps the selection and its menu, and later page turns stay whole), the selection menu for words low on the screen, and the reader's buttons fitting one row at 320px with read aloud on.

## 1.0.64 (18 October 2026)

Read aloud, checked the way it is used: listening while reading along with the highlight, pausing to highlight and comment, then picking up again. Every case below was reproduced first with a scripted voice that behaves like Safari's, Chrome's and Android's, faults included, and is now part of the regression check.

**Fixed**
- **A chapter that ends in a picture, or with an empty last page, was read again and again.** At the end of the words the voice turned one page, landed on the chapter's own last page, and started the chapter over, for ever. It now goes to the next chapter by the book's own order.
- **After going to another chapter while paused, play read the old chapter aloud,** unseen, while showing the new one, and the page never followed. Play now reads the chapter on screen; in the same chapter it picks up where the voice stopped, turning back to it if you paged away to look.
- **Block quotes and list items were read twice,** first run together and then paragraph by paragraph, and so were nested lists. **Text kept in plain divs and table cells was skipped.** Hidden text was read, and so were the small numbers that link to notes ("the river1 flows"). Each passage is now read once, in the book's order; verse lines broken within a paragraph are read as separate lines, not run together; and "Mr." no longer ends a sentence.
- **Selecting words while it read:** the voice turned the page under your finger and the highlight menu disappeared. While words are selected, a menu or the comment box is open, or the search over your books is up, the voice reads on and the page holds still; it catches up once you are done.
- **A voice that fails** (an online voice with no connection) raced through the book, dozens of paragraphs a second. After three failures in a row it now pauses and says to choose another voice.
- **Chrome's online voices can fall silent mid-paragraph** with no end and no error. The watchdog only noticed an engine that had stopped, not one that claimed to be speaking. It now notices either and repeats the sentence.
- **Dragging the speed slider restarted the voice at every step,** which in Chrome could leave several seconds of silence. The new speed now applies once you let go, from the start of the sentence.
- **In scroll mode the voice pulled the page back** a couple of seconds after you scrolled to look at something, because scrolling inside the book was never noticed. It now waits for you.

**Changed**
- **The page turns with the voice word by word,** not sentence by sentence, so a sentence that runs onto the next page is never heard off screen. With voices that report no words (Chrome's online voices, Android) the page used to turn late; it now keeps up.
- **Play starts with the first sentence on the page you see,** not with the paragraph begun on the page before. A page with only a picture starts with the next words after it.
- **Pause and play pick up at the start of the sentence,** never mid-sentence or mid-word.
- **Turning the page yourself pauses the voice instead of stopping it,** so the player and your place stay. Play takes you back to the voice; a tap on a paragraph reads from there. Going to a mark, a search result or a link pauses it too, and switching between pages and scrolling keeps your place for play.
- **The screen stays on through a pause** for as long as you keep using the page (up to ten minutes after your last touch), so it does not go dark while you mark a passage. Stopping read aloud lets it sleep at once.
- The voice speaks a few sentences at a time, short enough that no engine cuts it off, and very long sentences are broken at a comma. Back steps to the start of the paragraph, then to the one before; forward past the last paragraph goes on to the next chapter.
- The guide's chapter on listening describes how to mark up while listening (revision 18).

**Checks**
- The regression check drives read aloud on a phone with a scripted voice (`tools/check/speech_stub.js`): each passage once and in order, a chapter ending in a picture, the first sentence on the page, the page following the voice with and without word reports, pause then highlight and comment then play, selecting while it reads, a swipe pausing it, play after going to another chapter, a failing voice, the speed slider, and an engine that goes silent.

## 1.0.63 (18 October 2026)

A pass over Backchat on phones, with real touch input on iPhone and Android screen sizes from 320px up, upright and sideways.

**Fixed**
- **Back left Backchat.** Android's Back button or gesture, an iPhone's swipe from the left edge, and a browser's Back button all left the site, because Backchat added nothing to the browser's history. Back now works as it does in an app: it closes the innermost open thing (a dialog, a panel, the find bar), then the book or page, and only leaves once you are home with nothing open. A comment you were typing is saved, not thrown away, and the margins on a book's page are saved as they are on any click away.
- **A tap on the edge of the page did nothing on a phone.** The guide and the help both say it turns the page, but below 600px wide only a swipe worked. On a touch screen in page mode, a tap on the outer quarter of either side now turns the page. The middle stays free for tapping marks and for read aloud, and a mouse click never turns.
- **Scroll mode stranded you at the end of each chapter.** Scrolling stopped at a chapter's end, and the only ways on were a sideways swipe nobody would guess, the arrow keys, or Contents. A Next button now waits at the end of each chapter, with room left under the last line so it covers nothing. Pulling down at the top of a chapter offers the chapter before, and arrives at its end.
- **Find in book on a phone.** On a 320px screen the close button was pushed off the edge, so the bar could not be closed. On every phone the matches were listed below the search box, exactly where the keyboard covers them. They now sit above the box, and the keyboard's Search key puts the keyboard away.
- **Scrolling a panel to its end then scrolled the page behind it.** Panels, lists and dialogs now stop at their end. While a book or a book's page is open, pulling down no longer reloads the page.
- **An iPhone zoomed in when you tapped a search box or the sync fields,** and stayed zoomed, because their text was under 16px. On touch screens these boxes now use 16px text.
- **The Handoff button showed a count on a brand-new install.** It counted the guide's sample marks, which arrive with the guide on every device.
- **On iPhone the keyboard sometimes did not open** for search, Find, a comment or the margins, because the box was focused a moment after the tap rather than during it. Focus is now immediate. Edit details no longer raises the keyboard over the form on a phone, and a search started from selected words shows its results without a keyboard over them.
- Four screenshots taken while checking 1.0.62 were committed by mistake and published with the site. They are removed.

**Changed**
- **The selection menu on a touch screen** sits below the selected words, clear of the phone's own Copy menu above them and its drag handles below. Its buttons are larger.
- **Bigger targets for fingers:** the reader's sync dot, Connections and Library on the home screen, Shuffle, the close buttons on Connections and link previews, Edit and Advanced, the colour and filter chips in the highlights panels, and the links under each mark.
- **The notch and the home bar.** Sideways, or as an app on the home screen, the page is drawn edge to edge, and nothing now sits under the notch or the home bar: the top bars, the side arrows, the reading area, the bottom bar, the panels and the messages all keep clear.
- **The home header scrolls away on a phone** instead of covering a third of a small screen.
- The comment box opens in the top half of a phone screen, so Save stays above the keyboard. The highlights panel's header, the star rating in Edit details, the selection menu and the read-aloud controls all fit a 320px screen.
- A quick second tap is never read as a double-tap zoom, and turning a phone sideways no longer enlarges the text.
- The guide says how Back works on a phone and how to move between chapters in scroll mode (revision 17).

**Checks**
- The regression check now drives a phone with real touch input: a swipe and an edge tap turn the page, a mouse click at the edge does not, no text box is small enough to make an iPhone zoom, a panel scrolled to its end leaves the page behind still, Back closes a panel, the find bar and then the book and keeps a comment being typed, the app's own close buttons keep history in step, the selection menu sits clear of the selection, scroll mode offers the next and previous chapter, the find bar fits 320px with its matches above it, nothing sits under an emulated notch or home bar, and the Handoff count leaves out the guide's marks.

## 1.0.62 (18 October 2026)

**Added**
- **Tables in the margins.** Write a table the way Obsidian and GitHub do, with cells between pipes and a line of dashes under the first row, and the margins show a real table. Colons in the dashes set the alignment (`:--` left, `:-:` centre, `--:` right), and `\|` puts a pipe inside a cell. Bold, highlights, links and location links all work inside cells. In the narrow margins panel a wide table scrolls sideways instead of squeezing. Tables are read exactly as Point First reads them when it publishes, so a table looks the same in both apps, and in your folder's notes it stays a plain pipe table that Obsidian shows as a table. A location link inside a table cell is written for Obsidian with its pipe escaped, so the link cannot split the cell.
- The guide's chapter on the margins mentions tables (revision 16).

## 1.0.61 (18 October 2026)

The built-in guide, *How to talk back to your books*, is rewritten as the way in for someone who has never seen Backchat, and it now lives in its own files.

**Changed**
- **The guide covers everything a new reader meets.** It opens with a five-step start. Then it walks through every button on the home screen, in the reader and on a book's page, what each highlight colour means, comments, the highlights panel, links between passages, search, read aloud, video books, the folder, sync between devices and setting up a phone. It ends with where Backchat's code lives on GitHub and how to report a problem. Its icons are drawn from the app's own buttons, so the picture in the guide always matches the button on screen.
- **The guide moved out of the page,** into `guide/guide.md` and `guide/cover.jpg`. The page is 82 KB lighter on every load. The guide is fetched only on a first run, when you ask for it, or when you open it to see whether a newer version exists. It can now be edited like any document, without touching the app's code or its security fingerprint. Raise `revision` in guide.md and readers get the new text the next time they open the guide, with their own marks on it kept.
- The selection menu, the highlight menu and the guide draw their icons from one table.

**Fixed**
- **The guide's sample highlights never appeared on the page.** A mark saved without a position was tied to the first chapter, where its words are not, so it showed in the highlights panel but never in the text. Such marks now find the chapter that holds their words. The same goes for any mark imported without a position.
- **Web links inside a book did nothing.** A link to a website in a book's text, such as a footnote's source or the guide's own links, was blocked, because books are shown in a frame that may not open windows. These links now open in a new tab.
- Add the guide book now says when the guide cannot be fetched, instead of failing silently.

**Checks**
- The regression check now covers the guide: it arrives whole from `guide/` with its sample marks painted, every icon it names is drawn, an ordinary page load never fetches it, a newer guide.md updates it on opening while keeping the reader's marks, a failed fetch is reported, and a web link in a book opens a new tab.

## 1.0.60 (17 October 2026)

Every way of going back to a place in a book now lands on the place itself. Each case below was reproduced in a real browser first and is now part of the regression check, in page mode and in scroll mode.

**Fixed**
- **A highlight found in search opened the right chapter on the wrong page.** Clicking a highlight or a comment in the library search sent the reader to a position that epub.js could not place exactly, so it stopped pages short of the mark. It now lands on the mark, the same way the highlights panel does.
- **The same words twice in a chapter.** When a sentence appears twice and you marked the second, the highlights panel, all marks, search, rhymes and highlight links went to the first. They now go to the one you marked, using the bit of text saved on either side of it.
- **Find in book** went to the first match in the chapter whichever match you chose. Each match now lands on its own occurrence.
- **Reopening a book could put you one page before where you stopped.** The reader now checks that the first words of the page you left are on screen, and turns forward if they are not.
- **Changing the font size, line spacing, margins or font, resizing the window, or turning a phone moved you to another page.** The words you were reading now stay on screen, including while you drag a slider. Switching between pages and scrolling keeps them on screen too, and in scroll mode a saved position goes back to the top of the view instead of drifting a line each time.
- **A position link** (a raw position rather than a paragraph) landed on its chapter, not its passage. It lands on the passage now.
- A mark imported without a position, or one whose chapter changed after the EPUB was edited, now lands on its words wherever they are in the book. If the words are gone, the reader says so.
- The flash that shows where you landed no longer clears read-aloud's highlight of the sentence being spoken.

**Changed**
- All of these go through one function, `bcGoTo`, in place of the separate routines that had grown up with their own guesses at timing. It opens the chapter and waits for it, finds the words the way a highlight is painted, turns to their page, checks they are on screen, and keeps checking for a few seconds while the chapter finishes laying out. It stops correcting as soon as you touch a key, tap, click or scroll (the display settings excepted), or read-aloud is turning the pages.
- Opening a book no longer attaches its page-turn and selection handlers a second time when it opens another copy of the same book, or attaches them to the book already on screen when the new one cannot be opened.
- The regression check gains 41 landing checks: search (highlight, comment, inside-book, from inside the reader), the highlights panel, all marks, the daily highlight, rhymes, highlight, paragraph and position links, find in book, the saved listening spot, reopening a book, the Return button, every layout change, a stale mark, a mark with no position, a mark from an older copy of the book, and two quick jumps in a row.

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
