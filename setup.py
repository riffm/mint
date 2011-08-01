#!/usr/bin/env python

from distutils.core import setup

setup(
    name='mint',
    version='0.4',
    author='Tim Perevezentsev',
    url='http://github.com/riffm/mint',
    author_email='riffm2005@gmail.com',
    packages=['mint'],
    license = 'LICENSE.txt',
    description='Simple indetion based template engine',
    long_description=open('README.rst').read(),
)
