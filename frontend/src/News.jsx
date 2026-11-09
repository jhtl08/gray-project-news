import { useState, useEffect } from "react";

const API_BASE = "http://localhost:8000";

function News() {
  const [subTab, setSubTab] = useState("collect");
  const [collectForm, setCollectForm] = useState({
    query: "",
    maxrecords: "",
    timespan: "",
    sort: "datedesc",
  });
  const [collectLoading, setCollectLoading] = useState(false);
  const [collectFeedback, setCollectFeedback] = useState(null);

  const [news, setNews] = useState([]);
  const [newsTotal, setNewsTotal] = useState(0);
  const [newsLoading, setNewsLoading] = useState(false);
  const [orderBy, setOrderBy] = useState("seendate");
  const [orderDir, setOrderDir] = useState("desc");
  const [limit] = useState(100);
  const [offset, setOffset] = useState(0);

  const handleCollectChange = (e) => {
    const { name, value } = e.target;
    setCollectForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleCollectSubmit = async (e) => {
    e.preventDefault();
    setCollectLoading(true);
    setCollectFeedback(null);

    try {
      const payload = {
        query: collectForm.query.trim() || null,
        maxrecords: collectForm.maxrecords
          ? parseInt(collectForm.maxrecords)
          : null,
        timespan: collectForm.timespan.trim() || null,
        sort: collectForm.sort || "datedesc",
      };

      const res = await fetch(`${API_BASE}/api/news/collect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
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
      let message = `Success! Collected ${data.articles} articles (query: ${data.query_used}, maxrecords: ${data.maxrecords}, timespan: ${data.timespan}, sort: ${data.sort})`;
      if (data.ingested) {
        message += ` | Ingested ${data.ingested.inserted} new, skipped ${data.ingested.skipped} existing.`;
      }
      if (data.ingest_error) {
        message += ` | Ingestion warning: ${data.ingest_error}`;
      }
      setCollectFeedback({
        type: "success",
        message: message,
      });
    } catch (err) {
      let message = err.message || "Error occurred";
      if (err instanceof TypeError && message.includes("Failed to fetch")) {
        message = `Network error: Could not reach backend at ${API_BASE}. Is the API server running?`;
      }
      setCollectFeedback({
        type: "error",
        message: message,
      });
    } finally {
      setCollectLoading(false);
    }
  };

  const fetchNews = async () => {
    setNewsLoading(true);
    try {
      const params = new URLSearchParams({
        limit: limit.toString(),
        offset: offset.toString(),
        order_by: orderBy,
        order_dir: orderDir,
      });
      const res = await fetch(`${API_BASE}/api/news?${params}`);
      if (!res.ok) {
        let errMsg = "Failed to fetch news";
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
          errMsg = `${res.status} ${res.statusText}` || errMsg;
        }
        throw new Error(errMsg);
      }
      const data = await res.json();
      setNews(data.news || []);
      setNewsTotal(data.total || 0);
    } catch (err) {
      console.error(err);
      if (err instanceof TypeError && err.message.includes("Failed to fetch")) {
        console.error(
          `Network error: Could not reach backend at ${API_BASE}. Is the API server running?`,
        );
      }
    } finally {
      setNewsLoading(false);
    }
  };

  useEffect(() => {
    if (subTab === "query") {
      fetchNews();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orderBy, orderDir, offset]);

  const handleQueryTabClick = () => {
    setSubTab("query");
    setOffset(0);
  };

  const handleRefresh = () => {
    fetchNews();
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
      <div className="news-subtabs">
        <button
          className={`news-subtab-button ${subTab === "collect" ? "active" : ""}`}
          onClick={() => setSubTab("collect")}
        >
          Collect New Data
        </button>
        <button
          className={`news-subtab-button ${subTab === "query" ? "active" : ""}`}
          onClick={handleQueryTabClick}
        >
          Query Local News Database
        </button>
      </div>

      {subTab === "collect" && (
        <section className="collect-section">
          <h2 className="section-title">Collect New Data</h2>
          <form onSubmit={handleCollectSubmit} className="collect-form">
            <div className="form-group">
              <label htmlFor="query">Query</label>
              <input
                id="query"
                name="query"
                type="text"
                value={collectForm.query}
                onChange={handleCollectChange}
                placeholder="e.g., (iran OR hormuz)"
              />
            </div>
            <div className="form-group">
              <label htmlFor="maxrecords">Max Records</label>
              <input
                id="maxrecords"
                name="maxrecords"
                type="number"
                value={collectForm.maxrecords}
                onChange={handleCollectChange}
                placeholder="200 (default)"
              />
            </div>
            <div className="form-group">
              <label htmlFor="timespan">Timespan</label>
              <input
                id="timespan"
                name="timespan"
                type="text"
                value={collectForm.timespan}
                onChange={handleCollectChange}
                placeholder="1h (default)"
              />
            </div>
            <div className="form-group">
              <label htmlFor="sort">Sort</label>
              <select
                id="sort"
                name="sort"
                value={collectForm.sort}
                onChange={handleCollectChange}
              >
                <option value="datedesc">Date Descending</option>
                <option value="dateasc">Date Ascending</option>
                <option value="hybridrel">Hybrid Relevance</option>
              </select>
            </div>
            <button
              type="submit"
              className="submit-button"
              disabled={collectLoading}
            >
              {collectLoading ? "Collecting..." : "Submit"}
            </button>
          </form>
          {collectFeedback && (
            <div className={`feedback ${collectFeedback.type}`}>
              {collectFeedback.message}
            </div>
          )}
        </section>
      )}

      {subTab === "query" && (
        <section className="query-section">
          <h2 className="section-title">Query Local News Database</h2>
          <div className="controls">
            <div className="control-group">
              <label htmlFor="orderBy">Order by</label>
              <select
                id="orderBy"
                value={orderBy}
                onChange={(e) => {
                  setOrderBy(e.target.value);
                  setOffset(0);
                  setTimeout(() => fetchNews(), 0);
                }}
              >
                <option value="seendate">Seendate</option>
                <option value="disruptiveness_score">
                  Disruptiveness Score
                </option>
                <option value="created_at">Created At</option>
                <option value="id">ID</option>
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
                  setTimeout(() => fetchNews(), 0);
                }}
              >
                <option value="desc">Ascending</option>
                <option value="asc">Descending</option>
              </select>
            </div>
            <button onClick={handleRefresh} className="pagination-button">
              Refresh
            </button>
          </div>

          {newsLoading ? (
            <div className="placeholder">Loading...</div>
          ) : news.length === 0 ? (
            <div className="placeholder">No news entries found.</div>
          ) : (
            <>
              <div className="table-container">
                <table className="news-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Title</th>
                      <th>Disruptiveness</th>
                      <th>Query</th>
                      <th>Seendate</th>
                      <th>Language</th>
                      <th>Source Country</th>
                      <th>URL</th>
                    </tr>
                  </thead>
                  <tbody>
                    {news.map((item) => (
                      <tr key={item.id}>
                        <td>{item.id}</td>
                        <td>{item.title || "-"}</td>
                        <td>{item.disruptiveness_score ?? "-"}</td>
                        <td>{item.query}</td>
                        <td>{formatDate(item.seendate)}</td>
                        <td>{item.language || "-"}</td>
                        <td>{item.sourcecountry || "-"}</td>
                        <td>
                          {item.url ? (
                            <a
                              href={item.url}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
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
                  Showing {offset + 1} to {Math.min(offset + limit, newsTotal)}{" "}
                  of {newsTotal}
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
                    disabled={offset + limit >= newsTotal}
                  >
                    Next
                  </button>
                </div>
              </div>
            </>
          )}
        </section>
      )}
    </div>
  );
}

export default News;
