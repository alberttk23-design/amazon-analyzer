import os
import re
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import backend.db as db

logger = logging.getLogger("amazon.diagnostics")

DEBUG_DIR = BASE_DIR / "data" / "debug"
HTML_DIR = DEBUG_DIR / "html"
SCREENSHOTS_DIR = DEBUG_DIR / "screenshots"

HTML_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def sanitize_filename(text: str) -> str:
    """Sanitize query string or ASIN for safe file naming."""
    clean = re.sub(r"[^\w\-_]", "_", text)
    return clean[:40].strip("_")


def capture_failure_snapshot(
    niche: str,
    query_or_asin: str,
    status: str,
    reason: str,
    html: Optional[str] = None,
    page_handle = None,
    run_id: str = ""
) -> Dict[str, Any]:
    """
    amkarpe mechanism:
    Captures debug HTML dump and/or browser screenshot on failure/captcha/zero cards,
    and logs the incident in diagnostics_log table.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = sanitize_filename(query_or_asin)
    html_rel_path = ""
    screenshot_rel_path = ""

    # 1. Dump HTML
    if html and len(html.strip()) > 0:
        html_filename = f"{timestamp}_{slug}_{status}.html"
        html_file = HTML_DIR / html_filename
        try:
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(html)
            html_rel_path = f"data/debug/html/{html_filename}"
            logger.info(f"[Diagnostics] Saved HTML debug snapshot to {html_rel_path}")
        except Exception as e:
            logger.error(f"[Diagnostics] Failed saving HTML debug dump: {e}")

    # 2. Dump Screenshot if Playwright page is present
    if page_handle:
        screenshot_filename = f"{timestamp}_{slug}_{status}.png"
        screenshot_file = SCREENSHOTS_DIR / screenshot_filename
        try:
            page_handle.screenshot(path=str(screenshot_file), full_page=False)
            screenshot_rel_path = f"data/debug/screenshots/{screenshot_filename}"
            logger.info(f"[Diagnostics] Saved screenshot debug dump to {screenshot_rel_path}")
        except Exception as e:
            logger.error(f"[Diagnostics] Failed capturing screenshot debug dump: {e}")

    # 3. Log event into SQLite
    diag_id = db.record_diagnostic_log(
        run_id=run_id,
        niche=niche,
        query_or_asin=query_or_asin,
        status=status,
        reason=reason,
        html_path=html_rel_path,
        screenshot_path=screenshot_rel_path
    )

    return {
        "id": diag_id,
        "niche": niche,
        "query_or_asin": query_or_asin,
        "status": status,
        "reason": reason,
        "html_path": html_rel_path,
        "screenshot_path": screenshot_rel_path,
        "timestamp": timestamp
    }
