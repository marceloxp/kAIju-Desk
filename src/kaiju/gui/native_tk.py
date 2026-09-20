from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# uv-managed CPython ships Tk without Xft/fontconfig, so glyphs look jagged
# (https://github.com/astral-sh/uv/issues/15668). On Linux we re-exec with a
# system Python whose libtk is linked to Xft, when we can import kaiju there.


def maybe_reexec_for_native_tk() -> None:
    if os.environ.get("KAIJU_GUI_REEXEC") == "1":
        return
    if "PYTEST_CURRENT_TEST" in os.environ:
        return
    if sys.platform != "linux":
        return
    if _current_has_xft():
        return
    exe = _find_system_xft_python()
    if exe is None:
        return
    env = os.environ.copy()
    env["KAIJU_GUI_REEXEC"] = "1"
    pythonpath = _import_path()
    old = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = pythonpath if old == "" else pythonpath + os.pathsep + old
    os.execve(exe, [exe, "-m", "kaiju", *sys.argv[1:]], env)


def _current_has_xft() -> bool:
    try:
        import _tkinter  # noqa: F401
    except ImportError:
        return False
    return _maps_have_xft()


def _maps_have_xft() -> bool:
    try:
        text = Path("/proc/self/maps").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return "libXft" in text or "libfontconfig" in text


def _import_path() -> str:
    import kaiju

    roots = [str(Path(kaiju.__file__).resolve().parent.parent)]
    try:
        import tomli
    except ImportError:
        pass
    else:
        tomli_root = str(Path(tomli.__file__).resolve().parent.parent)
        if tomli_root not in roots:
            roots.append(tomli_root)
    return os.pathsep.join(roots)


def _find_system_xft_python() -> str | None:
    seen: set[str] = set()
    here = str(Path(sys.executable).resolve())
    candidates: list[str] = []
    for name in ("python3", "python3.12", "python3.11", "python3.10"):
        candidates.append(f"/usr/bin/{name}")
        found = shutil.which(name)
        if found is not None:
            candidates.append(found)
    pythonpath = _import_path()
    for raw in candidates:
        if not os.path.isfile(raw):
            continue
        path = str(Path(raw).resolve())
        if path in seen or path == here or not os.access(path, os.X_OK):
            continue
        seen.add(path)
        if _python_has_xft_and_kaiju(path, pythonpath):
            return path
    return None


def _python_has_xft_and_kaiju(exe: str, pythonpath: str) -> bool:
    env = os.environ.copy()
    old = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = pythonpath if old == "" else pythonpath + os.pathsep + old
    probe = (
        "import kaiju.workspace\n"
        "import _tkinter\n"
        "text = open('/proc/self/maps', encoding='utf-8', errors='replace').read()\n"
        "raise SystemExit(0 if ('libXft' in text or 'libfontconfig' in text) else 1)\n"
    )
    try:
        completed = subprocess.run(
            [exe, "-c", probe],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0
