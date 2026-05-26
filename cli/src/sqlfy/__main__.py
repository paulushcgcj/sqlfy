"""Module entrypoint for ``python -m sqlfy`` and ``python sqlfy``."""

try:
    # Package execution path (python -m sqlfy)
    from .main import main
except ImportError:
    # Directory/script execution path (python sqlfy)
    from sqlfy.main import main


if __name__ == '__main__':
    main()
