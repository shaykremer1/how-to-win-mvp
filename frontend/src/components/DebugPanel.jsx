import React from "react";

export default function DebugPanel({ lines }) {
  if (import.meta.env.DEV !== true || import.meta.env.VITE_SHOW_DEBUG_PANEL !== "true") {
    return null;
  }

  return (
    <section className="debug-panel">
      <div className="debug-title">Debug Panel</div>
      {lines.map((line) => (
        <div key={line.label} className="debug-line">
          {line.label}: {line.value}
        </div>
      ))}
    </section>
  );
}
