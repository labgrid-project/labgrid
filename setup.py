#!/usr/bin/env python3
import fastentrypoints

from setuptools import setup

setup(
    name='labgrid',
    description='labgrid: lab hardware and software contol layer',
    author='Rouven Czerwinski and Jan Luebbe',
    author_email='entwicklung@pengutronix.de',
    license='LGPL-2.1',
    use_scm_version=True,
    url='https://github.com/labgrid-project',
    data_files=[('share/man/1', ['man/labgrid-client.1',
                                 'man/labgrid-exporter.1',
                                 'man/labgrid-device-config.1'])],
    extras_require={
        'onewire': ['onewire>=0.2'],
        'coordinator': ['crossbar']
    },
    setup_requires=['pytest-runner', 'setuptools_scm'],
    tests_require=['pytest-mock', ],
    install_requires=[
        'attrs',
        'jinja2',
        'pexpect',
        'pyserial>=3.3',
        'pytest',
        'pyyaml',
        'pyudev',
        'requests',
        'autobahn'
    ],
    packages=[
        'labgrid',
        'labgrid.driver',
        'labgrid.driver.power',
        'labgrid.external',
        'labgrid.protocol',
        'labgrid.provider',
        'labgrid.pytestplugin',
        'labgrid.remote',
        'labgrid.resource',
        'labgrid.strategy',
        'labgrid.util',
    ],
    # the following makes a plugin available to pytest
    entry_points={
        'pytest11': [
            'labgrid = labgrid.pytestplugin',
        ],
        'console_scripts': [
            'labgrid-client = labgrid.remote.client:main',
            'labgrid-exporter = labgrid.remote.exporter:main',
        ]
    },
    # custom PyPI classifier for pytest plugins
    classifiers=["Framework :: Pytest", ],
)
