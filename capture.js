// Walks every screen in screens.yaml using the saved SSO session, and for each
// one saves:
//   capture/<id>.png    full screenshot
//   capture/<id>.json   { id, name, order, note, url, text, controls }
//
// `text` is the visible page text. `controls` is the accessible name + role of
// every button/link/field. draft.py grounds the LLM on these so it uses your
// REAL labels instead of hallucinating UI from pixels.
//
//   npm run capture                 # all screens
//   npm run capture -- dashboard-home appointments-calendar   # just these ids
//
import { chromium } from "playwright";
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import { parse } from "yaml";

const root = new URL("./", import.meta.url);
const cfg = parse(readFileSync(new URL("config.yaml", root), "utf8"));
const screens = parse(readFileSync(new URL("screens.yaml", root), "utf8"));

// Auth is optional. With `auth: true` we require a saved session from `npm run
// auth`. With `auth: false` (app is open or serves its own token), capture without one.
const useAuth = cfg.auth === true;
if (useAuth && !existsSync(new URL(cfg.storageState, root))) {
  console.error(`\n  auth is enabled but no saved session (${cfg.storageState}). Run: npm run auth\n`);
  process.exit(1);
}

const only = process.argv.slice(2);
const todo = only.length ? screens.filter((s) => only.includes(s.id)) : screens;
if (!todo.length) {
  console.error("  No matching screens.");
  process.exit(1);
}

mkdirSync(new URL("capture/", root), { recursive: true });

const browser = await chromium.launch();
const context = await browser.newContext({
  ...(useAuth ? { storageState: cfg.storageState } : {}),
  viewport: cfg.viewport,
});

async function runStep(page, step) {
  if (step.goto !== undefined) {
    const url = step.goto.startsWith("http") ? step.goto : cfg.baseUrl.replace(/\/$/, "") + step.goto;
    await page.goto(url, { waitUntil: "networkidle" });
  } else if (step.click !== undefined) {
    await page.click(step.click);
  } else if (step.fill !== undefined) {
    await page.fill(step.fill.selector, step.fill.value);
  } else if (step.hover !== undefined) {
    await page.hover(step.hover);
  } else if (step.waitFor !== undefined) {
    await page.waitForSelector(step.waitFor, { state: "visible" });
  } else if (step.press !== undefined) {
    await page.keyboard.press(step.press);
  } else if (step.wait !== undefined) {
    await page.waitForTimeout(step.wait);
  } else {
    console.warn(`    unknown step:`, JSON.stringify(step));
  }
}

// Grow inner-scrolling panels to their full height so fullPage captures
// below-the-fold content. Elements matching freezeSelectors are pinned at their
// current height first, so a persistent side rail (chat history) doesn't inflate
// the page. Returns nothing; call before screenshot.
async function expandScroll(page, freezeSelectors, maxHeightPx) {
  await page.evaluate(({ freeze, cap }) => {
    const frozen = new Set();
    // Pin frozen elements at their current height BEFORE expanding the rest.
    for (const sel of freeze || []) {
      for (const el of document.querySelectorAll(sel)) {
        const h = el.clientHeight;
        el.style.height = `${h}px`;
        el.style.maxHeight = `${h}px`;
        el.style.overflow = "hidden";
        frozen.add(el);
        el.querySelectorAll("*").forEach((c) => frozen.add(c));
      }
    }
    for (const el of [document.documentElement, document.body]) {
      el.style.height = "auto";
      el.style.maxHeight = "none";
      el.style.overflow = "visible";
    }
    const isScrollable = (el) => {
      const s = getComputedStyle(el);
      if (!/(auto|scroll)/.test(s.overflowY) || el.scrollHeight <= el.clientHeight + 4) return false;
      // Leave huge virtualized lists (contacts, logs, inbox) alone — expanding
      // them produces a giant mostly-blank image. A viewport-height shot of the
      // top rows is the better doc result; the screenshot cap is the backstop.
      if (cap && el.scrollHeight > cap) return false;
      return true;
    };
    // For each inner scroller, relax it and its ancestor chain (which usually
    // pins height to the viewport) so content flows into document height.
    const scrollers = [...document.querySelectorAll("*")].filter((el) => !frozen.has(el) && isScrollable(el));
    for (const start of scrollers) {
      let node = start;
      while (node && node !== document.body) {
        if (!frozen.has(node)) {
          node.style.height = "auto";
          node.style.maxHeight = "none";
          node.style.minHeight = "0";
          node.style.overflow = "visible";
        }
        node = node.parentElement;
      }
    }
  }, { freeze: freezeSelectors, cap: maxHeightPx });
  await page.waitForTimeout(350); // let layout reflow
}

// Pull the accessible name + role of interactive controls, so the docs use the
// exact labels a user sees.
async function extractControls(page) {
  return page.evaluate(() => {
    const out = [];
    const sel = "button, a[href], input, select, textarea, [role=button], [role=tab], [role=menuitem]";
    for (const el of document.querySelectorAll(sel)) {
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) continue; // skip hidden
      const label =
        el.getAttribute("aria-label") ||
        el.innerText?.trim() ||
        el.getAttribute("placeholder") ||
        el.getAttribute("name") ||
        el.getAttribute("title") ||
        "";
      const role = el.getAttribute("role") || el.tagName.toLowerCase();
      const clean = label.replace(/\s+/g, " ").slice(0, 80);
      if (clean) out.push(`${role}: ${clean}`);
    }
    return [...new Set(out)]; // dedupe
  });
}

let ok = 0;
for (const s of todo) {
  const page = await context.newPage();
  try {
    process.stdout.write(`  ${s.id} ... `);
    for (const step of s.steps) await runStep(page, step);
    await page.waitForTimeout(cfg.settleMs);
    if (cfg.expandScroll) await expandScroll(page, cfg.freezeSelectors, cfg.maxHeightPx);

    const pngPath = fileURLToPath(new URL(`capture/${s.id}.png`, root));
    // Cap very tall pages (long lists/logs) so images stay doc-sized and small
    // enough for a vision model, while still showing header + controls + top rows.
    const docHeight = await page.evaluate(() => document.documentElement.scrollHeight);
    if (cfg.maxHeightPx && cfg.fullPage && docHeight > cfg.maxHeightPx) {
      await page.screenshot({
        path: pngPath,
        clip: { x: 0, y: 0, width: cfg.viewport.width, height: cfg.maxHeightPx },
      });
    } else {
      await page.screenshot({ path: pngPath, fullPage: cfg.fullPage });
    }

    const text = (await page.evaluate(() => document.body.innerText || "")).replace(/\n{3,}/g, "\n\n").trim();
    const controls = await extractControls(page);

    // Structural fingerprint of the screen (sorted controls only, not volatile
    // text/data), so a later capture can detect UI drift deterministically.
    const fingerprint = createHash("sha256").update([...controls].sort().join("\n")).digest("hex").slice(0, 16);

    writeFileSync(
      new URL(`capture/${s.id}.json`, root),
      JSON.stringify(
        { id: s.id, name: s.name, order: s.order ?? 999, note: s.note ?? "", url: page.url(), fingerprint, text, controls },
        null,
        2
      )
    );
    console.log(`ok (${controls.length} controls, ${text.length} chars)`);
    ok++;
  } catch (err) {
    console.log(`FAILED: ${err.message}`);
  } finally {
    await page.close();
  }
}

await browser.close();
console.log(`\n  Captured ${ok}/${todo.length} screens into capture/. Next: python draft.py\n`);
