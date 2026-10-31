// Offline test of the sign-up page script with a fake browser. Run: node docs/test_page.js
const fs = require("fs");
const vm = require("vm");
const path = require("path");
const assert = require("assert").strict;

const HTML = fs.readFileSync(path.join(__dirname, "index.html"), "utf8");
const SCRIPT = HTML.match(/<script>([\s\S]*?)<\/script>/)[1];
const REAL_URL = "https://script.google.com/macros/s/TEST/exec";

function makePage({ url = REAL_URL, fetchImpl } = {}) {
  const els = {};
  const el = (id) => (els[id] ||= { id, value: "", disabled: false, textContent: "", className: "", handlers: {},
    addEventListener(type, fn) { this.handlers[type] = fn; }, focus() { this.focused = true; } });
  const calls = [];
  const sandbox = {
    document: { getElementById: el },
    fetch: async (u, opts) => { calls.push({ u, opts }); return fetchImpl ? fetchImpl() : {}; },
    setTimeout: (fn) => fn(),                       // run the "re-enable buttons" timer immediately
    JSON, RegExp, String,
  };
  vm.createContext(sandbox);
  // vm.runInContext(SCRIPT.replace("PASTE_YOUR_WEB_APP_URL_HERE", url), sandbox);
  vm.runInContext(SCRIPT.replace("https://script.google.com/macros/s/AKfycbwBQRifPe4PPHpEskqVlzlcPw7aPmycSzyivqXYYXkS9wAE6zPi2aMw3r0jZCLLh06m/exec", url), sandbox);

  return { els, calls, click: (id) => els[id].handlers.click() };
}

const tests = [];
const test = (n, f) => tests.push([n, f]);

test("the page has the required texts and controls", () => {
  assert.match(HTML, /Welcome to Cat Research Weekly Reading/);
  assert.match(HTML, /id="email"/);
  assert.match(HTML, /id="subscribe"[^>]*>Subscribe/);
  assert.match(HTML, /id="cancel"[^>]*>Cancel subscription/);
  assert.match(HTML, /name="viewport"/);
  assert.match(HTML, /prefers-color-scheme: dark/);
});

test("intro text is the requested one, the Example section is gone, and the disclaimer comes last", () => {
  assert.match(HTML, /Curious about what science can teach you about your cat 🐱\?/);
  assert.match(HTML, /translated into insights you can actually use/);
  assert.match(HTML, /live a happier, healthier life/);
  assert.ok(!/Example:/.test(HTML) && !/class="tip"/.test(HTML) && !/kidney trouble/.test(HTML));
  assert.match(HTML, /<strong>AI Disclaimer:<\/strong> Summaries and practical tips are AI-generated/);
  assert.match(HTML, /<strong>Copyright &amp; Sources:<\/strong> Research papers remain the intellectual property/);
  assert.ok(HTML.indexOf("AI Disclaimer:") > HTML.indexOf('id="cancel"'));
  assert.ok(HTML.indexOf("Copyright &amp; Sources:") > HTML.indexOf("AI Disclaimer:"));
  assert.ok(HTML.indexOf("Copyright &amp; Sources:") > HTML.indexOf("Browse all past papers"));
});

test("invalid email: shows an error and sends nothing", async () => {
  const p = makePage();
  for (const bad of ["", "nope", "a@b", "a b@c.com", "x@y.com,z@w.com"]) {
    p.els.email.value = bad;
    await p.click("subscribe");
    assert.equal(p.els.msg.className, "err");
  }
  assert.equal(p.calls.length, 0);
});

test("placeholder URL: tells the owner the page is not connected yet", async () => {
  const p = makePage({ url: "PASTE_YOUR_WEB_APP_URL_HERE" });
  p.els.email.value = "ann@example.com";
  await p.click("subscribe");
  assert.match(p.els.msg.textContent, /not connected/);
  assert.equal(p.calls.length, 0);
});

test("subscribe: posts the right JSON as a simple no-cors request and shows the neutral message", async () => {
  const p = makePage();
  p.els.email.value = "  ann@example.com ";
  await p.click("subscribe");
  assert.equal(p.calls.length, 1);
  const { u, opts } = p.calls[0];
  assert.equal(u, REAL_URL);
  assert.equal(opts.method, "POST");
  assert.equal(opts.mode, "no-cors");
  assert.match(opts.headers["Content-Type"], /^text\/plain/);
  assert.deepEqual(JSON.parse(opts.body), { action: "subscribe", email: "ann@example.com", website: "" });
  assert.equal(p.els.msg.className, "ok");
  assert.match(p.els.msg.textContent, /confirmation email/);
});

test("cancel: posts the cancel action and uses the 'if subscribed' wording", async () => {
  const p = makePage();
  p.els.email.value = "ann@example.com";
  await p.click("cancel");
  assert.equal(JSON.parse(p.calls[0].opts.body).action, "cancel");
  assert.match(p.els.msg.textContent, /If this address is subscribed/);
});

test("honeypot value is passed along so the server can discard bots", async () => {
  const p = makePage();
  p.els.email.value = "bot@example.com";
  p.els.website.value = "http://spam";
  await p.click("subscribe");
  assert.equal(JSON.parse(p.calls[0].opts.body).website, "http://spam");
});

test("network failure shows an error, and the buttons are usable again", async () => {
  const p = makePage({ fetchImpl: () => { throw new TypeError("Failed to fetch"); } });
  p.els.email.value = "ann@example.com";
  await p.click("subscribe");
  assert.equal(p.els.msg.className, "err");
  assert.equal(p.els.subscribe.disabled, false);
  assert.equal(p.els.cancel.disabled, false);
});

test("Enter key in the email box subscribes", async () => {
  const p = makePage();
  p.els.email.value = "ann@example.com";
  await p.els.email.handlers.keydown({ key: "Enter" });
  assert.equal(JSON.parse(p.calls[0].opts.body).action, "subscribe");
});

(async () => {
  let failed = 0;
  for (const [name, fn] of tests) {
    try { await fn(); console.log("PASS", name); }
    catch (err) { failed++; console.log("FAIL", name, "\n  ", err.message); }
  }
  console.log(`${tests.length - failed} passed, ${failed} failed`);
  process.exit(failed ? 1 : 0);
})();
