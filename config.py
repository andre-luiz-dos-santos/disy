# coding=utf-8
import sys
import functools
import logging
import logging.config
import logging.handlers
import yaml
import adapter
import routeros

log = logging.getLogger(__name__)
config = {
    'map': {},
}
DEFAULT_LOGGING_CONFIGURATION = """
    root:
        level: DEBUG
        handlers: [syslog]
    handlers:
        console:
            class: logging.StreamHandler
            stream: ext://sys.stderr
            level: DEBUG
            formatter: detailed
        syslog:
            class: logging.handlers.SysLogHandler
            level: WARNING
            address: /dev/log
            formatter: detailed
    formatters:
        detailed:
            format: '%(filename)s:[%(funcName)s]:%(lineno)s %(message)s'
"""
DEFAULT_FILE_LOGGING_CONFIGURATION = """
    file:
        class: logging.handlers.WatchedFileHandler
        level: WARNING
        filename: {log_file}
        formatter: detailed
"""


def read() -> None:
    """
    Read configuration into global variable 'config'.
    """
    with open('disy.yml') as f:
        y = yaml.load(f) or {}
        config.update(y.items())


def setup_logging() -> None:
    """
    Setup the logging module.
    """
    try:
        d = config['log']
    except KeyError:
        # Load default logging configuration.
        d = yaml.load(DEFAULT_LOGGING_CONFIGURATION)
        # Log to stderr if it's a TTY.
        if sys.stderr.isatty():
            d['root']['handlers'].append('console')
        # Log to file if 'log_file' is set.
        if 'log_file' in config:
            s = DEFAULT_FILE_LOGGING_CONFIGURATION.format(**config)
            y = yaml.load(s)
            d['handlers'].update(y)
            d['root']['handlers'].extend(y.keys())
    # Default options.
    d.setdefault('version', 1)
    d.setdefault('disable_existing_loggers', False)
    logging.handlers.SysLogHandler.ident = 'disy: '
    # Let 'logging' configure itself.
    logging.config.dictConfig(d)


@functools.lru_cache(maxsize=None)
def build_routeros(name: str) -> routeros.Client:
    try:
        d = config['routeros'][name]
        args = ((d['address'], d.get('port', 8728)),
                d['username'], d['password'])
    except KeyError as err:
        log.critical("Missing configuration for RouterOS %s: %s", name, err)
        sys.exit(2)
    return routeros.Client(*args)


def build_directory_dict(name: str) -> adapter.Directory:
    try:
        d = config['map'][name]
        args = (d['path'],
                d.get('pattern', None))
    except KeyError as err:
        log.fatal("Missing configuration for directory %s: %s", name, err)
        sys.exit(2)
    return adapter.Directory(*args)


def build_address_list_dict(name: str) -> adapter.AddressList:
    try:
        d = config['map'][name]
        args = (build_routeros(d['routeros']),)
        kwargs = {k: v for k, v in d.items()
                  if k not in ('routeros',)}
    except KeyError as err:
        log.fatal("Missing configuration for RouterOS address-list %s: %s", name, err)
        sys.exit(2)
    return adapter.AddressList(*args, **kwargs)


def build_dict(name: str):
    try:
        dict_type = config['map'][name]['type']
    except KeyError:
        log.fatal("Missing type option for map %s", name)
        sys.exit(2)
    try:
        builder = globals()['build_' + dict_type + '_dict']
    except KeyError:
        log.error('Unknown dictionary type: %s', dict_type)
        sys.exit(2)
    return builder(name)


def source_dict():
    return build_dict(sys.argv[1])


def dest_dict():
    return build_dict(sys.argv[2])
