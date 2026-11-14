import { useEffect, useRef } from "react";
import Button from "./Button.jsx";

/**
 * A native modal dialog. The browser makes the background inert, handles the
 * top layer and exposes Escape through the cancel event. Focus enters on open
 * and returns to the trigger on close.
 */
function Dialog({ open, onClose, labelledBy, children, className = "" }) {
  const ref = useRef(null);
  const triggerRef = useRef(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog || !open) return undefined;

    triggerRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;

    if (!dialog.open) dialog.showModal();

    const focusTarget =
      dialog.querySelector("[data-autofocus]") ??
      dialog.querySelector("input:not([type='hidden']), select, textarea") ??
      dialog.querySelector("button");

    focusTarget?.focus();

    return () => {
      if (dialog.open) dialog.close();
      triggerRef.current?.focus();
      triggerRef.current = null;
    };
  }, [open]);

  return (
    <dialog
      ref={ref}
      className={`dialog ${className}`.trim()}
      aria-labelledby={labelledBy}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      {open ? <div className="dialog__content">{children}</div> : null}
    </dialog>
  );
}

export function DialogHeader({ titleId, title, description, onClose }) {
  return (
    <header className="dialog__header">
      <div className="dialog__heading">
        <h2 id={titleId} className="dialog__title">
          {title}
        </h2>
        {description ? <p className="dialog__description">{description}</p> : null}
      </div>
      <Button
        variant="ghost"
        iconOnly
        icon="close"
        label="Close dialog"
        onClick={onClose}
      />
    </header>
  );
}

export function DialogFooter({ children }) {
  return <footer className="dialog__footer">{children}</footer>;
}

export default Dialog;
