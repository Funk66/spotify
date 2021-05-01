from logging import getLogger
from pathlib import Path
from typing import Any

from yaml import dump, safe_load


class ConfigError(Exception):
    def __init__(self, param: str):
        self.param = param

    def __str__(self) -> str:
        return f"'{self.param}' is not a valid configuration parameter"


class MetaConfig(type):
    def __new__(mcs, name, bases, namespace):
        fields = namespace['__annotations__'].keys()
        meta = {
            'data': dict(zip(fields, [''] * len(fields))),
            'loaded': False,
        }
        return super().__new__(mcs, name, bases, {
            **namespace, '__meta__': meta
        })

    def __getattr__(self, name: str) -> Any:
        if name not in self.__meta__['data']:
            raise ConfigError(name)
        if not self.__meta__['loaded']:
            self.load()
        return self.__meta__['data'][name]

    def __setattr__(self, name: str, value: Any) -> None:
        self.update(**{name: value})

    def load(self) -> None:
        if self.path.exists():
            with open(self.path) as data:
                log.info('Reading config file')
                self.__meta__['data'].update(safe_load(data))
        self.__meta__['loaded'] = True

    def write(self) -> None:
        if not self.path.parent.exists():
            self.path.parent.mkdir(parents=True)
        with open(self.path, 'w') as output:
            log.info('Writing config file')
            dump(self.__meta__['data'], output, default_flow_style=False)

    def update(self, **kwargs) -> None:
        for name, value in kwargs.items():
            if name not in self.__meta__['data']:
                raise ConfigError(name)
            if not self.__meta__['loaded']:
                self.load()
            self.__meta__['data'][name] = value
        self.write()


class Config(metaclass=MetaConfig):
    client: str
    secret: str
    token: str
    refresh: str
    validity: float
    path = Path.home() / '.config/spotify/config.yaml'


log = getLogger('spotify.config')
