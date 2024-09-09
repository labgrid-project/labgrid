Step by step guide to releasing a new labgrid version.
labgrid follows the `calver <https://calver.org>`_ versioning scheme
``YY.MINOR[.MICRO]``.
The ``MINOR`` number starts at 0.
The ``MICRO`` number for stable releases starts at 1.

1. Check for relevant PRs that need a merge
===========================================

- `Milestones <https://github.com/labgrid-project/labgrid/milestones>`_
- `Fixes <https://github.com/labgrid-project/labgrid/pulls?q=label%3Afix>`_
- `Fixes for stable <https://github.com/labgrid-project/labgrid/issues?q=label%3A%22fix+for+stable%22>`_

2. Update CHANGES.rst
=====================

Update the `CHANGES.rst` file.
Ensure that no incompatibilities are unlisted and that all major features are
described in a separate section.
It's best to compare against the git log.

Add new sections including the version number for the release in `CHANGES.rst`
(if not already done).
Set the release date.

If you are bumping the ``MINOR`` number, import the changes from the latest stable
branch and add a new (unreleased) section for the next release.
Also add a new section into ``debian/changelog``.

3. Create a tag
===============

Wait for the CI to succeed on the commit you are about to tag.

Now create a (signed) tag of the new release.
If it should be signed (``-s``), your PGP-key has to be available on the
computer.
The release tag should start with a lower case ``v``, e.g. ``v24.0`` or
``v24.0.1``.

.. code-block:: bash

    git tag -s $VERSION

If you're happy with it, push it:

.. code-block:: bash

    git push upstream $VERSION

The CI should take care of the rest.
Make sure it succeeds and the new release is available on PyPi.

4. Draft a release
==================

On GitHub, draft a new release, add the changes in Markdown format and create a
discussion for the release:
https://github.com/labgrid-project/labgrid/releases/new

5. Create new stable branch
===========================

If you are bumping the ``MINOR`` number, push a new stable branch
``stable-YY.MINOR`` based on the release tag.
