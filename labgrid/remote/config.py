from pprint import pprint

import glob
import os

import attr
import jinja2

from ..util.yaml import load
from ..exceptions import NoConfigFoundError


@attr.s(eq=False)
class ResourceConfig:
    filename = attr.ib(validator=attr.validators.instance_of(str))
    template_env = attr.ib(default=attr.Factory(dict), validator=attr.validators.instance_of(dict))

    def __attrs_post_init__(self):
        _dirname = os.path.dirname(self.filename)
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(_dirname),
            line_statement_prefix="#",
            line_comment_prefix="##",
        )
        try:
            template = env.get_template(os.path.basename(self.filename))
        except jinja2.TemplateNotFound:
            raise NoConfigFoundError(f"{self.filename} could not be found")
        drop_ins = [
            os.path.relpath(p, _dirname) for p in sorted(glob.glob(os.path.join(self.filename + ".d", "*.yaml")))
        ]

        self.template_env["drop_ins"] = drop_ins
        rendered = template.render(self.template_env)
        pprint(("rendered", rendered))
        self.data = load(rendered)
        pprint(("loaded", self.data))
