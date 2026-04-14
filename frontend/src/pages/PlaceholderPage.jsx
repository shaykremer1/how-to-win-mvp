import React from "react";

export default function PlaceholderPage({ title, description }) {
  return (
    <section className="section">
      <div className="panel">
        <h2 className="section-title">{title}</h2>
        <p className="empty">{description}</p>
      </div>
    </section>
  );
}
