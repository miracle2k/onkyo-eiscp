#!/usr/bin/env python
# coding: utf8

from setuptools import setup, find_packages

setup(
    name='onkyo-eiscp',
    version='0.9',
    url='https://github.com/miracle2k/onkyo-eiscp',
    license='MIT',
    author='Michael Elsdörfer',
    author_email='michael@elsdoerfer.com',
    description='Control Onkyo receivers over ethernet.',
    packages = find_packages(),
    install_requires=['docopt==0.4.1'],
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
