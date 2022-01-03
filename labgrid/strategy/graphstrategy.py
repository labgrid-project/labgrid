from tempfile import TemporaryDirectory
import os

from .common import Strategy, StrategyError
from ..step import step

__all__ = [
    'InvalidGraphStrategyError',
    'GraphStrategyRuntimeError',
    'GraphStrategyError',
    'GraphStrategy',
]


class GraphStrategyError(StrategyError):
    """Generic GraphStrategy error"""
    pass


class InvalidGraphStrategyError(GraphStrategyError):
    """GraphStrategy error raised during initialization of broken strategies"""
    pass


class GraphStrategyRuntimeError(GraphStrategyError):
    """GraphStrategy error raised during runtime when used in unintended ways"""
    pass


class GraphStrategy(Strategy):
    def __attrs_post_init__(self):
        super().__attrs_post_init__()

        self.__transition_running = False

        # find states
        self.states = {}

        for state_name in dir(self):
            if not state_name.startswith('state_'):
                continue

            method = getattr(self, state_name)

            if not callable(method):
                raise InvalidGraphStrategyError(
                    f"GraphStrategy state '{state_name}' is not callable"
                )

            state_name = '_'.join(state_name.split('_')[1:])

            self.states[state_name] = {
                'method': step()(method),
                'dependencies': getattr(method, 'dependencies', []),
            }

        if not self.states:
            raise InvalidGraphStrategyError(
                'GraphStrategies without states are invalid')

        # check dependencies
        state_names = self.states.keys()

        for state_name in state_names:
            for dependency in self.states[state_name]['dependencies']:
                if dependency not in state_names:
                    raise InvalidGraphStrategyError(
                        f"{state_name}: State '{dependency}' is unknown. State names are: {', '.join(state_names)}"  # pylint: disable=line-too-long
                    )

        # find root state
        root_states = [k for k, v in self.states.items()
                       if not v['dependencies']]

        if not root_states:
            raise InvalidGraphStrategyError(
                'GraphStrategies without root state are invalid')

        # check check if exact one root state is defined
        if len(root_states) > 1:
            raise InvalidGraphStrategyError(
                'Only one root state supported. Defined root states: {}'.format(  # NOQA
                    ', '.join(root_states),
                )
            )

        self.root_state = root_states[0]
        self.invalidate()

        # setup grahviz cache
        self._graph_cache = {
            'tempdir': None,
            'graph': None,
            'path': self.path,
        }

    def invalidate(self):
        """
        Marks the path to the current state as out-of-date. Subsequent transition() calls will
        start from the root state.
        Will be called if exceptions in state methods occur.
        """
        self.path = []

        # deactivate all drivers to restore initial state
        self.target.deactivate_all_drivers()

    @step(args=['state'])
    def transition(self, state, via=None):
        """
        Computes the path from root state (via "via" state, if given) to given state.
        If the computed path is fully incremental to the path executed previously, only the state's
        methods relative to the previous path are executed. Otherwise all states' methods of the
        computed path (starting from the root node) are executed.
        """
        if not isinstance(via, (type(None), list)):
            raise GraphStrategyRuntimeError(
                "'via' has to be a list or None"
                )
        # for use with labgrid-client -s, if only state is set, try to extract
        # the via states
        if ':' in state and via is None:
            state, via = state.split(':')
            via = via.split(',')
        via = via or []
        try:
            # check if another transition is running
            if self.__transition_running:
                raise GraphStrategyRuntimeError(
                    'Another transition is already running')

            # lock transition
            self.__transition_running = True

            # check if state is known
            if state not in self.states:
                raise GraphStrategyRuntimeError(
                    f"Unknown state '{state}'. State names are: {', '.join(self.states.keys())}"
                )

            # find path
            abs_path = self.find_abs_path(state, via=via)

            if abs_path == self.path:
                return []

            path = self.find_rel_path(abs_path)

            # run state methods
            for state_name in path:
                if state_name == self.root_state:
                    # deactivate drivers before root state method is called
                    self.target.deactivate_all_drivers()

                try:
                    self.states[state_name]['method']()

                except Exception:
                    self.invalidate()

                    raise

            self.path = abs_path

            return path

        finally:
            # unlock transition
            self.__transition_running = False

    def find_abs_path(self, state, via=None):
        """
        Computes the absolute path from the root state, via "via" (if given), to the given state.
        """
        via = via or []
        via = via[::-1]
        path = [state, ]
        current_state = self.states[state]

        for via_state in via:
            if via_state not in self.states.keys():
                raise GraphStrategyRuntimeError(
                    f"Unknown state '{via_state}' in via. State names are: {', '.join(self.states.keys())}"  # pylint: disable=line-too-long
                )

        while current_state['dependencies']:
            next_state = current_state['dependencies'][0]

            for i in via:
                if i in current_state['dependencies']:
                    via.remove(i)
                    next_state = i

            path.insert(0, next_state)
            current_state = self.states[next_state]

        # no via states should be left now
        if via:
            raise GraphStrategyRuntimeError(
                "Path to '{}' via {} does not exist".format(
                    state, ', '.join(["'{}'".format(v) for v in via])
                )
            )


        return path

    def find_rel_path(self, path):
        """
        If the given path is fully incremental to the path executed before, returns the path
        relative to the previously executed one.
        Otherwise the given path is returned.
        """
        if path[:-(len(path) - len(self.path))] == self.path:
            return path[len(self.path):]

        return path

    @property
    def graph(self):
        """
        Returns a graphviz.Digraph for the directed graph the inheriting strategy represents.

        The graph can be rendered with:
        ``mystrategy.graph.render("filename") # renders to filename.png``
        """
        from graphviz import Digraph

        if(self._graph_cache['graph'] and
           self._graph_cache['path'] == self.path):
            return self._graph_cache['graph']

        if not self._graph_cache['tempdir']:
            self._graph_cache['tempdir'] = TemporaryDirectory()

        dg = Digraph(
            filename=os.path.join(self._graph_cache['tempdir'].name, 'graph'),
            format='png',
        )

        edges = []

        dg.attr('node', style='filled', fillcolor='lightblue2', penwidth='1')
        dg.attr('edge', style='solid')

        for index, node_name in enumerate(self.path):
            attrs = {}

            if node_name == self.path[-1]:
                attrs = {'penwidth': '2'}

            dg.node(node_name, **attrs)

            if index < len(self.path) - 1:
                edges.append((node_name, self.path[index + 1], ))
                dg.edge(*edges[-1])

        dg.attr('node', style='filled', color='lightgrey',
                fillcolor='lightgrey')

        dg.attr('edge', style='dashed', arrowhead='empty')

        for node_name in self.states:
            if node_name not in self.path:
                dg.node(node_name)

            for edge in self.states[node_name]['dependencies']:
                if (edge, node_name, ) in edges:
                    continue

                dg.edge(edge, node_name)

        self._graph_cache['graph'] = dg

        return dg

    @classmethod
    def depends(cls, *dependencies):
        """``@depends`` decorator used to list states the decorated state directly depends on."""
        def decorator(function):
            function.dependencies = list(dependencies)

            return function

        return decorator
