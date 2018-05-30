import time
import pytest

from labgrid.external import HawkbitTestClient


@pytest.fixture()
def hawkbit():
    # Requires a hawkbit server instance to be running.
    # See: https://github.com/eclipse/hawkbit on how to set up
    # a test instance of hawkbit
    client = HawkbitTestClient("localhost", "8080", "admin", "admin")
    assert isinstance(client, HawkbitTestClient)
    return client

def test_upgrade(hawkbit):
    # modify this to point to the image to pack in the software module
    image = 'path/to/image'

    # Create modules with artifacts
    module_id = hawkbit.add_swmodule('Yocto module')
    hawkbit.add_artifact(module_id, image)
    # Create distributions of it
    dist_id = hawkbit.add_distributionset(module_id, name="Test-Distribution")

    # Create rollout with 3 groups
    rollout_id = hawkbit.add_rollout("Test Rollout #1", dist_id, 3)

    # Wait for rollout to become ready
    rollout_status = hawkbit.get_endpoint('rollouts/{}'.format(rollout_id))
    while not rollout_status['status'] == 'ready':
        time.sleep(1)
        rollout_status = hawkbit.get_endpoint('rollouts/{}'.format(rollout_id))

    # Start the rollout
    hawkbit.start_rollout(rollout_id)

    # Wait until rollout is done
    rollout_status = hawkbit.get_endpoint('rollouts/{}'.format(rollout_id))
    while not rollout_status['status'] == 'finished':
        time.sleep(30)
        rollout_status = hawkbit.get_endpoint('rollouts/{}'.format(rollout_id))
