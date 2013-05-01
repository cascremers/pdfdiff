pdfdiff
=======

Command-line tool to inspect the difference between (the text in) two PDF files.


Purpose and function
--------------------

`pdfdiff` takes two arguments, each being the filename of a PDF file,
and generates a textual diff between the two. It visualises this diff
using the first diff-viewer it finds on the system.

`pdfdiff` relies on `pdftotext` to extract the plaintext from a PDF
file.  However, small changes in the text between two PDF files can make
a huge difference in the resulting extracted text. More often than not,
the difference is so large that doing a `diff` on the output does not
yield a sensible result.

The main function of this program, `pdfdiff`, is to normalize the output
of `pdftotext`, such that the result is suitable for diff viewing. To
achieve this, it attempts to detect sentence endings to reformat
paragraphs and lines.  Along the way, it removes some ligature encodings
to give `diff` viewers an easier time. After this normalisation
procedure, `diff` viewers commonly yield a substantially better
comparison between the contents of the files.

Note that if a single file is provided as input, `pdfdiff` will directly
output the normalised text, enabling its use as a preprocessor for other
tools.


Running `pdfdiff.py`
--------------------

After downloading, either run it through python or make it executable
(chmod +x pdfdiff.py) to use it directly from the commandline.


Requirements
------------


- `pdftotext`, which is part of the `xpdf` package.

- `Python`

- A diff viewer, preferably one that supports unicode, like `kdiff3` or
  `meld`. If these don't work for you, you can use `xxdiff`, `tkdiff`,
  `opendiff`, `vimdiff`, or even good old `diff`.  You only need one of
  these to use `pdfdiff.py`.

Note that for most Linux distributions, installing `xpdf` is
usually sufficient to get it working. (Afterwards one might
want to upgrade to a better diff viewer though).


Caveats
-------

- `pdfdiff` ignores many elements of PDF files, such as figures. As a
  result, if the (textual) difference between two files is empty, there
  is no guarantee that the PDF files are identical.

- Some PDF files do not contain embedded text. In this case `pdftotext`
  will not work correctly, and will return empty diffs. In this case you
  would need to resort to OCR (Optical Character Recognition) to extract
  the text. This is outside the scope of this program.


Use cases
---------

- (Scientific) Reviews: you reviewed version A of a paper, and receive
  version B, and wonder what the changes are.


License
-------

Currently the `pdfdiff` sources are licensed under the GPL 2, as indicated
in the source code. Contact Cas Cremers if you have any questions.

