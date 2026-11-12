import { useState, useEffect } from "react";

const API_BASE = "http://localhost:8000";

function Matches() {
  const [seeds, setSeeds] = useState([]);
  const [seedsLoading, setSeedsLoading] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [related, setRelated] = useState([]);
  const [relatedLoading, setRelatedLoading] = useState(false);
  const [feedback, setFeedback] = useState(null);

  const fetchSeeds = async () => {
    setSeedsLoading(true);
    setFeedback(null);
    try {
      const res = await fetch(`${API_BASE}/api/matches`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setSeeds(data.matches || []);
    } catch (err) {
      setFeedback({ type: "error", message: err.message || "Failed to load matches" });
    } finally {
      setSeedsLoading(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchSeeds();
  }, []);

  const handleSelect = async (id) => {
    setSelectedId(id);
    setRelated([]);
    setRelatedLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/matches/${id}/related`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setRelated(data.items || []);
    } catch (err) {
      setFeedback({ type: "error", message: err.message || "Failed to load related" });
    } finally {
      setRelatedLoading(false);
    }
  };

  const selectedSeed = seeds.find((s) => s.id === selectedId);

  return (
    <div className="news-container">
      <section className="query-section">
        <h2 className="section-title">Matches</h2>
        {feedback && (
          <div className={`feedback ${feedback.type}`}>{feedback.message}</div>
        )}
        <button onClick={fetchSeeds} className="pagination-button">
          Refresh
        </button>
        {seedsLoading ? (
          <div className="placeholder">Loading...</div>
        ) : seeds.length === 0 ? (
          <div className="placeholder">No match seeds found.</div>
        ) : (
          <div className="table-container">
            <table className="news-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Source</th>
                  <th>Text</th>
                  <th>Select</th>
                </tr>
              </thead>
              <tbody>
                {seeds.map((seed) => (
                  <tr key={seed.id}>
                    <td>{seed.id}</td>
                    <td>
                      {seed.source_type || "-"}
                      {seed.source_id ? ` #${seed.source_id}` : ""}
                    </td>
                    <td>{seed.text || "-"}</td>
                    <td>
                      <button
                        className="pagination-button"
                        onClick={() => handleSelect(seed.id)}
                        disabled={relatedLoading && selectedId === seed.id}
                      >
                        {selectedId === seed.id ? "Selected" : "View related"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {selectedId && (
        <section className="query-section">
          <h2 className="section-title">
            Related to seed {selectedId}
            {selectedSeed ? ` (${selectedSeed.source_type})` : ""}
          </h2>
          {relatedLoading ? (
            <div className="placeholder">Loading...</div>
          ) : related.length === 0 ? (
            <div className="placeholder">No related items found.</div>
          ) : (
            <div className="table-container">
              <table className="news-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Title / Question</th>
                    <th>URL</th>
                    <th>Similarity</th>
                  </tr>
                </thead>
                <tbody>
                  {related.map((item) => (
                    <tr key={item.id}>
                      <td>{item.id}</td>
                      <td>{item.title || item.question || "-"}</td>
                      <td>
                        {item.url ? (
                          <a href={item.url} target="_blank" rel="noopener noreferrer">
                            Link
                          </a>
                        ) : (
                          "-"
                        )}
                      </td>
                      <td>
                        {item.similarity !== null && item.similarity !== undefined
                          ? Number(item.similarity).toFixed(4)
                          : "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

export default Matches;
