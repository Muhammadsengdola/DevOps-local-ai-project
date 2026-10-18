import os
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Literal

from mcp.server.fastmcp import FastMCP

import crew_pdf_4agents


WORKSPACE_ROOT = Path(os.environ["WORKSPACE_ROOT"]).resolve(strict=True)
if not WORKSPACE_ROOT.is_dir():
    raise NotADirectoryError(f"WORKSPACE_ROOT is not a directory: {WORKSPACE_ROOT}")

mcp = FastMCP("CrewAI Local")


@mcp.tool()
def explain_file(
    path: str,
    language: Literal["Thai", "English"] = "Thai",
    detail: Literal["short", "detailed"] = "short",
) -> str:
    """Explain a text, source-code, or PDF file in the configured workspace."""
    relative_path = Path(path)
    if not path.strip() or relative_path.is_absolute() or relative_path.drive or relative_path.root:
        raise ValueError("path must be a non-empty path relative to the workspace")

    file_path = (WORKSPACE_ROOT / relative_path).resolve(strict=True)
    try:
        file_path.relative_to(WORKSPACE_ROOT)
    except ValueError as exc:
        raise ValueError("path must stay inside the configured workspace") from exc
    if not file_path.is_file():
        raise ValueError(f"File not found: {path}")

    with redirect_stdout(sys.stderr):
        return crew_pdf_4agents.explain_file(str(file_path), language, detail)


if __name__ == "__main__":
    mcp.run(transport="stdio")
