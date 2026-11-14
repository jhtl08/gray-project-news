function Skeleton({ rows = 5, variant = "row" }) {
  return (
    <div className={`skeleton skeleton--${variant}`} aria-hidden="true">
      {Array.from({ length: rows }, (_, index) => (
        <div className="skeleton__item" key={index}>
          <span className="skeleton__bar skeleton__bar--wide" />
          <span className="skeleton__bar skeleton__bar--short" />
          <span className="skeleton__bar skeleton__bar--medium" />
        </div>
      ))}
    </div>
  );
}

export default Skeleton;
