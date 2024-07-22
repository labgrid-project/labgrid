"""The autoinstall.main module runs an installation script automatically on multiple targets."""
import ast
import argparse
import logging
import multiprocessing
import textwrap
from time import sleep

from .. import Environment, target_factory
from ..logging import basicConfig, StepLogger
from ..exceptions import NoResourceFoundError


class Handler(multiprocessing.Process):
    def __init__(self, env, args, name):
        super().__init__(name=name)
        self.env = env
        self.args = args
        self.config = env.config
        self.name = name

        self.context = {
            'name': self.name,
            'env': self.env,
            'config': self.config,
        }
        self.context.update(target_factory.resources)
        self.context.update(target_factory.drivers)

    def _get_function(self, name, context):
        snippet = self.config.data['autoinstall'].get(name)
        if not snippet:
            return None

        code = f"def {name}():\n{textwrap.indent(snippet, ' ')}"
        tree = ast.parse(code, filename=self.env.config_file)
        ast.increment_lineno(tree, snippet.start_mark.line)
        co = compile(tree, filename=self.env.config_file, mode='exec')

        stage = {}
        exec(co, context, stage)  # pylint: disable=exec-used
        return stage[name]

    def _get_setup_function(self):
        context = self.context
        context['log'] = self.log.getChild('setup')
        setup = self._get_function('setup', self.context)
        if setup is None:
            def setup():
                pass
        return setup

    def _get_handler_function(self):
        context = self.context.copy()
        context['log'] = self.log.getChild('handler')
        handler = self._get_function('handler', context)
        return handler

    def _get_initial_resource(self):
        cls = self.config.data['autoinstall'].get('initial-resource')
        if not cls:
            return None

        return self.target.get_resource(self.context[cls], wait_avail=False)

    def run(self):
        self.log = logging.getLogger(self.name)
        self.log.info("creating new handler (PID %s)", self.pid)

        try:
            self.target = self.env.get_target(self.name)
            self.context['target'] = self.target
            if self.target is None:
                raise KeyError
        except Exception:  # pylint: disable=broad-except
            self.log.exception("target creation failed")
            return

        self.setup = self._get_setup_function()
        self.setup()

        self.initial_resource = self._get_initial_resource()

        self.handler = self._get_handler_function()
        while self.run_once():
            sleep(3)

    def run_once(self):
        try:
            if self.initial_resource:
                self.log.info("waiting until %s is available",
                              self.initial_resource.display_name)
                while True:
                    self.target.update_resources()
                    if self.initial_resource.avail:
                        break
                    sleep(0.25)

            self.log.info("starting handler")
            self.target.update_resources()
            result = self.handler()
            if result is not None:
                self.log.warning("unexpected return value from handler: %s",
                                 repr(result))
            self.log.info("completed handler")

            if self.initial_resource:
                self.log.info("waiting until %s is unavailable",
                              self.initial_resource.display_name)
                while True:
                    self.target.update_resources()
                    if not self.initial_resource.avail:
                        break
                    sleep(0.25)

        except NoResourceFoundError as e:
            if e.filter and len(e.filter) > 1:
                self.log.warning("resources %s not found, restarting",
                                 e.filter)
            elif e.filter:
                self.log.warning("resource %s not found, restarting",
                                 next(iter(e.filter)))
            else:
                self.log.warning("resource not found, restarting")
        except Exception:  # pylint: disable=broad-except
            self.log.exception("handler failed")
            return False

        if self.args.once:
            self.log.info("stopping handler (--once)")
            return False

        return True


class Manager:
    def __init__(self, env, args):
        self.env = env
        self.args = args
        self.config = env.config
        self.log = logging.getLogger("manager")

    def configure(self):
        if not 'autoinstall' in self.env.config.data:
            self.log.error("no 'autoinstall' section found in '%s'",
                           self.env.config_file)
            return False

        if not 'handler' in self.env.config.data['autoinstall']:
            self.log.error("no 'handler' definition found in '%s'",
                           self.env.config_file)
            return False

        self.handlers = {}
        for target_name in self.config.data.get('targets', {}).keys():
            self.handlers[target_name] = Handler(self.env, self.args,
                                                 target_name)

        if not self.handlers:
            self.log.error("no targets found in '%s'",
                           self.env.config_file)
            return False

        return True

    def start(self):
        for i, handler in enumerate(self.handlers.values()):
            if i:
                # give previous handler some time to start
                sleep(3)
            handler.daemon = True
            handler.start()

    def join(self):
        for handler in self.handlers.values():
            handler.join()

def main():
    basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-d',
        '--debug',
        action='store_true',
        default=False,
        help="enable debug mode"
    )
    parser.add_argument(
        '--once',
        action='store_true',
        default=False,
        help="handle each target only once"
    )
    parser.add_argument(
        'config',
        type=str,
        help="config file"
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    env = Environment(config_file=args.config)

    StepLogger.start()

    manager = Manager(env, args)
    if not manager.configure():
        exit(1)
    manager.start()
    manager.join()


if __name__ == "__main__":
    main()
