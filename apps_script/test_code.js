// Offline tests for Code.gs using fake Google services. Run: node apps_script/test_code.js
const fs = require("fs");
const vm = require("vm");
const path = require("path");
const assert = require("assert").strict;
const crypto = require("crypto");

const SOURCE = fs.readFileSync(path.join(__dirname, "Code.gs"), "utf8");
const DAY = 24 * 3600 * 1000;

function makeEnv() {
  const rows = [];
  let exists = false;
  const sheet = {
    getName: () => "Subscribers",
    getDataRange: () => ({ getValues: () => rows.map((r) => r.slice()) }),
    appendRow: (r) => rows.push(r.slice()),
    getRange: (row, col) => ({ setValue: (v) => { rows[row - 1][col - 1] = v; } }),
    deleteRow: (row) => rows.splice(row - 1, 1),
  };
  const props = new Map();
  const sent = [];
  const clock = { now: Date.UTC(2026, 9, 31, 12, 0, 0) };
  class FakeDate extends Date {
    constructor(...a) { if (a.length) super(...a); else super(clock.now); }
    static now() { return clock.now; }
  }
  const out = (s) => ({ content: s, setMimeType() { return this; }, getContent() { return this.content; } });
  const sandbox = {
    Date: FakeDate, JSON, String, Number, Math, Map, Date_: FakeDate,
    Logger: { log() {} },
    SpreadsheetApp: { getActiveSpreadsheet: () => ({
      getSheetByName: () => (exists ? sheet : null),
      insertSheet: () => { exists = true; return sheet; } }) },
    PropertiesService: { getScriptProperties: () => ({
      getProperty: (k) => (props.has(k) ? props.get(k) : null), setProperty: (k, v) => props.set(k, String(v)) }) },
    Utilities: { getUuid: () => crypto.randomUUID(), formatDate: (d) => d.toISOString().slice(0, 10) },
    LockService: { getScriptLock: () => ({ waitLock() {}, releaseLock() {} }) },
    MailApp: { sendEmail: (m) => sent.push(m) },
    ContentService: { createTextOutput: out, MimeType: { JSON: "json" } },
    HtmlService: { createHtmlOutput: (h) => ({ html: h, setTitle(t) { this.title = t; return this; }, getContent() { return h; } }) },
    ScriptApp: { getService: () => ({ getUrl: () => "https://script.google.com/macros/s/TEST/exec" }) },
  };
  vm.createContext(sandbox);
  vm.runInContext(SOURCE, sandbox);
  const post = (obj) => JSON.parse(sandbox.doPost({ postData: { contents: JSON.stringify(obj) } }).getContent());
  const get = (p) => sandbox.doGet({ parameter: p });
  const tokenOf = (email) => rows.find((r) => r[0] === email)[2];
  return { ctx: sandbox, rows, sent, clock, props, post, get, tokenOf };
}

const tests = [];
const test = (name, fn) => tests.push([name, fn]);

test("setup creates the sheet and a stable ADMIN_KEY", () => {
  const e = makeEnv();
  const k1 = e.ctx.setup();
  const k2 = e.ctx.setup();
  assert.equal(k1, k2);
  assert.ok(k1.length >= 60);
  assert.equal(JSON.stringify(e.rows[0]), JSON.stringify(["email", "status", "token", "requested_at", "confirmed_at", "last_email_at"]));
});

test("subscribe: sends a confirmation email and stores a pending row", () => {
  const e = makeEnv(); e.ctx.setup();
  assert.deepEqual(e.post({ action: "subscribe", email: "  Ann@Example.COM " }), { ok: true });
  assert.equal(e.sent.length, 1);
  assert.equal(e.sent[0].to, "ann@example.com");
  assert.match(e.sent[0].body, /action=confirm&token=[0-9a-f]{32}/);
  assert.match(e.sent[0].body, /请点击链接确认订阅/);
  assert.equal(e.rows[1][1], "pending");
});

test("subscribe: invalid addresses are ignored but the reply stays neutral", () => {
  const e = makeEnv(); e.ctx.setup();
  for (const bad of ["", "nope", "a@b", "a b@c.com", "x@y.com,z@w.com"]) {
    assert.deepEqual(e.post({ action: "subscribe", email: bad }), { ok: true });
  }
  assert.equal(e.sent.length, 0);
  assert.equal(e.rows.length, 1);
});

test("subscribe: repeat within 10 minutes is ignored, later it re-sends the same token", () => {
  const e = makeEnv(); e.ctx.setup();
  e.post({ action: "subscribe", email: "a@x.com" });
  e.clock.now += 5 * 60 * 1000;
  e.post({ action: "subscribe", email: "a@x.com" });
  assert.equal(e.sent.length, 1);
  e.clock.now += 6 * 60 * 1000;
  e.post({ action: "subscribe", email: "A@x.com" });
  assert.equal(e.sent.length, 2);
  assert.equal(e.rows.length, 2);                                  // still one subscriber row
  assert.ok(e.sent[1].body.includes(e.tokenOf("a@x.com")));
});

test("confirm link activates the subscription; repeat clicks are harmless; bad token is rejected", () => {
  const e = makeEnv(); e.ctx.setup();
  e.post({ action: "subscribe", email: "a@x.com" });
  const t = e.tokenOf("a@x.com");
  assert.match(e.get({ action: "confirm", token: t }).getContent(), /You're subscribed!/);
  assert.equal(e.rows[1][1], "confirmed");
  assert.match(e.get({ action: "confirm", token: t }).getContent(), /You're subscribed!/);
  assert.match(e.get({ action: "confirm", token: "bogus" }).getContent(), /Link not valid/);
  assert.match(e.get({ action: "confirm" }).getContent(), /Link not valid/);
});

test("already-confirmed address subscribing again gets no email", () => {
  const e = makeEnv(); e.ctx.setup();
  e.post({ action: "subscribe", email: "a@x.com" });
  e.get({ action: "confirm", token: e.tokenOf("a@x.com") });
  e.clock.now += DAY;
  e.post({ action: "subscribe", email: "a@x.com" });
  assert.equal(e.sent.length, 1);
});

test("list: refuses without the right key and returns only confirmed subscribers", () => {
  const e = makeEnv(); const key = e.ctx.setup();
  e.post({ action: "subscribe", email: "ok@x.com" });
  e.post({ action: "subscribe", email: "pending@x.com" });
  e.get({ action: "confirm", token: e.tokenOf("ok@x.com") });
  for (const p of [{ action: "list" }, { action: "list", key: "wrong" }, { action: "list", key: "" }]) {
    const r = JSON.parse(e.get(p).getContent());
    assert.deepEqual(r, { ok: false, error: "unauthorized" });
  }
  const r = JSON.parse(e.get({ action: "list", key }).getContent());
  assert.equal(r.ok, true);
  assert.deepEqual(r.subscribers, [{ email: "ok@x.com", token: e.tokenOf("ok@x.com") }]);
});

test("list is unauthorized when setup() was never run (no key exists)", () => {
  const e = makeEnv();
  assert.equal(JSON.parse(e.get({ action: "list", key: "anything" }).getContent()).ok, false);
});

test("cancel: emails a link only to existing addresses; the link page does not delete by itself", () => {
  const e = makeEnv(); const key = e.ctx.setup();
  e.post({ action: "subscribe", email: "a@x.com" });
  e.get({ action: "confirm", token: e.tokenOf("a@x.com") });
  e.clock.now += DAY;
  assert.deepEqual(e.post({ action: "cancel", email: "stranger@x.com" }), { ok: true });
  assert.equal(e.sent.length, 1);                                  // nothing sent to the stranger
  assert.deepEqual(e.post({ action: "cancel", email: "a@x.com" }), { ok: true });
  assert.equal(e.sent.length, 2);
  assert.match(e.sent[1].body, /action=unsubscribe&token=/);
  const token = e.tokenOf("a@x.com");
  const page = e.get({ action: "unsubscribe", token }).getContent();   // what an email scanner would do
  assert.match(page, /unsubscribeNow/);
  assert.equal(JSON.parse(e.get({ action: "list", key }).getContent()).subscribers.length, 1);
});

test("unsubscribeNow deletes the row completely; calling it again is harmless", () => {
  const e = makeEnv(); const key = e.ctx.setup();
  e.post({ action: "subscribe", email: "a@x.com" });
  const t = e.tokenOf("a@x.com");
  e.get({ action: "confirm", token: t });
  assert.equal(e.ctx.unsubscribeNow(t), "removed");
  assert.equal(e.rows.length, 1);                                  // header only
  assert.equal(e.ctx.unsubscribeNow(t), "unknown");
  assert.deepEqual(JSON.parse(e.get({ action: "list", key }).getContent()).subscribers, []);
});

test("unsubscribe page strips anything unsafe from the token", () => {
  const e = makeEnv(); e.ctx.setup();
  const page = e.get({ action: "unsubscribe", token: "');alert(1);//<script>" }).getContent();
  assert.ok(!page.includes("alert(1);//"));
  assert.ok(!page.includes("<script>alert"));
});

test("honeypot: a filled hidden field is silently ignored", () => {
  const e = makeEnv(); e.ctx.setup();
  assert.deepEqual(e.post({ action: "subscribe", email: "bot@x.com", website: "http://spam" }), { ok: true });
  assert.equal(e.sent.length, 0);
  assert.equal(e.rows.length, 1);
});

test("daily cap stops email sending at 60 and resets the next day", () => {
  const e = makeEnv(); e.ctx.setup();
  for (let i = 0; i < 65; i++) e.post({ action: "subscribe", email: `u${i}@x.com` });
  assert.equal(e.sent.length, 60);
  e.clock.now += DAY;
  e.post({ action: "subscribe", email: "late@x.com" });
  assert.equal(e.sent.length, 61);
});

test("unconfirmed requests older than 7 days are deleted; confirmed ones are kept", () => {
  const e = makeEnv(); e.ctx.setup();
  e.post({ action: "subscribe", email: "old@x.com" });
  e.post({ action: "subscribe", email: "keep@x.com" });
  e.get({ action: "confirm", token: e.tokenOf("keep@x.com") });
  e.clock.now += 8 * DAY;
  e.post({ action: "subscribe", email: "new@x.com" });
  const emails = e.rows.slice(1).map((r) => r[0]).sort();
  assert.deepEqual(emails, ["keep@x.com", "new@x.com"]);
});

test("doPost: bad JSON and unknown actions never crash and never email", () => {
  const e = makeEnv(); e.ctx.setup();
  assert.deepEqual(JSON.parse(e.ctx.doPost({ postData: { contents: "{not json" } }).getContent()), { ok: false });
  assert.deepEqual(e.post({ action: "dance", email: "a@x.com" }), { ok: true });
  assert.equal(e.sent.length, 0);
});

test("ping and default GET answers", () => {
  const e = makeEnv();
  assert.equal(e.get({ action: "ping" }).getContent(), "ok");
  assert.match(e.get({}).getContent(), /subscription service/);
});

let failed = 0;
for (const [name, fn] of tests) {
  try { fn(); console.log("PASS", name); }
  catch (err) { failed++; console.log("FAIL", name, "\n  ", err.message); }
}
console.log(`${tests.length - failed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
