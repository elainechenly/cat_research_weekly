/**
 * Cat Research Weekly - subscription backend (Google Apps Script, bound to a Google Sheet).
 *
 * What it does
 *  - The subscribe page (GitHub Pages) POSTs {action: "subscribe" | "cancel", email, website}.
 *  - Subscribing sends a confirmation email; the address is only added to the list after the link is clicked.
 *  - Cancelling sends an email with a link to a page with a button; clicking it DELETES the row.
 *  - The weekly GitHub job fetches confirmed subscribers with ?action=list&key=ADMIN_KEY.
 *
 * Emails are sent by MailApp from the Google account that owns this script.
 * Free consumer Gmail accounts can send about 100 Apps Script emails per day, so requests are capped below that.
 */

const SHEET_NAME = "Subscribers";
const HEADERS = ["email", "status", "token", "requested_at", "confirmed_at", "last_email_at"];
const COOLDOWN_MS = 10 * 60 * 1000;            // do not email the same address twice within 10 minutes
const PENDING_TTL_MS = 7 * 24 * 3600 * 1000;   // unconfirmed requests are deleted after 7 days
const DAILY_EMAIL_CAP = 60;                    // confirmation / cancel emails per day (quota is ~100)
const SENDER_NAME = "Cat Research Weekly";
const EMAIL_RE = /^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$/;

// ---------- one-time setup: run this function once from the Apps Script editor ----------
function setup() {
  const sheet = getSheet_();
  const props = PropertiesService.getScriptProperties();
  let key = props.getProperty("ADMIN_KEY");
  if (!key) {
    key = Utilities.getUuid().replace(/-/g, "") + Utilities.getUuid().replace(/-/g, "");
    props.setProperty("ADMIN_KEY", key);
  }
  Logger.log("Sheet ready: " + sheet.getName());
  Logger.log("ADMIN_KEY (copy this into the GitHub secret SUBSCRIBERS_API_KEY): " + key);
  return key;
}

// ---------- web app entry points ----------
function doGet(e) {
  const p = (e && e.parameter) || {};
  switch (p.action) {
    case "confirm":     return confirmPage_(p.token);
    case "unsubscribe": return unsubscribePage_(p.token);
    case "list":        return json_(listConfirmed_(p.key));
    case "ping":        return text_("ok");
    default:            return text_("Cat Research Weekly subscription service.");
  }
}

function doPost(e) {
  let body = {};
  try { body = JSON.parse(e.postData.contents); } catch (err) { return json_({ ok: false }); }
  if (body.website) return json_({ ok: true });            // honeypot field filled in: a bot, pretend success
  if (body.action === "subscribe") requestSubscribe_(body.email);
  else if (body.action === "cancel") requestCancel_(body.email);
  return json_({ ok: true });                              // always neutral: never reveals who is subscribed
}

// ---------- core logic ----------
function normalizeEmail_(raw) {
  const email = String(raw || "").trim().toLowerCase();
  return (email.length <= 254 && EMAIL_RE.test(email)) ? email : "";
}

function requestSubscribe_(raw) {
  const email = normalizeEmail_(raw);
  if (!email) return "invalid";
  return withLock_(function () {
    const sheet = getSheet_();
    cleanupPending_(sheet);
    const found = findRow_(sheet, "email", email);
    const now = Date.now();
    if (found && found.row[1] === "confirmed") return "already";
    if (found) {                                           // pending: resend, but not too often
      if (now - Number(found.row[5] || 0) < COOLDOWN_MS) return "cooldown";
      if (!reserveEmail_()) return "cap";
      sendConfirmEmail_(email, found.row[2]);
      sheet.getRange(found.index, 6).setValue(now);
      return "resent";
    }
    if (!reserveEmail_()) return "cap";
    const token = Utilities.getUuid().replace(/-/g, "");
    sendConfirmEmail_(email, token);
    sheet.appendRow([email, "pending", token, now, "", now]);
    return "sent";
  });
}

function requestCancel_(raw) {
  const email = normalizeEmail_(raw);
  if (!email) return "invalid";
  return withLock_(function () {
    const sheet = getSheet_();
    const found = findRow_(sheet, "email", email);
    if (!found) return "unknown";                          // say nothing: do not reveal who is subscribed
    if (Date.now() - Number(found.row[5] || 0) < COOLDOWN_MS) return "cooldown";
    if (!reserveEmail_()) return "cap";
    sendCancelEmail_(email, found.row[2]);
    sheet.getRange(found.index, 6).setValue(Date.now());
    return "sent";
  });
}

function confirmToken_(token) {
  return withLock_(function () {
    const sheet = getSheet_();
    const found = token ? findRow_(sheet, "token", String(token)) : null;
    if (!found) return "unknown";
    if (found.row[1] !== "confirmed") {
      sheet.getRange(found.index, 2).setValue("confirmed");
      sheet.getRange(found.index, 5).setValue(Date.now());
    }
    return "confirmed";
  });
}

function removeToken_(token) {
  return withLock_(function () {
    const sheet = getSheet_();
    const found = token ? findRow_(sheet, "token", String(token)) : null;
    if (!found) return "unknown";
    sheet.deleteRow(found.index);
    return "removed";
  });
}

function listConfirmed_(key) {
  const real = PropertiesService.getScriptProperties().getProperty("ADMIN_KEY");
  if (!real || !key || String(key) !== real) return { ok: false, error: "unauthorized" };
  const rows = getSheet_().getDataRange().getValues().slice(1);
  const subscribers = rows.filter(function (r) { return r[1] === "confirmed"; })
                          .map(function (r) { return { email: r[0], token: r[2] }; });
  return { ok: true, subscribers: subscribers };
}

// ---------- pages opened from email links ----------
// Called by the button on the unsubscribe page (google.script.run). Links alone never delete anything,
// because email scanners often open links automatically.
function unsubscribeNow(token) { return removeToken_(token); }

function confirmPage_(token) {
  const result = confirmToken_(token);
  const ok = result === "confirmed";
  return page_(ok ? "You're subscribed!" : "Link not valid",
    ok ? "<p>Thank you! You'll get the Cat Research Weekly email every Tuesday.</p><p lang='zh'>谢谢！您将在每周二收到猫咪研究周报。</p>"
       : "<p>This confirmation link is invalid or has expired. Please subscribe again on the sign-up page.</p><p lang='zh'>此确认链接无效或已过期，请回到订阅页面重新订阅。</p>");
}

function unsubscribePage_(token) {
  const t = String(token || "").replace(/[^a-zA-Z0-9]/g, "");
  const html =
    "<p>Click the button to stop receiving Cat Research Weekly. Your email address will be deleted from our list.</p>" +
    "<p lang='zh'>点击下方按钮即可取消订阅，您的邮箱地址将从名单中删除。</p>" +
    "<button id='b' onclick='go()'>Yes, unsubscribe me / 确认取消订阅</button><p id='m'></p>" +
    "<script>function go(){document.getElementById('b').disabled=true;" +
    "google.script.run.withSuccessHandler(function(r){document.getElementById('m').innerText=" +
    "(r==='removed'||r==='unknown')?'You have been unsubscribed. / 您已取消订阅。':'Something went wrong. Please try again.';})" +
    ".withFailureHandler(function(){document.getElementById('m').innerText='Something went wrong. Please try again.';})" +
    ".unsubscribeNow('" + t + "');}</script>";
  return page_("Unsubscribe", html);
}

function page_(title, bodyHtml) {
  const html = "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>" +
    "<style>body{font-family:-apple-system,Segoe UI,Roboto,'PingFang SC','Microsoft YaHei',Arial,sans-serif;max-width:520px;margin:48px auto;padding:0 20px;color:#2d3748}" +
    "h1{font-size:22px;color:#1a365d}button{font-size:16px;padding:10px 18px;border:0;border-radius:8px;background:#2b6cb0;color:#fff;cursor:pointer}" +
    "button:disabled{opacity:.5}</style></head><body><h1>" + title + "</h1>" + bodyHtml + "</body></html>";
  return HtmlService.createHtmlOutput(html).setTitle(title);
}

// ---------- emails ----------
function webAppUrl_() { return ScriptApp.getService().getUrl(); }

function sendConfirmEmail_(email, token) {
  const link = webAppUrl_() + "?action=confirm&token=" + token;
  MailApp.sendEmail({
    to: email, name: SENDER_NAME,
    subject: "Please confirm your subscription / 请确认订阅",
    body: "Thanks for signing up for Cat Research Weekly!\nConfirm your subscription: " + link +
          "\n\nIf you did not ask for this, just ignore this email and nothing will happen.\n\n" +
          "感谢订阅猫咪研究周报！请点击链接确认订阅：" + link + "\n如果这不是您本人的操作，请忽略此邮件。",
    htmlBody: "<p>Thanks for signing up for <b>Cat Research Weekly</b>!</p><p><a href='" + link + "'>Confirm my subscription</a></p>" +
              "<p style='color:#718096'>If you did not ask for this, just ignore this email and nothing will happen.</p><hr>" +
              "<p lang='zh'>感谢订阅猫咪研究周报！</p><p lang='zh'><a href='" + link + "'>点击这里确认订阅</a></p>" +
              "<p lang='zh' style='color:#718096'>如果这不是您本人的操作，请忽略此邮件。</p>"
  });
}

function sendCancelEmail_(email, token) {
  const link = webAppUrl_() + "?action=unsubscribe&token=" + token;
  MailApp.sendEmail({
    to: email, name: SENDER_NAME,
    subject: "Confirm cancelling your subscription / 请确认取消订阅",
    body: "We received a request to cancel your Cat Research Weekly subscription.\nConfirm here: " + link +
          "\n\nIf you did not ask for this, ignore this email and you will stay subscribed.\n\n" +
          "我们收到了取消订阅猫咪研究周报的请求。请点击确认：" + link + "\n如果这不是您本人的操作，请忽略此邮件，您将继续收到周报。",
    htmlBody: "<p>We received a request to cancel your <b>Cat Research Weekly</b> subscription.</p>" +
              "<p><a href='" + link + "'>Confirm cancellation</a></p>" +
              "<p style='color:#718096'>If you did not ask for this, ignore this email and you will stay subscribed.</p><hr>" +
              "<p lang='zh'>我们收到了取消订阅猫咪研究周报的请求。</p><p lang='zh'><a href='" + link + "'>点击这里确认取消订阅</a></p>" +
              "<p lang='zh' style='color:#718096'>如果这不是您本人的操作，请忽略此邮件，您将继续收到周报。</p>"
  });
}

// ---------- helpers ----------
function getSheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
    sheet.appendRow(HEADERS);
  }
  return sheet;
}

function findRow_(sheet, column, value) {
  const col = HEADERS.indexOf(column);
  const rows = sheet.getDataRange().getValues();
  for (let i = 1; i < rows.length; i++) {
    if (String(rows[i][col]) === value) return { index: i + 1, row: rows[i] };   // index = 1-based sheet row
  }
  return null;
}

function cleanupPending_(sheet) {
  const rows = sheet.getDataRange().getValues();
  const now = Date.now();
  for (let i = rows.length - 1; i >= 1; i--) {             // bottom-up so deleting keeps indexes valid
    if (rows[i][1] === "pending" && now - Number(rows[i][3] || 0) > PENDING_TTL_MS) sheet.deleteRow(i + 1);
  }
}

function reserveEmail_() {                                 // daily cap so bots cannot burn the email quota
  const props = PropertiesService.getScriptProperties();
  const today = Utilities.formatDate(new Date(), "UTC", "yyyy-MM-dd");
  let count = props.getProperty("mail_day") === today ? Number(props.getProperty("mail_count") || 0) : 0;
  if (count >= DAILY_EMAIL_CAP) return false;
  props.setProperty("mail_day", today);
  props.setProperty("mail_count", String(count + 1));
  return true;
}

function withLock_(fn) {
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try { return fn(); } finally { lock.releaseLock(); }
}

function json_(obj) { return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON); }
function text_(s) { return ContentService.createTextOutput(s); }
