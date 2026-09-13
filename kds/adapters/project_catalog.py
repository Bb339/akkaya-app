"""Catalog-only data boundary for readiness before a full bundle exists."""
from contextlib import contextmanager
from kds.science.providers import using_provider


@contextmanager
def project_catalog_scope(crops):
    import app
    catalog = {app.normalize_crop_key(c['name']): dict(name=c['name'], category=c.get('crop_group', '')) for c in crops}
    class CatalogProvider:
        def read(self, name, legacy_reader):
            if name != 'crop_catalog':
                raise ValueError('Readiness requested an unavailable project resource: '+name)
            return catalog
    with using_provider(CatalogProvider()):
        yield
