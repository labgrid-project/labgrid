from collections import OrderedDict, UserString

import pytest
import yaml

from labgrid.util.yaml import *


def test_default_loader():
    """Importing labgrid should not modify the default loaders"""
    doc = """
    foo: |
      multi
      line
    bar: False
    """

    data = yaml.load(doc, Loader=yaml.SafeLoader)
    assert type(data) == dict
    assert type(data["foo"]) == str

    data = yaml.load(doc, Loader=yaml.FullLoader)
    assert type(data) == dict
    assert type(data["foo"]) == str

    data = yaml.load(doc, Loader=yaml.Loader)
    assert type(data) == dict
    assert type(data["foo"]) == str


def test_labgrid_loader():
    doc = """
    foo: |
      multi
      line
    bar: False
    """
    data = load(doc)
    assert type(data) == OrderedDict
    assert type(data["foo"]) == UserString
    assert data["foo"].start_mark.line == 1
    assert data["foo"].end_mark.line == 4


def test_default_dumper():
    """Importing labgrid should not modify the default dumpers"""
    data = OrderedDict([])
    assert "!!python/object/apply:collections.OrderedDict\n- []\n" == yaml.dump(data, Dumper=yaml.Dumper)
    with pytest.raises(yaml.representer.RepresenterError):
        yaml.dump(data, Dumper=yaml.SafeDumper)


def test_labgrid_dumper():
    data = OrderedDict([])
    doc = dump(data)
    assert "{}\n" == doc
