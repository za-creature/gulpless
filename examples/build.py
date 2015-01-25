# coding=utf-8
"""Before running gulpless, make sure you run:

`npm install -g autoprefixer uglify-js less typescript imagemin`

"""
from __future__ import absolute_import, unicode_literals, division

import subprocess
import gulpless
import logging
import shutil
import re
import os


UGLIFY = "uglifyjs"
TSC = "tsc"
LESSC = "lessc"
AUTOPREFIXER = "autoprefixer"
IMAGEMIN = "imagemin"


if os.name != "posix":
    UGLIFY += ".cmd"
    TSC += ".cmd"
    LESSC += ".cmd"
    AUTOPREFIXER += ".cmd"
    IMAGEMIN += ".cmd"


class JavascriptHandler(gulpless.TreeHandler):
    include = re.compile("///.*?<reference\s+path=[\"\'](.*)[\"\']\s*/>", re.I)

    def __init__(self, patterns, ignore_patterns=None):
        super(JavascriptHandler, self).__init__(patterns, ignore_patterns,
                                                ["", ".gz", ".map", ".map.gz"])

    def build(self, input_path, output_paths):
        js, js_gz, smap, smap_gz = output_paths

        # concatenate and minify
        imports = set()
        cmdline = [UGLIFY]
        current = os.path.dirname(input_path)

        for line in open(input_path):
            match = self.include.search(line)
            if match:
                path = os.path.normcase(os.path.normpath(
                    os.path.join(current, match.group(1))))
                if path in imports:
                    logging.warning("Skipping duplicate import for '{0}' in "
                                    "'{1}'".format(path, input_path))
                else:
                    imports.add(path)
                    cmdline.append(path.replace(os.sep, "/"))
        if len(cmdline) == 1:
            raise EnvironmentError("Nothing to build")

        cmdline += ["--source-map", smap,
                    "--source-map-url", os.path.basename(smap),
                    "--source-map-include-sources",
                    "--prefix", str(input_path.count(os.sep)),
                    "--compress", "warnings=false,drop_debugger=false",
                    "--mangle"]
        try:
            if subprocess.call(cmdline, stdout=open(js, "wb")) != 0:
                raise EnvironmentError("Non-zero exit code in "
                                       "{0}".format(UGLIFY))
        except EnvironmentError:
            raise EnvironmentError("Unable to start {0}. Did you run `npm "
                                   "install -g uglify-js` ?".format(UGLIFY))

        # gzip
        gulpless.gzip(js, js_gz, 6)
        gulpless.gzip(smap, smap_gz, 6)


class TypescriptHandler(gulpless.TreeHandler):
    def __init__(self, patterns, ignore_patterns=None):
        super(TypescriptHandler, self).__init__(patterns, ignore_patterns,
                                                ["", ".gz", ".map", ".map.gz"])

    def _outputs(self, src, path):
        return super(TypescriptHandler, self)._outputs(src, path[:-2] + "js")

    def build(self, input_path, output_paths):
        js, js_gz, smap, smap_gz = output_paths

        # compile
        cmdline = [TSC, input_path,
                   "--out", js,
                   "--sourcemap",
                   "--sourceRoot", "."]
        try:
            if subprocess.call(cmdline) != 0:
                raise EnvironmentError("Non-zero exit code in {0}".format(TSC))
        except EnvironmentError:
            raise EnvironmentError("Unable to start {0}. Did you run "
                                   "`npm install -g typescript` ?".format(TSC))

        # uglify
        cmdline = [UGLIFY, js,
                   "--in-source-map", smap,
                   "--source-map", smap,
                   "--source-map-url", os.path.basename(smap),
                   "--source-map-include-sources",
                   "--prefix", "relative",
                   "--compress", "warnings=false,drop_debugger=false",
                   "--mangle",
                   "--output", js]
        try:
            if subprocess.call(cmdline) != 0:
                raise EnvironmentError("Non-zero exit code in "
                                       "{0}".format(UGLIFY))
        except EnvironmentError:
            raise EnvironmentError("Unable to run {0}. Did you run `npm "
                                   "install -g uglify-js` ?".format(UGLIFY))

        # gzip
        gulpless.gzip(js, js_gz, 6)
        gulpless.gzip(smap, smap_gz, 6)


class LessHandler(gulpless.TreeHandler):
    def __init__(self, patterns, ignore_patterns=None):
        super(LessHandler, self).__init__(patterns, ignore_patterns,
                                          ["", ".gz", ".map", ".map.gz"])

    def _outputs(self, src, path):
        return super(LessHandler, self)._outputs(src, path[:-4] + "css")

    def build(self, input_path, output_paths):
        css, css_gz, smap, smap_gz = output_paths

        # compile
        cmdline = [LESSC,
                   "--source-map={0}".format(smap),
                   "--source-map-url={0}".format(os.path.basename(smap)),
                   "--source-map-less-inline",
                   "--compress",
                   input_path,
                   css]
        try:
            if subprocess.call(cmdline) != 0:
                raise EnvironmentError("Non-zero exit code in "
                                       "{0}".format(LESSC))
        except EnvironmentError:
            raise EnvironmentError("Unable to start {0}. Did you run `npm "
                                   "install -g less` ?".format(LESSC))

        # autoprefix
        cmdline = [AUTOPREFIXER,
                   css,
                   "--map",
                   "--no-cascade",
                   "--output", css]
        try:
            if subprocess.call(cmdline) != 0:
                raise EnvironmentError("Non-zero exit code in "
                                       "{0}".format(AUTOPREFIXER))
        except EnvironmentError:
            raise EnvironmentError("Unable to start {0}. Did you run `npm "
                                   "install -g autoprefixer` "
                                   "?".format(AUTOPREFIXER))

        # gzip
        gulpless.gzip(css, css_gz, 6)
        gulpless.gzip(smap, smap_gz, 6)


class StaticHandler(gulpless.Handler):
    def __init__(self, patterns, ignore_patterns=None):
        super(StaticHandler, self).__init__(patterns, ignore_patterns,
                                            ["", ".gz"])

    def build(self, input_path, output_paths):
        output_path, gzip_path = output_paths
        shutil.copy(input_path, output_path)
        gulpless.gzip(input_path, gzip_path)


class ImageHandler(gulpless.Handler):
    def __init__(self, patterns, ignore_patterns=None):
        super(ImageHandler, self).__init__(patterns, ignore_patterns)

    def build(self, input_path, output_paths):
        output_path, = output_paths

        # minify
        cmdline = [IMAGEMIN, input_path,
                   "--interlaced",
                   "--optimizationLevel", "3",
                   "--progressive"]
        try:
            if subprocess.call(cmdline, stdout=open(output_path, "wb")) != 0:
                raise EnvironmentError("Non-zero exit code in "
                                       "{0}".format(IMAGEMIN))
        except EnvironmentError:
            raise EnvironmentError("Unable to start {0}. Did you run `npm "
                                   "install -g imagemin` ?".FORMAT(IMAGEMIN))

# project configuration
SRC = "resources/"
DEST = "static/"
HANDLERS = [
    JavascriptHandler(["js/*.js"]),
    TypescriptHandler(["js/*.ts"], ["js/*.d.ts"]),
    LessHandler(["css/*.less"], ["*bootstrap/*.less"]),
    StaticHandler(["fonts/*", "crossdomain.xml", "respond-*"]),
    ImageHandler(["img/*"])
]
