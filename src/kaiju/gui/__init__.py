from __future__ import annotations

from pathlib import Path


def run(start: Path) -> None:
    """Open the Tk viewer. Imports tkinter only when called."""
    from kaiju.errors import KaijuError

    try:
        from kaiju.gui.app import run_app
    except ImportError as exc:
        raise KaijuError(f"tkinter is not available ({exc})") from exc
    run_app(start)
