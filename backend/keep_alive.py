"""Keep-alive service to prevent Render free-tier sleeping."""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime

import requests


class KeepAliveService:
    def __init__(self, app_url: str | None = None, interval: int = 840) -> None:
        self.app_url = app_url or os.environ.get("RENDER_EXTERNAL_URL")
        self.interval = interval
        self.running = False
        self.thread: threading.Thread | None = None

    def ping(self) -> bool:
        if not self.app_url:
            print("Keep-alive: No URL configured, skipping ping")
            return False

        try:
            url = f"{self.app_url.rstrip('/')}/api/health"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                print(
                    "Keep-alive ping successful at "
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                return True
            print(f"Keep-alive ping returned status {response.status_code}")
            return False
        except requests.exceptions.RequestException as exc:
            print(f"Keep-alive ping failed: {exc}")
            return False

    def _run(self) -> None:
        print(
            "Keep-alive service started. "
            f"Pinging {self.app_url} every {self.interval / 60} minutes"
        )
        time.sleep(60)
        while self.running:
            self.ping()
            time.sleep(self.interval)

    def start(self) -> None:
        if self.running:
            print("Keep-alive service already running")
            return
        if not self.app_url:
            print("Keep-alive service not started: No URL configured")
            print("Set RENDER_EXTERNAL_URL environment variable to enable keep-alive")
            return

        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        print("Keep-alive service thread started")

    def stop(self) -> None:
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("Keep-alive service stopped")


_keep_alive_service: KeepAliveService | None = None


def init_keep_alive(app_url: str | None = None, interval: int = 840) -> KeepAliveService | None:
    global _keep_alive_service

    if not os.environ.get("RENDER"):
        print("Not running on Render, keep-alive service disabled")
        return None

    if _keep_alive_service is None:
        _keep_alive_service = KeepAliveService(app_url=app_url, interval=interval)
        _keep_alive_service.start()

    return _keep_alive_service


def get_keep_alive_service() -> KeepAliveService | None:
    return _keep_alive_service
