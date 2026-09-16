#!/usr/bin/env node
"use strict";

// Run the same React-free cases registered with Vitest, without downloading
// dependencies, starting a server, or contacting a model provider.
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const root = path.resolve(__dirname, "..");
let compiler;
try {
  compiler = require.resolve("typescript/bin/tsc", {
    paths: [path.join(root, "apps/web"), root],
  });
} catch {
  console.error(
    "TypeScript is unavailable. Install the repository's locked Web dependencies first.",
  );
  process.exit(1);
}

const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "reponpc-chat-tests-"));
let exitCode = 1;
try {
  const sources = ["sse.ts", "visitorChat.ts", "visitorChat.test-cases.ts"].map(
    (file) => path.join(root, "apps/web/src/app", file),
  );
  const compiled = spawnSync(
    process.execPath,
    [
      compiler,
      "--strict",
      "--target",
      "es2022",
      "--module",
      "commonjs",
      "--lib",
      "es2022,dom",
      "--outDir",
      temporary,
      ...sources,
    ],
    { stdio: "inherit", timeout: 60000 },
  );
  if (compiled.error) throw compiled.error;
  if (compiled.status !== 0) {
    exitCode = compiled.status ?? 1;
  } else {
    const runner = path.join(temporary, "run.test.cjs");
    fs.writeFileSync(
      runner,
      'const { test } = require("node:test");\n' +
        'const { registerVisitorChatTests } = require("./visitorChat.test-cases.js");\n' +
        "registerVisitorChatTests(test);\n",
    );
    const tested = spawnSync(process.execPath, ["--test", runner], {
      stdio: "inherit",
      timeout: 60000,
    });
    if (tested.error) throw tested.error;
    exitCode = tested.status ?? 1;
  }
} catch (error) {
  console.error(error instanceof Error ? error.message : "Contract tests failed");
} finally {
  fs.rmSync(temporary, { recursive: true, force: true });
}
process.exitCode = exitCode;
