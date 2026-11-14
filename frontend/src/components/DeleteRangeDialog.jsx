import { useEffect, useState } from "react";
import Button from "./Button.jsx";
import Dialog, { DialogFooter, DialogHeader } from "./Dialog.jsx";
import Feedback from "./Feedback.jsx";
import Field from "./Field.jsx";
import { apiDelete } from "../lib/api.js";
import { formatCount, formatDateTime } from "../lib/format.js";

/**
 * A two-step range delete: review the boundary, then confirm the consequence.
 * The parent remounts this on each open with a `key`, so the form always
 * starts clean and focus is never left on an element that just unmounted.
 */
function DeleteRangeDialog({
  open,
  onClose,
  titleId,
  formTitle,
  formDescription,
  confirmTitle,
  subject,
  verb,
  noun,
  endpoint,
  onDeleted,
  announce,
}) {
  const [step, setStep] = useState("form");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!open) return;
    // The confirm step focuses its safe action, not the destructive one.
    const target =
      step === "confirm" ? `${titleId}-back` : `${titleId}-start`;
    document.getElementById(target)?.focus();
  }, [open, step, titleId]);

  const startText = start ? formatDateTime(new Date(start).toISOString()) : null;
  const endText = end ? formatDateTime(new Date(end).toISOString()) : null;

  let rangeText = `${subject} ${verb} on or before ${endText}`;
  if (startText && endText) {
    rangeText = `${subject} ${verb} between ${startText} and ${endText}`;
  } else if (startText) {
    rangeText = `${subject} ${verb} on or after ${startText}`;
  }

  const review = (event) => {
    event.preventDefault();

    if (!start && !end) {
      setError("Choose a start date, an end date or both.");
      return;
    }
    if (start && end && new Date(start) > new Date(end)) {
      setError("The start date must be before the end date.");
      return;
    }

    setError(null);
    setStep("confirm");
  };

  const confirm = async () => {
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      if (start) params.set("start", new Date(start).toISOString());
      if (end) params.set("end", new Date(end).toISOString());

      const data = await apiDelete(`${endpoint}?${params}`);
      const message = `Deleted ${formatCount(data?.deleted)} ${noun}.`;

      announce(message);
      onDeleted(message);
      onClose();
    } catch (requestError) {
      setError(requestError.message);
      announce(`Delete failed. ${requestError.message}`, { urgent: true });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} labelledBy={titleId}>
      {step === "form" ? (
        <form className="dialog__form" onSubmit={review} noValidate>
          <div className="dialog__span">
            <DialogHeader
              titleId={titleId}
              title={formTitle}
              description={formDescription}
              onClose={onClose}
            />
          </div>

          <Field id={`${titleId}-start`} label="Start of range">
            <input
              className="input"
              type="datetime-local"
              value={start}
              onChange={(event) => setStart(event.target.value)}
            />
          </Field>

          <Field id={`${titleId}-end`} label="End of range">
            <input
              className="input"
              type="datetime-local"
              value={end}
              onChange={(event) => setEnd(event.target.value)}
            />
          </Field>

          {error ? <Feedback tone="danger">{error}</Feedback> : null}

          <DialogFooter>
            <Button onClick={onClose}>Cancel</Button>
            <Button type="submit" variant="secondary">
              Review delete
            </Button>
          </DialogFooter>
        </form>
      ) : (
        <>
          <DialogHeader
            titleId={titleId}
            title={confirmTitle}
            description={`${rangeText}. This cannot be undone.`}
            onClose={onClose}
          />

          {error ? <Feedback tone="danger">{error}</Feedback> : null}

          <DialogFooter>
            <Button
              id={`${titleId}-back`}
              onClick={() => setStep("form")}
              disabled={loading}
            >
              Back
            </Button>
            <Button
              variant="danger"
              icon="trash"
              onClick={confirm}
              loading={loading}
              disabled={loading}
            >
              {loading ? "Deleting…" : `Delete ${noun}`}
            </Button>
          </DialogFooter>
        </>
      )}
    </Dialog>
  );
}

export default DeleteRangeDialog;
