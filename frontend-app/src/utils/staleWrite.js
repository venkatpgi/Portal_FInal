export const STALE_WRITE_MESSAGE =
  "Another nurse saved this day. Showing their latest version — add your answers again and save.";

export function isStaleWrite(err) {
  return err?.response?.status === 409;
}

/** FastAPI `detail` is a string, or a validation list. */
export function apiDetailMessage(err, fallback = "Error saving — please try again") {
  const d = err?.response?.data?.detail;
  if (typeof d === "string" && d.trim()) return d;
  if (Array.isArray(d) && d.length) {
    const first = d[0];
    if (typeof first === "string" && first.trim()) return first;
    if (first?.msg) return String(first.msg);
  }
  return fallback;
}

export function expectedUpdatedAtConfig(updatedAt) {
  if (!updatedAt) return {};
  return { params: { expected_updated_at: updatedAt } };
}
