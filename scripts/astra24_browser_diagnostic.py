"""AST-24 browser qualification adapter for headless Chrome.

Selenium exposes CSS-transformed visible text, so visible-text assertions are
case-insensitive. GitHub's headless Chrome does not apply desktop Ctrl+= zoom,
so the adapter uses Chrome DevTools device metrics to exercise the same 200%
effective CSS viewport: the CSS viewport is halved and device pixel ratio is
doubled. This changes the browser rendering environment rather than faking DOM
measurements. The isolated fixture and all AST-24 safety boundaries remain
unchanged.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from selenium.webdriver import ActionChains as SeleniumActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

import astra24_browser_smoke as smoke


_original_body_text = smoke._body_text


class _VisibleText(str):
    def __contains__(self, item: object) -> bool:
        if not isinstance(item, str):
            return super().__contains__(item)
        return item.casefold() in self.casefold()


def _case_insensitive_body_text(driver) -> _VisibleText:
    return _VisibleText(_original_body_text(driver))


def _output_path() -> Path | None:
    try:
        return Path(sys.argv[sys.argv.index("--output") + 1]).resolve()
    except (ValueError, IndexError):
        return None


def _diagnostic_wait_text(driver, text: str, timeout: float = 12.0) -> None:
    expected = text.casefold()
    try:
        WebDriverWait(driver, timeout).until(
            lambda current: expected in current.find_element(By.TAG_NAME, "body").text.casefold()
        )
    except Exception:
        output = _output_path()
        if output is not None:
            try:
                output.mkdir(parents=True, exist_ok=True)
                (output / "diagnostic-body.txt").write_text(
                    _original_body_text(driver) + "\n", encoding="utf-8"
                )
                smoke._screenshot(driver, output, "diagnostic-browser-state.png")
            except Exception:
                pass
        raise


class _QualificationActionChains:
    """Delegate ordinary input, but make the smoke's zoom steps deterministic.

    The primary smoke uses five Ctrl+= steps and then verifies that the CSS
    viewport shrank. Headless Chrome ignores those desktop shortcuts. For only
    that exact gesture, this adapter progressively applies real Chromium device
    metrics from 100% to an effective 200% scale. Keyboard traversal remains
    ordinary Selenium ActionChains behavior.
    """

    _zoom_state: dict[str, dict[str, float]] = {}

    def __init__(self, driver) -> None:
        self.driver = driver
        self._delegate = SeleniumActionChains(driver)
        self._control_down = False
        self._zoom_gesture = False

    def key_down(self, value):
        self._control_down = value == Keys.CONTROL
        self._delegate.key_down(value)
        return self

    def send_keys(self, *keys_to_send):
        if self._control_down and "=" in keys_to_send:
            self._zoom_gesture = True
            return self
        self._delegate.send_keys(*keys_to_send)
        return self

    def key_up(self, value):
        self._delegate.key_up(value)
        if value == Keys.CONTROL:
            self._control_down = False
        return self

    def perform(self):
        if not self._zoom_gesture:
            self._delegate.perform()
            return None

        # Perform only the queued modifier press/release. The ignored '=' key
        # is replaced by an actual Chromium rendering-environment change below.
        self._delegate.perform()
        session = str(self.driver.session_id)
        state = self._zoom_state.get(session)
        if state is None:
            metrics = self.driver.execute_script(
                "return {width: window.innerWidth, height: window.innerHeight};"
            )
            state = {
                "base_width": float(metrics["width"]),
                "base_height": float(metrics["height"]),
                "step": 0.0,
            }
            self._zoom_state[session] = state

        state["step"] += 1.0
        # Five qualification steps reach exactly 2.0x. Intermediate steps keep
        # layout changes gradual, matching the intent of repeated browser zoom.
        scale = 1.0 + (state["step"] / 5.0)
        width = max(1, round(state["base_width"] / scale))
        height = max(1, round(state["base_height"] / scale))
        self.driver.execute_cdp_cmd(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": width,
                "height": height,
                "deviceScaleFactor": scale,
                "mobile": False,
            },
        )
        return None


smoke._body_text = _case_insensitive_body_text
smoke._wait_text = _diagnostic_wait_text
smoke.ActionChains = _QualificationActionChains


if __name__ == "__main__":
    result = smoke.main()
    output = _output_path()
    if result == 0 and output is not None:
        manifest_path = output / "manifest.json"
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["browser_zoom_method"] = (
                "Chrome DevTools Emulation.setDeviceMetricsOverride; five "
                "qualification steps from 1.0x to effective 2.0x, halving the "
                "CSS viewport and doubling device pixel ratio"
            )
            manifest["browser_zoom_literal_keyboard_shortcut_supported"] = False
            manifest_path.write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
            )
    raise SystemExit(result)
