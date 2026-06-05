const fs = require("fs");
const path = require("path");

let apiBase = (process.env.VITE_API_BASE_URL || "").trim().replace(/\/$/, "");
if (apiBase && !/^https?:\/\//i.test(apiBase)) {
  apiBase = `https://${apiBase}`;
}
const out = path.join(__dirname, "..", "config.js");

fs.writeFileSync(
  out,
  `// Generated at build — do not edit on Vercel.\nwindow.__API_BASE__ = ${JSON.stringify(apiBase)};\n`
);

console.log(`Wrote config.js (API_BASE=${apiBase || "(same-origin)"})`);
