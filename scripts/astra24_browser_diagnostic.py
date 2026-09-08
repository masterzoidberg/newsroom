"""AST-24 browser qualification wrapper with rendered-text diagnostics.

Selenium exposes CSS-transformed visible text, so qualification text matching is
case-insensitive. On failure, the wrapper preserves the rendered body and a
screenshot for diagnosis. The underlying isolated fixture and safety boundaries
remain unchanged.
"""
from __future__ import annotations

import sys
from pathlib import Path

from selenium.webdriver.common.by import By
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


def _diagnostic_wait_text(driver, text: str, timeout: float = 12.0) -> None:
    expected = text.casefold()
    try:
        WebDriverWait(driver, timeout).until(
            lambda current: expected in current.find_element(By.TAG_NAME, "body").text.casefold()
        )
    except Exception:
        try:
            output_index = sys.argv.index("--output") + 1
            output = Path(sys.argv[output_index]).resolve()
            output.mkdir(parents=True, exist_ok=True)
            (output / "diagnostic-body.txt").write_text(_original_body_text(driver) + "\n", encoding="utf-8")
            smoke._screenshot(driver, output, "diagnostic-browser-state.png")
        except Exception:
            pass
        raise


smoke._body_text = _case_insensitive_body_text
smoke._wait_text = _diagnostic_wait_text

if __name__ == "__main__":
    raise SystemExit(smoke.main())
