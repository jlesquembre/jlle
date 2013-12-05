__import__('pkg_resources').declare_namespace(__name__)

import pkg_resources

__version__ = pkg_resources.get_distribution('jlle').version

