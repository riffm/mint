#!/usr/bin/env python

from distutils.core import setup

setup(
    name='mint',
    version='0.1',
    description='Simple indetion based template engine',
    scripts=['mint/mint-import'],
    author='Tim Perevezentsev',
    author_email='riffm2005@gmail.com',
    packages=['mint']
)
