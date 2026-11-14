import { useEffect, useState } from "react";
import Button from "./components/Button.jsx";
import DeleteRangeDialog from "./components/DeleteRangeDialog.jsx";
import EmptyState from "./components/EmptyState.jsx";
import ErrorState from "./components/ErrorState.jsx";
import Feedback from "./components/Feedback.jsx";
import Field from "./components/Field.jsx";
import Icon from "./components/Icon.jsx";
import Meter from "./components/Meter.jsx";
import Pagination from "./components/Pagination.jsx";
import RecordLink from "./components/RecordLink.jsx";
import Skeleton from "./components/Skeleton.jsx";
import { apiFetch, apiPost } from "./lib/api.js";
import { useAnnounce } from "./lib/announce.js";
import {
  deltaTone,
  formatCompactCurrency,
  formatCount,
  formatDate,
  formatDelta,
  formatProbability,
  formatScore,
  parseTags,
} from "./lib/format.js";
import { useDebouncedValue, useMediaQuery } from "./lib/hooks.js";

// Nine columns need more room than the four-column news table, so this view
// switches to cards later. The width comes from the content, not a device.
const WIDE_QUERY = "(min-width: 1024px)";

const SORT_OPTIONS = [
  { value: "collected_at", label: "Collected at" },
  { value: "question", label: "Question" },
  { value: "volume", label: "Volume" },
  { value: "one_day_price_change", label: "1D change" },
  { value: "one_week_price_change", label: "1W change" },
  { value: "one_month_price_change", label: "1M change" },
  { value: "emotionality_score", label: "Unrest" },
  { value: "status_quo_deviation", label: "Status quo" },
  { value: "end_date", label: "End date" },
];

function FilterChip({ pressed, onClick, children }) {
  return (
    <button type="button" className="chip" aria-pressed={pressed} onClick={onClick}>
      {pressed ? <Icon name="check" size={14} /> : null}
      {children}
    </button>
  );
}

function Delta({ value }) {
  const text = formatDelta(value);
  if (text === null) return <span className="delta delta--flat">—</span>;

  const tone = deltaTone(value);

  return (
    <span className={`delta delta--${tone}`}>
      {tone === "flat" ? null : (
        <Icon name={tone === "up" ? "arrowUp" : "arrowDown"} size={12} />
      )}
      {text}
    </span>
  );
}

function Unrest({ value }) {
  const score = formatScore(value);
  if (score === null) return <span className="badge badge--warning">Pending</span>;
  return <Meter value={value} format={formatScore} />;
}

function StatusBadge({ item }) {
  if (item.status_quo_deviation === null || item.status_quo_deviation === undefined) return null;

  const deviates = Boolean(Number(item.status_quo_deviation));

  return (
    <span className={`badge ${deviates ? "badge--accent" : "badge--neutral"}`}>
      <Icon name={deviates ? "alert" : "check"} size={12} />
      {deviates ? "Unsettling" : "Status quo"}
    </span>
  );
}

function MarketBadges({ item }) {
  const tags = parseTags(item.tags);

  return (
    <div className="record-badges">
      <StatusBadge item={item} />
      {item.is_new ? <span className="badge badge--accent">New</span> : null}
      {item.active ? (
        <span className="badge badge--success">Active</span>
      ) : item.closed ? (
        <span className="badge badge--neutral">Closed</span>
      ) : null}
      {tags.map((tag) => (
        <span className="badge badge--neutral tag" key={tag}>
          {tag}
        </span>
      ))}
    </div>
  );
}

function Bets({ onNavigate }) {
  const announce = useAnnounce();
  const wide = useMediaQuery(WIDE_QUERY);

  const [activeOnly, setActiveOnly] = useState(false);
  const [newOnly, setNewOnly] = useState(false);
  const [tag, setTag] = useState("");
  const [minMove, setMinMove] = useState("");

  const debouncedTag = useDebouncedValue(tag, 250);
  const debouncedMinMove = useDebouncedValue(minMove, 250);

  const [sort, setSort] = useState("collected_at");
  const [direction, setDirection] = useState("desc");
  const [offset, setOffset] = useState(0);
  const [loadedOffset, setLoadedOffset] = useState(0);
  const [limit, setLimit] = useState(100);
  const [reloadToken, setReloadToken] = useState(0);

  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [collectLoading, setCollectLoading] = useState(false);
  const [rowState, setRowState] = useState({});
  const [lastSeed, setLastSeed] = useState(null);
  const [pageFeedback, setPageFeedback] = useState(null);
  const [manageOpen, setManageOpen] = useState(false);

  const tagParam = debouncedTag.trim();
  const minMoveNumber = Number(debouncedMinMove);
  const minMoveParam =
    debouncedMinMove.trim() && Number.isFinite(minMoveNumber) && minMoveNumber > 0
      ? minMoveNumber / 100
      : null;

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
      order_by: sort,
      order_dir: direction,
    });

    if (activeOnly) params.set("active", "true");
    if (newOnly) params.set("is_new", "true");
    if (tagParam) params.set("tag", tagParam);
    if (minMoveParam !== null) params.set("min_abs_change", String(minMoveParam));

    setLoading(true);
    setError(null);

    apiFetch(`/api/bets?${params}`, { signal: controller.signal })
      .then((data) => {
        const loaded = data?.bets ?? [];
        const count = data?.total ?? 0;
        setRows(loaded);
        setTotal(count);
        setLoadedOffset(offset);
        setLoading(false);
        announce(`Showing ${formatCount(count)} markets.`);
      })
      .catch((requestError) => {
        if (requestError.name === "AbortError") return;
        setError(requestError.message);
        setLoading(false);
        announce(`Can't load bets. ${requestError.message}`, { urgent: true });
      });

    return () => controller.abort();
  }, [
    activeOnly,
    newOnly,
    tagParam,
    minMoveParam,
    sort,
    direction,
    offset,
    limit,
    reloadToken,
    announce,
  ]);

  const reload = () => setReloadToken((token) => token + 1);

  const hasFilters =
    activeOnly || newOnly || tag.trim().length > 0 || minMove.trim().length > 0;

  const clearFilters = () => {
    setActiveOnly(false);
    setNewOnly(false);
    setTag("");
    setMinMove("");
    setOffset(0);
  };

  const changeSort = (event) => {
    setSort(event.target.value);
    setOffset(0);
  };

  const changeDirection = (event) => {
    setDirection(event.target.value);
    setOffset(0);
  };

  const changeLimit = (nextLimit) => {
    setLimit(nextLimit);
    setOffset(0);
  };

  const handleCollect = async () => {
    setCollectLoading(true);
    setPageFeedback(null);

    try {
      const data = await apiPost("/api/bets/collect");
      let message = `Collected ${formatCount(data?.collected)} markets.`;

      if (data?.ingested?.inserted !== undefined) {
        message += ` ${formatCount(data.ingested.inserted)} new, ${formatCount(
          data.ingested.skipped,
        )} already stored.`;
      }

      setPageFeedback({ tone: "success", message });
      announce(message);
      setOffset(0);
      reload();
    } catch (requestError) {
      const message = `Collection failed. ${requestError.message}`;
      setPageFeedback({ tone: "danger", message });
      announce(message, { urgent: true });
    } finally {
      setCollectLoading(false);
    }
  };

  const findRelated = async (item) => {
    setRowState((previous) => ({ ...previous, [item.id]: { state: "pending" } }));

    try {
      const data = await apiPost("/api/matches", {
        source_type: "bet",
        source_id: item.id,
      });

      setRowState((previous) => ({
        ...previous,
        [item.id]: { state: "success", seedId: data?.id },
      }));
      setLastSeed({ id: data?.id, title: item.question });
      announce(`Seed created for ${item.question}.`);
    } catch (requestError) {
      setRowState((previous) => ({
        ...previous,
        [item.id]: { state: "error", message: requestError.message },
      }));
      announce(`Match failed. ${requestError.message}`, { urgent: true });
    }
  };

  const renderAction = (item, compact) => {
    const state = rowState[item.id];

    if (state?.state === "success") {
      return (
        <span className="row-note row-note--success">
          <Icon name="check" size={14} /> Seed created
        </span>
      );
    }

    if (state?.state === "pending") {
      return <span className="row-note">Matching…</span>;
    }

    if (state?.state === "error") {
      return (
        <span className="row-note-group">
          <span className="row-note row-note--danger">{state.message}</span>
          <Button size="sm" onClick={() => findRelated(item)}>
            Retry
          </Button>
        </span>
      );
    }

    return (
      <Button
        variant="ghost"
        size={compact ? "md" : "sm"}
        icon="target"
        iconOnly={!compact}
        label={`Find related news for “${item.question}”`}
        onClick={() => findRelated(item)}
      >
        Find related news
      </Button>
    );
  };

  const listState = (() => {
    if (rows.length === 0 && loading) {
      return (
        <div className="table-panel">
          <Skeleton rows={6} />
        </div>
      );
    }

    if (rows.length === 0 && error) {
      return (
        <ErrorState
          title="Can't load bets"
          message={error}
          onRetry={reload}
          retrying={loading}
        />
      );
    }

    if (rows.length === 0 && hasFilters) {
      return (
        <EmptyState
          title="No markets match these filters"
          action={<Button onClick={clearFilters}>Clear filters</Button>}
        >
          Every filter is applied by the API. Clearing them shows the full list again.
        </EmptyState>
      );
    }

    if (rows.length === 0) {
      return (
        <EmptyState
          title="No markets collected yet"
          action={
            <Button variant="primary" icon="collect" onClick={handleCollect} loading={collectLoading}>
              Collect bets
            </Button>
          }
        >
          Bets are collected from Polymarket and scored for emotionality and status-quo deviation.
        </EmptyState>
      );
    }

    if (!wide) {
      return (
        <ul className="cards">
          {rows.map((item) => (
            <li className="card" key={item.id}>
              <div className="card__top">
                <span className="card__price">
                  {formatProbability(item.price) ?? "Price unknown"}
                </span>
                <span className="card__time">
                  {item.end_date ? `Ends ${formatDate(item.end_date)}` : "No end date"}
                </span>
              </div>

              <RecordLink className="card__title" href={item.url}>
                {item.question || "Untitled market"}
              </RecordLink>

              <MarketBadges item={item} />

              <dl className="card__stats">
                <div className="card__stat">
                  <dt>1D</dt>
                  <dd>
                    <Delta value={item.one_day_price_change} />
                  </dd>
                </div>
                <div className="card__stat">
                  <dt>1W</dt>
                  <dd>
                    <Delta value={item.one_week_price_change} />
                  </dd>
                </div>
                <div className="card__stat">
                  <dt>1M</dt>
                  <dd>
                    <Delta value={item.one_month_price_change} />
                  </dd>
                </div>
              </dl>

              <p className="card__meta">
                {`Volume ${formatCompactCurrency(item.volume) ?? "unknown"} · Liquidity ${
                  formatCompactCurrency(item.liquidity) ?? "unknown"
                }`}
              </p>

              <p className="card__meta card__meta--meter">
                <span>Unrest</span>
                <Unrest value={item.emotionality_score} />
              </p>

              <div className="card__actions">{renderAction(item, true)}</div>
            </li>
          ))}
        </ul>
      );
    }

    return (
      <div className="table-panel">
        <table className="table table--bets">
          <thead>
            <tr>
              <th scope="col">Market</th>
              <th scope="col" className="col-price numeric">
                Price
              </th>
              <th scope="col" className="col-delta numeric">
                1D
              </th>
              <th scope="col" className="col-delta numeric">
                1W
              </th>
              <th scope="col" className="col-delta numeric">
                1M
              </th>
              <th scope="col" className="col-volume numeric">
                Volume
              </th>
              <th scope="col" className="col-unrest">
                Unrest
              </th>
              <th scope="col" className="col-ends">
                Ends
              </th>
              <th scope="col" className="row-action">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((item) => (
              <tr key={item.id}>
                <td>
                  <RecordLink href={item.url}>
                    {item.question || "Untitled market"}
                  </RecordLink>
                  <MarketBadges item={item} />
                  {item.category ? <span className="record-meta">{item.category}</span> : null}
                </td>
                <td className="col-price numeric">
                  {formatProbability(item.price) ?? "—"}
                </td>
                <td className="col-delta numeric">
                  <Delta value={item.one_day_price_change} />
                </td>
                <td className="col-delta numeric">
                  <Delta value={item.one_week_price_change} />
                </td>
                <td className="col-delta numeric">
                  <Delta value={item.one_month_price_change} />
                </td>
                <td className="col-volume numeric">
                  {formatCompactCurrency(item.volume) ?? "—"}
                </td>
                <td className="col-unrest">
                  <Unrest value={item.emotionality_score} />
                </td>
                <td className="col-ends">{formatDate(item.end_date) ?? "—"}</td>
                <td className="row-action">
                  <div className="row-action__inner">{renderAction(item, false)}</div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  })();

  return (
    <div className="view">
      <header className="view-header">
        <div className="view-header__text">
          <h1>Bets</h1>
          <p className="view-header__description">
            Polymarket markets, scored for how much they unsettle the status quo.
          </p>
        </div>
        <div className="view-header__actions">
          <Button variant="ghost" onClick={() => setManageOpen(true)}>
            Manage data
          </Button>
          <Button
            variant="primary"
            icon="collect"
            onClick={handleCollect}
            loading={collectLoading}
            disabled={collectLoading}
          >
            {collectLoading ? "Collecting…" : "Collect bets"}
          </Button>
        </div>
      </header>

      <div className="toolbar">
        <div className="toolbar__chips">
          <FilterChip pressed={activeOnly} onClick={() => setActiveOnly((value) => !value)}>
            Active only
          </FilterChip>
          <FilterChip pressed={newOnly} onClick={() => setNewOnly((value) => !value)}>
            New only
          </FilterChip>
        </div>

        <Field id="bets-tag" label="Tag" className="field--narrow">
          <input
            className="input"
            type="search"
            value={tag}
            onChange={(event) => setTag(event.target.value)}
            placeholder="Politics"
          />
        </Field>

        <Field id="bets-min-move" label="Minimum move (%)" className="field--narrow">
          <input
            className="input"
            type="number"
            min="0"
            step="0.1"
            value={minMove}
            onChange={(event) => setMinMove(event.target.value)}
            placeholder="0"
          />
        </Field>

        <Field id="bets-sort" label="Sort by" className="field--narrow">
          <select className="select" value={sort} onChange={changeSort}>
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </Field>

        <Field id="bets-direction" label="Direction" className="field--narrow">
          <select className="select" value={direction} onChange={changeDirection}>
            <option value="asc">Ascending</option>
            <option value="desc">Descending</option>
          </select>
        </Field>

        <div className="toolbar__spacer" />

        <p className="toolbar__count">
          {formatCount(total)} markets{hasFilters ? " match" : ""}
        </p>

        {hasFilters ? <Button onClick={clearFilters}>Clear filters</Button> : null}

        <Button onClick={reload} disabled={loading}>
          Refresh
        </Button>
      </div>

      {pageFeedback ? (
        <Feedback
          tone={pageFeedback.tone}
          action={
            <Button
              variant="ghost"
              size="sm"
              iconOnly
              icon="close"
              label="Dismiss message"
              onClick={() => setPageFeedback(null)}
            />
          }
        >
          {pageFeedback.message}
        </Feedback>
      ) : null}

      {lastSeed ? (
        <Feedback
          tone="success"
          action={
            <div className="feedback__buttons">
              <Button
                size="sm"
                onClick={() => onNavigate("matches", { seedId: lastSeed.id })}
              >
                View in Matches
              </Button>
              <Button
                variant="ghost"
                size="sm"
                iconOnly
                icon="close"
                label="Dismiss message"
                onClick={() => setLastSeed(null)}
              />
            </div>
          }
        >
          {`Seed created for ${lastSeed.title}.`}
        </Feedback>
      ) : null}

      {error && rows.length > 0 ? (
        <Feedback
          tone="danger"
          action={
            <Button size="sm" onClick={reload} disabled={loading}>
              Try again
            </Button>
          }
        >
          {`Couldn't refresh the list. ${error}`}
        </Feedback>
      ) : null}

      <div
        className="list"
        aria-busy={loading || undefined}
        aria-label="Bets results"
        role="region"
      >
        {listState}
        {rows.length > 0 ? (
          <Pagination
            total={total}
            offset={loadedOffset}
            limit={limit}
            onOffsetChange={setOffset}
            onLimitChange={changeLimit}
            busy={loading}
          />
        ) : null}
      </div>

      <DeleteRangeDialog
        key={manageOpen ? "manage-open" : "manage-closed"}
        open={manageOpen}
        onClose={() => setManageOpen(false)}
        titleId="manage-bets-title"
        formTitle="Delete bets by date"
        formDescription="Rows are matched on the date they were collected. Everything outside the range stays."
        confirmTitle="Delete these bets?"
        subject="Bets"
        verb="collected"
        noun="bets"
        endpoint="/api/bets"
        announce={announce}
        onDeleted={(message) => {
          setPageFeedback({ tone: "success", message });
          setOffset(0);
          reload();
        }}
      />
    </div>
  );
}

export default Bets;
