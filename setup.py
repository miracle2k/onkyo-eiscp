#!/usr/bin/env python
# coding: utf8

from setuptools import setup, find_packages

# Get long_description from README
import os
here = os.path.dirname(os.path.abspath(__file__))
f = open(os.path.join(here, 'README.rst'))
long_description = f.read().strip()
f.close()

setup(
    name='dannytrigo-onkyo-eiscp',
    version='1.2.11',
    url='https://github.com/dannytrigo/onkyo-eiscp',
    license='MIT',
    author='Michael Elsdörfer',
    author_email='michael@elsdoerfer.com',
    description='Control Onkyo receivers over ethernet. (dannytrigo fork for bugfix)',
    long_description=long_description,
    packages = find_packages(exclude=('tests*',)),
    entry_points="""[console_scripts]\nonkyo = eiscp.script:run\n""",
    install_requires=['docopt>=0.4.1', 'netifaces', 'xmltodict>=0.12.0'],
    platforms='any',
    classifiers=[
        'Topic :: System :: Networking',
        'Topic :: Games/Entertainment',
        'Topic :: Multimedia',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
    ]
)
