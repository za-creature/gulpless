#!/usr/bin/env python

from distutils.core import setup

setup(name="Gulpless",
      version="0.3",
      description="Simple python build system",
      author="Radu Dan",
      author_email="za_creature@yahoo.com",
      url="http://git.full-throttle.ro/radu/gulpless",
      packages=["gulpless"],
      install_requires="watchdog",
      entry_points={"console_scripts": ["gulpless=gulpless:main"]})
