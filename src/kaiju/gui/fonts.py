from __future__ import annotations

_UI_WANTED = (
    "DejaVu Sans",
    "Noto Sans",
    "Liberation Sans",
    "Ubuntu",
    "Cantarell",
    "FreeSans",
    "Carlito",
    "Verdana",
    "Helvetica",
    "Arial",
    "Sans",
)

_MONO_WANTED = (
    "DejaVu Sans Mono",
    "Noto Sans Mono",
    "Liberation Mono",
    "Ubuntu Mono",
    "FreeMono",
    "Consolas",
    "Menlo",
    "Monospace",
)

_MONO_HINTS = ("mono", "console", "courier", "fixed", "typewriter")


def pick_ui_family(families: set[str]) -> str:
    return _pick_family(families, _UI_WANTED, allow_mono=False)


def pick_mono_family(families: set[str]) -> str:
    return _pick_family(families, _MONO_WANTED, allow_mono=True)


def _looks_mono(name: str) -> bool:
    folded = name.casefold()
    return any(hint in folded for hint in _MONO_HINTS)


def _normalize(name: str) -> str:
    return "".join(ch for ch in name.casefold() if ch.isalnum())


def _pick_family(families: set[str], wanted: tuple[str, ...], *, allow_mono: bool) -> str:
    candidates: list[str] = []
    seen: set[str] = set()
    for fam in sorted(families, key=str.casefold):
        if allow_mono:
            if not _looks_mono(fam):
                continue
        elif _looks_mono(fam):
            continue
        key = fam.casefold()
        if key in seen:
            continue
        seen.add(key)
        candidates.append(fam)

    by_fold = {fam.casefold(): fam for fam in candidates}
    by_alnum = {_normalize(fam): fam for fam in candidates}
    for name in wanted:
        match = by_fold.get(name.casefold()) or by_alnum.get(_normalize(name))
        if match is not None:
            return match
    if not allow_mono:
        for fam in candidates:
            if "sans" in fam.casefold():
                return fam
    if candidates:
        return candidates[0]
    return wanted[0]
