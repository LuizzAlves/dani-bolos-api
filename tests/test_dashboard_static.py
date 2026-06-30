"""
Static checks for the admin dashboard.
"""

import re
from pathlib import Path


def test_direct_event_listener_targets_exist_in_initial_html():
    """Prevent startup crashes from missing DOM nodes."""
    root = Path(__file__).resolve().parents[1]
    html = (root / "dashboard" / "index.html").read_text(encoding="utf-8")
    js = (root / "dashboard" / "app.js").read_text(encoding="utf-8")

    html_ids = set(re.findall(r'id="([^"]+)"', html))
    dynamic_ids = {
        # Created by renderServiceHours/renderGeneralSettings before listener binding.
        "btn-save-service-hours",
        "btn-save-general",
    }

    missing = []
    pattern = r"document\.getElementById\('([^']+)'\)\.addEventListener"
    for match in re.finditer(pattern, js):
        element_id = match.group(1)
        if element_id not in html_ids and element_id not in dynamic_ids:
            missing.append(element_id)

    assert missing == []
