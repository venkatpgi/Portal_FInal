// Watches every number typed on a form page and lists values outside the
// PI-approved ranges (utils/valueRanges.js) in one panel, with the input
// outlined. Inputs are matched by name attribute, or data-range="<key>".
// Typing only: values loaded from the server are checked by Data queries.
import React, { useCallback, useEffect, useRef, useState } from "react";
import { RANGE_BY_KEY, RANGE_BY_NAME, rangeCheckText } from "../utils/valueRanges";
import "./RangeWatch.css";

let nextId = 1;

export default function RangeWatch({ children }) {
  const ref = useRef(null);
  const [items, setItems] = useState({}); // id -> {el, text, level}

  const onInput = useCallback((e) => {
    const el = e.target;
    if (!el || el.tagName !== "INPUT") return;
    const rule = RANGE_BY_KEY[el.dataset?.range] || RANGE_BY_NAME[el.name];
    if (!rule) return;
    if (!el.dataset.rangeId) el.dataset.rangeId = String(nextId++);
    const id = el.dataset.rangeId;
    const res = rangeCheckText(rule, el.value);
    if (res) el.setAttribute("data-range-level", res.level);
    else el.removeAttribute("data-range-level");
    setItems((prev) => {
      const next = { ...prev };
      if (res) next[id] = { el, ...res };
      else delete next[id];
      return next;
    });
  }, []);

  useEffect(() => {
    const root = ref.current;
    if (!root) return undefined;
    root.addEventListener("input", onInput, true);
    root.addEventListener("change", onInput, true);
    return () => {
      root.removeEventListener("input", onInput, true);
      root.removeEventListener("change", onInput, true);
    };
  }, [onInput]);

  // Drop entries whose input left the page (day or baby switched).
  const live = Object.entries(items).filter(([, v]) => v.el.isConnected);
  useEffect(() => {
    if (live.length !== Object.keys(items).length) {
      setItems(Object.fromEntries(live));
    }
  });

  return (
    <div ref={ref} className="range-watch-root">
      {children}
      {live.length > 0 && (
        <div className="range-watch-panel" role="status" aria-live="polite">
          <div className="range-watch-title">Check these values</div>
          {live.map(([id, v]) => (
            <button key={id} type="button" className={`range-watch-item range-watch-item--${v.level}`}
              onClick={() => { v.el.scrollIntoView({ block: "center", behavior: "smooth" }); v.el.focus(); }}>
              {v.text}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
