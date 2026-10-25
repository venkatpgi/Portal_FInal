"""Form A screening_status, shared by main.py and participant_counts.py
(moved out of main.py 2026-10-24 so modules other than main can use it)."""


def compute_screening_status(data):
    """Authoritative screening_status for web + mobile (Form A).

    Labels match Screening Form / ViewEntries banners:
      Screen Failure — GA undeterminable (Neither) OR any exclusion Yes
      Not Eligible   — GA outside 25w0d–31w6d, OR consent No / Not approached
      Eligible       — GA in window, no exclusion, consent Yes
                       ("Trial run" no longer counts as consent: PI
                       2026-10-18, after the trial started)
      Pending        — screening incomplete (no GA yet) OR clinically OK
                       but consent not yet recorded
    """
    gestation_known = getattr(data, "gestation_known", None)
    ga_source = getattr(data, "ga_source", None)
    if gestation_known == "No" and ga_source == "Neither":
        return "Screen Failure"

    if data.gestation_weeks is None:
        return "Pending"

    weeks = int(data.gestation_weeks)
    days = int(getattr(data, "gestation_days", None) or 0)
    total_days = weeks * 7 + days
    # Eligible window: 25w0d – 31w6d inclusive (Form A GA banner = Not Eligible)
    if total_days < 25 * 7 or total_days > 31 * 7 + 6:
        return "Not Eligible"

    if data.exclusion_present:
        return "Screen Failure"

    consent = getattr(data, "consent_given", None)
    if consent == "Yes":
        return "Eligible"

    if consent in ("No", "Not approached"):
        return "Not Eligible"

    # Clinically passed inclusion; consent not answered yet
    return "Pending"
