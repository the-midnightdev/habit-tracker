import { useState } from "react";
import DayView from "./DayView.jsx";
import TemplateEditor from "./TemplateEditor.jsx";

export default function App() {
  const [tab, setTab] = useState("day");
  return (
    <div className="app">
      <h1>Time-Blocking Planner</h1>
      <nav className="app__tabs">
        <button
          className={tab === "day" ? "active" : ""}
          onClick={() => setTab("day")}
        >
          Day
        </button>
        <button
          className={tab === "template" ? "active" : ""}
          onClick={() => setTab("template")}
        >
          Template
        </button>
      </nav>
      {tab === "day" ? <DayView /> : <TemplateEditor />}
    </div>
  );
}
