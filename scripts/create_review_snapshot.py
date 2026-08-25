"""Create a review ZIP from the repository's tracked files.

The file list comes from Git rather than a recursive directory walk so local
databases, secrets, build output, and unrelated untracked work are excluded.
Git's tracked dot-directories (including ``.github``) are included verbatim.
"""
from __future__ import annotations

import argparse
import subprocess
import zipfile
from pathlib import Path


def tracked_files(repo: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    files = [repo / Path(item) for item in result.stdout.decode("utf-8").split("\0") if item]
    return [path for path in files if path.is_file()]


def create_snapshot(repo: Path, output: Path) -> tuple[int, bool]:
    files = tracked_files(repo)
    ci_path = Path(".github/workflows/ci.yml")
    if not any(path.relative_to(repo) == ci_path for path in files):
        raise RuntimeError("tracked CI workflow is absent from the review file list")
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(repo).as_posix())
    with zipfile.ZipFile(output) as archive:
        included = ci_path.as_posix() in archive.namelist()
    return len(files), included


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    count, included = create_snapshot(args.repo.resolve(), args.output)
    print(f"files={count} ci_included={included} output={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
