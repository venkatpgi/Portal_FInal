import React from "react";
import { describeAuditChange, diffAuditValues } from "../utils/auditDiff";
import "./AuditChangeList.css";

export default function AuditChangeList({
  oldValues,
  newValues,
  hideKeys = [],
  compact = false,
  showUnchanged = false,
  filterText = "",
  emptyMessage = "",
}) {
  const { changes, unchanged } = diffAuditValues(oldValues, newValues, { hideKeys });
  const q = String(filterText || "").trim().toLowerCase();
  const match = (row) => (
    !q || row.label.toLowerCase().includes(q) || row.key.toLowerCase().includes(q)
  );
  const rows = (showUnchanged ? [...changes, ...unchanged] : changes).filter(match);

  if (rows.length === 0) {
    return (
      <p className="audit-changes-empty">
        {q
          ? "No fields match that search."
          : (emptyMessage || (showUnchanged ? "No fields recorded." : "No answers on this form changed."))}
      </p>
    );
  }

  if (compact) {
    return (
      <ul className="audit-changes-compact">
        {rows.map((row) => {
          const { was, now } = describeAuditChange(row);
          return (
            <li key={row.key} className={`audit-changes-compact-item audit-changes-compact-item--${row.kind}`}>
              <span className="audit-changes-compact-label">{row.label}</span>
              <span className="audit-changes-compact-vals">
                <span className="audit-changes-side">
                  <span className="audit-changes-side-label">Was</span>
                  <span className="audit-changes-from">{was}</span>
                </span>
                <span className="audit-changes-arrow" aria-hidden="true">→</span>
                <span className="audit-changes-side">
                  <span className="audit-changes-side-label">Now</span>
                  <span className="audit-changes-to">{now}</span>
                </span>
              </span>
            </li>
          );
        })}
      </ul>
    );
  }

  return (
    <div className="audit-changes-story">
      {rows.map((row) => {
        const { was, now } = describeAuditChange(row);
        return (
          <article key={row.key} className={`audit-changes-story-item audit-changes-story-item--${row.kind}`}>
            <h4 className="audit-changes-story-label">{row.label}</h4>
            <p className="audit-changes-story-line">
              <span className="audit-changes-story-k">Was</span>
              <span className="audit-changes-from">{was}</span>
            </p>
            <p className="audit-changes-story-line">
              <span className="audit-changes-story-k">Now</span>
              <span className="audit-changes-to">{now}</span>
            </p>
          </article>
        );
      })}
    </div>
  );
}
