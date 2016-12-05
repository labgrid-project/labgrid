#!/usr/bin/env python3

from setuptools import setup

setup(name='labgrid',
      version='0.0.1',
      description='labgrid: lab hardware and software contol layer',
      author='Rouven Czerwinski and Jan Luebbe',
      url='https://github.com/labgrid-project',
      packages=['labgrid', 'labgrid.resource', 'labgrid.protocol', 'labgrid.external'],
     )
