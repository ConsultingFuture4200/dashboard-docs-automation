// One-time interactive login. Opens a real browser window, you log in through
// your SSO normally, then press Enter here. The session (cookies + localStorage)
// is saved to auth.json so capture.js can run unattended afterwards.
//
// Re-run this whenever the saved session expires.
//
//   npm run auth
//
import { chromium } from "playwright";
import { readFileSync } from "node:fs";
import { parse } from "yaml";
import readline from "node:readline";

const cfg = parse(readFileSync(new URL("./config.yaml", import.meta.url), "utf8"));

const browser = await chromium.launch({ headless: false });
const context = await browser.newContext({ viewport: cfg.viewport });
const page = await context.newPage();

await page.goto(cfg.baseUrl);

console.log("\n  A browser window is open.");
console.log("  1. Log in through your SSO / login flow.");
console.log("  2. Navigate until you can see the dashboard home.");
console.log("  3. Come back here and press Enter to save the session.\n");

await new Promise((resolve) => {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  rl.question("  Press Enter once you are logged in... ", () => {
    rl.close();
    resolve();
  });
});

await context.storageState({ path: cfg.storageState });
console.log(`\n  Saved session to ${cfg.storageState}. You can now run: npm run capture\n`);

await browser.close();
