// Shown only on the training site (training.portaltrial.in), which runs the
// same build against its own practice database. Sites that are not yet
// enrolling practise there so test entries never reach the trial database
// (PI 2026-10-14).
import React, { useEffect } from "react";

export const IS_TRAINING_SITE =
  typeof window !== "undefined" && window.location.hostname.startsWith("training.");

export default function TrainingBanner() {
  useEffect(() => {
    if (IS_TRAINING_SITE && !document.title.startsWith("TRAINING")) {
      document.title = `TRAINING · ${document.title}`;
    }
  }, []);
  if (!IS_TRAINING_SITE) return null;
  return (
    <div
      role="status"
      style={{
        position: "fixed", left: 0, right: 0, bottom: 0, zIndex: 100000,
        background: "#b91c1c", color: "#fff", textAlign: "center",
        font: "600 13px/1.2 system-ui, sans-serif", padding: "6px 12px",
        pointerEvents: "none", letterSpacing: "0.02em",
      }}
    >
      TRAINING SITE: practice entries only. Real trial data goes on portaltrial.in.
    </div>
  );
}
