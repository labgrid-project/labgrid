from unittest.mock import Mock, patch

import pytest

from labgrid.driver.dfudriver import DFUDriver
from labgrid.resource.common import NetworkResource, Resource


@pytest.mark.parametrize(
    "options, flags",
    [
        ({}, []),
        ({"wait": True}, ["--wait"]),
        ({"reset": True}, ["--reset"]),
        ({"wait": True, "reset": True}, ["--wait", "--reset"]),
    ],
)
def test_download_options(options, flags):
    driver = DFUDriver.__new__(DFUDriver)
    driver.tool = "dfu-util"
    driver.dfu = resource = Mock(path="1-2.3", command_prefix=[])
    resource.wrap_command.side_effect = lambda command: Resource.wrap_command(resource, command)

    with patch("labgrid.driver.dfudriver.ManagedFile") as managed, patch(
        "labgrid.driver.dfudriver.processwrapper.check_output"
    ) as run:
        managed.return_value.get_remote_path.return_value = "/tmp/firmware.bin"
        DFUDriver.download.__wrapped__(driver, "firmware", "/tmp/firmware.bin", **options)

    managed.assert_called_once_with("/tmp/firmware.bin", resource)
    managed.return_value.sync_to_resource.assert_called_once_with()
    run.assert_called_once_with(
        ["dfu-util", "-p", "1-2.3", *flags, "--alt", "firmware", "--download", "/tmp/firmware.bin"],
        print_on_silent_log=True,
    )


@pytest.mark.parametrize(
    "method, args, suffix, kwargs",
    [
        ("download", ("firmware", "/tmp/firmware.bin"),
         ["--alt", "firmware", "--download", "'/tmp/firmware image.bin'"],
         {"print_on_silent_log": True}),
        ("detach", ("firmware",), ["--alt", "firmware", "--detach"], {}),
        ("list", (), ["--list"], {"print_on_silent_log": True}),
    ],
)
def test_remote_command(method, args, suffix, kwargs):
    driver = DFUDriver.__new__(DFUDriver)
    driver.tool = "dfu-util"
    driver.dfu = resource = Mock(path="1-2.3", command_prefix=["ssh", "example.org", "--"])
    resource.wrap_command.side_effect = lambda command: NetworkResource.wrap_command(resource, command)

    with patch("labgrid.driver.dfudriver.ManagedFile") as managed, patch(
        "labgrid.driver.dfudriver.processwrapper.check_output"
    ) as run:
        managed.return_value.get_remote_path.return_value = "/tmp/firmware image.bin"
        getattr(DFUDriver, method).__wrapped__(driver, *args)

    run.assert_called_once_with(
        ["ssh", "example.org", "--", "dfu-util", "-p", "1-2.3", *suffix], **kwargs
    )
