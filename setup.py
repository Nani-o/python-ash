from setuptools import setup
import re

def read(f):
    with open(f) as file:
        return file.read()

def get_version():
    _version_re = re.compile(r'__version__\s+=\s+(.*)')
    _to_parse = read('ash/__init__.py')
    version = _version_re.search(_to_parse).group(1).strip("'")
    return version

setup(name='ash',
    version = get_version(),
    description = 'The Ansible SHell',
    # long_description=read('README.rd') + '\n\n' + read('HISTORY.rd'),
    classifiers = [
        'Development Status :: 3 - Alpha',
        'License :: MIT License',
        'Programming Language :: Python :: 2.7',
        'Topic :: Ansible :: Shell :: cli',
    ],
    keywords = 'ash ansible shell cli prompt-toolkit pt',
    url = 'https://github.com/Nani-o/ash',
    author = 'Sofiane Medjkoune',
    author_email = 'sofiane@medjkoune.fr',
    license = 'MIT',
    packages = ['ash'],
    install_requires = [line.strip() for line in open('requirements.txt') if line.strip() and not line.startswith('#')],
    entry_points = {
        'console_scripts': ['ash=ash.main:main'],
    },
    include_package_data = True,
    zip_safe = False)
