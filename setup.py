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
        'pytest-mock',
      ],
      install_requires=[
        'attrs',
        'pexpect',
        'pyserial',
        'pytest',
        'pyyaml',
        'requests',
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
      # the following makes a plugin available to pytest
      entry_points = {
          'pytest11': [
              'name_of_plugin = labgrid.pytestplugin',
          ]
      },
      # custom PyPI classifier for pytest plugins
      classifiers=[
          "Framework :: Pytest",
      ],
     )
