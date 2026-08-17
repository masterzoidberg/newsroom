from pathlib import Path
import tempfile

import uvicorn

from newsroom.app import create_app
from newsroom.config import RuntimeConfig


if __name__ == "__main__":
    config = RuntimeConfig.for_environment(
        "dev",
        root=Path(tempfile.mkdtemp(prefix="newsroom-phase12-")) / "dev",
    )
    uvicorn.run(create_app(config=config), host="127.0.0.1", port=8127)
