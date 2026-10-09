import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

// Independent RFC 8785 canonicalization: it shares no code with Creator's
// Python implementation, so agreement on these vectors is cross-language
// evidence rather than a round trip.
const fixture = JSON.parse(
  readFileSync(new URL("./jcs-shared-vectors-v1.json", import.meta.url), "utf8"),
);

const loneSurrogate = /[\ud800-\udbff](?![\udc00-\udfff])|(?<![\ud800-\udbff])[\udc00-\udfff]/;

function parseStrict(text) {
  return JSON.parse(text, function (key, value, context) {
    if (loneSurrogate.test(key)) throw new Error("lone surrogate in member name");
    if (typeof value === "string" && loneSurrogate.test(value)) {
      throw new Error("lone surrogate in string");
    }
    if (
      typeof value === "number" &&
      /^-?\d+$/.test(context.source) &&
      !Number.isSafeInteger(Number(context.source))
    ) {
      throw new Error("integer outside the exactly representable range");
    }
    return value;
  });
}

function rejectDuplicateKeys(text) {
  // JSON.parse keeps the last duplicate silently; scan member names per object.
  const stack = [];
  let i = 0;
  while (i < text.length) {
    const ch = text[i];
    if (ch === '"') {
      let j = i + 1;
      while (text[j] !== '"') j += text[j] === "\\" ? 2 : 1;
      const token = text.slice(i, j + 1);
      let k = j + 1;
      while (/\s/.test(text[k] ?? "")) k += 1;
      if (text[k] === ":" && stack.length && stack.at(-1) !== null) {
        const name = JSON.parse(token);
        if (stack.at(-1).has(name)) throw new Error("duplicate member name");
        stack.at(-1).add(name);
      }
      i = j + 1;
      continue;
    }
    if (ch === "{") stack.push(new Set());
    else if (ch === "[") stack.push(null);
    else if (ch === "}" || ch === "]") stack.pop();
    i += 1;
  }
}

function canonical(value) {
  if (value === null || typeof value === "boolean") return JSON.stringify(value);
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new Error("non-finite number");
    return JSON.stringify(value);
  }
  if (typeof value === "string") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  // Array.prototype.sort orders strings by UTF-16 code units, as RFC 8785 requires.
  const keys = Object.keys(value).sort();
  return `{${keys.map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`;
}

function canonicalize(text) {
  rejectDuplicateKeys(text);
  return canonical(parseStrict(text));
}

for (const vector of fixture.valid) {
  const text = canonicalize(vector.input_json);
  if (text !== vector.canonical_text) {
    throw new Error(`${vector.name}: canonical text differs: ${text}`);
  }
  const digest = createHash("sha256").update(Buffer.from(text, "utf8")).digest("hex");
  if (digest !== vector.sha256) throw new Error(`${vector.name}: digest mismatch`);
}

for (const vector of fixture.invalid) {
  let refused = false;
  try {
    canonicalize(vector.input_json);
  } catch {
    refused = true;
  }
  if (!refused) throw new Error(`${vector.name}: invalid input was accepted`);
}

console.log(
  `verified ${fixture.valid.length} valid and refused ${fixture.invalid.length} invalid JCS shared vectors`,
);
