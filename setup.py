#!/usr/bin/env python

from distutils.core import setup

setup(
    name='Trabant',
    version='0.0.1',
    description='Trabant, teh web framework for embedded devices',
    author='Alberto Granzotto (vrde)',
    author_email='alberto@granzotto.net',
    url='',

    package_dir={'': 'src'},

    packages=[
        'trabant',
    ],
)
