// Shared config.yaml validation for capture.js / verify.js — same messages as
// the Python side (configcheck.py): config.yaml is gitignored and copied from
// config.example.yaml, so fail on a missing file or a still-placeholder key,
// pointing at the exact key and the cp step.
import { existsSync, readFileSync } from "node:fs";
import { parse } from "yaml";

// key -> substring that proves the value is still the .example placeholder
const PLACEHOLDERS = {
  baseUrl: "your-dashboard.example.com",
  productDescription: "one-line description of what the dashboard does",
};

const CP_HINT = "cp config.example.yaml config.yaml   # then edit baseUrl + productDescription";

// Parse and validate config.yaml under `root`; print actionable errors and
// exit(1) on a missing file or placeholder values.
export function loadConfig(root) {
  const path = new URL("config.yaml", root);
  if (!existsSync(path)) {
    console.error(`\n  ✗ config.yaml not found. Run: ${CP_HINT}\n`);
    process.exit(1);
  }
  const cfg = parse(readFileSync(path, "utf8"));
  const errs = [];
  for (const [key, placeholder] of Object.entries(PLACEHOLDERS)) {
    const value = cfg?.[key];
    if (!value) {
      errs.push(`config.yaml: "${key}" is missing — set it (see config.example.yaml).`);
    } else if (String(value).includes(placeholder)) {
      errs.push(`config.yaml: "${key}" is still the .example placeholder — edit config.yaml and set your real value.`);
    }
  }
  if (errs.length) {
    console.error("\n" + errs.map((e) => `  ✗ ${e}`).join("\n") + "\n");
    process.exit(1);
  }
  return cfg;
}
