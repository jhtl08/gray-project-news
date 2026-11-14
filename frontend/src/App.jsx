import { useEffect, useState } from "react";
import Tabs from "./components/Tabs.jsx";
import Icon from "./components/Icon.jsx";
import { Announcer } from "./components/Feedback.jsx";
import { panelId, tabId } from "./lib/ids.js";
import News from "./News.jsx";
import Bets from "./Bets.jsx";
import Matches from "./Matches.jsx";

const VIEWS = [
  { id: "news", label: "News", title: "News" },
  { id: "bets", label: "Bets", title: "Bets" },
  { id: "matches", label: "Matches", title: "Matches" },
];

function App() {
  const [activeView, setActiveView] = useState("news");
  const [visited, setVisited] = useState(() => new Set(["news"]));
  const [pendingSeedId, setPendingSeedId] = useState(null);

  const navigate = (view, options = {}) => {
    setActiveView(view);
    setVisited((previous) => {
      if (previous.has(view)) return previous;
      const next = new Set(previous);
      next.add(view);
      return next;
    });
    if (options.seedId) setPendingSeedId(options.seedId);
  };

  useEffect(() => {
    const view = VIEWS.find((item) => item.id === activeView) ?? VIEWS[0];
    document.title = `${view.title} · Gray Project News`;
  }, [activeView]);

  return (
    <Announcer>
      <a className="skip-link" href="#main">
        Skip to content
      </a>

      <header className="app-header">
        <div className="app-header__inner">
          <p className="brand">
            <span className="brand__mark" aria-hidden="true">
              <Icon name="news" size={18} />
            </span>
            <span className="brand__name">Gray Project News</span>
          </p>
          <Tabs items={VIEWS} active={activeView} onChange={navigate} label="Sections" />
        </div>
      </header>

      <main className="app-main" id="main" tabIndex={-1}>
        <section
          id={panelId("news")}
          className="view"
          role="tabpanel"
          aria-labelledby={tabId("news")}
          hidden={activeView !== "news"}
        >
          {visited.has("news") ? <News onNavigate={navigate} /> : null}
        </section>

        <section
          id={panelId("bets")}
          className="view"
          role="tabpanel"
          aria-labelledby={tabId("bets")}
          hidden={activeView !== "bets"}
        >
          {visited.has("bets") ? <Bets onNavigate={navigate} /> : null}
        </section>

        <section
          id={panelId("matches")}
          className="view"
          role="tabpanel"
          aria-labelledby={tabId("matches")}
          hidden={activeView !== "matches"}
        >
          {visited.has("matches") ? (
            <Matches
              key={pendingSeedId ?? "matches"}
              onNavigate={navigate}
              initialSeedId={pendingSeedId}
            />
          ) : null}
        </section>
      </main>
    </Announcer>
  );
}

export default App;
