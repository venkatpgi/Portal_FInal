/** Local filter for the Gestation log and the Log of All Births (both rows
 * carry mother_name, mother_uid and id). GET returns the full list.
 * Matches the name, the CR number, or the entry number ("64" or "#64",
 * the number a data query quotes). */
export function collapseSearchSpaces(value) {
  return String(value || "").trim().toLowerCase().replace(/\s+/g, " ");
}

export function gaCheckMatchesQuery(entry, query) {
  const q = collapseSearchSpaces(query);
  if (!q) return true;
  const name = collapseSearchSpaces(entry?.mother_name);
  const id = String(entry?.mother_uid || "").trim().toLowerCase();
  const idQuery = q.replace(/ /g, "");
  const entryNo = idQuery.replace(/^#/, "");
  if (/^\d+$/.test(entryNo) && String(entry?.id) === entryNo) return true;
  if (idQuery.startsWith("#")) return false;
  return name.includes(q) || (idQuery && id.includes(idQuery));
}

export function filterGaChecks(entries, query) {
  const list = entries || [];
  if (!collapseSearchSpaces(query)) return list;
  return list.filter((e) => gaCheckMatchesQuery(e, query));
}

export const filterLogEntries = filterGaChecks;
