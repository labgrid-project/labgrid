"""Config convenience class

This class encapsulates access functions to the environment configuration

"""
import os
from yaml import YAMLError
import attr

from .exceptions import NoConfigFoundError, InvalidConfigError
from .util.yaml import load, resolve_templates

@attr.s(eq=False)
class Config:
    filename = attr.ib(validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        # load and parse the yaml configuration file
        self.base = os.path.dirname(os.path.abspath(self.filename))
        try:
            with open(self.filename) as file:
                self.data = load(file)
        except FileNotFoundError:
            raise NoConfigFoundError(
                "configuration file '{}' could not be found".format(self.filename)
            )
        except YAMLError as err:
            raise InvalidConfigError("Error in configuration file: {}".format(err))

        substitutions = {
            'BASE': self.base,
        }
        # map LG_* variables from OS environment into YAML config file using !template $LG_*
        # Only map LG_*, to protect from weird things in environment
        for x in os.environ.keys():
            if x.startswith("LG_"):
                substitutions[x] = os.environ[x]

        try:
            resolve_templates(self.data, substitutions)
        except KeyError as e:
            raise InvalidConfigError(
                "configuration file '{}' refers to unknown variable '{}'".format(
                    self.filename, e.args[0]
                )
            )
        except ValueError as e:
            raise InvalidConfigError(
                "configuration file '{}' is invalid: {}".format(
                    self.filename, e
                )
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
        except KeyError as e:
            raise KeyError("no path configured for image '{}'".format(kind)) from e

    def get_path(self, kind):
        """Retrieve an entry from the paths subkey

        Args:
            kind (str): the type of path to retrieve the path for

        Returns:
            str: path to the path

        Raises:
            KeyError: if the requested image can not be found in the
                configuration
        """
        try:
            path = str(self.data['paths'][kind])
            return self.resolve_path(path)
        except KeyError as e:
            raise KeyError("no path configured for path '{}'".format(kind)) from e

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
                raise KeyError("no option '{}' found in configuration".format(name))
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

    def get_imports(self):
        """Helper function that returns the list of all imports

        Returns:
            List: List of files which should be imported
        """
        imports = []

        if isinstance(self.data.get('imports', []), str):
            raise KeyError("imports needs to be list not string")
        for user_import in self.data.get('imports', []):
            # Try to resolve the import to a .py file
            import_path = self.resolve_path(user_import)
            if import_path.endswith('.py'):
                imports.append(import_path)
            else:
                # Fallback to importing module if not a .py file path
                imports.append(user_import)

        return imports

    def get_paths(self):
        """Helper function that returns the subdict of all paths

        Returns:
            Dict: Dictionary containing all path definitions
        """
        paths = {}

        for name, path in self.data.get('paths', {}).items():
            paths[name] = self.resolve_path(path)

        return paths

    def get_images(self):
        """Helper function that returns the subdict of all images

        Returns:
            Dict: Dictionary containing all image definitions
        """
        images = {}

        for name, image in self.data.get('images', {}).items():
            images[name] = self.resolve_path(image)

        return images

    def get_features(self):
        return set(self.data.get('features', {}))
