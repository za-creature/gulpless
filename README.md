Like `gulp`, but ~~less~~ more derpy.

First and foremost, I'd like to emphasize that gulpless was born as a strongly opinionated internal project that was hacked together in a couple of days and I never intended to release it to the public. The only reason it's on PyPI is because this way, it's easier for me to deploy it within my own company. It's also on Github now because people were signing up for access to my private repo :)

Here be dragons. You have been warned!

If that's not enough to ward you off, you should probably know that the average `build.py` module will always contain an order of magnitude more code than configuration directives, which may or may not be what you're looking for. Usually, it's not.

For a usage example, check out the sample [build.py](examples/build.py):

* compiles typescript and less files
* stitches together javascripts
* minifies scripts via uglify
* does a best effort to minify images
* applies autoprefixer on top of the compiled less files
* generates source maps whenever possible
* gzips everything

The file assumes that all less, css and js files need to be annotated with a
```
/// <base path="path_to_parent_file"/>
```
line for every file that includes them, so that gulpless can figure out what to compile whenever an included file is changed.

So, uhm, good luck I guess!

P.S. When running interactively, the entire source / destination tree is scanned every time a FS event is emitted (well, it's throttled not to occur more than 10 times a second, but still). This is because FS events are pretty unreliable (especially cross-platform) and I'd rather have a slower build system than one that skips files every once in a while.
