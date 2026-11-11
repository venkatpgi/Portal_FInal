import React from "react";
import { describeAuditChange, diffAuditValues } from "../utils/auditDiff";
import "./AuditChangeList.css";

function groupChangeRows(rows) {
  const order = [];
  const map = new Map();
  rows.forEach((row) => {
    const g = row.group || "";
    if (!map.has(g)) {
      map.set(g, []);
      order.push(g);
    }
    map.get(g).push(row);
  });
  return order.map((group) => ({ group, items: map.get(group) }));
}

function ChangeLines({ row }) {
  const { was, now } = describeAuditChange(row);
  return (
    <>
      <p className="audit-changes-story-line">
        <span className="audit-changes-story-k">Was</span>
        <span className="audit-changes-from">{was}</span>
      </p>
      <p className="audit-changes-story-line">
        <span className="audit-changes-story-k">Now</span>
        <span className="audit-changes-to">{now}</span>
      </p>
    </>
  );
}

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
    !q
    || row.label.toLowerCase().includes(q)
    || row.key.toLowerCase().includes(q)
    || String(row.group || "").toLowerCase().includes(q)
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
              <span className="audit-changes-compact-label">
                {row.group ? `${row.group} · ${row.label}` : row.label}
              </span>
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
      {groupChangeRows(rows).map(({ group, items }) => (
        <section key={group || items[0].key} className="audit-changes-story-item">
          {group ? <h4 className="audit-changes-story-label">{group}</h4> : null}
          {items.map((row) => (
            <div key={row.key} className={`audit-changes-fieldblock audit-changes-story-item--${row.kind}`}>
              <div className="audit-changes-fieldname">{row.label}</div>
              <ChangeLines row={row} />
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}
