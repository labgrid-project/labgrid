from collections import OrderedDict

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
              str: test
              list: [1, 2, 3]
              dict:
                a: 1
                b: 2
              bool: False
              int: 0x20
              float: 3.14
              none: null
        """
    )
    c = Config(str(p))
    assert c.get_target_option("main", "str") == "test"
    assert c.get_target_option("main", "list") == [1, 2, 3]
    assert c.get_target_option("main", "dict") == OrderedDict([('a', 1), ('b', 2)])
    assert c.get_target_option("main", "bool") is False
    assert c.get_target_option("main", "int") == 0x20
    assert c.get_target_option("main", "float") == 3.14
    assert c.get_target_option("main", "none") is None

    with pytest.raises(KeyError) as err:
        c.get_target_option("main", "blah")
    assert "No option" in str(err)

    with pytest.raises(KeyError) as err:
        c.get_target_option("nonexist", "str")
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

    obj = object()
    c.set_target_option("main", "obj", obj)
    assert c.get_target_option("main", "obj") is obj

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

def test_includes(tmpdir):
    a = tmpdir.join("a.yaml")
    b = tmpdir.join("b.yaml")
    c1 = tmpdir.join("c1.yaml")
    c2 = tmpdir.join("c2.yaml")
    a.write(
        """
        targets:
          main:
            options:
              foo: bar
              spam: apple
        includes:
            - !include %s
        """ % (b)
    )
    b.write(
        """
        targets:
          main:
            options:
              foo: bar
              spam: banana
        includes:
            - !include %s
            - !include %s
        """ % (c1,c2)
    )

    c1.write(
        """
        targets:
          main:
            options:
              foo: bar
              spam: pinapple
              blub: bla
        """
    )

    c2.write(
        """
        targets:
          main:
            options:
              foo: bar
              spam: orange
              blub: bla
        """
    )

    d = Config(str(a))

    assert d.get_target_option("main", "spam") == "orange"
