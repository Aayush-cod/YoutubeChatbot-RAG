import logging


def setup_logging(level: str = "INFO") -> None:
    """One simple log format for the whole app."""
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )