const countFormat = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });

const percentFormat = new Intl.NumberFormat(undefined, {
  style: "percent",
  maximumFractionDigits: 1,
});

const similarityFormat = new Intl.NumberFormat(undefined, {
  style: "percent",
  maximumFractionDigits: 0,
});

const deltaFormat = new Intl.NumberFormat(undefined, {
  style: "percent",
  maximumFractionDigits: 1,
  signDisplay: "exceptZero",
});

const compactCurrencyFormat = new Intl.NumberFormat(undefined, {
  style: "currency",
  currency: "USD",
  notation: "compact",
  maximumFractionDigits: 1,
});

const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: "medium" });

const dateTimeFormat = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

const relativeFormat = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });

function toNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function toDate(value) {
  if (!value) return null;
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** 1,203 */
export function formatCount(value) {
  const number = toNumber(value);
  return number === null ? "0" : countFormat.format(number);
}

/** 0 to 100, rounded. Returns null for an unscored row. */
export function formatScore(value) {
  const number = toNumber(value);
  if (number === null) return null;
  return countFormat.format(Math.min(100, Math.max(0, Math.round(number))));
}

/** A prediction-market price, 0.106 to 10.6%. */
export function formatProbability(value) {
  const number = toNumber(value);
  return number === null ? null : percentFormat.format(number);
}

/** A similarity above the 0.7 threshold, 0.823 to 82%. */
export function formatSimilarity(value) {
  const number = toNumber(value);
  return number === null ? null : similarityFormat.format(number);
}

/** A price move, -0.002 to -0.2%. */
export function formatDelta(value) {
  const number = toNumber(value);
  return number === null ? null : deltaFormat.format(number);
}

/** up, down or flat. Half of one rendered decimal counts as flat. */
export function deltaTone(value) {
  const number = toNumber(value);
  if (number === null || Math.abs(number) < 0.0005) return "flat";
  return number > 0 ? "up" : "down";
}

/** Market volume and liquidity, 28696338 to $28.7M. */
export function formatCompactCurrency(value) {
  const number = toNumber(value);
  return number === null ? null : compactCurrencyFormat.format(number);
}

export function formatDate(value) {
  const date = toDate(value);
  return date ? dateFormat.format(date) : null;
}

export function formatDateTime(value) {
  const date = toDate(value);
  return date ? dateTimeFormat.format(date) : null;
}

/** Minutes, hours or days ago up to a week, then an absolute date. */
export function formatRelative(value) {
  const date = toDate(value);
  if (!date) return null;

  const diff = date.getTime() - Date.now();
  const abs = Math.abs(diff);
  const direction = diff < 0 ? -1 : 1;

  const minutes = Math.round(abs / 60000);
  if (minutes < 60) return relativeFormat.format(direction * minutes, "minute");

  const hours = Math.round(abs / 3600000);
  if (hours < 24) return relativeFormat.format(direction * hours, "hour");

  const days = Math.round(abs / 86400000);
  if (days <= 7) return relativeFormat.format(direction * days, "day");

  return dateFormat.format(date);
}

/** The hostname of an article URL, without a www prefix. */
export function hostnameOf(url) {
  if (!url) return null;
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
}

/**
 * Tags arrive as a JSON string from the database, but an array, a plain
 * comma-separated string or a malformed value all have to degrade quietly.
 */
export function parseTags(value) {
  if (!value) return [];

  if (Array.isArray(value)) {
    return value.map(tagLabel).filter(Boolean);
  }

  if (typeof value === "object") {
    return [];
  }

  const raw = String(value).trim();
  if (!raw) return [];

  if (raw.startsWith("[")) {
    try {
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed.map(tagLabel).filter(Boolean) : [];
    } catch {
      return [];
    }
  }

  return raw
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
}

function tagLabel(tag) {
  if (typeof tag === "string") return tag.trim();
  if (tag && typeof tag === "object") return tag.label ?? tag.name ?? "";
  return "";
}
