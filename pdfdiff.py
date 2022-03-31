#!/usr/bin/env python3
# This Python file uses the following encoding: latin-1
"""
pdfdiff.py : inspect the difference between two PDF files.

Copyright (C) 2007-2022 Cas Cremers

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 
02110-1301, USA.
"""

"""
Module dependencies
"""
import sys
import string
import subprocess
import os.path
import tempfile

"""
Global declarations
"""
# Preference order of diff viewers (top most is most preferred)
# Note that e.g.:
# 
# kdiff3 works well with unicode things and can nicely do things like
# '\phi'. 
#
# Meld shows unicode well but I couldn't get it to wrap as I wanted from
# the command line (you can use preferences though).
#
diffViewers = [ \
        "kdiff3 --cs WordWrap=1 --cs ShowWhiteSpaceCharacters=0", \
        "meld", \
        "tkdiff", \
        "xxdiff", \
        "gvimdiff", \
        "vimdiff", \
        "diff", \
        "opendiff", \
        ]

# pdftotext program with switches
pdftotextProgram = "pdftotext"
pdftotextOptions = "-nopgbrk -enc UTF-8"

# Myname
progName = "pdfdiff.py"
progVersion = "0.93"

# Define what a long sentence is.
# When a sentence is longer than this, any punctuations count as sentence
# ends.
longSentenceLength = 50


"""
Code overview.

The procedure is fairly trivial. We exploit pdftotext, which converts
pdf files to text. However, this does not work very well because in
general, semantical sentences are distributed randomly over file lines.
We use a very crude form of normalization that attempts to output (file)
lines that somewhat correspond to sentences. In practice, this turns out
to be sufficient for diff programs to work.

With respect to the diff programs, pdftotext handles formulas amazingly
well, and turns most symbols into useful unicode. Thus, it is worthwile
to have a diff viewer (kdiff3, meld) that can display unicode
characters. Also, make sure to turn on word wrap for full effect.

I'm sure it can be done better/faster/cleaner/..., as this is just a
hack, so feel free to improve it. Please send me an e-mail with the
result if you do. I also bet there is somebody that can do it in one
line using sed.

The code is split into five sections:

1. Basics
2. Text normalization
3. Conversions from format A to B
4. High-level commands
5. Main code

"""


#-------------------------------------------------------------------------
# 1. Basics
#-------------------------------------------------------------------------

def get_viewer_list():
    """
    Return the list of viewers
    """
    global diffViewers

    return map(lambda s:(s.split())[0], diffViewers)


def is_command_available(prg):
    """
    Detect whether prg exists. Note that it may have switches, i.e. 
    it will find "kdiff3 -a"
    """
    cmd = "which %s" % ((prg.split())[0])
    status, out = subprocess.getstatusoutput(cmd)
    return (status == 0)


def find_first(plist):
    """
    Find the first program from the list that exists.
    """
    for prg in plist:
        if is_command_available(prg):
            return prg
    return None


def apply_command_temp(prg,options,notfound,filename,prefix="",suffix=""):
    """
    Execute 'prg options filename tempout' if prg exists.
    Report 'notfound' if prg is not there.

    Returns (tempfileFilehandle,output) tuple.
    """
    fout = tempfile.NamedTemporaryFile(mode='w+', suffix=suffix, prefix=prefix)

    if not is_command_available(prg):
        print("Error: %s" % notfound)
        sys.exit(1)

    cmd = "%s %s \"%s\" \"%s\"" % (prg,options,filename,fout.name)
    output = subprocess.getoutput(cmd)
    return (fout,output)


def make_prefix(fname):
    """
    Turn file name into a prefix we can use.
    """
    (head,tail) = os.path.split(fname)
    (root,ext) = os.path.splitext(tail)
    return root + "_"


def get_filetype(filename):
    """
    Determine the filetype.
    """
    if is_command_available("file"):
        # On systems where we have 'file', this is a nice
        # and solid solution.
        cmd = "file --brief \"%s\"" % filename
        output = subprocess.getoutput(cmd)
        type = (output.split())[0].lower()
    else:
        # If we don't have 'file', we just take an educated
        # guess based on the filename extension.
        (head,tail) = os.path.split(filename)
        (root,ext) = os.path.splitext(tail)
        type = ext.lower()
        if type.startswith("."):
            type = type[1:]

    # Case distinctions for possible results.
    #
    # Be aware we might be matching either the output from 'file' or the
    # extension!
    if type in ['pdf','fdf']:
        return "pdf"
    elif type in ['postscript','ps']:
        return "ps"
    else:
        # Default assumption: text
        return "txt"


def fix_ff_problem(sentence):
    """
    Hack to fix an often occurring latex problem with 'ff' combinations.
    This is ultimately a font problem (with Times New Roman), and not our
    problem (probably latex, alternatively pdftotext ought to fix it).
    For now, we just stupidly revert the weird character combos.
    """
    sentence = sentence.replace("ﬃ","ffi")
    sentence = sentence.replace("ﬄ","ffl")
    sentence = sentence.replace("ﬀ","ff")
    return sentence


#-------------------------------------------------------------------------
# 2. Text normalization
#-------------------------------------------------------------------------

def is_sentence_end(c):
    """
    The following characters are considered to be sentence endings for our
    normalization.
    """
    return c in ".!?"


def is_sentence_break(c):
    """
    The following characters are considered to be sentence breaks for our
    normalization of long sentences.
    """
    return c in string.punctuation


def is_sentence_done(sentence):
    """
    Detect whether the sentence is done
    """
    global longSentenceLength

    if len(sentence) > 0:
        if is_sentence_end(sentence[-1]):
            return True
        else:
            if len(sentence) >= longSentenceLength:
                if is_sentence_break(sentence[-1]):
                    return True
    return False


def flush_sentence(fout,forceNewLine = False):
    """
    Flush the sentence buffer.
    """
    global sentenceBuf
    global lastWordLength

    lastWordLength = 0
    l = sentenceBuf.lstrip()
    l = fix_ff_problem(l)
    fout.write(l)
    if forceNewLine or (sentenceBuf != ""):
        fout.write("\n")
    sentenceBuf = ""


def normalize_text(fin,fout):
    """
    Normalize the lines read from fin, and output to fout, which
    are file handles.
    """
    global sentenceBuf
    global lastWordLength

    sentenceBuf = ""    # stores unfinished sentences
    wordLength = 0
    lastWordLength = 0
    skipEnds = False

    # Alternatively, we could use xreadlines, if the files are really
    # really huge.
    for l in fin.readlines():
        # Cut of spacing from both ends
        ls = l.strip()
        
        # Empty line or not?
        if ls == "":
            # This occurs when there is an empty line.
            # We flush the sentence, and force a newline.
            #
            # Any further additional empty lines have no effect,
            # which is enforced by skipEnds.
            if not skipEnds:
                flush_sentence(fout)
                flush_sentence(fout,True)
                skipEnds = True
        else:
            # The file line is not empty, so this is some sort of
            # paragraph
            skipEnds = False
            if sentenceBuf != "":
                if not sentenceBuf[-1] in string.whitespace:
                    sentenceBuf += " "

            for c in ls:
                # Append the character to the current buffer.
                sentenceBuf += c

                # Some admin to know how long the last word was.
                if c in string.ascii_letters:
                    wordLength += 1
                    lastWordLength = wordLength
                else:
                    wordLength = 0

                if is_sentence_done(sentenceBuf):
                    # If the last word is only a single character,
                    # it's assumed that the punctuation does not
                    # refer to a sentence end.
                    if lastWordLength != 1:
                        # Sentence has ended, so flush it.
                        # We should skip any spacing directly after
                        # the sentence end mark.
                        flush_sentence(fout)

    flush_sentence(fout)
    fout.flush()


#-------------------------------------------------------------------------
# 3. Conversions from format A to B
#-------------------------------------------------------------------------

def ps_to_pdf(filename,prefix=""):
    """
    ps to pdf conversion
    """
    prg = "ps2pdf"
    notfound = "Could not find 'ps2pdf', which is needed for ps to pdf conversion." 
    (fout,output) = apply_command_temp(prg,"",notfound,filename,prefix,".pdf")
    return fout


def pdf_to_text(filename,prefix=""):
    """
    pdf to text conversion
    """
    global pdftotextProgram,pdftotextOptions

    notfound = """\
Could not find '%s', which is needed for pdf to text conversion.
%s is part of the 'xPdf' suite of programs, obtainable at:
  http://www.foolabs.com/xpdf/
""" % (pdftotextProgram,pdftotextProgram)
    (fout,output) = apply_command_temp(pdftotextProgram,pdftotextOptions,notfound,filename,prefix,".txt")
    return fout


def normalize_anything(filename,fout=sys.stdout):
    """
    This function takes any file type and tries to apply converters
    until we can finall churn out normalized text.
    """
    prefix = make_prefix(filename)
    filetype = get_filetype(filename)

    # Iterate until we have text
    temphandle = None
    fhandle = None
    while filetype != "txt":
        if filetype == "pdf":
            fhandle = pdf_to_text(filename,prefix=prefix)
        elif filetype == "ps":
            fhandle = ps_to_pdf(filename,prefix=prefix)
        else:
            print("Error: Don't know how to handle file type '%s'" % filetype)
            sys.exit(1)
        if temphandle:
            temphandle.close()

        filename = fhandle.name
        filetype = get_filetype(filename)
        # Store for destruction of intermediate objects later
        temphandle = fhandle

    if not fhandle:
        fhandle = open(filename,'r')

    # Now fhandle is considered text
    normalize_text(fhandle,fout)


def normalize_anything_tempfile(filename):
    """
    Normalize anything with a wrapper for tempfile generation.
    """
    prefix = make_prefix(filename)
    fout = tempfile.NamedTemporaryFile(mode="w+", suffix=".txt", prefix=prefix)
    normalize_anything(filename,fout)
    return fout


#-------------------------------------------------------------------------
# 4. High-level commands
#-------------------------------------------------------------------------

def view_diff(fnleft,fnright):
    """
    Show the diff between two files using the first program that is
    found.
    """
    global diffViewers
    global diffViewerPrefix

    fleft  = normalize_anything_tempfile(fnleft)
    fright = normalize_anything_tempfile(fnright)

    viewers = []
    if diffViewerPrefix != "":
        # Attempt to use the prefix as a program (overrides defaults)
        viewers = [diffViewerPrefix]
        # Also add filtered known ones
        viewers += filter(lambda s:s.startswith(diffViewerPrefix),diffViewers)
    # Add known ones
    viewers += diffViewers

    prg = find_first(viewers)

    if prg is None:
        estr = "Error: Could not find a suitable diff viewer from the list %s" % (diffViewers)
        print(estr)
        sys.exit(1)

    cmd = "%s \"%s\" \"%s\"" % (prg,fleft.name,fright.name)
    out = subprocess.getoutput(cmd)
    # Also print the result (e.g. for programs like diff that send
    # output to stdout)
    print(out)

    fleft.close()
    fright.close()


def display_help():
    """
    Program manual
    """
    global progName, progVersion
    global diffViewers

    helpstr = """\
PRG version %s
Copyright 2007 Cas Cremers

Usage: PRG [switches] <file1> [<file2>]

  View the difference between two files, or output a normalized version
  of the text in a single file.
  Supported file types are: pdf,ps,txt.

Switches:
  -d <prefix>, --diffviewer <prefix>|<viewername>
       Try to use the diff viewer of the given name, or try to select
       the first available diffviewer from the list:
        %s
       that starts with <prefix>.
""" % (progVersion, ", ".join(get_viewer_list()))
    print(helpstr.replace("PRG", progName))


#-------------------------------------------------------------------------
# 5. Main code
#-------------------------------------------------------------------------

if __name__ == "__main__":
    """
    Main code
    """
    global diffViewerPrefix

    args = sys.argv[1:]
    diffViewerPrefix = ""

    # No arguments, show help
    if len(args) == 0:
        display_help()
        sys.exit(0)

    # Check for special commands
    while len(args) > 0:
        optcmd = args[0]
        if optcmd in ["-?","-h","--help"]:
            # Help
            display_help()
            sys.exit(0)

        elif optcmd in ["-d","--diffviewer"]:
            # Selecting diff viewer prefix
            if len(args) < 2:
                print("Error: Diff viewer preference requires a string prefix argument")
                sys.exit(1)
            diffViewerPrefix = args[1]
            if len(list(filter(lambda s:s.startswith(diffViewerPrefix),get_viewer_list()))) == 0:
                if not is_command_available(diffViewerPrefix):
                    print("Error: program '%s' not found, and no viewer from the list %s starts with '%s'" %
                          (diffViewerPrefix, get_viewer_list(), diffViewerPrefix))
                    sys.exit(1)
            args = args[2:]

        else:
            # Default mode: 1 argument is normalize, 2 is diff
            if len(args) == 1:
                normalize_anything(args[0])
                sys.exit(0)
            elif len(args) == 2:
                view_diff(args[0],args[1])
                sys.exit(0)
            else:
                print("Error: I don't know what to do with more than two files")
                sys.exit(1)

# vim: set ts=4 sw=4 et fileencoding=utf-8 list lcs=tab\:>-:
