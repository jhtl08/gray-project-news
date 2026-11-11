import { useState, useEffect } from "react";

const API_BASE = "http://localhost:8000";

function formatNumber(value) {
  if (value === null || value === undefined || value === "") return "-";
  const num = Number(value);
  if (Number.isNaN(num)) return String(value);
  return num.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

function formatChange(value) {
  if (value === null || value === undefined || value === "") return "-";
  const num = Number(value);
  if (Number.isNaN(num)) return String(value);
  const sign = num > 0 ? "+" : "";
  return `${sign}${num.toFixed(4)}`;
}

function Bets() {
  const [bets, setBets] = useState([]);
  const [betsTotal, setBetsTotal] = useState(0);
  const [betsLoading, setBetsLoading] = useState(false);

  const [activeOnly, setActiveOnly] = useState(false);
  const [newOnly, setNewOnly] = useState(false);
  const [tag, setTag] = useState("");
  const [minAbsChange, setMinAbsChange] = useState("");

  const [orderBy, setOrderBy] = useState("collected_at");
  const [orderDir, setOrderDir] = useState("desc");
  const [limit] = useState(100);
  const [offset, setOffset] = useState(0);

  const [collectLoading, setCollectLoading] = useState(false);
  const [collectFeedback, setCollectFeedback] = useState(null);

  const fetchBets = async () => {
    setBetsLoading(true);
    try {
      const params = new URLSearchParams({
        limit: limit.toString(),
        offset: offset.toString(),
        order_by: orderBy,
        order_dir: orderDir,
      });
      if (activeOnly) params.set("active", "true");
      if (newOnly) params.set("is_new", "true");
      if (tag.trim()) params.set("tag", tag.trim());
      if (minAbsChange.trim()) params.set("min_abs_change", minAbsChange.trim());

      const res = await fetch(`${API_BASE}/api/bets?${params}`);
      if (!res.ok) {
        let errMsg = "Failed to fetch bets";
        try {
          const err = await res.json();
          if (err.detail) {
            if (typeof err.detail === "string") {
              errMsg = err.detail;
            } else if (typeof err.detail === "object") {
              errMsg = err.detail.error || JSON.stringify(err.detail);
            }
          }
        } catch {
          errMsg = `${res.status} ${res.statusText}`.trim() || errMsg;
        }
        throw new Error(errMsg);
      }
      const data = await res.json();
      setBets(data.bets || []);
      setBetsTotal(data.total || 0);
    } catch (err) {
      console.error(err);
      if (err instanceof TypeError && err.message.includes("Failed to fetch")) {
        console.error(
          `Network error: Could not reach backend at ${API_BASE}. Is the API server running?`,
        );
      }
    } finally {
      setBetsLoading(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchBets();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orderBy, orderDir, offset, activeOnly, newOnly, tag, minAbsChange]);

  const handleCollect = async () => {
    setCollectLoading(true);
    setCollectFeedback(null);
    try {
      const res = await fetch(`${API_BASE}/api/bets/collect`, {
        method: "POST",
      });
      if (!res.ok) {
        let errMsg = "Request failed";
        try {
          const err = await res.json();
          if (err.detail) {
            if (typeof err.detail === "string") {
              errMsg = err.detail;
            } else if (typeof err.detail === "object") {
              errMsg = err.detail.error || JSON.stringify(err.detail);
              if (err.detail.traceback) {
                console.error("Backend traceback:", err.detail.traceback);
              }
            }
          }
        } catch {
          errMsg = res.statusText || errMsg;
        }
        throw new Error(errMsg);
      }
      const data = await res.json();
      let message = `Success! Collected ${data.collected} bets`;
      if (data.collected_at) {
        message += ` (collected at ${data.collected_at})`;
      }
      if (data.ingested) {
        if (typeof data.ingested === "object") {
          if (data.ingested.inserted !== undefined) {
            message += ` | Ingested ${data.ingested.inserted} new, skipped ${data.ingested.skipped} existing.`;
          } else {
            message += ` | Ingested: ${JSON.stringify(data.ingested)}`;
          }
        }
      }
      setCollectFeedback({ type: "success", message });
      setOffset(0);
      fetchBets();
    } catch (err) {
      let message = err.message || "Error occurred";
      if (err instanceof TypeError && message.includes("Failed to fetch")) {
        message = `Network error: Could not reach backend at ${API_BASE}. Is the API server running?`;
      }
      setCollectFeedback({ type: "error", message });
    } finally {
      setCollectLoading(false);
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return "-";
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="news-container">
      <section className="collect-section">
        <h2 className="section-title">Collect Bets</h2>
        <div className="collect-form">
          <button
            type="button"
            className="submit-button"
            onClick={handleCollect}
            disabled={collectLoading}
          >
            {collectLoading ? "Collecting..." : "Collect"}
          </button>
        </div>
        {collectFeedback && (
          <div className={`feedback ${collectFeedback.type}`}>
            {collectFeedback.message}
          </div>
        )}
      </section>

      <section className="query-section">
        <h2 className="section-title">Bets</h2>
        <div className="controls">
          <div className="control-group">
            <label>
              <input
                type="checkbox"
                checked={activeOnly}
                onChange={(e) => {
                  setActiveOnly(e.target.checked);
                  setOffset(0);
                }}
              />
              Active only
            </label>
          </div>
          <div className="control-group">
            <label>
              <input
                type="checkbox"
                checked={newOnly}
                onChange={(e) => {
                  setNewOnly(e.target.checked);
                  setOffset(0);
                }}
              />
              New only
            </label>
          </div>
          <div className="control-group">
            <label htmlFor="tag">Tag</label>
            <input
              id="tag"
              type="text"
              value={tag}
              onChange={(e) => {
                setTag(e.target.value);
                setOffset(0);
              }}
              placeholder="tag"
              style={{ padding: "6px 10px" }}
            />
          </div>
          <div className="control-group">
            <label htmlFor="minAbsChange">Min abs change</label>
            <input
              id="minAbsChange"
              type="number"
              step="any"
              value={minAbsChange}
              onChange={(e) => {
                setMinAbsChange(e.target.value);
                setOffset(0);
              }}
              placeholder="0.0"
              style={{ padding: "6px 10px" }}
            />
          </div>
          <div className="control-group">
            <label htmlFor="orderBy">Order by</label>
            <select
              id="orderBy"
              value={orderBy}
              onChange={(e) => {
                setOrderBy(e.target.value);
                setOffset(0);
              }}
            >
              <option value="collected_at">Collected At</option>
              <option value="question">Question</option>
              <option value="volume">Volume</option>
              <option value="one_day_price_change">1D Change</option>
              <option value="one_week_price_change">1W Change</option>
              <option value="one_month_price_change">1M Change</option>
              <option value="emotionality_score">Emotionality</option>
              <option value="status_quo_deviation">Status Quo</option>
              <option value="end_date">End Date</option>
            </select>
          </div>
          <div className="control-group">
            <label htmlFor="orderDir">Direction</label>
            <select
              id="orderDir"
              value={orderDir}
              onChange={(e) => {
                setOrderDir(e.target.value);
                setOffset(0);
              }}
            >
              <option value="asc">Ascending</option>
              <option value="desc">Descending</option>
            </select>
          </div>
          <button onClick={() => fetchBets()} className="pagination-button">
            Refresh
          </button>
        </div>

        {betsLoading ? (
          <div className="placeholder">Loading...</div>
        ) : bets.length === 0 ? (
          <div className="placeholder">No bets found.</div>
        ) : (
          <>
            <div className="table-container">
              <table className="news-table">
                <thead>
                  <tr>
                    <th>Question</th>
                    <th>Price</th>
                    <th>1D/1W/1M change</th>
                    <th>Volume</th>
                    <th>Liquidity</th>
                    <th>Emotionality</th>
                    <th>Status Quo</th>
                    <th>Tags</th>
                    <th>End Date</th>
                    <th>Link</th>
                  </tr>
                </thead>
                <tbody>
                  {bets.map((item) => (
                    <tr key={item.id}>
                      <td>{item.question || "-"}</td>
                      <td>{formatNumber(item.price)}</td>
                      <td>
                        {formatChange(item.one_day_price_change)} /{" "}
                        {formatChange(item.one_week_price_change)} /{" "}
                        {formatChange(item.one_month_price_change)}
                      </td>
                      <td>{formatNumber(item.volume)}</td>
                      <td>{formatNumber(item.liquidity)}</td>
                      <td>{item.emotionality_score ?? "-"}</td>
                      <td>{item.status_quo_deviation ?? "-"}</td>
                      <td>{item.tags || "-"}</td>
                      <td>{formatDate(item.end_date)}</td>
                      <td>
                        {item.url ? (
                          <a href={item.url} target="_blank" rel="noopener noreferrer">
                            Link
                          </a>
                        ) : (
                          "-"
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="pagination">
              <div className="pagination-info">
                Showing {offset + 1} to {Math.min(offset + limit, betsTotal)} of{" "}
                {betsTotal}
              </div>
              <div className="pagination-buttons">
                <button
                  className="pagination-button"
                  onClick={() => setOffset(Math.max(0, offset - limit))}
                  disabled={offset === 0}
                >
                  Previous
                </button>
                <button
                  className="pagination-button"
                  onClick={() => setOffset(offset + limit)}
                  disabled={offset + limit >= betsTotal}
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </section>
    </div>
  );
}

export default Bets;
