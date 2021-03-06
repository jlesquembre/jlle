import logging
import tempfile
import os
import sys

from jlle.releaser.utils import system, ask
from jlle.releaser.vcs import BaseVersionControl

logger = logging.getLogger(__name__)


class Git(BaseVersionControl):
    """Command proxy for Git"""
    internal_filename = '.git'
    setuptools_helper_package = 'setuptools-git'

    def is_setuptools_helper_package_installed(self):
        # The package is setuptools-git with a dash, the module is
        # setuptools_git with an underscore.  Thanks.
        try:
            __import__('setuptools_git')
        except ImportError:
            return False
        return True

    @property
    def name(self):
        package_name = self.get_setup_py_name()
        if package_name:
            return package_name
        # No setup.py? With git we can probably only fall back to the directory
        # name as there's no svn-url with a usable name in it.
        dir_name = os.path.basename(os.getcwd())
        return dir_name

    def available_tags(self):
        tag_info = system('git tag')
        tags = [line for line in tag_info.split('\n') if line]
        logger.debug("Available tags: %r", tags)
        return tags

    def prepare_checkout_dir(self, prefix):
        # Watch out: some git versions can't clone into an existing
        # directory, even when it is empty.
        temp = tempfile.mkdtemp(prefix=prefix)
        cwd = os.getcwd()
        os.chdir(temp)
        cmd = 'git clone %s %s' % (self.workingdir, 'gitclone')
        logger.debug(system(cmd))
        os.chdir(cwd)
        return os.path.join(temp, 'gitclone')

    def tag_url(self, version):
        # this doesn't apply to Git, so we just return the
        # version name given ...
        return version

    def cmd_diff(self):
        return 'git diff'

    def cmd_commit(self, message):
        return 'git commit -a -m "%s"' % message

    def cmd_diff_last_commit_against_tag(self, version):
        return "git diff %s" % version

    def cmd_log_since_tag(self, version):
        """Return log since a tagged version till the last commit of
        the working copy.
        """
        return "git log %s..HEAD" % version

    def cmd_create_tag(self, version):
        msg = "Tagging %s" % (version,)
        cmd = 'git tag %s -m "%s"' % (version, msg)
        return cmd

    def cmd_checkout_from_tag(self, version, checkout_dir):
        if not (os.path.realpath(os.getcwd()) ==
                os.path.realpath(checkout_dir)):
            # Specific to git: we need to be in that directory for the command
            # to work.
            logger.warn("We haven't been chdir'ed to %s", checkout_dir)
            sys.exit(1)
        return 'git checkout %s' % version

    def merge_to_master(self):
        branch = system('git rev-parse --abbrev-ref HEAD')
        #print system('git rebase {} master'.format(data['version']))

        return ['git checkout master',
                'git merge {}'.format(branch),
                'git checkout {}'.format(branch)]

    def is_clean_checkout(self):
        """Is this a clean checkout?
        """
        head = system('git symbolic-ref --quiet HEAD')
        # This returns something like 'refs/heads/maurits-warn-on-tag'
        # or nothing.  Nothing would be bad as that indicates a
        # detached head: likely a tag checkout
        if not head:
            # Greetings from Nearly Headless Nick.
            return False
        if system('git status --short --untracked-files=no'):
            # Uncommitted changes in files that are tracked.
            return False
        return True

    def check_master(self):
        #cur_branch = system('git rev-parse --abbrev-ref HEAD').strip()
        cur_branch = open('.git/HEAD').read().strip().split('/')[-1]
        if cur_branch == 'master':
            q = ("Your current branch is master\n"
                 "Are you sure you want to continue?")
            if not ask(q, default=False):
                sys.exit(1)

    def push_commands(self):
        """Push changes to the server."""
        return ['git push --all --follow-tags']
        # return ['git push', 'git push --tags']

    def list_files(self):
        """List files in version control."""
        return system('git ls-tree -r HEAD --name-only').splitlines()
