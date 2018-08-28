# Prerequisites #
To run the docker example one has to have docker-ce installed and
accessible via "unix:///var/run/docker.sock" (the default). The
default docker bridge network also needs to be accessible from the
pytest executor since the test tries to establish an ssh connection to
the container (again the default after a standard installation of
docker-ce).

After following steps similar to [Getting started](https://labgrid.readthedocs.io/en/latest/getting_started.html#running-your-first-test) the demo can be run with:

    pytest -s --lg-env env.yaml test_shell.py

Successfully tested against Docker version 18.06.1-ce, build e68fc7a.
But it should work with later versions as well.
