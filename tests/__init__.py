def _have_flake8():
    try:
        MYPY = False
        if not MYPY:
            import flake8  # noqa: F401
        return True
    except ImportError:
        return False


LINT = _have_flake8()
CHECK_SPELLING = False
