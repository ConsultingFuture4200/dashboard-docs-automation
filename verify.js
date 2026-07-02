// Audit Layer 2: verify the docs against the LIVE app (drift + broken steps).
//
// This is the Doc Detective role, integrated with our own collection data. For
// each screen it re-runs the reach steps from screens.yaml (same definition used
// to capture) and then checks that each element the docs claim under "Key
// elements" is actually present on the live page right now. It reports:
//
//   NAV BROKEN   - the screen's reach steps no longer succeed
//   MISSING      - a documented element is not found on the live page (drift, or
//                  a hallucination confirmed against the running app)
//
// Layer 1 (audit.py) compares docs to the capture snapshot; this layer compares
// them to the live app, so it catches changes made since the last capture.
// Requires the app reachable (open the tunnel first) and audit/audit.json to
// exist (run `python audit.py` first).
//
//   npm run verify                 # all screens
//   npm run verify -- home inbox   # only these ids
//
import { chromium } from "playwright";
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { parse } from "yaml";
import { loadConfig } from "./config-check.js";

const root = new URL("./", import.meta.url);
const cfg = loadConfig(root);
const screens = parse(readFileSync(new URL("screens.yaml", root), "utf8"));

const auditPath = new URL("audit/audit.json", root);
if (!existsSync(auditPath)) {
  console.error("\n  audit/audit.json not found. Run: python audit.py\n");
  process.exit(1);
}
const documented = Object.fromEntries(
  JSON.parse(readFileSync(auditPath, "utf8")).map((r) => [r.id, r.documented || []])
);

const only = process.argv.slice(2);
const todo = only.length ? screens.filter((s) => only.includes(s.id)) : screens;

async function runStep(page, step) {
  if (step.goto !== undefined) {
    const url = step.goto.startsWith("http") ? step.goto : cfg.baseUrl.replace(/\/$/, "") + step.goto;
    await page.goto(url, { waitUntil: "networkidle" });
  } else if (step.click !== undefined) await page.click(step.click);
  else if (step.fill !== undefined) await page.fill(step.fill.selector, step.fill.value);
  else if (step.hover !== undefined) await page.hover(step.hover);
  else if (step.waitFor !== undefined) await page.waitForSelector(step.waitFor, { state: "visible" });
  else if (step.press !== undefined) await page.keyboard.press(step.press);
  else if (step.wait !== undefined) await page.waitForTimeout(step.wait);
}

// A documented element is "present" if a visible node contains its text, or a
// meaningful chunk of it (docs sometimes append explanatory words to a label).
const ROLE = { a: "link", link: "link", button: "button", tab: "tab",
               menuitem: "menuitem", input: "textbox", textarea: "textbox", select: "combobox" };
// Generic role words docs append to a control name ("Home link", "Reddit module").
const TRAIL = /\s+(links?|buttons?|fields?|tabs?|icons?|menus?|selects?|dropdowns?|toggles?|modules?|sections?|panels?|areas?|options?)$/i;

async function present(page, label) {
  // Strip markdown emphasis/code and any surrounding quotation marks the draft
  // may have wrapped around the label.
  const md = label.replace(/`|\*\*/g, "").replace(/^["'“”']+|["'“”']+$/g, "").trim();
  const prefix = md.match(/^\s*(a|link|button|input|select|textarea|tab|menuitem|div|span|img)\s*:\s*(.+)$/i);
  let name = (prefix ? prefix[2] : md).trim().replace(TRAIL, "").trim();
  const shortName = name.split(/\s+/).slice(0, 3).join(" ");
  const names = name === shortName ? [name] : [name, shortName];

  // Match by accessible role + name (handles labels split across DOM nodes and
  // icon buttons whose visible text is empty but have an aria-label).
  const roles = prefix && ROLE[prefix[1].toLowerCase()]
    ? [ROLE[prefix[1].toLowerCase()]]
    : ["button", "link", "tab", "menuitem"];
  for (const n of names) {
    if (n.length < 2) continue;
    for (const role of roles) {
      try { if ((await page.getByRole(role, { name: n }).count()) > 0) return true; } catch { /* next */ }
    }
    try { if ((await page.getByText(n, { exact: false }).count()) > 0) return true; } catch { /* next */ }
  }
  return false;
}

const browser = await chromium.launch();
const context = await browser.newContext({
  ...(cfg.auth === true ? { storageState: cfg.storageState } : {}),
  viewport: cfg.viewport,
});

const results = [];
for (const s of todo) {
  const page = await context.newPage();
  const r = { id: s.id, navBroken: false, missing: [], checked: 0 };
  try {
    process.stdout.write(`  ${s.id} ... `);
    for (const step of s.steps) await runStep(page, step);
    await page.waitForTimeout(cfg.settleMs || 800);
    for (const el of documented[s.id] || []) {
      r.checked++;
      if (!(await present(page, el))) r.missing.push(el);
    }
    console.log(`nav ok, ${r.checked} checked, ${r.missing.length} missing`);
  } catch (err) {
    r.navBroken = true;
    console.log(`NAV BROKEN: ${err.message.split("\n")[0]}`);
  } finally {
    results.push(r);
    await page.close();
  }
}
await browser.close();

// Report
mkdirSync(new URL("audit/", root), { recursive: true });
const brokenNav = results.filter((r) => r.navBroken).map((r) => r.id);
const totalMissing = results.reduce((n, r) => n + r.missing.length, 0);
const lines = [
  "# Doc Accuracy Audit — Layer 2 (live verification)",
  "",
  `- Screens checked: **${results.length}**`,
  `- Screens with broken navigation: **${brokenNav.length}**${brokenNav.length ? " (" + brokenNav.join(", ") + ")" : ""}`,
  `- Documented elements missing on the live app: **${totalMissing}**`,
  "",
  "| Screen | Nav | Checked | Missing |",
  "|--------|-----|---------|---------|",
  ...results.map((r) => `| ${r.id} | ${r.navBroken ? "BROKEN" : "ok"} | ${r.checked} | ${r.missing.length} |`),
  "",
];
for (const r of results) {
  if (!r.missing.length) continue;
  lines.push(`## ${r.id}`, "**Documented but not found on the live page:**", ...r.missing.map((m) => `- ${m}`), "");
}
writeFileSync(new URL("audit/live-report.md", root), lines.join("\n") + "\n");
console.log(`\n  Layer 2 done: ${brokenNav.length} broken nav, ${totalMissing} missing elements. Report: audit/live-report.md\n`);
process.exit(brokenNav.length || totalMissing ? 1 : 0);
