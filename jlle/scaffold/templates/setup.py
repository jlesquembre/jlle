from setuptools import setup
import os

version = '0.0.1.dev0'

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.rst'), 'rt') as f:
    README = f.read()


setup(name='{{project}}',
      version=version,
      author='José Luis Lafuente',
      author_email='jlesquembre@gmail.com',
      description='blabla',
      long_description=README,
      license='{{license}}',
      url='http://jlesquembre.github.io/{{project}}',
      packages=['{{project}}'],
      include_package_data=True,
      classifiers=[
        'Development Status :: 3 - Alpha',
        'Topic :: Utilities',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: {{license}}',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.3',
        ],
      keywords=['python'],
      #entry_points = {
      #  'console_scripts': [
      #      'doc2git = doc2git.cmdline:main',
      #      'd2g = doc2git.cmdline:main',
      #    ],
      #  },
      #install_requires=['sarge']
    )

