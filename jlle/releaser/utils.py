import logging
import os
import re
import subprocess
import sys

logger = logging.getLogger(__name__)


WRONG_IN_VERSION = ['svn', 'dev', '(']
# For zc.buildout's system() method:
MUST_CLOSE_FDS = not sys.platform.startswith('win')

AUTO_RESPONSE = False
#VERBOSE = False


def ask_version(question, default=None):
    if AUTO_RESPONSE:
        if default is None:
            msg = ("We cannot determine a default version, but "
                   "we're running in --no-input mode. The original "
                   "question: %s")
            msg = msg % question
            raise RuntimeError(msg)
        logger.debug("Auto-responding '%s' to the question below.", default)
        logger.debug(question)
        return default
    if default:
        question += " [%s]: " % default
    else:
        question += ": "
    while True:
        answer = input(question)
        if answer:
            return answer
        if default:
            return default


def ask(question, default=True, exact=False):
    """Ask the question in y/n form and return True/False.

    If you don't want a default 'yes', set default to None (or to False if you
    want a default 'no').

    With exact=True, we want to get a literal 'yes' or 'no', at least
    when it does not match the default.

    """
    if AUTO_RESPONSE:
        if default is None:
            msg = ("The question '%s' requires a manual answer, but " +
                   "we're running in --no-input mode.")
            msg = msg % question
            raise RuntimeError(msg)
        logger.debug("Auto-responding '%s' to the question below." % (
            default and "yes" or "no"))
        logger.debug(question)
        return default
    while True:
        yn = 'y/n'
        if default is True:
            yn = 'Y/n'
        if default is False:
            yn = 'y/N'
        q = question + " (%s)? " % yn
        answer = input(q)
        if answer:
            answer = answer
        else:
            answer = ''
        if not answer and default is not None:
            return default
        if exact and answer.lower() not in ('yes', 'no'):
            print("Please explicitly answer yes/no in full "
                  "(or accept the default)")
            continue
        if answer:
            answer = answer[0].lower()
            if answer == 'y':
                return True
            if answer == 'n':
                return False
        # We really want an answer.
        print('Please explicitly answer y/n')
        continue


def system(command, answer=''):
    """commands.getoutput() replacement that also works on windows"""
    p = subprocess.Popen(command,
                         shell=True,
                         stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         close_fds=MUST_CLOSE_FDS)
    i, o, e = (p.stdin, p.stdout, p.stderr)
    if answer:
        i.write(answer)
    i.close()
    result = o.read() + e.read()
    o.close()
    e.close()
    return result.decode('utf8')


def fix_rst_heading(heading, below):
    """If the 'below' line looks like a reST line, give it the correct length.

    This allows for different characters being used as header lines.
    """
    if len(below) == 0:
        return below
    first = below[0]
    if first not in '-=`~':
        return below
    if not len(below) == len([char for char in below
                              if char == first]):
        # The line is not uniformly the same character
        return below
    below = first * len(heading)
    return below


def extract_headings_from_history(history_lines):
    """Return list of dicts with version-like headers.

    We check for patterns like '2.10 (unreleased)', so with either
    'unreleased' or a date between parenthesis as that's the format we're
    using. Just fix up your first heading and you should be set.

    As an alternative, we support an alternative format used by some
    zope/plone paster templates: '2.10 - unreleased' or '2.10 ~ unreleased'

    Note that new headers that zest.releaser sets are in our preferred
    form (so 'version (date)').
    """
    pattern = re.compile(r"""
    (?P<version>.+)  # Version string
    \(               # Opening (
    (?P<date>.+)     # Date
    \)               # Closing )
    \W*$             # Possible whitespace at end of line.
    """, re.VERBOSE)
    alt_pattern = re.compile(r"""
    ^                # Start of line
    (?P<version>.+)  # Version string
    \ [-~]\          # space dash/twiggle space
    (?P<date>.+)     # Date
    \W*$             # Possible whitespace at end of line.
    """, re.VERBOSE)
    headings = []
    line_number = 0
    for line in history_lines:
        match = pattern.search(line)
        alt_match = alt_pattern.search(line)
        if match:
            result = {'line': line_number,
                      'version': match.group('version').strip(),
                      'date': match.group('date'.strip())}
            headings.append(result)
            logger.debug("Found heading: %r", result)
        if alt_match:
            result = {'line': line_number,
                      'version': alt_match.group('version').strip(),
                      'date': alt_match.group('date'.strip())}
            headings.append(result)
            logger.debug("Found alternative heading: %r", result)
        line_number += 1
    return headings


def extract_headings_from_history_modified(changelog):
    """Return list of dicts with version-like headers.

    We check for patterns like '2.10 (unreleased)', so with either
    'unreleased' or a date between parenthesis as that's the format we're
    using. Just fix up your first heading and you should be set.

    As an alternative, we support an alternative format used by some
    zope/plone paster templates: '2.10 - unreleased' or '2.10 ~ unreleased'

    Note that new headers that zest.releaser sets are in our preferred
    form (so 'version (date)').
    """
    pattern = re.compile(r"""
    (?P<version>.+)  # Version string
    \(               # Opening (
    (?P<date>.+)     # Date
    \)               # Closing )
    \W*$             # Possible whitespace at end of line.
    """, re.VERBOSE)
    alt_pattern = re.compile(r"""
    ^                # Start of line
    (?P<version>.+)  # Version string
    \ [-~]\          # space dash/twiggle space
    (?P<date>.+)     # Date
    \W*$             # Possible whitespace at end of line.
    """, re.VERBOSE)
    headings = []
    line_number = 0
    with open(changelog, 'r') as f:
        for line in f:
            match = pattern.search(line)
            alt_match = alt_pattern.search(line)
            if match:
                result = {'line': line_number,
                          'version': match.group('version').strip(),
                          'date': match.group('date'.strip())}
                headings.append(result)
                logger.debug("Found heading: %r", result)
            if alt_match:
                result = {'line': line_number,
                          'version': alt_match.group('version').strip(),
                          'date': alt_match.group('date'.strip())}
                headings.append(result)
                logger.debug("Found alternative heading: %r", result)
            line_number += 1
    return headings


def sanity_check(vcs):
    """Do sanity check before making changes

    Check that we are not on a tag and/or do not have local changes.

    Returns True when all is fine.
    """
    if not vcs.is_clean_checkout():
        q = ("This is NOT a clean checkout. You are on a tag or you have "
             "local changes.\n"
             "Are you sure you want to continue?")
        if not ask(q, default=False):
            sys.exit(1)


def check_recommended_files(data, vcs):
    """Do check for recommended files.

    Returns True when all is fine.
    """
    main_files = os.listdir(data['workingdir'])
    if not 'setup.py' in main_files and not 'setup.cfg' in main_files:
        # Not a python package.  We have no recommendations.
        return True
    if not 'MANIFEST.in' in main_files and not 'MANIFEST' in main_files:
        q = ("This package is missing a MANIFEST.in file. This file is "
             "recommended. "
             "See http://docs.python.org/distutils/sourcedist.html"
             " for more info. Sample contents:"
             "\n"
             "recursive-include main_directory *"
             "recursive-include docs *"
             "include *"
             "global-exclude *.pyc"
             "\n"
             "You may want to quit and fix this.")

        if not vcs.is_setuptools_helper_package_installed():
            q += "Installing %s may help too.\n" % \
                vcs.setuptools_helper_package
        # We could ask, but simply printing it is nicer.  Well, okay,
        # let's avoid some broken eggs on PyPI, per
        # https://github.com/zestsoftware/zest.releaser/issues/10
        q += "Do you want to continue with the release?"
        if not ask(q, default=False):
            return False
        print(q)
    return True


def setup_py(rest_of_cmdline):
    """Return 'python setup.py' command (with hack for testing)"""
    executable = sys.executable
    return '%s setup.py %s' % (executable, rest_of_cmdline)


def strip_version(version):
    """Strip the version of all whitespace."""
    return version.strip().replace(' ', '')


def cleanup_version(version):
    """Check if the version looks like a development version."""
    for w in WRONG_IN_VERSION:
        if version.find(w) != -1:
            logger.debug("Version indicates development: %s.", version)
            version = version[:version.find(w)].strip()
            logger.debug("Removing debug indicators: %r", version)
        version = version.rstrip('.')  # 1.0.dev0 -> 1.0. -> 1.0
    return version


def show_first_and_last_lines(result):
    """Just print the first and last five lines of (pypi) output"""
    lines = [line for line in result.split('\n')]
    if len(lines) < 11:
        for line in lines:
            print(line)
        return
    print('Showing first few lines...')
    for line in lines[:5]:
        print(line)
    print('...')
    print('Showing last few lines...')
    for line in lines[-5:]:
        print(line)