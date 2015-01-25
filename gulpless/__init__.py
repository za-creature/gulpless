# coding=utf-8
from __future__ import absolute_import, unicode_literals, division
from gulpless.handlers import Handler, TreeHandler
from gulpless.reactor import Reactor
from gulpless.helpers import gzip


__all__ = ["Handler", "TreeHandler", "Reactor", "gzip"]


def main():
    """Entry point for command line usage."""
    import colorama
    import argparse
    import logging
    import sys
    import os

    parser = argparse.ArgumentParser(prog="gulpless",
                                     description="Simple build system.")
    parser.add_argument("-v", "--version",
                        action="version",
                        version="%(prog)s 0.7")
    parser.add_argument("-d", "--directory",
                        action="store",
                        default=os.getcwd(),
                        help="Look for `build.py` in this folder (defaults to "
                             "the current directory)")
    parser.add_argument("mode",
                        action="store",
                        choices=["build", "interactive"],
                        default="interactive",
                        metavar="mode",
                        nargs="?",
                        help="If `interactive` (the default), will wait for "
                             "filesystem events and attempt to keep the input "
                             "and output folders in sync. If `build`, it will "
                             "attempt to build all updated files, then exit.")

    args = parser.parse_args()
    os.chdir(args.directory)
    sys.path.append(os.getcwd())

    if os.environ.get("TERM") == "cygwin":
        # colorama doesn't play well with git bash
        del os.environ["TERM"]
        colorama.init()
        os.environ["TERM"] = "cygwin"
    else:
        colorama.init()

    try:
        old, sys.dont_write_bytecode = sys.dont_write_bytecode, True
        import build
    except ImportError:
        sys.exit("No `build.py` found in current folder.")
    finally:
        sys.dont_write_bytecode = old

    try:
        logging.basicConfig(level=build.LOGGING,
                            format="%(message)s")
    except AttributeError:
        logging.basicConfig(level=logging.INFO,
                            format="%(message)s")

    reactor = Reactor(build.SRC, build.DEST)
    for handler in build.HANDLERS:
        reactor.add_handler(handler)
    reactor.run(args.mode == "build")
