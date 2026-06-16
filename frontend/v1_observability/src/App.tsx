import { useState } from "react";
import "./App.css";
import { OverviewSection } from "./components/OverviewSection";
import { VictoriaSection } from "./components/VictoriaSection";

function App() {
  const [activeSection, setActiveSection] = useState<"overview" | "victoria">(
    "overview",
  );

  return (
    <main className="page">
      <header className="page-header">
        <h1>NEM Regional Dashboard</h1>
        <p>Overview plus Victoria-focused weather and energy analytics.</p>
      </header>

      <div className="section-tabs" role="tablist" aria-label="Dashboard sections">
        <button
          type="button"
          role="tab"
          aria-selected={activeSection === "overview"}
          className={activeSection === "overview" ? "active" : ""}
          onClick={() => setActiveSection("overview")}
        >
          Overview
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeSection === "victoria"}
          className={activeSection === "victoria" ? "active" : ""}
          onClick={() => setActiveSection("victoria")}
        >
          Victoria
        </button>
      </div>

      {activeSection === "overview" ? <OverviewSection /> : <VictoriaSection />}
    </main>
  );
}

export default App;
