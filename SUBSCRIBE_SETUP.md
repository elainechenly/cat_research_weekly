# Subscribe page setup (about 20 minutes)

How it fits together
- **Google Sheet + Apps Script** (in the Google account that sends the emails) stores subscribers and sends the
  confirm / cancel emails.
- **`docs/index.html`** is the public sign-up page (GitHub Pages).
- **The weekly GitHub job** reads the confirmed list and sends each person their own email with a personal unsubscribe link.

## 1. Create the Sheet and script (sign in as the NEW project Gmail account, the same one as `GMAIL_USER`)
1. Go to sheets.google.com, create a **blank spreadsheet**, name it `Cat Research Weekly Subscribers`. Keep it private.
2. **Extensions -> Apps Script**. Delete the sample code, paste in all of `apps_script/Code.gs`, click **Save**.
3. In the function drop-down (top bar) choose **`setup`**, click **Run**. Google asks for permission:
   Review permissions -> choose the account -> "Google hasn't verified this app" -> **Advanced -> Go to ... (unsafe) -> Allow**.
   (It is your own script; the warning appears for every personal script.)
4. When the run finishes, the **Execution log** at the bottom shows a line starting with
   `ADMIN_KEY (copy this into the GitHub secret SUBSCRIBERS_API_KEY): ...`. Copy that long key.
   A tab named `Subscribers` now exists in the Sheet.

## 2. Publish it as a web app
1. **Deploy -> New deployment -> (gear icon) Web app**.
2. Description `v1`. **Execute as: Me**. **Who has access: Anyone**. Click **Deploy**.
3. Copy the **Web app URL** (ends in `/exec`).
4. Test in your browser:
   - `<URL>?action=ping` shows `ok`.
   - `<URL>?action=list&key=wrong` shows `{"ok":false,"error":"unauthorized"}`.
5. After any later change to `Code.gs`: **Deploy -> Manage deployments -> pencil -> Version: New version -> Deploy**
   (the URL stays the same).

## 3. GitHub secrets (Settings -> Secrets and variables -> Actions)
| Name | Value |
|---|---|
| `SUBSCRIBERS_URL` | the Web app URL ending in `/exec` |
| `SUBSCRIBERS_API_KEY` | the `ADMIN_KEY` from step 1.4 |

`EMAIL_RECIPIENTS` can stay as your own address (you then also get a copy) or be emptied.

## 4. Publish the sign-up page
1. Open `docs/index.html`, replace `PASTE_YOUR_WEB_APP_URL_HERE` with the Web app URL, commit and push.
2. GitHub repo **Settings -> Pages -> Build and deployment**: Source **Deploy from a branch**, Branch **main**, folder **/docs**, Save.
3. After 1-2 minutes the page is at `https://elainechenly.github.io/cat_research_weekly/`.

## 5. Test everything
1. On the page, subscribe with a second address of yours. Check Inbox/Spam for the confirmation email, click the link.
   The Sheet row changes from `pending` to `confirmed`.
2. Actions -> Run workflow -> **untick Dry run**, tick **Force** -> the digest goes to confirmed subscribers
   (plus `EMAIL_RECIPIENTS`). It has a personal "Unsubscribe" link.
3. On the page, click **Cancel subscription** with that address, open the email, click the link, then the button.
   The row is deleted from the Sheet.

## Good to know
- Free Gmail accounts can send about 100 Apps Script emails a day; the script stops at 60 confirmation / cancel
  emails per day. The weekly digest is sent through Gmail SMTP (about 500 messages a day), not Apps Script.
- Unconfirmed sign-ups are deleted after 7 days. The same address can be emailed at most once every 10 minutes.
- The page never reveals whether an address is on the list.
- Never share the `ADMIN_KEY`. If it leaks, delete the `ADMIN_KEY` row in Apps Script -> Project Settings ->
  Script Properties, run `setup` again, and update the GitHub secret.
