from pathlib import Path


def test_installed_launcher_has_explicit_success_exit() -> None:
    source = Path("scripts/phase16_windows_deploy.ps1").read_text(encoding="utf-8")
    browser_block = "if (-not `$NoBrowser) {\n    Start-Process 'http://127.0.0.1:$ListenPort/' | Out-Null\n}\nexit 0\n\"@"
    assert browser_block in source
