// Open a log at one entry: /ga-check?entry=64, /log-of-all-births?entry=64
// (PI 2026-10-17: "Open the log" on a data query must land on the entry the
// query is about). Once the entries have loaded, `reveal()` clears any search
// or filter that could hide the row, the row is scrolled into view and its id
// returned for highlighting. Runs once per entry number in the URL, so a
// later refresh does not undo the user's own search.
import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";

export function entryParam(search) {
  const v = new URLSearchParams(search || "").get("entry");
  return v && /^\d+$/.test(v) ? Number(v) : null;
}

export default function useEntryFocus({ entries, loading, reveal, rowIdPrefix }) {
  const { search } = useLocation();
  const target = entryParam(search);
  const handled = useRef(null);
  const [focusedId, setFocusedId] = useState(null);
  const [missingId, setMissingId] = useState(null);

  useEffect(() => {
    if (target == null || loading || handled.current === target) return;
    handled.current = target;
    if (!(entries || []).some((e) => e.id === target)) {
      setMissingId(target);
      setFocusedId(null);
      return;
    }
    setMissingId(null);
    reveal();
    setFocusedId(target);
  }, [target, loading, entries, reveal]);

  useEffect(() => {
    if (focusedId == null) return undefined;
    const t = setTimeout(() => {
      const row = document.getElementById(`${rowIdPrefix}-${focusedId}`);
      if (row) row.scrollIntoView({ block: "center", behavior: "smooth" });
    }, 80);
    return () => clearTimeout(t);
  }, [focusedId, rowIdPrefix]);

  return { focusedId, missingId };
}
