import React from "react";

export default function LineupCard({ item, tone = "neutral", title, subtitle }) {
  const diffTotal = Number(item?.diff_total || 0);
  const diffPerMin = Number(item?.diff_per_min || 0);
  const minutes = Number(item?.minutes || 0);

  return (
    <div className={`card ${tone}`}>
      {title ? <div className="card-title">{title}</div> : null}
      <div className="lineup">{item?.lineup || "-"}</div>
      {subtitle ? <div className="card-subtitle">{subtitle}</div> : null}
      <div className="stats">Diff: {diffTotal.toFixed(1)}</div>
      <div className="stats">Diff/Min: {diffPerMin.toFixed(2)}</div>
      <div className="stats">Minutes: {minutes.toFixed(2)}</div>
    </div>
  );
}
