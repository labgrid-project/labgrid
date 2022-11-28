Step by step guide to releasing a new labgrid version.

0. Preparations
===============
Clean the `dist/` directory:

.. code-block:: bash

   rm dist/*

Check your commit mail and name:

.. code-block:: bash

   git config --get user.name
   git config --get user.email

1. Update CHANGES.rst
=====================

Update the `CHANGES.rst` file.
Ensure that no incompatiblities are unlisted and that all major features are
described in a separate section.
It's best to compare against the git log.

2. Bump Version Number
======================

Bump the version number in `CHANGES.rst`.

3. Create a signed Tag
======================

Create a signed tag of the new release.
Your PGP-key has to be available on the computer.

.. code-block:: bash

    git tag -s <your-version-number>

4. Create sdist
===============

Run the following command:

::

   pip install build
   python -m build --sdist

The sdist file will be available in the `dist/` directory.

5. Test upload to pypi dev
==========================

Test the upload by using twine to upload to pypi test service

::

   twine upload --repository-url https://test.pypi.org/legacy/ dist/*

6. Test download from pypi dev
==============================

Test the upload by using pypi dev as a download source

::

   virtualenv -p python3 labgrid-crossbar-release-<your-version-number>
   labgrid-crossbar-release-<your-version-number>/bin/pip install --upgrade pip
   labgrid-crossbar-release-<your-version-number>/bin/pip install -r crossbar-requirements.txt

   virtualenv -p python3 labgrid-release-<your-version-number>
   source labgrid-release-<your-version-number>/bin/activate
   pip install --upgrade pip setuptools wheel
   pip install --index-url https://test.pypi.org/simple/ labgrid

And optionally run the tests:

::

   pip install ".[dev]"
   pytest tests --crossbar-venv labgrid-crossbar-release-<your-version-number>

7. Upload to pypi
=================

Upload the tested dist file to pypi.

::

   twine upload dist/*

8. Upload the signed tag
========================

Upload the signed tag to the upstream repository

::

   git push upstream <your-version-number>
