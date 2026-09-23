import json
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Dict, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
PROFILE_DIR = BASE_DIR / "data" / "browser_profile"
CDP_PROFILE_DIR = PROFILE_DIR / "cdp_research_profile"
COOKIES_DB = PROFILE_DIR / "Default" / "Cookies"


def get_session_status() -> Dict:
    """
    Check if the Playwright browser profile contains saved Amazon session cookies.
    Inspects the SQLite cookies database inside data/browser_profile/Default/Cookies.
    """
    if not PROFILE_DIR.exists():
        return {
            "is_logged_in": False,
            "status": "no_profile",
            "message": "Chưa khởi tạo profile trình duyệt (Chế độ khách)",
            "cookie_count": 0,
            "zip_code": "10001",
            "user_id": None
        }

    if not COOKIES_DB.exists():
        return {
            "is_logged_in": False,
            "status": "guest",
            "message": "Phiên khách Amazon (Chưa đăng nhập tài khoản)",
            "cookie_count": 0,
            "zip_code": "10001",
            "user_id": None
        }

    try:
        uri = f"file:{COOKIES_DB.resolve()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=3.0)
        c = conn.cursor()
        c.execute("""
            SELECT name, host_key 
            FROM cookies 
            WHERE host_key LIKE '%amazon.com%'
        """)
        rows = c.fetchall()
        conn.close()

        cookie_names = {r[0] for r in rows}
        # Amazon session identifiers
        auth_cookie_names = {"session-id", "session-token", "at-main", "ubid-main", "x-main"}
        has_auth = "at-main" in cookie_names or "session-token" in cookie_names

        return {
            "is_logged_in": has_auth,
            "status": "logged_in" if has_auth else "guest_active",
            "message": "Đã đăng nhập tài khoản Amazon US" if has_auth else "Phiên khách US hoạt động (Đã lưu cookies)",
            "cookie_count": len(rows),
            "zip_code": "10001",
            "auth_keys": list(cookie_names & auth_cookie_names)
        }
    except Exception as e:
        return {
            "is_logged_in": False,
            "status": "active_locked",
            "message": f"Profile đang được truy cập ({str(e)})",
            "cookie_count": 0,
            "zip_code": "10001",
            "auth_keys": []
        }


def ensure_amazon_zip_code(page, target_zip: str = "10001") -> bool:
    """
    Ensure the Amazon session delivers to US Zip Code 10001 (New York).
    Checks the delivery location slot in navbar; if not 10001, opens the zip modal and updates it.
    """
    try:
        # Check current location text
        location_text = page.evaluate("""() => {
            const locSlot = document.querySelector('#nav-global-location-slot, #glow-ingress-block, #glow-ingress-line2');
            return locSlot ? locSlot.innerText : '';
        }""")

        if target_zip in location_text or "New York" in location_text:
            print(f"[SessionManager] Amazon location is already set to {target_zip} (New York).")
            return True

        print(f"[SessionManager] Current location '{location_text.strip()}'. Setting Zip Code to {target_zip}...")

        # Click the location changer in the header
        location_btn = page.query_selector("#nav-global-location-slot") or page.query_selector("#glow-ingress-block")
        if location_btn:
            location_btn.click()
            page.wait_for_timeout(1500)

            # Wait for zip input
            zip_input = page.wait_for_selector("#GLUXZipUpdateInput", timeout=5000)
            if zip_input:
                zip_input.fill("")
                zip_input.fill(target_zip)
                page.wait_for_timeout(500)

                # Click apply
                apply_btn = page.query_selector("#GLUXZipUpdate input, #GLUXZipUpdate-announce, input[aria-labelledby*='GLUXZipUpdate']")
                if apply_btn:
                    apply_btn.click()
                    page.wait_for_timeout(2000)

                # Look for Done button or close
                done_btn = page.query_selector("button[name='glowDoneButton'], input[name='glowDoneButton'], .a-popover-footer button")
                if done_btn:
                    done_btn.click()
                    page.wait_for_timeout(2500)
                else:
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(1000)

                print(f"[SessionManager] Successfully updated delivery zip to {target_zip}!")
                return True
    except Exception as e:
        print(f"[SessionManager Notice] ensure_amazon_zip_code: {e}")

    return False


def launch_gui_browser_for_login(target_url: str = "https://www.amazon.com") -> Dict:
    """
    Launch interactive Chromium browser with persistent profile on macOS screen.
    User can log into Amazon, solve captcha, or verify Zip Code 10001.
    """
    script_path = BASE_DIR / "scripts" / "interactive_login.py"
    script_path.parent.mkdir(parents=True, exist_ok=True)

    with open(script_path, "w", encoding="utf-8") as f:
        f.write(f'''# Auto-generated interactive login helper for Amazon US
import time
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

profile = Path(r"{PROFILE_DIR.resolve()}")
target = "{target_url}"

print("[Amazon Browser] Launching interactive browser for profile:", profile)
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(profile),
        headless=False,
        viewport={{"width": 1400, "height": 900}},
        args=["--disable-blink-features=AutomationControlled"],
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    try:
        page.goto(target, timeout=45000)
        page.wait_for_load_state("domcontentloaded")
    except Exception as e:
        print("[Amazon Browser] Nav notice:", e)

    print("[Amazon Browser] Trình duyệt đang mở! Bạn có thể:")
    print(" - Đăng nhập tài khoản Amazon")
    print(" - Kiểm tra/chỉnh địa chỉ Deliver to: New York 10001")
    print(" - Giải Captcha nếu xuất hiện")
    print("Khi hoàn tất, hãy đóng cửa sổ trình duyệt.")

    while len(ctx.pages) > 0:
        try:
            time.sleep(1)
        except (KeyboardInterrupt, Exception):
            break

    try:
        ctx.close()
    except Exception:
        pass
    print("[Amazon Browser] Trình duyệt đã đóng. Toàn bộ phiên và cookies đã được lưu.")
''')

    venv_python = BASE_DIR / ".venv" / "bin" / "python3"
    python_cmd = str(venv_python) if venv_python.exists() else sys.executable

    subprocess.Popen([python_cmd, str(script_path)])
    return {
        "status": "opened",
        "message": "Đã mở cửa sổ trình duyệt Amazon trên màn hình! Bạn hãy kiểm tra địa chỉ New York 10001 hoặc đăng nhập tài khoản rồi đóng cửa sổ lại."
    }


def clear_session() -> Dict:
    """
    Clear all saved cookies and session storage from data/browser_profile.
    """
    if not PROFILE_DIR.exists():
        return {"status": "success", "message": "Profile chưa tồn tại."}

    deleted_items = []
    default_dir = PROFILE_DIR / "Default"
    if default_dir.exists():
        for f in default_dir.glob("*Cookie*"):
            try:
                if f.is_file():
                    f.unlink()
                    deleted_items.append(f.name)
            except Exception as e:
                print(f"Error removing {f}: {e}")

        session_storage = default_dir / "Session Storage"
        if session_storage.exists():
            try:
                shutil.rmtree(session_storage)
                deleted_items.append("Session Storage")
            except Exception:
                pass

def is_cdp_available(port: int = 9222, timeout: float = 0.5) -> bool:
    """
    Checks if a local Chrome process is actively exposing Chrome DevTools Protocol on port.
    Pings http://127.0.0.1:{port}/json/version.
    """
    import urllib.request
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/json/version")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def get_cdp_launch_command(port: int = 9222) -> str:
    """
    Returns the exact terminal launch command for macOS/Windows/Linux
    using a dedicated research profile to satisfy Chrome 136+ security requirements.
    """
    CDP_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    p_str = str(CDP_PROFILE_DIR.resolve())

    if sys.platform == "darwin":
        return f'/Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port={port} --user-data-dir="{p_str}" --no-first-run &'
    elif sys.platform == "win32":
        return f'start chrome.exe --remote-debugging-port={port} --user-data-dir="{p_str}" --no-first-run'
    else:
        return f'google-chrome --remote-debugging-port={port} --user-data-dir="{p_str}" --no-first-run &'


if __name__ == "__main__":
    print("Testing Amazon session manager...")
    st = get_session_status()
    print("Status:", json.dumps(st, indent=2, ensure_ascii=False))
