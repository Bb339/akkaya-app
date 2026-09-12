"""Injection is restricted to data acquisition, never algorithm selection or math."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from typing import Protocol
from .contract import ScientificInputBundle


class ScientificDataProvider(Protocol):
    def read(self, name: str, legacy_reader): ...


class LegacyReferenceProvider:
    def read(self, name, legacy_reader):
        return legacy_reader()


class ProjectDataProvider:
    def __init__(self, bundle: ScientificInputBundle):
        self._resources = dict(bundle.resources)

    def read(self, name, legacy_reader):
        if name not in self._resources:
            raise ValueError(f'Missing scientific resource: {name}')
        return self._resources[name].copy()


_provider = ContextVar('scientific_provider', default=None)


@contextmanager
def using_provider(provider):
    token = _provider.set(provider)
    try:
        yield
    finally:
        _provider.reset(token)


def source(name):
    def decorate(reader):
        @wraps(reader)
        def read():
            provider = _provider.get() or LegacyReferenceProvider()
            return provider.read(name, reader)
        return read
    return decorate


def optional_reference(name):
    # The legacy file mapping lives exclusively in the reference adapter.
    from kds.adapters.scientific_reference import read_optional
    provider = _provider.get() or LegacyReferenceProvider()
    return provider.read(name, lambda: read_optional(name))
