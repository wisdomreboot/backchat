# Security

## What Backchat can reach

- **Your books and notes** live in your browser's storage for this one address, and in the folder you connect, if you connect one. No other website can read either. Neither is on the internet: there is no address anyone can connect to.
- **The folder** is the one you pick, and only while Backchat is open in a tab. You can revoke it at any time in the browser's site settings.
- **Your books and notes are sent nowhere** unless you turn on sync. Sync sends your notes, encrypted on your device with AES-256 and a key from your passphrase, to a relay you set up and own. The passphrase is never stored or sent. Book files never travel.
- **Outside requests** are limited to a page-view count sent to GoatCounter when the page opens (the address without anything after `#`, the referring site, the page title and the screen size; see the [README](README.md#page-view-count)), YouTube, when you play a video in a transcript book, and images a book or note links to on the web.

## What protects it

- **Only this repository's code runs.** The page's Content-Security-Policy lets the browser run scripts from this site and the inline scripts whose fingerprints it lists, and nothing else. The four libraries, the page-view counter included, are stored in [lib/](lib/), unchanged from their published versions. A script linked from another site is refused, which is why the counter is kept here rather than loaded from GoatCounter's server.
- **Books can't run code.** Book pages render in a sandboxed frame with scripts off, and scripts, plug-ins and event handlers are stripped before display.
- **Imported data is treated as untrusted.** Notes, records, backups, hand-off files and synced bundles are escaped before display. Settings from a backup are checked key by key.

## What it can't protect

- **Your device.** Files in your folder and the browser's storage are as safe as your computer. Use a login password and disk encryption (FileVault on a Mac, BitLocker on Windows).
- **Browser extensions** with permission to read every site can read Backchat too. Install few.
- **A weak passphrase.** Whoever runs a relay holds only encrypted data, but a short passphrase can be guessed. Use a long one.

## For the owner of a copy

Whoever controls the repository controls the code every user runs. Turn on two-factor sign-in for GitHub, for the DNS provider that points the address at GitHub, and for the domain registrar. Don't merge a pull request you haven't read line by line.

## Reporting a problem

Use GitHub's private vulnerability reporting on this repository (the **Security** tab, **Report a vulnerability**). Please don't open a public issue for a security problem. This is a personal project with no support promise, but security reports will be read.
