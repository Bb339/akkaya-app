import os

os.environ.setdefault('KDS_DEPLOYMENT_MODE', 'local-development')


def pytest_collection_modifyitems(config,items):
    if os.environ.get('KDS_FULL_PROJECT')=='1':return
    selected=[];deferred=[]
    for item in items:
        (deferred if item.get_closest_marker('full_project') else selected).append(item)
    items[:]=selected
    if deferred:config.hook.pytest_deselected(items=deferred)
