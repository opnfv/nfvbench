.. This work is licensed under a Creative Commons Attribution 4.0 International License.
.. SPDX-License-Identifier: CC-BY-4.0

================
Testing NFVbench
================

tox
===

NFVbench project uses `tox`_ to orchestrate the testing of the code base:

* run unit tests
* check code style
* run linter
* check links in the docs

In addition to testing, tox is also used to generate the documentation in HTML
format.

What tox should do is specified in a ``tox.ini`` file located at the project root.

tox is used in jenkins-ci: all the actions performed by tox must succeed before
a patchset can be merged.  As a developer, it is also useful to run tox locally
to detect and fix the issues before pushing the code for review.

.. _tox: https://tox.readthedocs.io/en/latest/



Using tox on a developer's machine
==================================

Requirement: |python-version|
-----------------------------

.. |python-version| replace:: Python 3.6

The current version of Python used by NFVbench is |python-version|.  In
particular, this means that |python-version| is used:

* by tox in CI
* in nfvbench Docker image
* in nfvbench traffic generator VM image

|python-version| is needed to be able to run tox locally.  If it is not
available through the package manager, it can be installed using `pyenv`_.  In
that case, it will also be necessary to install the `pyenv-virtualenv`_ plugin.
Refer to the documentation of those projects for installation instructions.

.. _pyenv: https://github.com/pyenv/pyenv
.. _pyenv-virtualenv: https://github.com/pyenv/pyenv-virtualenv


tox installation
----------------

Install tox with::

    $ pip install tox tox-pip-version


Running tox
-----------

In nfvbench root directory, simply run tox with::

    $ tox

If all goes well, tox shows a green summary such as::

    py36: commands succeeded
    pep8: commands succeeded
    lint: commands succeeded
    docs: commands succeeded
    docs-linkcheck: commands succeeded
    congratulations :)

It is possible to run only a subset of tox *environments* with the ``-e``
command line option.  For instance, to check the code style only, do::

    $ tox -e pep8

Each tox *environment* uses a dedicated python virtual environment.  The
``-r`` command line option can be used to force the recreation of the virtual
environment(s).  For instance::

    $ tox -r
