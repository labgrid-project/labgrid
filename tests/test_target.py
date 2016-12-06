from labgrid import Target

def test_instanziation():
    t = Target("name")
    assert(isinstance(t, Target))
