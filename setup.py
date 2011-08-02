from distutils.core import setup

version = '0.5'

setup(
    name='mint',
    version=version,
    description='Simple indetion based template engine',
    long_description=open('README.rst').read()+'\n\n'+open('CHANGELOG').read(),
    py_modules=['mint'],
    license='MIT',
    author='Tim Perevezentsev',
    author_email='riffm2005@gmail.com',
    url='http://github.com/riffm/mint'
)
