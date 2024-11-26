import logging
import os

import attr
import grpc
import pkg_resources

from .plugins_interceptors import DefaultAuthMetadataPlugin, DefaultServerInterceptor

DEFAULT_CERTIFICATE_PATH = "../certificates/server.crt"
DEFAULT_KEY_PATH = "../certificates/server.key"

@attr.s(eq=False)
class AuthenticationPluginError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))


def load_certificate_from_file(filepath):
    '''
    Loads certificate from file and returns it as bytes

    :raises FileNotFoundError: when a file with certificate cannot be found

    Args:
        filepath (str): The path to the file to load

    Returns:
        The content of the certificate file as bytes
    '''
    if filepath in (DEFAULT_CERTIFICATE_PATH, DEFAULT_KEY_PATH):
        logging.warn('Using default self-signed certificate or certificate key')

    real_path = os.path.join(os.path.dirname(__file__), filepath)

    if not os.path.exists(real_path):
        raise FileNotFoundError(f"File {real_path} not found")

    with open(real_path, "rb") as f:
        return f.read()


def get_auth_meta_plugin(plugin_name):
    '''
    Returns an instance of the grpc.AuthMetadataPlugin class specified by name
    passed as an input parameter.
    The plugin should be available via installed Python package.

    It is also possible to use the default plugin: DefaultAuthMetadataPlugin when
    the value of the input argument is 'default.

    :raises AuthenticationPluginError: when the plugin does not meet certain requirements

    Args:
        plugin_name (str): name of the authentication plugin used for the gRPC
            channel authentication/authorization purposes

    Returns:
        Instance of the grpc.AuthMetadataPlugin class
    '''
    instance = None

    if plugin_name != "default":

        for entry_point in pkg_resources.iter_entry_points('auth_plugin'):
            if entry_point.name == plugin_name:
                auth_metadata_plugin = entry_point.load()
                instance = auth_metadata_plugin()
                break

    else:
        instance = DefaultAuthMetadataPlugin()

    if not isinstance(instance, grpc.AuthMetadataPlugin):
        raise AuthenticationPluginError(f'Plugin: {plugin_name}'
                                        ' is not of grpc.AuthMetadataPlugin type')

    if not callable(instance):
        raise AuthenticationPluginError(f'Plugin: {plugin_name}'
                                        ' does not implement __call__ method')

    return instance


def get_server_interceptor(interceptor_name):
    '''
    Returns an instance of the grpc.ServerInterceptor class specified by name passed as an input parameter.

    The server interceptor should be available via installed Python package.

    It is also possible to use the default interceptor: DefaultServerInterceptor when
        the value of the input argument is 'default'.

    :raises AuthenticationPluginError: when the interceptor does not meet certain requirements
    '''
    instance = None

    if interceptor_name != "default":

        for entry_point in pkg_resources.iter_entry_points('server_interceptor'):
            if entry_point.name == interceptor_name:
                interceptor = entry_point.load()
                instance = interceptor()
                return instance

    else:
        instance = DefaultServerInterceptor()

    if not isinstance(instance, grpc.aio.ServerInterceptor):
        raise AuthenticationPluginError(f'Interceptor: {interceptor_name}'
                                        ' is not of grpc.aio.ServerInterceptor type')

    if not hasattr(instance, 'intercept_service'):
        raise AuthenticationPluginError(f'Interceptor: {interceptor_name}'
                                        ' does not implement intercept_servcice method')

    return instance
