#!/usr/bin/env python3

from setuptools import setup

setup(name='labgrid',
      version='0.0.1',
      description='labgrid: lab hardware and software contol layer',
      author='Rouven Czerwinski and Jan Luebbe',
      url='https://github.com/labgrid-project',
      setup_requires=[
        'pytest-runner',
      ],
      tests_require=[
        'pytest',
        'pytest-mock',
      ],
      install_requires=[
        'pyserial',
        'attrs',
        'pexpect',
        'pyyaml',
      ],
      packages=[
        'labgrid',
        'labgrid.driver',
        'labgrid.external',
        'labgrid.protocol',
        'labgrid.provider',
        'labgrid.resource',
        'labgrid.util',
      ],
     )
