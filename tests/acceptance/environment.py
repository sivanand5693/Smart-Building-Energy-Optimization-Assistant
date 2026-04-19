import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

from tests.acceptance.support.database_reset import reset_test_database

BACKEND_PORT = 8000
FRONTEND_URL = "http://localhost:5173"
BACKEND_URL = f"http://localhost:{BACKEND_PORT}"
ROOT = Path(__file__).resolve().parents[2]


def _start_backend() -> subprocess.Popen:
    env = os.environ.copy()
    env["TESTING"] = "1"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(BACKEND_PORT),
        ],
        cwd=str(ROOT / "backend"),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            if httpx.get(f"{BACKEND_URL}/health", timeout=1.0).status_code == 200:
                return proc
        except httpx.HTTPError:
            pass
        time.sleep(0.3)
    proc.terminate()
    raise RuntimeError("Backend failed to start on port 8000")


def before_all(context):
    context.backend_proc = _start_backend()
    context.playwright = sync_playwright().start()
    context.browser = context.playwright.chromium.launch(headless=True)


def before_scenario(context, scenario):
    reset_test_database()
    context.page = context.browser.new_page()
    context.frontend_url = FRONTEND_URL
    context.backend_url = BACKEND_URL
    context.last_response = None
    context.submit_start_ms = None
    context.submit_end_ms = None


def after_scenario(context, scenario):
    if hasattr(context, "page"):
        context.page.close()


def after_all(context):
    if hasattr(context, "browser"):
        context.browser.close()
    if hasattr(context, "playwright"):
        context.playwright.stop()
    if hasattr(context, "backend_proc"):
        context.backend_proc.terminate()
        try:
            context.backend_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            context.backend_proc.kill()
