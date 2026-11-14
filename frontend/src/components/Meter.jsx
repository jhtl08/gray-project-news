function Meter({ value, max = 100, format = (number) => String(number) }) {
  if (value === null || value === undefined) return null;

  const number = Number(value);
  if (!Number.isFinite(number)) return null;

  const percent = Math.min(100, Math.max(0, (number / max) * 100));

  return (
    <span className="meter">
      <span className="meter__track" aria-hidden="true">
        <span className="meter__fill" style={{ inlineSize: `${percent}%` }} />
      </span>
      <span className="meter__value">{format(number)}</span>
    </span>
  );
}

export default Meter;
