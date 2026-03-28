import logging

def setup_logging(name: str = __name__) -> logging.Logger:
    logging.basicConfig(
        level=logging.WARNING,
        format='%(levelname)s  %(name)s  %(message)s',
    )
    return logging.getLogger(name)
