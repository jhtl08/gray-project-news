import { useState } from "react";
import "./App.css";
import News from "./News.jsx";
import Bets from "./Bets.jsx";
import Matches from "./Matches.jsx";

function App() {
  const [activeTab, setActiveTab] = useState("news");

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title">Gray Project News</h1>
        <nav className="tabs">
          <button
            className={`tab-button ${activeTab === "news" ? "active" : ""}`}
            onClick={() => setActiveTab("news")}
          >
            News
          </button>
          <button
            className={`tab-button ${activeTab === "bets" ? "active" : ""}`}
            onClick={() => setActiveTab("bets")}
          >
            Bets
          </button>
          <button
            className={`tab-button ${activeTab === "matches" ? "active" : ""}`}
            onClick={() => setActiveTab("matches")}
          >
            Matches
          </button>
        </nav>
      </header>

      <main className="app-main">
        {activeTab === "news" && <News />}
        {activeTab === "bets" && <Bets />}
        {activeTab === "matches" && <Matches />}
      </main>
    </div>
  );
}

export default App;
