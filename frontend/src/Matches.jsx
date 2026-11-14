import { useEffect, useRef, useState } from "react";
import Button from "./components/Button.jsx";
import EmptyState from "./components/EmptyState.jsx";
import ErrorState from "./components/ErrorState.jsx";
import Feedback from "./components/Feedback.jsx";
import Icon from "./components/Icon.jsx";
import Meter from "./components/Meter.jsx";
import RecordLink from "./components/RecordLink.jsx";
import Skeleton from "./components/Skeleton.jsx";
import { apiDelete, apiFetch } from "./lib/api.js";
import { useAnnounce } from "./lib/announce.js";
import { formatCount, formatRelative, formatSimilarity } from "./lib/format.js";
import { useMediaQuery } from "./lib/hooks.js";

const TWO_PANE_QUERY = "(min-width: 1024px)";
const THRESHOLD = "0.7";

function Matches({ onNavigate, initialSeedId }) {
  const announce = useAnnounce();
  const twoPane = useMediaQuery(TWO_PANE_QUERY);
  const headingRef = useRef(null);

  const [seeds, setSeeds] = useState([]);
  const [seedsLoading, setSeedsLoading] = useState(true);
  const [seedsError, setSeedsError] = useState(null);
  const [seedsToken, setSeedsToken] = useState(0);

  const [selectedId, setSelectedId] = useState(initialSeedId ?? null);
  const [related, setRelated] = useState([]);
  const [relatedLoading, setRelatedLoading] = useState(false);
  const [relatedError, setRelatedError] = useState(null);
  const [relatedToken, setRelatedToken] = useState(0);

  const [removingId, setRemovingId] = useState(null);
  const [removeError, setRemoveError] = useState(null);

  useEffect(() => {
    const controller = new AbortController();

    // Fetching is external-system synchronization, which is what an effect is for.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSeedsLoading(true);
    setSeedsError(null);

    apiFetch("/api/matches", { signal: controller.signal })
      .then((data) => {
        const loaded = data?.matches ?? [];
        setSeeds(loaded);
        setSeedsLoading(false);
        announce(`Showing ${formatCount(loaded.length)} match seeds.`);
      })
      .catch((requestError) => {
        if (requestError.name === "AbortError") return;
        setSeedsError(requestError.message);
        setSeedsLoading(false);
        announce(`Can't load match seeds. ${requestError.message}`, { urgent: true });
      });

    return () => controller.abort();
  }, [seedsToken, announce]);

  useEffect(() => {
    if (!selectedId) return undefined;

    const controller = new AbortController();

    // eslint-disable-next-line react-hooks/set-state-in-effect
    setRelatedLoading(true);
    setRelatedError(null);

    apiFetch(`/api/matches/${selectedId}/related`, { signal: controller.signal })
      .then((data) => {
        const items = data?.items ?? [];
        setRelated(items);
        setRelatedLoading(false);
        announce(`${formatCount(items.length)} related items at ${THRESHOLD} or higher.`);
      })
      .catch((requestError) => {
        if (requestError.name === "AbortError") return;
        setRelated([]);
        setRelatedError(requestError.message);
        setRelatedLoading(false);
        announce(`Can't load related items. ${requestError.message}`, { urgent: true });
      });

    return () => controller.abort();
  }, [selectedId, relatedToken, announce]);

  const selectedSeed = seeds.find((seed) => seed.id === selectedId) ?? null;

  const selectSeed = (id) => {
    setSelectedId(id);
    setRemoveError(null);
    if (!twoPane) {
      requestAnimationFrame(() => headingRef.current?.focus());
    }
  };

  const reloadSeeds = () => setSeedsToken((token) => token + 1);

  const removeSeed = async (seed) => {
    setRemovingId(seed.id);
    setRemoveError(null);

    try {
      await apiDelete(`/api/matches/${seed.id}`);
      setSeeds((previous) => previous.filter((item) => item.id !== seed.id));
      if (selectedId === seed.id) setSelectedId(null);
      announce("Seed removed.");
    } catch (requestError) {
      setRemoveError(requestError.message);
      announce(`Couldn't remove the seed. ${requestError.message}`, { urgent: true });
    } finally {
      setRemovingId(null);
    }
  };

  const relatedType = selectedSeed?.source_type === "news" ? "Bet" : "News";

  return (
    <div className="view">
      <header className="view-header">
        <div className="view-header__text">
          <h1>Matches</h1>
          <p className="view-header__description">
            News and markets that describe the same thing, linked by embedding similarity at
            0.7 or higher.
          </p>
        </div>
        <div className="view-header__actions">
          <Button onClick={reloadSeeds} disabled={seedsLoading}>
            Refresh
          </Button>
        </div>
      </header>

      {removeError ? (
        <Feedback
          tone="danger"
          action={
            <Button
              variant="ghost"
              size="sm"
              iconOnly
              icon="close"
              label="Dismiss message"
              onClick={() => setRemoveError(null)}
            />
          }
        >
          {`Couldn't remove the seed. ${removeError}`}
        </Feedback>
      ) : null}

      <div className="matches">
        <section className="matches__seeds" aria-labelledby="seeds-heading">
          <div className="matches__seeds-header">
            <h2 id="seeds-heading" className="matches__heading">
              Seeds
            </h2>
            <span className="toolbar__count">{formatCount(seeds.length)}</span>
          </div>

          {seedsLoading && seeds.length === 0 ? <Skeleton rows={4} /> : null}

          {seedsError && seeds.length === 0 ? (
            <ErrorState
              title="Can't load match seeds"
              message={seedsError}
              onRetry={reloadSeeds}
              retrying={seedsLoading}
            />
          ) : null}

          {!seedsLoading && !seedsError && seeds.length === 0 ? (
            <EmptyState
              title="No match seeds yet"
              action={<Button onClick={() => onNavigate("news")}>Browse news</Button>}
            >
              Open a news story or a bet and choose Find related to create one.
            </EmptyState>
          ) : null}

          {seeds.length > 0 ? (
            <ul className="seed-list">
              {seeds.map((seed) => (
                <li
                  className={`seed${seed.id === selectedId ? " is-selected" : ""}`}
                  key={seed.id}
                >
                  <button
                    type="button"
                    className="seed__select"
                    aria-current={seed.id === selectedId ? "true" : undefined}
                    onClick={() => selectSeed(seed.id)}
                  >
                    <span className="seed__top">
                      <span
                        className={`badge ${
                          seed.source_type === "news" ? "badge--accent" : "badge--neutral"
                        }`}
                      >
                        {seed.source_type === "news" ? "News" : "Bet"}
                      </span>
                      {seed.created_at ? (
                        <time className="seed__time" dateTime={seed.created_at}>
                          {formatRelative(seed.created_at)}
                        </time>
                      ) : null}
                    </span>
                    <span className="seed__text">{seed.text || "Untitled seed"}</span>
                  </button>

                  <Button
                    variant="ghost"
                    size="sm"
                    iconOnly
                    icon="trash"
                    label={`Remove seed ${seed.text || seed.id}`}
                    loading={removingId === seed.id}
                    disabled={removingId === seed.id}
                    onClick={() => removeSeed(seed)}
                  />
                </li>
              ))}
            </ul>
          ) : null}

          {seedsError && seeds.length > 0 ? (
            <Feedback
              tone="danger"
              action={
                <Button size="sm" onClick={reloadSeeds} disabled={seedsLoading}>
                  Try again
                </Button>
              }
            >
              {`Couldn't refresh the seeds. ${seedsError}`}
            </Feedback>
          ) : null}
        </section>

        <section className="matches__detail" aria-labelledby="related-heading">
          {!selectedId ? (
            <EmptyState title="Select a seed">
              Choose a seed to see the news and markets that describe the same thing.
            </EmptyState>
          ) : (
            <>
              <div className="matches__detail-header">
                <h2 id="related-heading" className="matches__heading" ref={headingRef} tabIndex={-1}>
                  Related to {selectedSeed?.text || "this seed"}
                </h2>
                <p className="view-header__description">
                  The closest items at {THRESHOLD} similarity or higher, strongest first.
                </p>
              </div>

              {relatedLoading ? <Skeleton rows={3} /> : null}

              {!relatedLoading && relatedError ? (
                <ErrorState
                  title="Can't load related items"
                  message={relatedError}
                  onRetry={() => setRelatedToken((token) => token + 1)}
                />
              ) : null}

              {!relatedLoading && !relatedError && related.length === 0 ? (
                <EmptyState title={`Nothing above the ${THRESHOLD} threshold`}>
                  No item in the database describes this seed closely enough yet. Collect more
                  news or markets and try again.
                </EmptyState>
              ) : null}

              {related.length > 0 ? (
                <ol className="related-list">
                  {related.map((item, index) => {
                    const title = item.title || item.question || "Untitled item";
                    return (
                      <li className="related" key={`${item.id}-${index}`}>
                        <span className="related__rank" aria-hidden="true">
                          {index + 1}
                        </span>
                        <div className="related__body">
                          <div className="related__top">
                            <span className="badge badge--neutral">{relatedType}</span>
                            <Meter
                              value={item.similarity}
                              max={1}
                              format={formatSimilarity}
                            />
                          </div>
                          <RecordLink className="card__title" href={item.url}>
                            {title}
                          </RecordLink>
                        </div>
                      </li>
                    );
                  })}
                </ol>
              ) : null}
            </>
          )}
        </section>
      </div>

      <p className="matches__note">
        <Icon name="info" size={14} />
        Similarity comes from multilingual embeddings of the title or question. A seed is a
        saved item, not a claim that the two are related in the world.
      </p>
    </div>
  );
}

export default Matches;
