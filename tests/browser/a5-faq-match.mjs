// Check the actual API/export payload captured by test_question_variant_export_and_matcher_inputs.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";

const require = createRequire(
  new URL("../../apps/web/package.json", import.meta.url),
);
const ts = require("typescript");
const source = readFileSync(
  new URL("../../apps/web/src/app/offlineFaq.ts", import.meta.url),
  "utf8",
);
const { outputText } = ts.transpileModule(source, {
  compilerOptions: {
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.ESNext,
  },
});
const { matchOfflineFaq, normalize } = await import(
  `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`
);
const { cases, normalization } = JSON.parse(
  readFileSync(resolve(process.argv[2]), "utf8"),
);
assert.equal(cases.length, 2);
for (const { faq, pending, variant } of cases) {
  assert.equal(matchOfflineFaq(variant, pending).kind, "suggestions");
  assert.equal(matchOfflineFaq(faq.entries[0].question, faq).kind, "answer");
  assert.equal(matchOfflineFaq(variant, faq).kind, "answer");
  assert.equal(
    matchOfflineFaq(`${variant} unapproved`, faq).kind,
    "suggestions",
  );
}
for (const [value, expected] of normalization)
  assert.equal(normalize(value), expected);
console.log(
  `Actual bilingual API/export FAQ: 8 matcher and ${normalization.length} normalization checks passed.`,
);
