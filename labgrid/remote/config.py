from pprint import pprint

import os

import attr
import jinja2

from ..util.yaml import load
from ..exceptions import NoConfigFoundError


@attr.s(eq=False)
class ResourceConfig:
    filename = attr.ib(validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(os.path.dirname(self.filename)),
            line_statement_prefix='#',
            line_comment_prefix='##',
        )
        try:
            with open(self.filename) as file:
                template = env.from_string(file.read())
        except FileNotFoundError:
            raise NoConfigFoundError(
                f"{self.filename} could not be found"
            )
        rendered = template.render(env=os.environ)
        pprint(('rendered', rendered))
        self.data = load(rendered)
        pprint(('loaded', self.data))
