import pytest

from labgrid import Environment, Target
from labgrid.resource.udev import USBDebugger
from labgrid.driver.pyocddriver import PyOCDDriver

LABGRID_TEST_SERIAL = "LABGRID_TEST_SER"
LABGRID_TARGET = "target_mcu"
LABGRID_TOOL_CMD = "/some/path/to/nowhere"


def test_pyocd_driver_activate(target):
    r = USBDebugger(target, name=None, match={"sys_name": "1-12"})
    r.avail = True
    d = PyOCDDriver(target, name=None)
    target.activate(d)


def test_pyocd_driver_reset(target, mocker):
    r = USBDebugger(target, name=None, match={"sys_name": "1-12"})
    r.avail = True
    d = PyOCDDriver(target, name=None)
    target.activate(d)

    check_output_mock = mocker.patch("labgrid.util.helper.processwrapper.check_output")

    d.reset()

    check_output_mock.assert_called_once()
    cmd = check_output_mock.call_args.kwargs["command"]
    assert cmd == ["pyocd", "reset", "--no-config"]
    assert check_output_mock.call_args.kwargs["print_on_silent_log"]


def test_pyocd_driver_load(target, mocker):
    r = USBDebugger(target, name=None, match={"sys_name": "1-12"})
    r.avail = True
    d = PyOCDDriver(target, name=None)
    target.activate(d)

    check_output_mock = mocker.patch("labgrid.util.helper.processwrapper.check_output")

    d.load(__file__)

    check_output_mock.assert_called_once()
    cmd = check_output_mock.call_args.kwargs["command"]
    assert cmd == ["pyocd", "load", "--no-config", "-e", "sector", __file__]
    assert check_output_mock.call_args.kwargs["print_on_silent_log"]


def test_pyocd_load_error_on_missing_file(target, mocker):
    r = USBDebugger(target, name=None, match={"sys_name": "1-12"})
    r.avail = True
    d = PyOCDDriver(target, name=None)
    target.activate(d)

    check_output_mock = mocker.patch("labgrid.util.helper.processwrapper.check_output")

    with pytest.raises(FileNotFoundError):
        d.load()

    check_output_mock.assert_not_called()


def test_pyocd_load_error_on_missing_target_env(target, mocker):
    r = USBDebugger(target, name=None, match={"sys_name": "1-12"})
    r.avail = True
    d = PyOCDDriver(target, name=None, image="test")
    target.activate(d)

    check_output_mock = mocker.patch("labgrid.util.helper.processwrapper.check_output")

    with pytest.raises(FileNotFoundError):
        d.load()

    check_output_mock.assert_not_called()


def test_pyocd_load_image_on_missing_file(tmpdir, mocker):
    p = tmpdir.join("config.yaml")
    p.write(f"""
        images:
          test: {__file__}
        """)
    env = Environment(str(p))
    target = Target("test", env=env)
    r = USBDebugger(target, name=None, match={"sys_name": "1-12"})
    r.avail = True
    d = PyOCDDriver(target, name=None, image="test")
    target.activate(d)

    check_output_mock = mocker.patch("labgrid.util.helper.processwrapper.check_output")

    d.load()

    check_output_mock.assert_called_once()
    cmd = check_output_mock.call_args.kwargs["command"]
    assert cmd[0] == "pyocd"
    assert cmd[1] == "load"
    assert cmd[-1] == __file__


@pytest.mark.parametrize(
    "args,params,missing",
    [
        ({"serial": LABGRID_TEST_SERIAL}, ["--uid", LABGRID_TEST_SERIAL], []),
        ({"target_name": LABGRID_TARGET}, ["--target", LABGRID_TARGET], []),
        ({"config": __file__}, ["--config", __file__], ["--no-config"]),
        # make sure, that it is not the file loaded argument
        ({}, ["--no-config"], [__file__]),
        ({"frequency": "400000"}, ["--frequency", "400000"], []),
        # load commands should take precedens
        ({"frequency": "400000", "load_commands": ["--frequency", "100"]}, ["--frequency", "100"], ["400000"]),
        # even as a string instead of array
        ({"frequency": "400000", "load_commands": "--frequency 100"}, ["--frequency", "100"], ["400000"]),
        # load commands overwrite default load commands
        ({"load_commands": ["--frequency", "100"]}, ["--frequency", "100"], ["-e", "sector"]),
    ],
)
def test_pyocd_driver_params_load(target, mocker, args, params, missing):
    r = USBDebugger(target, name=None, match={"sys_name": "1-12"})
    r.avail = True
    d = PyOCDDriver(target, name=None, **args)
    target.activate(d)

    check_output_mock = mocker.patch("labgrid.util.helper.processwrapper.check_output")

    d.load(__file__)

    check_output_mock.assert_called_once()
    cmd = check_output_mock.call_args.kwargs["command"]
    assert cmd[0] == "pyocd"
    assert cmd[1] == "load"
    assert cmd[-1] == __file__
    for p in params:
        assert p in cmd[2:-1]
    for m in missing:
        assert m not in cmd[2:-1]
    assert check_output_mock.call_args.kwargs["print_on_silent_log"]


@pytest.mark.parametrize(
    "args,params,missing",
    [
        ({"serial": LABGRID_TEST_SERIAL}, ["--uid", LABGRID_TEST_SERIAL], []),
        ({"target_name": LABGRID_TARGET}, ["--target", LABGRID_TARGET], []),
        ({"config": __file__}, ["--config", __file__], ["--no-config"]),
        ({"frequency": "400000"}, ["--frequency", "400000"], []),
        # load commands not be used
        ({"frequency": "400000", "load_commands": ["--frequency", "100"]}, ["--frequency", "400000"], ["100"]),
        ({"load_commands": ["--frequency", "100"]}, [], ["--frequency", "100"]),
    ],
)
def test_pyocd_driver_params_reset(tmpdir, mocker, args, params, missing):
    p = tmpdir.join("config.yaml")
    p.write("""
        dict: {}
        """)
    env = Environment(str(p))
    target = Target("test", env=env)
    r = USBDebugger(target, name=None, match={"sys_name": "1-12"})
    r.avail = True
    d = PyOCDDriver(target, name=None, **args)
    target.activate(d)

    check_output_mock = mocker.patch("labgrid.util.helper.processwrapper.check_output")

    d.reset()

    check_output_mock.assert_called_once()
    cmd = check_output_mock.call_args.kwargs["command"]
    assert cmd[0] == "pyocd"
    assert cmd[1] == "reset"
    for p in params:
        assert p in cmd[2:]
    for m in missing:
        assert m not in cmd[2:]
    assert check_output_mock.call_args.kwargs["print_on_silent_log"]


def test_pyocd_respects_env_tool(mocker, tmpdir):
    p = tmpdir.join("config.yaml")
    p.write(f"""
        tools:
          pyocd: {LABGRID_TOOL_CMD}
        """)
    env = Environment(str(p))
    target = Target("test", env=env)
    r = USBDebugger(target, name=None, match={"sys_name": "1-12"})
    r.avail = True
    d = PyOCDDriver(target, name=None)
    target.activate(d)

    assert d.tool == LABGRID_TOOL_CMD

    # Make sure, that the tool actually is used in command
    check_output_mock = mocker.patch("labgrid.util.helper.processwrapper.check_output")

    d.reset()

    check_output_mock.assert_called_once()
    cmd = check_output_mock.call_args.kwargs["command"]
    assert cmd[0] == LABGRID_TOOL_CMD
    assert cmd[1] == "reset"


def test_pyocd_respects_missing_env_tool(tmpdir):
    p = tmpdir.join("config.yaml")
    p.write(f"""
        tools:
          none: {LABGRID_TOOL_CMD}
        """)
    env = Environment(str(p))
    target = Target("test", env=env)
    r = USBDebugger(target, name=None, match={"sys_name": "1-12"})
    r.avail = True
    d = PyOCDDriver(target, name=None)
    target.activate(d)

    assert d.tool == "pyocd"
