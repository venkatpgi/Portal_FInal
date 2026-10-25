// Participant tiles shown on both View Entries and the Dashboard (PI 2026-10-24).
// Counts come from the server (backend/participant_counts.py) so the two
// pages always show the same items with the same numbers.

export const SCREENING_TILES = [
  { key: "screened",        label: "Screened",        tone: "primary" },
  { key: "eligible",        label: "Eligible",        tone: "success" },
  { key: "not_eligible",    label: "Not eligible",    tone: "muted"   },
  { key: "screen_failures", label: "Screen failures", tone: "danger"  },
  { key: "pending",         label: "Pending",         tone: "warning" },
  { key: "consented",       label: "Consented",       tone: "teal"    },
];

// Form B counts; no arm is shown anywhere (allocation is blinded).
export const RANDOMISATION_TILES = [
  { key: "awaiting_delivery", label: "Awaiting delivery",   tone: "warning" },
  { key: "delivered",         label: "Delivered (Form B)",  tone: "teal"    },
  { key: "needed_ppv",        label: "Needed PPV",          tone: "primary" },
  { key: "randomised",        label: "Randomised",          tone: "success" },
  { key: "not_randomised",    label: "PPV, not randomised", tone: "danger"  },
  { key: "no_ppv",            label: "No PPV (A–B only)",   tone: "muted"   },
];

export const PARTICIPANT_TILES = [...SCREENING_TILES, ...RANDOMISATION_TILES];
