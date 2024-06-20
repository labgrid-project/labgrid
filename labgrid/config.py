"""Config convenience class

This class encapsulates access functions to the environment configuration

"""
import os
import warnings
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
                f"configuration file '{self.filename}' could not be found"
            )
        except YAMLError as err:
            raise InvalidConfigError(f"Error in configuration file: {err}")

        if self.data is None:
            raise InvalidConfigError("Configuration file is empty")

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
                f"configuration file '{self.filename}' refers to unknown variable '{e.args[0]}'"
            )
        except ValueError as e:
            raise InvalidConfigError(
                f"configuration file '{self.filename}' is invalid: {e}"
            )

        if self.get_option("crossbar_url", ""):
            warnings.warn("Ignored option 'crossbar_url' in config, use 'coordinator_address' instead", UserWarning)

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

    def resolve_path_str_or_list(self, path):
        """
        Resolves a single path or multiple paths. Always returns a list (containing a single or
        multiple resolved paths).

        Args:
            path (str, list): path(s) to resolve

        Returns:
            list: absolute path(s

        Raises:
            TypeError: if input is neither str nor list
        """
        if isinstance(path, str):
            return [self.resolve_path(path)]
        elif isinstance(path, list):
            return [self.resolve_path(p) for p in path]

        raise TypeError("path must be str or list")

    def get_tool(self, tool):
        """Retrieve an entry from the tools subkey

        Args:
            tool (str): the tool to retrieve the path for

        Returns:
            str: path to the requested tools
        """
        try:
            path = str(self.data['tools'][tool])
        except KeyError:
            return tool

        resolved = self.resolve_path(path)
        if os.path.exists(resolved):
            return resolved

        return path

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
            raise KeyError(f"no path configured for image '{kind}'") from e

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
            raise KeyError(f"no path configured for path '{kind}'") from e

    def get_option(self, name, default=None):
        """Retrieve an entry from the options subkey

        Args:
            name (str): name of the option
            default (any): A default parameter in case the option can not be
                found

        Returns:
            any: value of the option or default parameter

        Raises:
            KeyError: if the requested image can not be found in the
                configuration
        """
        try:
            return self.data['options'][name]
        except KeyError:
            if default is None:
                raise KeyError(f"no option '{name}' found in configuration")

            return default

    def set_option(self, name, value):
        """Set an entry in the options subkey

        Args:
            name (str): name of the option
            value (any): the new value
        """
        self.data.setdefault('options', {})[name] = value

    def get_target_option(self, target, name, default=None):
        """Retrieve an entry from the options subkey under the specified target
           subkey

        Args:
            target (str): name of the target
            name (str): name of the option
            default (any): A default parameter in case the option can not be
                found

        Returns:
            any: value of the option or default parameter

        Raises:
            KeyError: if the requested key can not be found in the
                configuration, or if the target can not be found in the
                configuration.
        """
        if target not in self.data['targets']:
            raise KeyError(f"No target '{target}' found in configuration")

        try:
            return self.data['targets'][target]['options'][name]
        except (KeyError, TypeError):
            # Empty target declarations become None in the target dict, hence
            # TypeError when we try to subscript it.
            if default is None:
                raise KeyError(f"No option '{name}' found in configuration for target '{target}'")
            else:
                return default

    def set_target_option(self, target, name, value):
        """Set an entry in the options subkey under the specified target subkey

        Args:
            target (str): name of the target
            name (str): name of the option
            value (any): the new value

        Raises:
            KeyError: if the requested target can not be found in the
                configuration
        """
        assert isinstance(target, str)
        assert isinstance(name, str)

        if target not in self.data['targets']:
            raise KeyError(f"No target '{target}' found in configuration")

        # Empty targets become None in the target dict. Delete it to enable
        # setdefault below to work on the actual default instead of None.
        if self.data['targets'][target] is None:
            del self.data['targets'][target]

        trg = self.data['targets'].setdefault(target, {})
        trg.setdefault('options', {})[name] = value

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
