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

1. Freeze Dependencies
======================

Freeze the dependencies into the `requirements.txt` file and update the separate
feature requirements files.
This ensures that known good dependencies are available for every release.

2. Update setup.py Dependencies
===============================

Update the minimum required dependencies in the `setup.py` file.
These are intentionally non restrictive, see `PYPA Discussion
<https://packaging.python.org/discussions/install-requires-vs-requirements/>`_.
A frozen environment is already created in the previous step.

3. Update CHANGES.rst
=====================

Update the `CHANGES.rst` file. This should ideally be done in every pull request,
but its better to check that the `CHANGES.rst` is up to date.
Ensure that no incompatiblities are unlisted and that all major features are
described in a separate section.
It's best to compare against the git log.

4. Bump Version Number
======================

Bump the version number in `CHANGES.rst` and `setup.py`

5. Create a signed Tag
======================

Create a signed tag of the new release.
Your PGP-key has to be available on the computer.

.. code-block:: bash

    git tag -s <your-version-number>

6. Create sdist
===============

Run the following command:

::

   python setup.py sdist

The sdist file will be available in the `dist/` directory.

7. Test upload to pypi dev
==========================

Test the upload by using twine to upload to pypi test service

::

   twine upload --repository-url https://test.pypi.org/legacy/ dist/*

8. Test download from pypi dev
==============================

Test the upload by using pypi dev as a download source

::

   virtualenv -p python3 labgrid-release-<your-version-number>
   source labgrid-release-<your-version-number>/bin/activate
   pip install --index-url https://test.pypi.org/simple/ labgrid

And optionally run the tests:

::

   pip install -r dev-requirements
   pytest tests

9. Upload to pypi
=================

Upload the tested dist file to pypi.

::

   twine upload dist/*

10. Upload the signed tag
==========================

Upload the signed tag to the upstream repository

::

   git push upstream <your-version-number>
