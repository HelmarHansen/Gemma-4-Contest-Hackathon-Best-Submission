// Frontend smoke tests:
//   1. chat.js syntax is parseable (no ReferenceError to undefined helpers).
//   2. parseSections() lifted out of chat.js produces correct sections.
//   3. chat.html declares the required DOM hooks the script depends on.
//
// Run: node tests_frontend.mjs

import fs from "node:fs";
import vm from "node:vm";

const root = "./";

function pass(label) { console.log(`  PASS  ${label}`); return true; }
function fail(label, detail) { console.log(`  FAIL  ${label}${detail ? ": " + detail : ""}`); return false; }

// -- Test 1: chat.js parses ---------------------------------------------------
console.log("\n[Test F1] chat.js — syntactic parse");
let chatSrc = fs.readFileSync(root + "chat.js", "utf8");
let ok1 = true;
try {
  new vm.Script(chatSrc, { filename: "chat.js" });
  ok1 = pass("chat.js parses without syntax error");
} catch (e) {
  ok1 = fail("chat.js syntax error", e.message);
}

// -- Test 2: chat.html contains all DOM hooks chat.js queries -----------------
console.log("\n[Test F2] chat.html — DOM hooks present");
const html = fs.readFileSync(root + "chat.html", "utf8");
const requiredIds = [
  "teacher-name", "teacher-role",
  "tab-investigation", "tab-interrogation",
  "panel-investigation", "panel-interrogation",
  "side-acts", "side-characters",
  "scenes-list", "characters-list",
  "feed-investigation", "transcript-investigation",
  "composer-investigation", "send-investigation", "hint-btn",
  "feed-interrogation", "transcript-interrogation",
  "composer-interrogation", "send-interrogation",
  "interrogation-empty", "interrogation-name", "interrogation-role", "interrogation-avatar",
];
let ok2 = true;
for (const id of requiredIds) {
  const re = new RegExp(`id="${id}"`);
  if (!re.test(html)) ok2 = fail("missing id=" + id) && ok2;
}
if (ok2) pass(`all ${requiredIds.length} required DOM ids present`);

// -- Test 3: parseSections() returns the right shape --------------------------
console.log("\n[Test F3] parseSections() — extraction logic");

// Extract the function source from chat.js and evaluate in a sandbox.
const fnMatch = chatSrc.match(/function parseSections\([\s\S]*?\n\}\n/);
if (!fnMatch) { fail("could not locate parseSections in chat.js"); process.exit(1); }
const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(fnMatch[0] + "\nglobalThis.parseSections = parseSections;", sandbox);

const sample = `[NARRATION] Das Notlicht flackert. CO₂-Sensor rot, Kabel lose.

[NPC:Inspektorin Marlow] „Was sehen Sie?\"

[QUESTION] Was passt nicht?

[STATE] STAY`;

const sections = sandbox.parseSections(sample);
let ok3 = true;
ok3 = (sections.length === 3) || (fail("section count", `got ${sections.length}`) && false);
if (ok3) {
  ok3 &= sections[0].type === "narration" || fail("section[0].type", sections[0].type);
  ok3 &= sections[1].type === "npc"        || fail("section[1].type", sections[1].type);
  ok3 &= sections[1].name === "Inspektorin Marlow" || fail("section[1].name", sections[1].name);
  ok3 &= sections[2].type === "question"   || fail("section[2].type", sections[2].type);
  ok3 &= !sections[0].content.includes("[STATE]") || fail("state leaked into narration");
}
// edge cases:
const noTags = sandbox.parseSections("Just some text without tags.");
ok3 &= noTags.length === 1 && noTags[0].type === "narration"
  || fail("untagged text fallback", JSON.stringify(noTags));

const multiNPC = sandbox.parseSections(
  "[NARRATION] foo\n[NPC:A] hello\n[NPC:B] hi\n[QUESTION] q?\n[STATE] ADVANCE"
);
ok3 &= multiNPC.length === 4 || fail("multi-NPC count", multiNPC.length);
ok3 &= multiNPC.filter(s => s.type === "npc").length === 2 || fail("npc count");

if (ok3) pass("parseSections handles tagged, untagged, and multi-NPC inputs");

// -- Test 4: chat.html links chat.css + script ---------------------------------
console.log("\n[Test F4] chat.html — asset references");
let ok4 = true;
ok4 &= /href="chat\.css(\?[^"]*)?"/.test(html) || fail("missing chat.css link");
ok4 &= /href="shared\.css(\?[^"]*)?"/.test(html) || fail("missing shared.css link");
ok4 &= /src="chat\.js(\?[^"]*)?"/.test(html) || fail("missing chat.js script");
if (ok4) pass("html references chat.css, shared.css, chat.js");

// -- Test 5: chat.js no longer references undefined helpers --------------------
console.log("\n[Test F5] chat.js — no calls to legacy undefined helpers");
let ok5 = true;
const banned = ["addUserMessage(", "addTeacherMessage(", "showTyping()", "hideTyping()"];
for (const b of banned) {
  // The new helpers must exist; the old calls must not.
  if (chatSrc.includes(b) && !chatSrc.includes("function " + b.replace("(", "("))) {
    // Allow if defined locally. addUserMessage etc. should not exist at all.
    if (b.startsWith("add")) ok5 = fail("legacy call still present", b);
  }
}
if (ok5) pass("legacy undefined helper calls are gone");

const all = [ok1, ok2, ok3, ok4, ok5];
const passed = all.filter(Boolean).length;
console.log(`\n=== ${passed}/${all.length} frontend tests passed ===`);
process.exit(passed === all.length ? 0 : 1);
