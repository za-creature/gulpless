# coding=utf-8
from __future__ import absolute_import, unicode_literals, division
from gulpless.handlers import Handler, TreeHandler
from gulpless.reactor import Reactor


__all__ = ["Handler", "TreeHandler", "Reactor"]


def main():
    """Entry point for command line usage."""
    import logging
    import sys
    import os

    sys.path.append(os.getcwd())

    try:
        import build
    except ImportError:
        sys.exit("No `build.py` found in current folder.")

    try:
        logging.basicConfig(level=build.LOGGING)
    except AttributeError:
        logging.basicConfig(level=logging.DEBUG)

    reactor = Reactor(build.SRC, build.DEST)
    for handler in build.HANDLERS:
        reactor.add_handler(handler)
    reactor.run()
