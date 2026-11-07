# Changelog

What changed in each build of Backchat, newest first. The build number shows at the bottom of **Settings > Advanced**.

## 1.0.74 (7 November 2026)

One merge and one format. Every way a record comes into the library goes through one merge, and every file that carries notes between devices, or brings a book back, is built one way.

**Changed**
- **One merge for every way in.** The folder, a notes file, a hand-off, a cloud conflict copy, a restore, device sync and the start-up tidy-up each kept their own copy of the merge, and the copies had drifted apart. Now each finds where a record belongs by one rule, and merges it with one function. A deleted book stays deleted. A record whose id names a different book here is refused. The same book held here under another id takes it. Anything else is a book new here. Only what changes is written, and the book on screen takes what arrived.
- **One notes format.** Export notes, a hand-off and device sync build their files the same way, with the same record of each book. A hand-off is now a notes file of the books you touched since the last one, so Load and the notes folder read it like any other. On screen nothing changes, a hand-off file made before 1.0.74 still merges, and an older Backchat still takes one made now.
- **One backup.** Save, the weekly backup, the backup offered before a reset, a book's own backup and the backup made before a delete are built by one function.
- **A restore adds and never replaces.** It brings back a book's file and cover when this browser has none, and leaves the ones you hold as they are.

**Fixed**
- **A hand-off or a restore could write one book over another.** When a record's id named a different book here, every other way in refused it. A hand-off wrote that book's title, margins and marks over yours, and a restore its title and margins. Both now refuse it.
- **Margins that arrived while their book was open were lost at the next page turn**, when they came by a hand-off, a restore or the tidy-up. The reader kept its own copy of the record and wrote it back. They come through the one merge now, which tells the open book.
- **A record merged with itself came out changed.** A book never opened gained a last-opened time of 0, a record never edited an edit time of 0, and an older record empty tags, a reading time and a finished flag. So the first time any copy of a record arrived, it was written again, in the browser and then in the folder: connecting a folder rewrote every such book. Hand-off, restore and the tidy-up wrote every record they touched, changed or not. Merging a record with itself now changes nothing, and only what changes is written.
- **A book's backup carried the whole app's settings.** Restoring one book put back your type size, theme and voice as they were the day it was saved. A book's backup now carries the book alone.
- **Check folder and the sync message disagreed about books with notes but no EPUB.** The message says Check folder lists them. For a book whose record had not reached the folder yet, Check folder said the next sync would write it, though no sync could give it a file. Both now use one rule.
- **A new edition of the guide dropped the marks whose words it no longer has, without a tombstone**, so a device still holding one brought it back. They are now deleted the way every mark is. 1.0.73 said the widened highlight was the last mark removed without a tombstone; this was another.

The guide, at revision 26, says that a restore adds and never replaces, and that a book's backup leaves your settings alone.

**Checks**
- New section 4f, twelve checks written as rules. Each one that concerns a record runs on every way a record comes in: the folder, a notes file, a hand-off, a conflict copy, a restore, device sync and the tidy-up. Nine fail on 1.0.73. Merging a record with itself changes nothing (1.0.73 changed all four record shapes). A record that brings nothing new writes nothing (1.0.73 wrote the record again on every path, and hand-off, restore and the tidy-up its marks too). A record whose id names a different book changes nothing (1.0.73: the hand-off and the restore wrote over the book). Notes, hand-off and device sync carry the same record. Check folder lists every book the sync message counts. A book's backup leaves your settings alone. A guide edition that drops a mark's words deletes the mark for good. Connecting a folder that holds this library's records rewrites none of them (1.0.73 rewrote two of two). Margins that arrive while their book is open survive the next page turn (1.0.73 lost them by hand-off, restore and tidy-up). Three pass on both builds and guard what already held: the newest version of each mark wins on every path and a deletion stays deleted, a record of a book held here under another id joins it, and a hand-off made today merges and is cleared. All 204 checks pass.

## 1.0.73 (7 November 2026)

The phone, built around how it is used: a reader for the train that holds its own books and, with device sync on, uses the folder as a bookshelf.

**Changed**
- **A phone keeps every book it holds.** Connecting the folder on a phone applied the computer's rule: keep the twenty books opened most recently and let the rest go, because the folder has them. On the train the folder is out of reach, so a phone holding thirty books found eleven it could not open until it connected again. A phone now never lets a book go for being in the folder. Remove from this device, which now appears on a phone with a folder too, is how you free its space.
- **With device sync on, a phone uses the folder as a bookshelf.** It reads book files from the folder, so a dimmed book opens from it, and it saves a book you add on the phone into it. It writes nothing else there: no records, Markdown notes, backups or library index. Device sync already carries the phone's marks, margins and places, and the computer writes them into the folder, so each notes file has one writer and the cloud client has nothing to make conflict copies from. Tidying the folder, Check folder and switching a book to a corrected copy are left to the computer. Without device sync, the folder is a phone's only channel for notes, so there it keeps working both ways.
- **No more notes snapshot.** `notes/latest.json`, a full copy of every note rewritten six seconds after any change, is no longer written: the per-book records already hold the notes, and device sync carries them between devices. Export notes still saves a file whenever you ask, and a notes file you put in `notes/` is still merged.

**Fixed**
- **Opening Settings read every book file in the browser** to add up their sizes: on a phone holding a whole library, hundreds of megabytes for one line. The line now comes from what the browser reports, and says how many books have their file here.
- **Reading rewrote the book's record every ten seconds** to add ten seconds of reading time, and woke device sync each time: about 180 rewrites in 30 minutes of reading. Reading time is still counted, and is saved with the next save of the book: a page turn, closing it, or the phone putting it away.
- **Highlighting over a highlight kept both.** A plain highlight inside a new one was dropped from the page without being marked deleted. Since 1.0.72 every save merges with the stored copy, so the save brought it straight back; before that, the next sync did. It is now deleted the way every mark is, and stays gone on every device. A highlight that carries a note or a star is no longer replaced at all: earlier builds dropped it, note and all.

The guide, at revision 25, says the same.

**Checks**
- Seven new checks. Six fail on 1.0.72: A phone keeps all 22 books it holds when its folder is connected (1.0.72 kept 19). A phone with a folder offers Remove from this device. With device sync on, a phone writes nothing to the folder but the book files it adds, and still opens a dimmed book from it (1.0.72 also wrote records, Markdown notes, a backup, the library index and the list of deletes). No notes snapshot is written, and Export notes writes only its own file. Settings counts storage without reading a book file. Reading time is counted without rewriting the record, survives a sync that arrives meanwhile, and is saved by the next save. The seventh fails on 1.0.72 and 1.0.71: highlighting over a plain highlight replaces it for good, and one with a note or a star stays (1.0.72 kept all six marks; 1.0.71 dropped the noted and starred ones, and a merge with an older copy brought all three back). All 192 checks pass.

## 1.0.72 (7 November 2026)

The book you are reading keeps what reaches it while it is open. A review of 1.0.71 for rules written more than once found four faults, each in a copy that had missed a fix its siblings had. Three of them could lose marks or margins.

**Fixed**
- **A hand-off merged while its book was open was lost at the next save.** Its marks reached the library, then went at your next highlight or favourite, from this browser and from the folder; the hand-off file had already been removed. Marks arriving by a restore, or folded in by the tidy-up from a second record of the book, went the same way. The open book now saves its marks by merging them into what is stored, as every sync merges, instead of writing its own copy over them. A mark that arrives while the book is open is kept, whichever way it came, and the book on screen shows it.
- **Changes made on the page of the book you were reading were undone when you went back to it.** Margins written there, a tag, a rating, the summary or the heart were written over by the reader's next page turn, or within ten seconds by the reading timer, because the page and the reader each held their own copy of the book's record. While a book is open, its page now edits the reader's own copy, and so does the heart on its cover.
- **Refresh EPUB from folder opened a book you had closed.** A closed book still counted as the open one. Closing a book now lets it go.
- **Starting Backchat on a phone took seconds longer than it needed to.** The tidy-up that runs at every start read the whole library again for every book with no file on the device, and a phone holds most of its books that way. It now reads the library once. In a test with 300 such books and the processor slowed to a phone's pace, reopening the last book after a reload went from 3.1 seconds to 0.5.

**Checks**
- Four new checks, all failing on 1.0.71. A mark that arrives while its book is open survives the reader's next save, by each of the seven ways a record arrives: the folder, a notes file, a hand-off, a cloud conflict copy, a restore, device sync and the tidy-up (1.0.71 lost it by the hand-off, the restore and the tidy-up). Margins, a tag and the heart set on the page of the book being read stay after going back to it and turning a page. Refreshing a closed book from the folder leaves you on its page. The start-up tidy-up reads the library three times, however many books have no file here (42 times for 40 such books on 1.0.71). All 185 checks pass.

## 1.0.71 (7 November 2026)

Folder sync, tidied: one copy of each rule where there were several, in less code. Testing the tidy-up with two devices opening Backchat in turn found three ways the folder was still being rewritten for nothing, and one thing Check folder promised that sync would not do. All four are fixed.

**Fixed**
- **Every notes file was rewritten once a day.** Each Markdown file in highlights/ carried the date it was written ("exported 2026-11-06"), so the first sync of each day, once the date turned in UTC (11am in Sydney), rewrote every one of them: 321 files on the folder checked, each a chance for the cloud client to make a conflict copy. The folder's copy now carries the date its notes last changed ("updated ...") and is written only when they change. A Markdown export you make yourself still carries the day of export.
- **Two devices took turns rewriting a book's record.** When the phone and the computer held the same marks for a book, but in a different order (both marked it before either saw the other's marks) or with a different time of last change (each folded a duplicate at its own moment), each wrote its own copy back to the folder every time Backchat opened. Records are now compared by content, and a merge keeps the later time, so the two copies agree and neither is written again.
- **Check folder promised to add a file sync had given up on.** A file Backchat could not add to the library (one holding thousands of files, say) was listed as new, to be added on the next sync, though sync does not try it again until the file changes. It is now listed with the files left alone, with the reason.

**Changed**
- **One set of rules for the files in books/**, followed by sync and by Check folder alike, so the report cannot promise what sync does not do. Check folder also no longer offers to rename a file already under its book's name, and judges a file with the same title and author but other contents the way sync does.
- **One merge step** for a book's record, whether it arrives from the folder, from a notes file or from a conflict copy, where there were three copies of it.
- **Book files are compared byte for byte** wherever sync decides whether two are the same file. Some places compared sampled signatures.
- **A book gets 60 seconds to open** before Backchat gives up on it, not 20, so a large book on a slow phone is not taken for a broken one.
- The header of each notes file, and the guide (revision 24), now say what is true: Backchat writes the file from your marks and never reads it back. Both used to say it was rewritten on every sync.

**Checks**
- Three new checks, all failing on 1.0.70: opening Backchat the next day rewrites no unchanged file; the same notes in another order, or with another time of change, are not rewritten; Check folder does not promise to add a file sync could not add. All 181 checks pass.
- Replayed against the real folder's records and notes, as for 1.0.70: the first sync makes the same 679 one-time writes, later syncs and a reopen make none, and no mark is lost. Opening Backchat the next day made 321 writes on 1.0.70 and makes none on this build.

## 1.0.70 (6 November 2026)

The folder, for a library where books come and go: added, deleted and added back, in Backchat and in the folder itself, with a cloud client carrying it between computers.

Checked against a real folder (315 book files, 333 notes records, 20 files in notes/) and against every way of adding, deleting and adding back a book. Two faults were doing real damage there: four books had lost their EPUB and five their notes file to the first, and the second had every sync rewriting the whole folder.

**Fixed**
- **Tidying a duplicate deleted the book's file and notes.** A second record of the same book (left by a second browser connecting to the folder, or by two syncs running at once) shares the book's file names, and removing it removed the surviving record's EPUB and Markdown notes as well. When this browser no longer held the book itself, the EPUB was gone from the folder for good. Duplicates are now folded into one record and the files stay. Every browser folds a duplicate into the same record, so two browsers on one folder no longer each remove the other's.
- **A duplicate came back on every sync.** Old notes snapshots in notes/ (latest.json and its cloud conflict copies) brought the removed record back, and tidying it removed the files again. A record of a book the library holds under another id is now folded into that book, from the folder, from notes files and from conflict copies alike.
- **One unreadable .epub in books/ stopped folder sync for good.** An empty file, one still downloading, or anything else named .epub made the reader wait forever at that file, silently, and nothing after it in the sync ran. Check folder waited forever too. Such a file is now left alone and named once; Check folder lists it with the reason. Add EPUB refuses it with the reason instead of hanging.
- **A new copy of a book you have was deleted.** A corrected edition dropped into books/ under another name, or a different book with the same title and author and no identifier, was removed as a stray copy, with the message "Tidied 1 book file name". A copy is now removed only when it is byte for byte the book's own file; any other copy is kept and named. To switch a book to a corrected copy, use Refresh EPUB from folder on its page: it now reads from that copy.
- **Adding a changed EPUB in the app did not reach the folder.** "Updated the book file" changed this browser's copy only; the folder kept the old file, which came back once the browser let go of its copy. The folder's copy is now replaced too, and a change is noticed by content, not only by a change in size.
- **Deleting a book again overwrote its first backup.** Delete, add back, delete: the second backup replaced the first, the one holding the marks. Each backup now gets a name of its own.
- **A book added back could be deleted again.** Another browser, the phone or an older copy of the folder still holding the delete passed it back, and the book went again, new marks and all. Adding back is now recorded with its time, and for any book the later of delete and add-back holds, on every device.
- **Two syncs at once imported a new book twice**, and folding the twins removed its file. A sync started while one is running now joins it.
- **Connecting or reopening wrote before it read.** This browser's records went into the folder first, over newer ones another browser had saved there. Sync now reads the folder first.
- **A delete made while the folder was disconnected stayed in this browser.** It is now written to the folder at the next sync, so other browsers learn of it.

**Changed**
- **A sync with nothing new writes nothing.** Each sync merged every file in notes/ again and marked every book as changed, so it rewrote every book's record once for each notes file: on the folder checked, about 6,400 writes a sync, each a chance for the cloud client to make a conflict copy. Notes files are now merged only when they change, this browser's own snapshot not at all, and a merge writes only what it changes.
- **Opening Backchat no longer rewrites the folder.** The first sync after opening wrote every record and note file again, unchanged, because the browser no longer remembered writing them. It now compares with what the folder holds and writes only differences.
- **A sync no longer reads the whole library into the browser.** It read every book file the browser had let go of (about 270 MB on the folder checked), only for the browser to let them go again. A book's file is read when you open it.
- **Cloud conflict copies in notes/ are merged and removed**, as copies of the records in .reader already were. Conflict copies of the Markdown notes in highlights/ are listed by Check folder, with a button to remove them: Backchat writes those notes from your records, so the copies hold nothing it needs.
- **Check folder says what each part of the folder is and what the next sync will do with it**, judging book files by their content, as sync does: duplicate records, books with notes but no EPUB anywhere, new files, copies of books you have (the same file, or different contents), books you deleted whose files are back, files it cannot read, conflict copies, leftovers. It used to say a deleted book's file would import on the next sync, which it never would. It now offers **Add back** for those books.
- **A deleted book's file dropped back into books/ is mentioned once**, instead of being passed over without a word.
- "Books with notes but no EPUB" is said once each time the set of such books changes, not at every sync.
- The guide (revision 23) describes Check folder, Add back, Refresh from a corrected copy, and backups that are never replaced.

**Checks**
- Seventeen new checks against a mock folder that keeps real file times, can lose permission or vanish, and logs every write: two syncs at once keep every book and its file; a notes snapshot's conflict copies are merged once and removed; a sync with nothing new writes nothing; a sync reads no book file into the browser; reopening Backchat rewrites no unchanged file; an unreadable file does not stop the sync and is mentioned once; folding a second record keeps the book's file and notes; a copy with different contents is kept; Refresh EPUB from folder reads from that copy and keeps the marks; adding a changed EPUB in the app replaces the folder's copy; deleting a book again keeps its first backup; a book added back stays when an older delete returns through the folder or the relay; a deleted book's file dropped back is left alone and mentioned; Check folder names it and offers Add back; Add back returns it; and two browsers sharing a folder settle on one record of a book. All seventeen fail on 1.0.69.
- Replayed against the real folder's records and notes: its first sync on 1.0.69 made 6,642 file operations, removing the notes file of six books and the EPUB of two (rewritten from the browser's copy), and its second made 12,944. On this build the first sync made 679 (one-time: duplicates folded, 26 conflict copies merged and removed, missing note files written again), every later sync none, and no mark was lost.

## 1.0.69 (25 October 2026)

Read aloud becomes a switch you flip while reading: the speaker in the top bar.

**Changed**
- **The speaker in the top bar switches read aloud on and off.** It is there from the start; nothing needs switching on in Display first. On: the voice reads from where you are, and the player takes the place of the progress row at the foot of the page. Off: the voice pauses, the player goes, and the page is yours to select, highlight and comment; no tap moves the voice. Before, the speaker only started and stopped the voice, stopping forgot where it was, and the real switch sat in Display, below the bottom of the panel on a phone.
- **The voice always starts where you are reading.** On the page where it stopped, it carries on from the sentence it was in, or from a passage you marked further down, since you read on to it. On any other page, because you read on, went back or have just opened the book, it starts at the top of that page. The same rule serves the speaker, play in the player, and the next time you open the book: the voice's place is kept with the book and syncs, the newest winning.
- **Nothing on the page moves when you switch.** The player and the progress row are the same height and share one place, so the page keeps its size. A page laid out again for a new height re-flows the whole chapter: the passage you were about to mark could move, or slip onto another page.
- **On and off show by shape, not colour.** Off is a crossed-out speaker; on is a speaker with sound waves on a solid button.
- **Play after turning the page yourself reads from the page you turned to.** It used to turn back to where the voice had stopped.
- The Read aloud switch and its note have gone from Display; the voice is still chosen there. The player's Stop button has gone too: switching off is the stop, and it keeps the place.
- The guide (revision 22) describes the switch and where the voice starts.
- With the player now off by default, the progress row is a little taller (44px on a phone), the same height as the player it trades places with.

**Fixed**
- **The selection menu could vanish after a selection settled on a whole page.** When a dragged selection snaps back to a whole page, the menu is brought back over the words; on a busy phone the page change could be reported after that and close the menu again, leaving the words selected with no menu. The menu now comes back a second time if that happens.

**Checks**
- Ten new checks on a phone with a scripted voice: the speaker is the switch, there from the start and off; on reads from the top of the page with the player in the progress row's place; off pauses with nothing on the page moving; off, highlight and comment, on carries on from the sentence it stopped in; off, read on a page, on starts at the top of that page; off, mark further down, on starts at the mark; with read aloud off a tap never starts the voice; the voice's place survives closing and reopening the book; scroll mode starts at the first sentence in view and keeps its size; and the voice's place merges newest first. Three existing checks now describe the new behaviour: play after a page turn, the page keeping its size on or off, and the margins with the player gone.

## 1.0.68 (20 October 2026)

Where you were: your place in a book and your saved listening spot, on one device and across devices.

Tested first on a phone-sized screen, in Page and in Scroll, for every way of leaving a book: closing it, going Home and tapping Continue, switching apps, the phone dropping the tab, a reload, and the voice turning pages when the tab went. In every case the words you were on came back on screen; in Scroll the line you were at returns to the top, within a line. What was wrong was around that.

**Fixed**
- **Going back to reread was undone by sync.** Across devices your place followed the furthest point read, so after rereading an earlier chapter on the phone, the desktop's next sync put the phone's place back at the desktop's furthest page. Your place now follows where you read last, on whichever device. Opening a book, a new layout or a sync landing you somewhere does not count as reading, so a device that is behind cannot outrank a newer place just by opening the book. Places saved before this build keep the old rule until one side reads on.
- **A saved listening spot could be replaced by an older one.** The spot followed whichever device last changed anything about the book, so a margin edit on the desktop brought back the desktop's older spot. The spot saved last now wins.
- **Back to my spot looked switched off after reopening a book.** The button stayed dimmed, as if nothing were saved, until a spot was saved again. It now shows the saved spot whenever the book opens.
- **After the phone dropped the tab, or a reload, Backchat came back to Home.** The book that was open now opens again on its page. Closing a book first means starting on Home, as before; and a reopening that never finished (a book too big for the phone) is not tried a second time.
- **A link followed at start could be put away** by Home repainting itself once the library check finished. Home now repaints only while it is what is showing.
- **On the desktop with a folder, a page turn after a folder pull could undo it.** The open book kept its own older copy of the record, and the next save wrote it back over what the pull had merged in. It now takes the merged record, as a device sync already did.

**Changed**
- **A book sitting open and untouched follows a place read since on another device.** When sync brings a newer place for the book open on screen, the page moves there, says so, and shows Return to go back. Not while you are in the middle of something: the voice reading, words selected, a comment open, or a touch in the last few seconds. Then the page stays, and reading on makes this device's place the newest again.
- Leaving Backchat (another app, the home screen) saves the page showing at that moment, so a move still settling is not lost if the phone later drops the tab.
- The guide (revision 21) says the book you leave open opens again, and that the saved spot stays and syncs. The sync notes say position follows where you read last.

**Checks**
- Nineteen new checks: nine, each run in Page and in Scroll, that a book open when Backchat went away opens again on its page; Back to my spot shows the saved spot after reopening; a book closed first does not reopen; a reopening that never finished is not tried again; going back to reread survives another device's sync; the newest saved spot wins; opening a book does not make its place the newest; an open book untouched here moves to a place read since elsewhere, with Return; a book being read here keeps its page. Plus one on how older records merge. Thirteen of them fail on 1.0.67; the other six guard what already worked.

## 1.0.67 (19 October 2026)

Margins, line spacing and font size, above all on a phone.

**Fixed**
- **Font size and margins changed on their own.** On a phone the Read aloud switch sits below the bottom of the Reading panel, so reaching it, or the Page and Scroll switch on the way back, takes a swipe up the panel. A swipe that started on the Font size or Margin slider dragged that slider to wherever the finger began: one swipe took font size from 100% to 150%, a second took the margin from 2.2 to 4.4. Font size is now two buttons, smaller and larger, in steps of 10%. A tap moves it; a swipe only scrolls the panel.
- **Scroll mode was cramped.** The page engine sets its own side margins, a 24th of the width on a page and a 12th in scroll mode, and puts them back every time a page settles. The Margin setting mostly did nothing, and scroll mode came out with twice the margin of a page: a narrow column of widely spaced words. On the moments the setting did win, a page margin wider than the engine's own pushed text past the edge of the page.
- **Closing a book with find still open saved a later page.** Find closed on the way out before your place was read, and the place measured against the taller reading area began a page or so after the one you were looking at. The place is now read first.

**Changed**
- **Margins and line spacing are set, not adjusted, and they are the same in Page and Scroll.** On a phone the margin is the one a page already had (15px on a 360px screen), since a phone's line is short and every pixel of margin costs words. On wider screens the margin widens to hold a line to about 66 characters, the length the eye follows best; at 100% on a desktop that is about 100px a side where lines used to run past 80 characters. Line spacing is 1.35 on the short lines of a phone and opens to 1.45 as lines approach full length, because a longer line needs more room for the eye to find the next one. A book's own line spacing gives way to these, except under Original styling. Both follow the font size you choose.
- The guide's Read your way chapter describes the new settings (revision 20).

**Checks**
- Nine new checks: closing a book with find open keeps the words you were reading, in pages and in scroll mode; a page keeps its margins and spacing when read aloud is switched off; pages and scroll mode have the same margins and line spacing on a phone; a phone's margins leave most of the screen to the words; a swipe that scrolls the Reading panel leaves the font size alone; the larger button steps the font by 10% with every line inside its page; a book's own line spacing gives way to the reader's; and on a wide screen a line holds about 66 characters in both layouts. The layout-change check now uses the font size buttons, and the landing checks close find once its own check is done, as a reader would.

## 1.0.66 (19 October 2026)

Highlighting on a phone, above all while read aloud is playing. Each fault was reproduced on a phone-sized screen with real touch input and a scripted voice, and is now in the regression check.

**Fixed**
- **The book laid itself out again in the middle of a swipe or a selection,** reflowing the text as if the font size and margins had changed, losing the words you were selecting, and moving the page. On a phone the page behind the book could scroll a little (a full-height page is taller than the screen while the address bar shows), so a swipe or a selection drag slid the address bar away, the window changed size, and the book was laid out again. While a book is open the page itself can no longer scroll.
- **The last lines of every page were hidden while read aloud played.** The player opened below a book laid out for the taller page, so the bottom lines sat behind it, and the voice turned the page before you had seen them. With read aloud switched on, the player now stays at the foot of the page whether it is playing or not, so the page never changes size when you press play or stop. Any other change in the size of the reading area lays the book out again to fit.
- **Find's list of matches hid the bottom of the page** the same way. The matches now open over the page.
- **The voice turned the page while you were pressing to select.** While a finger is on the page, and for a moment after, read aloud reads on but leaves the page where it is; once you have selected words it waits until you are done, as before.
- **A tap that only cleared a selection turned the page,** or moved the voice to the paragraph you tapped. A tap within a second of a selection now just clears it.
- **Taps on the words near either edge turned the page.** The edge that turns the page was a quarter of the screen on each side, so a tap meant for the text often moved on. It is now about a sixth: the margin and the first letters.
- **When the book was laid out again while the voice read** (a turned phone, a resized window), the voice lost its place and started again at the top of the page. It now carries on from the sentence it was in.

**Changed**
- The guide's chapter on listening says the player stays at the foot of the page (revision 19).

**Checks**
- Seven new checks on a phone: the page behind the book cannot scroll; the book always fits above the player; a finger on the page keeps read aloud from turning it; a tap that clears a selection, and a tap on the words near the edge, leave the page alone; find's matches leave the page its size; and a new layout mid-sentence leaves the voice in its sentence. All seven fail on 1.0.65.

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
