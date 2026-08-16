"""Entrypoint for ``python -m newsroom.evals``."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
