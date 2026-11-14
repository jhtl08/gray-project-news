import { useEffect, useState } from "react";
import Button from "./components/Button.jsx";
import DeleteRangeDialog from "./components/DeleteRangeDialog.jsx";
import Dialog, { DialogFooter, DialogHeader } from "./components/Dialog.jsx";
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
  formatCount,
  formatDate,
  formatRelative,
  formatScore,
  hostnameOf,
} from "./lib/format.js";
import { useDebouncedValue, useMediaQuery } from "./lib/hooks.js";

const SORT_OPTIONS = [
  { value: "seendate", label: "Seen date" },
  { value: "disruptiveness_score", label: "Disruptiveness" },
  { value: "created_at", label: "Collected at" },
  { value: "id", label: "ID" },
];

const COLLECT_SORT_OPTIONS = [
  { value: "datedesc", label: "Date descending" },
  { value: "dateasc", label: "Date ascending" },
  { value: "hybridrel", label: "Hybrid relevance" },
];

function Score({ value }) {
  const score = formatScore(value);
  if (score === null) {
    return <span className="badge badge--warning">Pending</span>;
  }
  return <Meter value={value} format={formatScore} />;
}

function News({ onNavigate }) {
  const announce = useAnnounce();
  const wide = useMediaQuery("(min-width: 760px)");

  const [sort, setSort] = useState("seendate");
  const [direction, setDirection] = useState("desc");
  const [offset, setOffset] = useState(0);
  const [loadedOffset, setLoadedOffset] = useState(0);
  const [limit, setLimit] = useState(100);
  const [reloadToken, setReloadToken] = useState(0);

  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [filter, setFilter] = useState("");
  const debouncedFilter = useDebouncedValue(filter, 200);

  const [rowState, setRowState] = useState({});
  const [lastSeed, setLastSeed] = useState(null);
  const [pageFeedback, setPageFeedback] = useState(null);

  const [collectOpen, setCollectOpen] = useState(false);
  const [collectForm, setCollectForm] = useState({
    query: "",
    maxrecords: "",
    timespan: "",
    sort: "datedesc",
  });
  const [collectLoading, setCollectLoading] = useState(false);
  const [collectError, setCollectError] = useState(null);
  const [collectFieldError, setCollectFieldError] = useState(null);
  const [collectResult, setCollectResult] = useState(null);

  const [manageOpen, setManageOpen] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
      order_by: sort,
      order_dir: direction,
    });

    setLoading(true);
    setError(null);

    apiFetch(`/api/news?${params}`, { signal: controller.signal })
      .then((data) => {
        const loaded = data?.news ?? [];
        const count = data?.total ?? 0;
        setRows(loaded);
        setTotal(count);
        setLoadedOffset(offset);
        setLoading(false);
        announce(`Showing ${formatCount(count)} news rows.`);
      })
      .catch((requestError) => {
        if (requestError.name === "AbortError") return;
        setError(requestError.message);
        setLoading(false);
        announce(`Can't load news. ${requestError.message}`, { urgent: true });
      });

    return () => controller.abort();
  }, [sort, direction, offset, limit, reloadToken, announce]);

  const reload = () => setReloadToken((token) => token + 1);

  const term = debouncedFilter.trim().toLowerCase();
  const filtered = term
    ? rows.filter((item) =>
        [item.title, item.query, item.sourcecountry, item.language, hostnameOf(item.url)].some(
          (value) => String(value ?? "").toLowerCase().includes(term),
        ),
      )
    : rows;

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

  const findRelated = async (item) => {
    setRowState((previous) => ({ ...previous, [item.id]: { state: "pending" } }));
    try {
      const data = await apiPost("/api/matches", {
        source_type: "news",
        source_id: item.id,
      });
      setRowState((previous) => ({
        ...previous,
        [item.id]: { state: "success", seedId: data?.id },
      }));
      setLastSeed({ id: data?.id, title: item.title });
      announce(`Seed created for ${item.title}.`);
    } catch (requestError) {
      setRowState((previous) => ({
        ...previous,
        [item.id]: { state: "error", message: requestError.message },
      }));
      announce(`Match failed. ${requestError.message}`, { urgent: true });
    }
  };

  const openCollect = () => {
    setCollectError(null);
    setCollectFieldError(null);
    setCollectResult(null);
    setCollectOpen(true);
  };

  const closeCollect = () => setCollectOpen(false);

  const handleCollect = async (event) => {
    event.preventDefault();

    const maxrecords = collectForm.maxrecords.trim();
    if (maxrecords && !/^\d+$/.test(maxrecords)) {
      setCollectFieldError("Enter a whole number, for example 200.");
      document.getElementById("collect-maxrecords")?.focus();
      return;
    }

    setCollectFieldError(null);
    setCollectError(null);
    setCollectLoading(true);

    try {
      const data = await apiPost("/api/news/collect", {
        query: collectForm.query.trim() || null,
        maxrecords: maxrecords ? Number(maxrecords) : null,
        timespan: collectForm.timespan.trim() || null,
        sort: collectForm.sort,
      });

      let message = `Collected ${formatCount(data?.articles)} articles.`;
      if (data?.ingested) {
        message += ` ${formatCount(data.ingested.inserted)} new, ${formatCount(
          data.ingested.skipped,
        )} already stored.`;
      }
      if (data?.ingest_error) {
        message += ` Ingestion warning: ${data.ingest_error}`;
      }

      setCollectResult({ message, warning: Boolean(data?.ingest_error) });
      announce(message);
      setOffset(0);
      reload();
    } catch (requestError) {
      setCollectError(requestError.message);
      announce(`Collection failed. ${requestError.message}`, { urgent: true });
    } finally {
      setCollectLoading(false);
    }
  };

  const openManage = () => setManageOpen(true);

  const metaFor = (item) =>
    [hostnameOf(item.url), item.sourcecountry, item.language].filter(Boolean).join(" · ");

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
        label={`Find related bets for “${item.title}”`}
        onClick={() => findRelated(item)}
      >
        Find related bets
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
          title="Can't load news"
          message={error}
          onRetry={reload}
          retrying={loading}
        />
      );
    }

    if (rows.length === 0) {
      return (
        <EmptyState
          title="No news stored yet"
          action={
            <Button variant="primary" icon="collect" onClick={openCollect}>
              Collect news
            </Button>
          }
        >
          News is collected from GDELT and scored for how much each story could move a market.
        </EmptyState>
      );
    }

    if (filtered.length === 0) {
      return (
        <EmptyState
          title="No loaded rows match"
          action={<Button onClick={() => setFilter("")}>Clear filter</Button>}
        >
          {`Your filter matches none of the ${formatCount(rows.length)} rows on this page.`}
        </EmptyState>
      );
    }

    if (!wide) {
      return (
        <ul className="cards">
          {filtered.map((item) => (
            <li className="card" key={item.id}>
              <div className="card__top">
                <Score value={item.disruptiveness_score} />
                <span className="card__meta">{metaFor(item)}</span>
                <time className="card__time" dateTime={item.seendate ?? undefined}>
                  {formatRelative(item.seendate) ?? "Date unknown"}
                </time>
              </div>
              <RecordLink className="card__title" href={item.url}>
                {item.title || "Untitled story"}
              </RecordLink>
              {item.query ? <p className="card__meta">{`Collected with ${item.query}`}</p> : null}
              <div className="card__actions">{renderAction(item, true)}</div>
            </li>
          ))}
        </ul>
      );
    }

    return (
      <div className="table-panel">
        <table className="table">
          <thead>
            <tr>
              <th scope="col" className="col-score">
                Score
              </th>
              <th scope="col">Story</th>
              <th scope="col" className="col-seen">
                Seen
              </th>
              <th scope="col" className="row-action">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((item) => (
              <tr key={item.id}>
                <td className="col-score">
                  <Score value={item.disruptiveness_score} />
                </td>
                <td>
                  <RecordLink href={item.url}>{item.title || "Untitled story"}</RecordLink>
                  <span className="record-meta">{metaFor(item)}</span>
                </td>
                <td className="col-seen">
                  <time dateTime={item.seendate ?? undefined}>
                    {formatDate(item.seendate) ?? "Date unknown"}
                  </time>
                </td>
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
          <h1>News</h1>
          <p className="view-header__description">
            Worldwide coverage, ranked by how much each story could move a market.
          </p>
        </div>
        <div className="view-header__actions">
          <Button variant="ghost" onClick={openManage}>
            Manage data
          </Button>
          <Button variant="primary" icon="collect" onClick={openCollect}>
            Collect news
          </Button>
        </div>
      </header>

      <div className="toolbar">
        <Field id="news-sort" label="Sort by" className="field--narrow">
          <select className="select" value={sort} onChange={changeSort}>
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </Field>

        <Field id="news-direction" label="Direction" className="field--narrow">
          <select className="select" value={direction} onChange={changeDirection}>
            <option value="asc">Ascending</option>
            <option value="desc">Descending</option>
          </select>
        </Field>

        <Field id="news-filter" label="Filter loaded rows" className="field--inline">
          <input
            className="input"
            type="search"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            placeholder="Title, query or source"
          />
        </Field>

        <div className="toolbar__spacer" />

        <p className="toolbar__count">
          {formatCount(filtered.length)} of {formatCount(rows.length)} loaded
        </p>

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
        aria-label="News results"
        role="region"
      >
        {listState}
        {rows.length > 0 && filtered.length > 0 ? (
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

      <Dialog open={collectOpen} onClose={closeCollect} labelledBy="collect-news-title">
        <DialogHeader
          titleId="collect-news-title"
          title="Collect news"
          description="Fetch articles from GDELT and store the new ones."
          onClose={closeCollect}
        />

        {collectResult ? (
          <>
            <Feedback tone={collectResult.warning ? "warning" : "success"}>
              {collectResult.message}
            </Feedback>
            <DialogFooter>
              <Button onClick={closeCollect}>Close</Button>
              <Button variant="primary" onClick={closeCollect}>
                View news
              </Button>
            </DialogFooter>
          </>
        ) : (
          <form className="dialog__form" onSubmit={handleCollect} noValidate>
            <Field
              id="collect-query"
              label="Query"
              hint="GDELT search syntax. Leave it blank for the default feed."
            >
              <input
                className="input"
                type="text"
                name="query"
                value={collectForm.query}
                onChange={(event) =>
                  setCollectForm((form) => ({ ...form, query: event.target.value }))
                }
                placeholder="(iran OR hormuz)"
              />
            </Field>

            <Field
              id="collect-maxrecords"
              label="Max records"
              hint="Defaults to 200."
              error={collectFieldError}
            >
              <input
                className="input"
                type="number"
                name="maxrecords"
                min="1"
                step="1"
                value={collectForm.maxrecords}
                onChange={(event) => {
                  setCollectForm((form) => ({ ...form, maxrecords: event.target.value }));
                  if (collectFieldError) setCollectFieldError(null);
                }}
                placeholder="200"
              />
            </Field>

            <Field id="collect-timespan" label="Timespan" hint="A window such as 1h, 24h or 7d.">
              <input
                className="input"
                type="text"
                name="timespan"
                value={collectForm.timespan}
                onChange={(event) =>
                  setCollectForm((form) => ({ ...form, timespan: event.target.value }))
                }
                placeholder="1h"
              />
            </Field>

            <Field id="collect-sort" label="Sort">
              <select
                className="select"
                name="sort"
                value={collectForm.sort}
                onChange={(event) =>
                  setCollectForm((form) => ({ ...form, sort: event.target.value }))
                }
              >
                {COLLECT_SORT_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>

            {collectError ? (
              <Feedback tone="danger">{collectError}</Feedback>
            ) : null}

            <DialogFooter>
              <Button onClick={closeCollect}>Cancel</Button>
              <Button
                type="submit"
                variant="primary"
                icon="collect"
                loading={collectLoading}
                disabled={collectLoading}
              >
                {collectLoading ? "Collecting…" : "Collect news"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </Dialog>

      <DeleteRangeDialog
        key={manageOpen ? "manage-open" : "manage-closed"}
        open={manageOpen}
        onClose={() => setManageOpen(false)}
        titleId="manage-news-title"
        formTitle="Delete news by date"
        formDescription="Rows are matched on the date each article was seen. Everything outside the range stays."
        confirmTitle="Delete these news rows?"
        subject="News"
        verb="seen"
        noun="news rows"
        endpoint="/api/news"
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

export default News;
