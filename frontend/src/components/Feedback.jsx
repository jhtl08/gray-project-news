import { useCallback, useMemo, useState } from "react";
import { AnnounceContext } from "../lib/announce.js";
import Icon from "./Icon.jsx";

/**
 * Two live regions are mounted once, before any message exists, so an update
 * is a text change rather than a new element. Urgent messages use the alert
 * region, everything else the polite one.
 */
export function Announcer({ children }) {
  const [message, setMessage] = useState({ text: "", urgent: false });

  const announce = useCallback((text, options = {}) => {
    if (!text) return;
    setMessage({ text, urgent: Boolean(options.urgent) });
  }, []);

  const value = useMemo(() => announce, [announce]);

  return (
    <AnnounceContext.Provider value={value}>
      {children}
      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {message.urgent ? "" : message.text}
      </div>
      <div className="sr-only" role="alert" aria-live="assertive" aria-atomic="true">
        {message.urgent ? message.text : ""}
      </div>
    </AnnounceContext.Provider>
  );
}

const TONE_ICON = {
  success: "check",
  danger: "alert",
  warning: "alert",
  info: "info",
};

/**
 * A visible banner. It carries no live region of its own; announcements go
 * through `useAnnounce` so the region is never mounted together with its text.
 */
export function Feedback({ tone = "success", children, action, className = "" }) {
  return (
    <div className={`feedback feedback--${tone} ${className}`.trim()}>
      <Icon name={TONE_ICON[tone] ?? "info"} size={16} className="feedback__icon" />
      <div className="feedback__text">{children}</div>
      {action ? <div className="feedback__action">{action}</div> : null}
    </div>
  );
}

export default Feedback;
