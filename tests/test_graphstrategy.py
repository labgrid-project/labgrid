import pytest


@pytest.fixture
def graph_strategy(target):
    from labgrid.strategy import GraphStrategy

    class TestStrategy(GraphStrategy):
        def state_Root(self):
            pass

        @GraphStrategy.depends('Root')
        def state_A1(self):
            pass

        @GraphStrategy.depends('Root')
        def state_A2(self):
            pass

        @GraphStrategy.depends('A1', 'A2')
        def state_B(self):
            pass

        @GraphStrategy.depends('B')
        def state_C1(self):
            pass

        @GraphStrategy.depends('B')
        def state_C2(self):
            pass

        @GraphStrategy.depends('C1', 'C2')
        def state_D(self):
            pass

    return TestStrategy(target, 'strategy')


# api tests ###################################################################
@pytest.mark.dependency
def test_fixture(graph_strategy, target):
    # test root state
    assert graph_strategy.root_state == 'Root'

    # test path
    assert graph_strategy.path == []

    # test state discovering
    state_names = sorted(list(graph_strategy.states.keys()))
    expected_state_names = ['A1', 'A2', 'B', 'C1', 'C2', 'D', 'Root']

    assert state_names == expected_state_names


@pytest.mark.dependency(depends=['test_fixture'])
def test_strategy_without_states(target):
    from labgrid.strategy import GraphStrategy, InvalidGraphStrategyError

    class TestStrategy(GraphStrategy):
        pass

    with pytest.raises(InvalidGraphStrategyError) as e:
        TestStrategy(target, 'strategy')

    assert e.value.msg == 'GraphStrategies without states are invalid'


@pytest.mark.dependency(depends=['test_fixture'])
def test_strategy_without_root_state(target):
    from labgrid.strategy import GraphStrategy, InvalidGraphStrategyError

    class TestStrategy(GraphStrategy):
        @GraphStrategy.depends('B')
        def state_A(self):
            pass

        @GraphStrategy.depends('A')
        def state_B(self):
            pass

    with pytest.raises(InvalidGraphStrategyError) as e:
        TestStrategy(target, 'strategy')

    assert e.value.msg == 'GraphStrategies without root state are invalid'


@pytest.mark.dependency(depends=['test_fixture'])
def test_multiple_root_states(target):
    from labgrid.strategy import GraphStrategy, InvalidGraphStrategyError

    class TestStrategy(GraphStrategy):
        def state_Root(self):
            pass

        def state_Root2(self):
            pass

    with pytest.raises(InvalidGraphStrategyError) as e:
        TestStrategy(target, 'strategy')

    assert e.value.msg.startswith("Only one root state supported.")


@pytest.mark.dependency(depends=['test_fixture'])
def test_unknown_dependencies(target):
    from labgrid.strategy import GraphStrategy, InvalidGraphStrategyError

    class TestStrategy(GraphStrategy):
        def state_Root(self):
            pass

        @GraphStrategy.depends('Root')
        def state_A(self):
            pass

        @GraphStrategy.depends('Root', 'A', 'C')
        def state_B(self):
            pass

    with pytest.raises(InvalidGraphStrategyError) as e:
        TestStrategy(target, 'strategy')

    assert e.value.msg.startswith("B: State 'C' is unknown")


@pytest.mark.dependency(depends=['test_fixture'])
def test_strategy_with_uncallable_states(target):
    from labgrid.strategy import GraphStrategy, InvalidGraphStrategyError

    class TestStrategy(GraphStrategy):
        state_foo = 1

        def state_Root(self):
            pass

    with pytest.raises(InvalidGraphStrategyError) as e:
        TestStrategy(target, 'strategy')

    assert e.value.msg.startswith(
        "GraphStrategy state 'state_foo' is not callable")


@pytest.mark.dependency(name='api-works',
                        depends=[
                            'test_fixture',
                            'test_strategy_without_states',
                            'test_strategy_without_root_state',
                            'test_unknown_dependencies',
                            'test_strategy_with_uncallable_states',
                        ])
def test_api_works():
    pass


# functional tests ############################################################
@pytest.mark.dependency(depends=['api-works'])
def test_graphviz_graph(graph_strategy):
    pytest.importorskip("graphviz")
    graph_strategy.graph
    graph_strategy.graph  # trigger the caching branch in the graph code

    graph_strategy.path = ['Root', 'A1', 'B']  # fake a post transition graph
    graph_strategy.graph


@pytest.mark.dependency(depends=['api-works'])
def test_transition(graph_strategy):
    assert graph_strategy.transition('B') == ['Root', 'A1', 'B']
    assert graph_strategy.path == ['Root', 'A1', 'B']

    assert graph_strategy.transition('B') == []
    assert graph_strategy.path == ['Root', 'A1', 'B']


@pytest.mark.dependency(depends=['api-works', 'test_transition'])
def test_transition_to_unknown_state(graph_strategy):
    from labgrid.strategy import GraphStrategyRuntimeError

    with pytest.raises(GraphStrategyRuntimeError) as e:
        graph_strategy.transition('G')

    assert e.value.msg.startswith("Unknown state 'G'.")


@pytest.mark.dependency(depends=['api-works', 'test_transition'])
def test_interleaved_transitions(target):
    from labgrid.strategy import GraphStrategy, GraphStrategyRuntimeError

    class TestStrategy(GraphStrategy):
        def state_Root(self):
            pass

        @GraphStrategy.depends('Root')
        def state_A(self):
            self.transition('B')

        @GraphStrategy.depends('Root')
        def state_B(self):
            self.transition('A')

    strategy = TestStrategy(target, 'strategy')

    with pytest.raises(GraphStrategyRuntimeError) as e:
        strategy.transition('A')

    assert e.value.msg == 'Another transition is already running'


@pytest.mark.dependency(depends=['api-works', 'test_transition'])
def test_transition_via(graph_strategy):
    assert graph_strategy.transition('D', via=['A2']) == ['Root', 'A2', 'B', 'C1', 'D']
    assert graph_strategy.path == ['Root', 'A2', 'B', 'C1', 'D']

    graph_strategy.invalidate()

    assert graph_strategy.transition('D:A2') == ['Root', 'A2', 'B', 'C1', 'D']
    assert graph_strategy.path == ['Root', 'A2', 'B', 'C1', 'D']

    assert graph_strategy.transition('D:C2,A2') == ['Root', 'A2', 'B', 'C2', 'D']
    assert graph_strategy.path == ['Root', 'A2', 'B', 'C2', 'D']

@pytest.mark.dependency(depends=['api-works',
                                 'test_transition',
                                 'test_transition_via'])
def test_incremental_transition(graph_strategy):
    assert graph_strategy.transition('B') == ['Root', 'A1', 'B']
    assert graph_strategy.transition('D') == ['C1', 'D']

    graph_strategy.invalidate()

    assert graph_strategy.transition('B', via=['A2']) == ['Root', 'A2', 'B']
    assert graph_strategy.transition('D') == ['Root', 'A1', 'B', 'C1', 'D']


@pytest.mark.dependency(depends=['api-works', 'test_transition'])
def test_transition_error(target):
    from labgrid.strategy import GraphStrategy

    class TestStrategy(GraphStrategy):
        def state_Root(self):
            pass

        @GraphStrategy.depends('Root')
        def state_A(self):
            pass

        @GraphStrategy.depends('A')
        def state_B(self):
            raise Exception

    strategy = TestStrategy(target, 'strategy')

    strategy.transition('A')
    assert strategy.path == ['Root', 'A']

    with pytest.raises(Exception):
        strategy.transition('B')

    with pytest.raises(Exception):
        strategy.transition('B', via='B')

    assert strategy.path == []
