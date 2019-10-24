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
        'snmp': ['pysnmp', 'pysnmp-mibs'],
        'modbus': ['pyModbusTCP'],
        'graph': ['graphviz'],
    },
    setup_requires=['pytest-runner', 'setuptools_scm'],
    tests_require=['pytest-mock', ],
    install_requires=[
        'attrs>=19.2.0',
        'ansicolors',
        'jinja2',
        'pexpect',
        'pyserial>=3.3',
        'pytest>=3.6',
        'pyyaml',
        'pyudev',
        'requests',
        'xmodem>=0.4.5',
        'autobahn',
    ],
    packages=[
        'labgrid',
        'labgrid.autoinstall',
        'labgrid.driver',
        'labgrid.driver.power',
        'labgrid.driver.usbtmc',
        'labgrid.external',
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
    ],
)
