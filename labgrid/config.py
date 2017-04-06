"""Config convenience class

This class encapsulates access functions to the environment configuration

"""
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
        """Resolve an absolute path

        Args:
            path (str): path to resolve

        Returns:
            str: the absolute path
        """
        path = os.path.expanduser(path)
        path = os.path.expandvars(path)
        if os.path.isabs(path):
            return path
        else:
            return os.path.join(self.base, path)

    def get_tool(self, tool):
        """Retrieve an entry from the tools subkey

        Args:
            tool (str): the tool to retrieve the path for

        Returns:
            str: path to the requested tools
        """
        try:
            path = str(self.data['tools'][tool])
            return self.resolve_path(path)
        except KeyError:
            return None

    def get_image_path(self, kind):
        """Retrieve an entry from the images subkey

        Args:
            kind (str): the kind of the image to retrieve the path for

        Returns:
            str: path to the image

        Raises:
            KeyError: if the requested image can not be found in the
                configuration
        """
        try:
            path = str(self.data['images'][kind])
            return self.resolve_path(path)
        except KeyError:
            logging.exception("no path configured for image {}".format(kind))
            raise

    def get_option(self, name, default=None):
        """Retrieve an entry from the options subkey

        Args:
            name (str): name of the option
            default (str): A default parameter in case the option can not be
                found

        Returns:
            str: value of the option or default parameter

        Raises:
            KeyError: if the requested image can not be found in the
                configuration
        """
        try:
            return str(self.data['options'][name])
        except KeyError:
            if default is None:
                logging.exception("no such option {}".format(name))
                raise
            else:
                return default

    def set_option(self, name, value):
        """Set an entry in the options subkey

        Args:
            name (str): name of the option
            value (str): the new value
        """
        assert isinstance(value, str)
        self.data.setdefault('options', {})[name] = value

    def get_targets(self):
        return self.data.get('targets', {})
