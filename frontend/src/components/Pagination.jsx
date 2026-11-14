import Button from "./Button.jsx";
import { formatCount } from "../lib/format.js";

const PAGE_SIZES = [50, 100, 250];

function Pagination({ total, offset, limit, onOffsetChange, onLimitChange, busy = false }) {
  const start = total === 0 ? 0 : offset + 1;
  const end = Math.min(offset + limit, total);

  return (
    <div className="pagination">
      <p className="pagination__info">
        Showing {formatCount(start)}–{formatCount(end)} of {formatCount(total)}
      </p>
      <div className="pagination__controls">
        <label className="pagination__size">
          Rows per page
          <select
            className="select select--sm"
            value={limit}
            onChange={(event) => onLimitChange(Number(event.target.value))}
            disabled={busy}
          >
            {PAGE_SIZES.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </label>
        <div className="pagination__buttons">
          {offset > 0 ? (
            <Button
              size="sm"
              icon="chevronLeft"
              onClick={() => onOffsetChange(Math.max(0, offset - limit))}
              disabled={busy}
            >
              Previous
            </Button>
          ) : null}
          <Button
            size="sm"
            iconAfter="chevronRight"
            onClick={() => onOffsetChange(offset + limit)}
            disabled={busy || end >= total}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}

export default Pagination;
