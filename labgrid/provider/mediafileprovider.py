import attr

from .fileprovider import FileProvider


@attr.s
class MediaFileProvider(FileProvider):
    groups = attr.ib(default={}, validator=attr.validators.instance_of(dict))

    def _add_file(self, name: str, remote_path, local_path):
        group = self.groups.setdefault(name, {})
        group[remote_path] = local_path

    def get(self, name):
        return self.groups[name]

    def list(self):
        return list(self.groups.keys())
