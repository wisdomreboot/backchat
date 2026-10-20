# Backchat sync: setup guide

You do this once, in about 15 minutes, using only a web browser. No terminal, no code to write. At the end, your phone and computer keep each other up to date on their own.

You need three things on hand:

- **Backchat 1.0.53 or later**, open at its address (for this copy, https://backchat.jonathandutoit.com).
- **`worker/backchat-sync-worker.js`** from this repository, the relay code. You will copy and paste it once.
- **A password manager or a private note** to keep two values safe: the access token and the relay address.

## What you are building

The relay is a mailbox you own. Each device drops an encrypted copy of its notes into its own slot and reads the other devices' slots. Cloudflare provides the mailbox for free. The relay never sees your notes, because Backchat encrypts them with your passphrase before they leave the device.

There are three keys, and each has one job:

| Name | What it does | Where it lives |
|---|---|---|
| **Relay address** | Where the mailbox is | Every device, and Cloudflare |
| **Access token** | Who may open the mailbox | Every device, and Cloudflare (as the secret `SYNC_TOKEN`) |
| **Passphrase** | What makes the contents readable | Only in your head. Typed once per device, never stored, never sent |

---

## Step 0. Check your version

Open Backchat and look at the bottom of **Settings > Advanced**. It should read **Backchat build 1.0.53** or later.

## Step 1. Make your access token (in Backchat, on your computer)

1. Open Backchat and tap the **gear icon** for **Settings**.
2. Scroll to **Sync between devices**.
3. Under **Access token**, tap **Make a token**.

Backchat fills the field with a long random code and copies it to your clipboard. **Paste it into your password manager now**, labelled "Backchat SYNC_TOKEN". You will paste it into Cloudflare in Step 5.

Leave this tab open.

## Step 2. Create a free Cloudflare account

1. Go to **dash.cloudflare.com** and sign up with your email.
2. Confirm your email when it asks.

You do not need to add a website or a domain. Skip anything about adding a site.

## Step 3. Create the storage box (KV namespace)

1. In the Cloudflare dashboard, open **Storage & Databases** in the left menu, then **Workers KV**.
2. Click **Create instance**. (Older screens call it **Create a namespace**.)
3. Name it `backchat-sync`.
4. Click **Create**.

## Step 4. Create the Worker and paste the relay code

1. In the left menu, open **Workers & Pages** (on some screens: **Compute (Workers)**).
2. Click **Create application**, choose **Start with Hello World!**, then **Get started**.
3. Name the Worker `backchat-sync`. If Cloudflare asks you to choose a **workers.dev subdomain**, pick anything, for example `jonathan`.
4. Click **Deploy**. Cloudflare creates a sample Worker.
5. Click **Edit code**. An editor opens with a file called `worker.js` or `workers.js`.
6. Select everything in that file and delete it.
7. Open `worker/backchat-sync-worker.js`, copy **all** of it, and paste it into the empty editor.
8. Click **Deploy** (top right).

Note the Worker's address, shown on its overview page. It looks like this:

```
https://backchat-sync.jonathan.workers.dev
```

Save it in your password manager next to the token.

## Step 5. Connect the storage box and add the token

Both settings are on the Worker's own page: **Workers & Pages > backchat-sync**.

**Connect the storage box**

1. Open the **Bindings** tab and click **Add binding**.
2. Choose **KV namespace**, then **Add binding**.
3. In **Variable name**, type `SYNC`. It must be exactly that: four capital letters.
4. In the dropdown, pick `backchat-sync`.
5. Click **Add binding**.

**Add the token as a secret**

1. Open **Settings**, find **Variables and Secrets**, and click **Add**.
2. For **Type**, choose **Secret**.
3. In **Variable name**, type `SYNC_TOKEN`, exactly like that.
4. In **Value**, paste the token from Step 1.
5. Click **Deploy** (or **Save**, then **Deploy**, if that is what the screen shows).

## Step 6. Check the relay

Paste the Worker address into a new browser tab. You should see a short line of text ending in:

```
"ok":true ... "message":"Ready. Paste this address into Backchat."
```

If it says **Setup incomplete**, the message names what is missing: the `SYNC` binding, the `SYNC_TOKEN` secret, or both. Fix that part of Step 5 and reload the tab.

## Step 7. Turn on sync on your computer

Back in Backchat, in **Settings > Sync between devices**:

1. **Relay address**: paste the Worker address.
2. **Access token**: already filled from Step 1. If you reloaded the page, paste it from your password manager.
3. **Passphrase**: choose something memorable, at least 8 characters. A short sentence works well.
4. Tap **Turn on sync**.

Backchat checks the relay and uploads your notes, then shows **Sync is on**.

## Step 8. Add your phone

1. On the computer, in the same section, tap **Copy setup link for another device**.
2. Send that link to yourself through Notes, Messages or email. Do not post it anywhere public: it contains the token.
3. On the phone, open the link. Backchat opens with **Settings** showing the address and token already filled in.
4. Type the **same passphrase** and tap **Turn on sync**.

**If you use Backchat as a home-screen app on the iPhone,** tapping the link opens Safari, which keeps its own separate storage. Instead: long-press the link and choose **Copy**, open Backchat from the home screen, go to **Settings > Sync between devices**, and paste the link into **Relay address**. The address and token fill in, and you type only the passphrase.

The phone catches up in a few seconds. Books from your computer appear on the phone with a small download badge: their marks have arrived, but the EPUB file has not. Add the EPUBs you want on the phone with **Add EPUB**, as you do today, and each one joins its marks.

You are done.

---

## Daily use

There is nothing to do. Backchat syncs when you open it, every few minutes while it is open, shortly after you change something, and when you leave the app. The **Backchat wordmark** on the home screen is the indicator:

- **Solid**: synced.
- **Pulsing**: syncing now.
- **Dimmed**: offline. Your changes are safe on this device and go out when you reconnect.
- **Faded, with "SYNC PAUSED"**: something needs you. Tap it to see why.

The **Hand off** button disappears while sync is on, because there is nothing left to carry.

## What syncs, and what does not

**Syncs:** highlights, comments, margins, tags, favourites, ratings, summaries, reading position, the saved listening spot, and deletions of marks and books.

**Does not sync:** EPUB files and covers (add each book once per device), display settings such as font and theme (these stay per device), and your folder.

Three behaviours worth knowing:

- **Your library is the collection; each device holds only the files you want there.** On the phone, open a book's page and tap **Remove from this device** to free its space. Only the EPUB file and its search index leave. The cover stays, dimmed with a download badge, and every mark, margin and position stays and keeps syncing. When you want the book again, its page shows **Add the EPUB to read**; pick the same file and it rejoins its marks.
- **Delete means delete everywhere.** With sync on, the button reads **Delete everywhere**, and it removes the book from every device, including your computer's library and folder. Backchat still saves a full backup of the book first, on the device where you deleted it. To free space, use Remove from this device instead.
- **Reading position follows where you read last,** on whichever device. Go back to reread a chapter on the phone and the desktop picks up there too. A book sitting open and untouched on one device moves to the newer place when the other syncs, with a Return button to go back; a book you are reading at that moment keeps its page. The saved listening spot works the same way: the spot saved last wins.

## If something goes wrong

| Backchat says | What it means | Fix |
|---|---|---|
| Could not reach that address | Wrong address, or the Worker was never deployed | Copy the address again from the Worker's overview page. Check Step 4 ended with Deploy |
| That address answered, but it is not a Backchat relay | The sample code is still in the Worker | Repeat Step 4, items 5 to 8 |
| Setup incomplete, add a KV binding named SYNC | Step 5 binding missing or misnamed | Variable name must be exactly `SYNC` |
| ...add a secret named SYNC_TOKEN | Secret missing, misnamed, or too short | Variable name must be exactly `SYNC_TOKEN` |
| The access token does not match | The token in Backchat differs from the secret | Paste the same token in both places. On the phone, open the setup link again |
| That passphrase does not match the one *(device)* uses | Different passphrases on two devices | Type the passphrase you used on the first device |
| Type your passphrase in Settings to resume sync | This browser lost its stored key, for example after clearing site data | Type the passphrase again and tap Turn on sync |

**If you forget the passphrase:** nothing on your devices is lost. Tap **Turn off sync on this device** on every device, then turn it on again everywhere with a new passphrase.

**If you get a new phone, or clear the browser:** open the setup link again (copy a fresh one from the computer) and type the passphrase.

**If you stop using a device:** in **Sync between devices**, tap **Forget** next to it. That removes its copy from the relay. Nothing on any device is deleted.

## Cost and limits

Cloudflare's free plan allows 1,000 uploads and 100,000 downloads a day, and 1 GB of storage. Backchat uploads only when something actually changed, so a heavy reading day uses perhaps a few dozen uploads. Your encrypted notes take a few megabytes at most. You should never pay anything.

## If Backchat ever moves to a new address

Browser storage belongs to the web address, so a browser sees an empty app at a new address. With sync running, recovery is simple: open the new address on each device, open a setup link, type the passphrase, and your marks come back. Only the EPUB files need adding again on browser-only devices. A setup link always points at the address it was copied from, so copy a fresh one at the new address.
