import pytest

from labgrid.config import Config
from labgrid.exceptions import InvalidConfigError

def test_get_target_option(tmpdir):
    p = tmpdir.join("config.yaml")
    p.write(
        """
        targets:
          main:
            options:
              foo: bar
              spam: eggs
        """
    )
    c = Config(str(p))
    assert c.get_target_option("main", "spam") == "eggs"

    with pytest.raises(KeyError) as err:
        c.get_target_option("main", "blah")
    assert "No option" in str(err)

    with pytest.raises(KeyError) as err:
        c.get_target_option("nonexist", "spam")
    assert "No target" in str(err)

def test_set_target_option(tmpdir):
    p = tmpdir.join("config.yaml")
    p.write(
        """
        targets:
          main:
        """
    )
    c = Config(str(p))

    with pytest.raises(KeyError) as err:
        c.get_target_option("main", "spam")
    assert "No option" in str(err)

    c.set_target_option("main", "spam", "eggs")
    assert c.get_target_option("main", "spam") == "eggs"

def test_template(tmpdir):
    p = tmpdir.join("config.yaml")
    p.write(
        """
        dict:
          list:
          - a
          - b
          - !template $BASE
          string: !template ${BASE}/suffix
        """
    )
    c = Config(str(p))
    assert 'a' in c.data['dict']['list']
    assert c.data['dict']['list'][2] == str(tmpdir)
    assert c.data['dict']['string'] == str(tmpdir)+'/suffix'

def test_template_bad_placeholder(tmpdir):
    p = tmpdir.join("config.yaml")
    p.write(
        """
        string: !template $
        """
    )
    with pytest.raises(InvalidConfigError) as excinfo:
        Config(str(p))
    assert "is invalid" in excinfo.value.msg
    assert "template string" in excinfo.value.msg

def test_template_bad_key(tmpdir):
    p = tmpdir.join("config.yaml")
    p.write(
        """
        string: !template ${INVALID}
        """
    )
    with pytest.raises(InvalidConfigError) as excinfo:
        Config(str(p))
    assert "unknown variable" in excinfo.value.msg
