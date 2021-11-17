# -*- coding: utf-8 -*-
#

from setuptools import setup
import os


long_description = """
owmeta-pytest-plugin
====================

Pytest plugin for testing in packages using owmeta-core
"""


for line in open('owmeta_pytest_plugin/__init__.py'):
    if line.startswith("__version__"):
        version = line.split("=")[1].strip()[1:-1]

package_data_excludes = ['.*', '*.bkp', '~*']


def excludes(base):
    res = []
    for x in package_data_excludes:
        res.append(os.path.join(base, x))
    return res


setup(
    name='owmeta-pytest-plugin',
    zip_safe=False,
    install_requires=[
        'pytest'
    ],
    version=version,
    packages=['owmeta_pytest_plugin'],
    author='OpenWorm.org authors and contributors',
    author_email='info@openworm.org',
    description='owmeta-pytest-plugin is a pytest plugin to aid in testing packages using'
    ' owemta-core',
    long_description=long_description,
    license='MIT',
    url='https://github.com/openworm/owmeta-pytest-plugin/',
    entry_points={
        'pytest11': [
            'owmeta_core_fixtures = owmeta_pytest_plugin'
        ]
    },
    classifiers=[
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Framework :: Pytest',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Topic :: Scientific/Engineering'
    ]
)
