import attr
import os

from .util.yaml import load


@attr.s
class Config:
    filename = attr.ib(validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        self.base = os.path.dirname(self.filename)
        try:
            with open(self.filename) as file:
                self.data = load(file)
        except FileNotFoundError:
            raise NoConfigFoundError(
                "{} could not be found".format(self.filename)
            )

    def resolve_path(self, path):
        if os.path.isabs(path):
            return path
        else:
            return os.path.join(self.base, path)

    def get_tool(self, tool):
        try:
            path = str(self.data['tools'][tool])
            return self.resolve_path(path)
        except KeyError:
            return None

    def get_image_path(self, kind):
        try:
            path = str(self.data['images'][kind])
            return self.resolve_path(path)
        except KeyError:
            logging.exception("no path configured for image {}".format(kind))
            raise

    def get_option(self, name, default=None):
        try:
            return str(self.data['options'][name])
        except KeyError:
            if default is None:
                logging.exception("no such option {}".format(name))
                raise
            else:
                return default

    def get_targets(self):
        return self.data.get('targets', {})
