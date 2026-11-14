import Icon from "./Icon.jsx";

/**
 * A native button. `iconOnly` requires `label`, because an icon alone has no
 * accessible name and the label must name the action and its object.
 */
function Button({
  children,
  variant = "secondary",
  size = "md",
  icon,
  iconAfter,
  iconOnly = false,
  label,
  "aria-label": ariaLabel,
  loading = false,
  className = "",
  type = "button",
  ...rest
}) {
  const accessibleLabel = label ?? ariaLabel;

  if (import.meta.env.DEV && iconOnly && !accessibleLabel) {
    console.warn("Button: an icon-only button needs a label.");
  }

  const classes = [
    "btn",
    `btn--${variant}`,
    size === "sm" ? "btn--sm" : "",
    iconOnly ? "btn--icon" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  const iconName = iconAfter ?? icon;
  const iconSize = size === "sm" ? 16 : 18;

  return (
    <button
      {...rest}
      type={type}
      className={classes}
      aria-label={accessibleLabel}
      aria-busy={loading || undefined}
    >
      {loading ? (
        <span className="btn__spinner" aria-hidden="true" />
      ) : iconName ? (
        <Icon name={iconName} size={iconSize} />
      ) : null}
      {iconOnly ? null : children}
    </button>
  );
}

export default Button;
