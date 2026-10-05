"""Also support python -m skrov after installation."""

from skrov.cli import main


# This condition is true when Python runs this module as a program.
if __name__ == "__main__":
    raise SystemExit(main())
