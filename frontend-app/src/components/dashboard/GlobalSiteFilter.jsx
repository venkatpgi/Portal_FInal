import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { SITE_ORDER } from "../../utils/siteNames";
import { formatSiteName } from "./siteLabels";
import "./GlobalSiteFilter.css";

/**
 * Cross-site dashboard filter — only shown for global users (superadmin / global_scientist).
 * value="" means all sites (omit API `site` query param).
 *
 * The menu is portaled to document.body so the left sidebar (z-index 150)
 * cannot cover site names, and so overflow:hidden ancestors cannot clip it.
 */
export default function GlobalSiteFilter({
  value = "",
  onChange,
  sites,
  className = "global-site-filter",
}) {
  const options = sites?.length ? sites : SITE_ORDER;
  const [open, setOpen] = useState(false);
  const [menuPos, setMenuPos] = useState(null);
  const rootRef = useRef(null);
  const menuRef = useRef(null);
  const current = value ? formatSiteName(value) : "All sites";

  const placeMenu = () => {
    const anchor = rootRef.current;
    if (!anchor) return;
    const r = anchor.getBoundingClientRect();
    const width = Math.max(r.width, 280);
    const maxLeft = window.innerWidth - width - 12;
    const left = Math.min(Math.max(12, r.left), Math.max(12, maxLeft));
    setMenuPos({
      top: r.bottom + 6,
      left,
      minWidth: Math.max(r.width, 240),
    });
  };

  useLayoutEffect(() => {
    if (!open) {
      setMenuPos(null);
      return undefined;
    }
    placeMenu();
    const close = () => setOpen(false);
    const onDoc = (event) => {
      if (rootRef.current?.contains(event.target)) return;
      if (menuRef.current?.contains(event.target)) return;
      setOpen(false);
    };
    window.addEventListener("resize", close);
    window.addEventListener("scroll", close, true);
    document.addEventListener("mousedown", onDoc);
    return () => {
      window.removeEventListener("resize", close);
      window.removeEventListener("scroll", close, true);
      document.removeEventListener("mousedown", onDoc);
    };
  }, [open]);

  const choose = (next) => {
    onChange(next);
    setOpen(false);
  };

  const menu = open && menuPos && createPortal(
    <ul
      ref={menuRef}
      className="global-site-filter__menu"
      role="listbox"
      aria-label="Filter by site"
      style={menuPos}
    >
      <li>
        <button
          type="button"
          role="option"
          aria-selected={value === ""}
          className={value === "" ? "is-active" : ""}
          onClick={() => choose("")}
        >
          All sites
        </button>
      </li>
      {options.map((code) => (
        <li key={code}>
          <button
            type="button"
            role="option"
            aria-selected={code === value}
            className={code === value ? "is-active" : ""}
            onClick={() => choose(code)}
          >
            {formatSiteName(code)}
          </button>
        </li>
      ))}
    </ul>,
    document.body,
  );

  return (
    <div className={className} ref={rootRef}>
      <span className="global-site-filter__label">Site</span>
      <button
        type="button"
        className="global-site-filter__select"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((isOpen) => !isOpen)}
      >
        {current}
      </button>
      {menu}
    </div>
  );
}

/** Build axios params: omit `site` when showing all sites. */
export function siteQueryParams(apiSite) {
  return apiSite ? { site: apiSite } : {};
}
