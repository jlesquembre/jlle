import os
import sys
import logging
import json

from shutil import copy

import requests

from jinja2 import Environment, FileSystemLoader

from sarge import run, Capture

from jlle.releaser.utils import ask, ask_version

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.INFO)


LICENSES = (
    ('GPLv2', 'GNU General Public License v2 (GPLv2)'),
    ('GPLv3', 'GNU General Public License v3 (GPLv3)'),
    ('Mozilla', 'Mozilla Public License 2.0 (MPL 2.0)'),
    ('Apache', 'Apache Software License'),
    ('MIT', 'MIT License'),
    )


def render(env, in_path, out_path, variables):
    template = env.get_template(in_path)
    with open(out_path, 'x') as out:
        out.write(template.render(**variables))


def is_even(num):
    return (num & 0x1) == 0


def replace(path, variables):
    index = path.find('+')
    count = 0
    while index != -1:
        sub = '{' if is_even(count) else '}'
        path = path.replace('+', sub, 1)
        count += 1
        index = path.find('+')

    if count:
        return path.format(**variables)

    return path

def should_skip_file(name):
    """
    Checks if a file should be skipped based on its name.

    If it should be skipped, returns the reason, otherwise returns
    None.
    """
    if name.endswith(('~', '.bak')):
        return 'Skipping backup file %(filename)s'
    if name.endswith(('.pyc', '.pyo')):
        return 'Skipping %s file ' % os.path.splitext(name)[1] + '%(filename)s'
    if name.endswith('$py.class'):
        return 'Skipping $py.class file %(filename)s'
    return None


def main():

    #
    # Ask about the project
    #

    here = os.path.dirname(os.path.realpath(__file__))

    project = ask_version('\nProject name')

    print('\nChoose a license, options are:')
    for index, license in enumerate(LICENSES):
        print('{}) {}'.format(index, license[0]))

    license = ask_version('Pick a version', '0')
    while 0 > int(license) or int(license) >= len(LICENSES):
        license = ask_version('Wrong version, try again', '0')

    license = LICENSES[int(license)]
    license_file = os.path.join(here, 'licenses', license[0])

    #
    # Create folder and copy license
    #

    project_dir = os.path.join(os.path.abspath(os.getcwd()), project)
    if not ask('\nCreate this project directory:\n{}'.format(project_dir)):
        print('Exit')
        sys.exit()

    try:
        os.mkdir(project)
    except FileExistsError:
        print('Directory "{}" already exits!!!'.format(project_dir))
        sys.exit(1)
    copy(license_file, os.path.join(project, 'LICENSE'))

    #
    # Render the templates
    #
    variables = {'project': project,
                 'license': license[1]}

    templates_dir = os.path.join(here, 'templates')
    env = Environment(loader=FileSystemLoader(templates_dir),
                      keep_trailing_newline=True)

    for path, subdirs, files in os.walk(templates_dir):
        if '__pycache__' in subdirs:
            subdirs.remove('__pycache__')

        for name in files:
            if should_skip_file(name):
                continue

            in_path = os.path.relpath(os.path.join(path, name), templates_dir)
            logging.info('Render {}'.format(in_path))
            out_path = os.path.join(project_dir, replace(in_path, variables))

            out_dir = os.path.dirname(out_path)
            if not os.path.exists(out_dir):
                os.makedirs(out_dir)

            render(env, in_path, out_path, variables)

    #
    # Init a git repo
    #

    logging.info('Create git repository')
    run('git init', cwd=project)
    run('git add .', cwd=project)
    run('git commit -a -m "Initial commit"', cwd=project)
    run('git checkout -b develop', cwd=project)

    # Create github repo
    if ask('Create a GitHub repo'):
        user = 'jlesquembre'
        pw = run('pass github | head -n 1', stdout=Capture()).stdout.text.strip()
        requests.post('https://api.github.com/user/repos',
                      auth=(user, pw),
                      data=json.dumps({'name': project,
                                       'homepage': 'http://{}.github.io/{}'.format(user, project)}))

        run('git remote add origin git@github.com:{}/{}.git'.format(user, project), cwd=project)
        run('git push --all --set-upstream origin', cwd=project)
