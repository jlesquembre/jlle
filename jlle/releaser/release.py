import logging
import os
import sys
import datetime
import urllib.request
import urllib.error

from jlle.releaser import git
from jlle.releaser import hg
from jlle.releaser import utils
from jlle.releaser import pypi

logger = logging.getLogger(__name__)

TODAY = datetime.datetime.today().strftime('%Y-%m-%d')
HISTORY_HEADER = '%(new_version)s (%(today)s)'
PRERELEASE_COMMIT_MSG = 'Release %(new_version)s'

NOTHING_CHANGED_YET = '- Nothing changed yet.'
COMMIT_MSG = 'Back to development: %(new_version)s'
DEV_VERSION_TEMPLATE = '%(new_version)s.dev0'


def version_control():
    """Return an object that provides the version control interface based
    on the detected version control system."""
    curdir_contents = os.listdir('.')
    if '.hg' in curdir_contents:
        return hg.Hg()
    elif '.git' in curdir_contents:
        return git.Git()
    else:
        logger.critical('No version control system detected.')
        sys.exit(1)


def package_in_pypi(package):
    """Check whether the package is registered on pypi"""
    url = 'http://pypi.python.org/simple/%s' % package
    try:
        urllib.request.urlopen(url)
        return True
    except urllib.error.HTTPError as e:
        logger.debug("Package not found on pypi: %s", e)
        return False


class Releaser:

    def __init__(self):
        self.vcs = version_control()
        self.data = {'workingdir': self.vcs.workingdir,
                     'name': self.vcs.name,
                     'today': TODAY,
                     'history_header': HISTORY_HEADER,
                     'prerelease_commit_msg': PRERELEASE_COMMIT_MSG,
                     'nothing_changed_yet': NOTHING_CHANGED_YET,
                     'commit_msg': COMMIT_MSG,
                     'dev_version_template': DEV_VERSION_TEMPLATE
                     }
        self.setup_cfg = pypi.SetupConfig()
        if self.setup_cfg.no_input():
            utils.AUTO_RESPONSE = True

    def _grab_version(self):
        """Set the version to a non-development version."""
        original_version = self.vcs.version
        logger.debug("Extracted version: %s", original_version)
        if original_version is None:
            logger.critical('No version found.')
            sys.exit(1)
        suggestion = utils.cleanup_version(original_version)
        new_version = utils.ask_version("Enter version", default=suggestion)
        if not new_version:
            new_version = suggestion
        self.data['original_version'] = original_version
        self.data['new_version'] = new_version

    def _write_version(self):
        if self.data['new_version'] != self.data['original_version']:
            # self.vcs.version writes it to the file it got the version from.
            self.vcs.version = self.data['new_version']
            logger.info("Changed version from %r to %r",
                        self.data['original_version'],
                        self.data['new_version'])

    def _grab_history(self):
        """Calculate the needed history/changelog changes

        Every history heading looks like '1.0 b4 (1972-12-25)'. Extract them,
        check if the first one matches the version and whether it has a the
        current date.
        """
        default_location = None
        config = self.setup_cfg.config
        if config and config.has_option('zest.releaser', 'history_file'):
            default_location = config.get('zest.releaser', 'history_file')
        history_file = self.vcs.history_file(location=default_location)
        if not history_file:
            logger.warn("No history file found")
            self.data['history_lines'] = None
            self.data['history_file'] = None
            return
        logger.debug("Checking %s", history_file)
        history_lines = open(history_file).read().split('\n')
        # ^^^ TODO: .readlines()?
        headings = utils.extract_headings_from_history(history_lines)
        if not len(headings):
            logger.error("No detectable version heading in the history "
                         "file %s", history_file)
            sys.exit()
        good_heading = self.data['history_header'] % self.data
        # ^^^ history_header is a string with %(abc)s replacements.
        line = headings[0]['line']
        previous = history_lines[line]
        history_lines[line] = good_heading
        logger.debug("Set heading from %r to %r.", previous, good_heading)
        history_lines[line + 1] = utils.fix_rst_heading(
            heading=good_heading,
            below=history_lines[line + 1])
        logger.debug("Set line below heading to %r",
                     history_lines[line + 1])
        self.data['history_lines'] = history_lines
        self.data['history_file'] = history_file
        # TODO: add line number where an extra changelog entry can be
        # inserted.

    def _write_history(self):
        """Write previously-calculated history lines back to the file"""
        if self.data['history_file'] is None:
            return
        contents = '\n'.join(self.data['history_lines'])
        history = self.data['history_file']
        open(history, 'w').write(contents)
        logger.info("History file %s updated.", history)

    def _diff_and_commit(self, commit_msg):
        diff_cmd = self.vcs.cmd_diff()
        diff = utils.system(diff_cmd)
        logger.info("The '%s':\n\n%s\n" % (diff_cmd, diff))
        if utils.ask("OK to commit this"):
            msg = self.data[commit_msg] % self.data
            commit_cmd = self.vcs.cmd_commit(msg)
            commit = utils.system(commit_cmd)
            logger.info(commit)

    def _check_if_tag_already_exists(self):
        """Check if tag already exists and show the difference if so"""
        version = self.data['new_version']
        if self.vcs.tag_exists(version):
            return True
        else:
            return False

    def _make_tag(self):
        version = self.data['new_version']
        cmds = self.vcs.cmd_create_tag(version)
        if not isinstance(cmds, list):
            cmds = [cmds]
        if len(cmds) == 1:
            print("Tag needed to proceed, you can use the following command:")
        for cmd in cmds:
            print(cmd)
            if utils.ask("Run this command"):
                print(utils.system(cmd))
            else:
                # all commands are needed in order to proceed normally
                print("Please create a tag for %s yourself and rerun." %
                      (version,))
                sys.exit()
        if not self.vcs.tag_exists(version):
            print("\nFailed to create tag %s!" % (version,))
            sys.exit()

    def _merge_to_master(self):
        cmds = self.vcs.merge_to_master()
        for cmd in cmds:
            print(utils.system(cmd))

    def _sdist_options(self):
        options = []
        return " ".join(options)

    def _upload_distributions(self, package, sdist_options, pypiconfig):
        # See if creating an sdist actually works.  Also, this makes
        # the sdist available for plugins.
        logger.info("Making an egg of a fresh tag checkout.")
        print(utils.system(utils.setup_py('sdist ' + sdist_options)))
        if not pypiconfig.is_pypi_configured():
            logger.warn("You must have a properly configured %s file in "
                        "your home dir to upload an egg.",
                        pypi.DIST_CONFIG_FILE)
            return

        # First ask if we want to upload to pypi, which should always
        # work, also without collective.dist.
        use_pypi = package_in_pypi(package)
        if use_pypi:
            logger.info("This package is registered on PyPI.")
        else:
            logger.warn("This package is NOT registered on PyPI.")
        if pypiconfig.is_old_pypi_config():
            pypi_command = 'register sdist %s upload' % sdist_options
            shell_command = utils.setup_py(pypi_command)
            if use_pypi:
                default = True
                exact = False
            else:
                # We are not yet on pypi.  To avoid an 'Oops...,
                # sorry!' when registering and uploading an internal
                # package we default to False here.
                default = False
                exact = True
            if utils.ask("Register and upload to PyPI", default=default,
                         exact=exact):
                logger.info("Running: %s", shell_command)
                result = utils.system(shell_command)
                utils.show_first_and_last_lines(result)

        # If collective.dist is installed (or we are using
        # python2.6 or higher), the user may have defined
        # other servers to upload to.
        for server in pypiconfig.distutils_servers():
            if pypi.new_distutils_available():
                commands = ('register', '-r', server, 'sdist',
                            sdist_options, 'upload', '-r', server)
            else:
                ## This would be logical, given the lines above:
                #commands = ('mregister', '-r', server, 'sdist',
                #            sdist_options, 'mupload', '-r', server)
                ## But according to the collective.dist documentation
                ## it should be this (with just one '-r'):
                commands = ('mregister', 'sdist',
                            sdist_options, 'mupload', '-r', server)
            shell_command = utils.setup_py(' '.join(commands))
            default = True
            exact = False
            if server == 'pypi' and not use_pypi:
                # We are not yet on pypi.  To avoid an 'Oops...,
                # sorry!' when registering and uploading an internal
                # package we default to False here.
                default = False
                exact = True
            if utils.ask("Register and upload to %s" % server,
                         default=default, exact=exact):
                logger.info("Running: %s", shell_command)
                result = utils.system(shell_command)
                utils.show_first_and_last_lines(result)

    def _release(self):
        """Upload the release, when desired"""

        pypiconfig = pypi.PypiConfig()

        # Does the user normally want a real release?  We are
        # interested in getting a sane default answer here, so you can
        # override it in the exceptional case but just hit Enter in
        # the usual case.
        main_files = os.listdir(self.data['workingdir'])
        if 'setup.py' not in main_files and 'setup.cfg' not in main_files:
            # Neither setup.py nor setup.cfg, so this is no python
            # package, so at least a pypi release is not useful.
            # Expected case: this is a buildout directory.
            default_answer = False
        else:
            default_answer = pypiconfig.want_release()

        if not utils.ask("Check out the tag (for tweaks or pypi/distutils "
                         "server upload)", default=default_answer):
            return

        package = self.vcs.name
        version = self.data['new_version']
        logger.info("Doing a checkout...")
        self.vcs.checkout_from_tag(version)
        self.data['tagdir'] = os.path.realpath(os.getcwd())
        logger.info("Tag checkout placed in %s", self.data['tagdir'])

        # Possibly fix setup.cfg.
        if self.setup_cfg.has_bad_commands():
            logger.info("This is not advisable for a release.")
            if utils.ask("Fix %s (and commit to tag if possible)" %
                         self.setup_cfg.config_filename, default=True):
                # Fix the setup.cfg in the current working directory
                # so the current release works well.
                self.setup_cfg.fix_config()

        sdist_options = self._sdist_options()

        if 'setup.py' in os.listdir(self.data['tagdir']):
            self._upload_distributions(package, sdist_options, pypiconfig)

        # Make sure we are in the expected directory again.
        os.chdir(self.vcs.workingdir)

    def _update_version(self):
        """Ask for and store a new dev version string."""
        #current = self.vcs.version
        current = self.data['new_version']

        # Clean it up to a non-development version.
        current = utils.cleanup_version(current)
        # Try to make sure that the suggestion for next version after
        # 1.1.19 is not 1.1.110, but 1.1.20.
        current_split = current.split('.')
        major = '.'.join(current_split[:-1])
        minor = current_split[-1]
        try:
            minor = int(minor) + 1
            suggestion = '.'.join([major, str(minor)])
        except ValueError:
            # Fall back on simply updating the last character when it is
            # an integer.
            try:
                last = int(current[-1]) + 1
                suggestion = current[:-1] + str(last)
            except ValueError:
                logger.warn("Version does not end with a number, so we can't "
                            "calculate a suggestion for a next version.")
                suggestion = None
        print("Current version is %r" % current)
        q = "Enter new development version ('.dev0' will be appended)"
        version = utils.ask_version(q, default=suggestion)
        if not version:
            version = suggestion
        if not version:
            logger.error("No version entered.")
            sys.exit()

        self.data['new_version'] = version
        dev_version = self.data['dev_version_template'] % self.data
        self.data['dev_version'] = dev_version
        logger.info("New version string is %r",
                    dev_version)

        self.vcs.version = self.data['dev_version']

    def _update_history(self):
        """Update the history file"""
        version = self.data['new_version']
        history = self.vcs.history_file()
        if not history:
            logger.warn("No history file found")
            return
        history_lines = open(history).read().split('\n')
        headings = utils.extract_headings_from_history(history_lines)
        if not len(headings):
            logger.warn("No detectable existing version headings in the "
                        "history file.")
            inject_location = 0
            underline_char = '-'
        else:
            first = headings[0]
            inject_location = first['line']
            underline_line = first['line'] + 1
            try:
                underline_char = history_lines[underline_line][0]
            except IndexError:
                logger.debug("No character on line below header.")
                underline_char = '-'
        header = '%s (unreleased)' % version
        inject = [header,
                  underline_char * len(header),
                  '',
                  self.data['nothing_changed_yet'],
                  '',
                  '']
        history_lines[inject_location:inject_location] = inject
        contents = '\n'.join(history_lines)
        open(history, 'w').write(contents)
        logger.info("Injected new section into the history: %r", header)

    def _push(self):
        """Offer to push changes, if needed."""

        push_cmds = self.vcs.push_commands()
        if not push_cmds:
            return
        if utils.ask("OK to push commits to the server?"):
            for push_cmd in push_cmds:
                output = utils.system(push_cmd)
                logger.info(output)

    def make_release(self):
        utils.sanity_check(self.vcs)
        self.vcs.check_master()

        self._grab_version()
        self._grab_history()

        if self._check_if_tag_already_exists():
            print("\nTag '%s' already exists!" % (self.data['new_version'],))
            sys.exit()

        self._write_version()
        self._write_history()
        self._diff_and_commit('prerelease_commit_msg')

        self._make_tag()
        self._merge_to_master()
        self._release()

        self._update_version()
        self._update_history()
        self._diff_and_commit('commit_msg')
        self._push()


def main():

    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s: %(message)s")

    r = Releaser()
    r. make_release()
