const GLYPHS = {
  collect: ["M12 4v11", "m7.5 10.5 4.5 4.5 4.5-4.5", "M5 20h14"],
  trash: [
    "M4 7h16",
    "M10 4h4a1 1 0 0 1 1 1v2H9V5a1 1 0 0 1 1-1Z",
    "m6 7 1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12",
    "M10 11v6",
    "M14 11v6",
  ],
  external: [
    "M14 4h6v6",
    "m20 4-8.5 8.5",
    "M18 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4",
  ],
  target: [
    "M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16Z",
    "M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Z",
  ],
  arrowUp: ["M12 19V5", "m6.5 10.5 5.5-5.5 5.5 5.5"],
  arrowDown: ["M12 5v14", "m6.5 13.5 5.5 5.5 5.5-5.5"],
  check: ["m4.5 12.5 5 5 10-11"],
  alert: [
    "M10.3 4.3 2.7 17.4a2 2 0 0 0 1.7 3h15.2a2 2 0 0 0 1.7-3L13.7 4.3a2 2 0 0 0-3.4 0Z",
    "M12 9.5v4",
    "M12 17h.01",
  ],
  close: ["m6 6 12 12", "m18 6-12 12"],
  chevronLeft: ["m14 6-6 6 6 6"],
  chevronRight: ["m10 6 6 6-6 6"],
  search: ["M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14Z", "m20 20-3.6-3.6"],
  info: ["M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z", "M12 11v5", "M12 8h.01"],
  news: [
    "M5 5a2 2 0 0 1 2-2h6l5 5v12a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2Z",
    "M14 3v5h5",
    "M8.5 12h7",
    "M8.5 16h4.5",
  ],
  chart: ["M4 20h16", "M7 20v-7", "M12 20V6", "M17 20v-4"],
};

function Icon({ name, size = 16, className = "" }) {
  const glyph = GLYPHS[name];
  if (!glyph) return null;

  // A 24-unit viewBox scaled to 16 or 20px renders the 1.5px stroke the
  // design calls for only when the stroke is scaled to match.
  const strokeWidth = (1.5 * 24) / size;

  return (
    <svg
      className={`icon ${className}`.trim()}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {glyph.map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}

export default Icon;
