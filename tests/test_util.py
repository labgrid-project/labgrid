import attr
import pytest

from labgrid.util import diff_dict, flat_dict, filter_dict

def test_diff_dict():
    dict_a = {"a": 1,
              "b": 2}
    dict_b = {"a": 1,
              "b": 3}
    gen = diff_dict(dict_a, dict_b)
    for res in gen:
        assert res[0] == 'b'
        assert res[1] == 2
        assert res[2] == 3

def test_flat_dict():
    dict_a = {"a":
              {"b": 3},
              "b": 2}
    res = flat_dict(dict_a)
    assert res == {"a.b": 3, "b": 2}

def test_filter_dict():
    @attr.s
    class A:
        foo = attr.ib()

    d_orig = {'foo': 1, 'bar': 2, 'baz': 3}

    with pytest.warns(None) as record:
        d_filtered = filter_dict(d_orig, A)
    assert not record
    assert d_filtered is not d_orig
    assert d_filtered == {'foo': 1}

    with pytest.warns(UserWarning) as record:
        d_filtered = filter_dict(d_orig, A, warn=True)
    assert len(record) == 2
    assert str(record[0].message) == "unsupported attribute 'bar' with value '2' for class 'A'"
    assert str(record[1].message) == "unsupported attribute 'baz' with value '3' for class 'A'"
    assert d_filtered is not d_orig
    assert d_filtered == {'foo': 1}
