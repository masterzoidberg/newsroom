"""Temporary AST-24 browser diagnostic wrapper.

Captures the rendered body and a screenshot when the onboarding qualification
cannot find the post-reload "Next: Add Sources" state. The underlying isolated
fixture and safety boundaries remain unchanged.
"""
from __future__ import annotations

import sys
from pathlib import Path

import astra24_browser_smoke as smoke


_original_wait_text = smoke._wait_text


def _diagnostic_wait_text(driver, text: str, timeout: float = 12.0) -> None:
    try:
        _original_wait_text(driver, text, timeout)
    except Exception:
        if text == "Next: Add Sources":
            try:
                output_index = sys.argv.index("--output") + 1
                output = Path(sys.argv[output_index]).resolve()
                output.mkdir(parents=True, exist_ok=True)
                (output / "diagnostic-body.txt").write_text(smoke._body_text(driver) + "\n", encoding="utf-8")
                smoke._screenshot(driver, output, "diagnostic-next-add-sources.png")
            except Exception:
                pass
        raise


smoke._wait_text = _diagnostic_wait_text

if __name__ == "__main__":
    raise SystemExit(smoke.main())
