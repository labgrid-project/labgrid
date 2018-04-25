#!/usr/bin/env python3
import fastentrypoints

from setuptools import setup

setup(
    name='labgrid',
    description='labgrid: lab hardware and software control layer',
    author='Rouven Czerwinski and Jan Luebbe',
    author_email='entwicklung@pengutronix.de',
    license='LGPL-2.1',
    use_scm_version=True,
    url='https://github.com/labgrid-project',
    data_files=[('share/man/1', ['man/labgrid-client.1',
                                 'man/labgrid-exporter.1',
                                 'man/labgrid-device-config.1'])],
    python_requires='>=3.4',
    extras_require={
        'onewire': ['onewire>=0.2'],
        'snmp': ['pysnmp', 'pysnmp-mibs'],
        'modbus': ['pyModbusTCP'],
    },
    setup_requires=['pytest-runner', 'setuptools_scm'],
    tests_require=['pytest-mock', ],
    install_requires=[
        'attrs>=17.4.0',
        'jinja2',
        'pexpect',
        'pyserial>=3.3',
        'pytest',
        'pyyaml',
        'pyudev',
        'requests',
        'xmodem>=0.4.5',
        'autobahn',
        'graphviz',
    ],
    packages=[
        'labgrid',
        'labgrid.autoinstall',
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
            'labgrid-autoinstall = labgrid.autoinstall.main:main',
        ]
    },
    # custom PyPI classifier for pytest plugins
    classifiers=["Framework :: Pytest", ],
)
