#!/usr/bin/env python

from distutils.core import setup

setup(name="gulpless",
      version="0.7",
      description="Simple python build system",
      author="Radu Dan",
      author_email="za_creature@yahoo.com",
      url="https://github.com/za-creature/gulpless",
      packages=["gulpless"],
      install_requires=["watchdog", "termcolor", "pathtools", "argparse"],
      entry_points={"console_scripts": ["gulpless=gulpless:main"]})
