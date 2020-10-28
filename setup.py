#!/usr/bin/env python3

from setuptools import setup

import fastentrypoints  # noqa: F401 # pylint: disable=unused-import


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
    python_requires='>=3.5',
    extras_require={
        'onewire': ['onewire>=0.2'],
        'snmp': ['pysnmp>=4.4.12', 'pysnmp-mibs>=0.1.6'],
        'modbus': ['pyModbusTCP>=0.1.8'],
        'graph': ['graphviz>0.13.2'],
        'docker': ['docker>=4.1.0'],
        'crossbar': ['crossbar>=19.11.1'],
        'xena': ['xenavalkyrie>=1.4'],
    },
    setup_requires=['setuptools_scm'],
    install_requires=[
        'attrs>=19.2.0',
        'ansicolors>=1.1.8',
        'jinja2>=2.10.3',
        'packaging>=14.0',
        'pexpect>=4.7',
        'pyserial>=3.3',
        'pytest>=4.5',
        'pyyaml>=5.1',
        'pyudev>=0.22.0',
        'requests>=2.22.0',
        'xmodem>=0.4.5',
        'autobahn>=19.11.0',
    ],
    packages=[
        'labgrid',
        'labgrid.autoinstall',
        'labgrid.driver',
        'labgrid.driver.power',
        'labgrid.driver.usbtmc',
        'labgrid.protocol',
        'labgrid.provider',
        'labgrid.pytestplugin',
        'labgrid.remote',
        'labgrid.resource',
        'labgrid.strategy',
        'labgrid.util',
        'labgrid.util.agents',
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
            'labgrid-suggest = labgrid.resource.suggest:main',
        ]
    },
    # custom PyPI classifiers
    classifiers=[
        "Topic :: Software Development :: Testing",
        "Framework :: Pytest",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
)
