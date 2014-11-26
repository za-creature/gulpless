# coding=utf-8
from __future__ import absolute_import, unicode_literals, division

import gzip as _gzip


__all__ = ["gzip"]


def gzip(original, compressed, *gzip_args, **gzip_kwargs):
    orig = comp = None
    try:
        orig = open(original, "rb")
        comp = _gzip.open(compressed, "wb", *gzip_args, **gzip_kwargs)
        comp.writelines(orig)
    finally:
        if comp:
            comp.close()
        if orig:
            orig.close()
