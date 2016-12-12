#!/usr/bin/env python3

from setuptools import setup, find_packages

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
        'mock-import',
      ],
      install_requires=[
          "pyserial",
          "attrs",
          "pexpect"
      ],
      packages=['labgrid', 'labgrid.resource', 'labgrid.protocol', 'labgrid.external', 'labgrid.driver', 'labgrid.util'],
     )
