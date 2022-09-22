import pytest
import subprocess
import textwrap

from labgrid.util.helper import processwrapper


def test_processwrapper_passes():
    processwrapper.check_output(["true"])


def test_processwrapper_fails():
    with pytest.raises(subprocess.CalledProcessError):
        processwrapper.check_output(["false"])


def test_processwrapper_output(tmpdir):
    content = textwrap.dedent(
        """\
        A
        B
        C
        """
    )

    tmpfile = tmpdir.join("output.txt")
    tmpfile.write(content)

    output = processwrapper.check_output(["cat", str(tmpfile)])

    assert output.decode("utf-8") == content


def test_processwrapper_input():
    content = textwrap.dedent(
        """\
        A
        B
        C
        """
    )

    output = processwrapper.check_output(["cat", "-"], input=content.encode("utf-8"))

    assert output.decode("utf-8") == content


def test_processwrapper_empty_input():
    output = processwrapper.check_output(["cat", "-"], input=b"")
    assert output.decode("utf-8") == ""
