"""One fresh process per run isolates legacy Python/NumPy RNG and caches."""
import multiprocessing
import traceback


def stable(value):
    if isinstance(value, dict):
        return {str(k): stable(v) for k,v in value.items()
                if not any(t in str(k).lower() for t in ('runtime','elapsed','timestamp','duration','generated_at'))}
    if isinstance(value, (list, tuple)):
        return [stable(v) for v in value]
    if hasattr(value, 'tolist'):
        return stable(value.tolist())
    return value


def _worker(bundle, connection):
    try:
        import app
        from .providers import ProjectDataProvider, using_provider
        config = bundle.algorithm_configuration.copy()
        with using_provider(ProjectDataProvider(bundle)):
            result = app.optimize(config['selected_ids'], config['algorithm'], config['objective'],
                                  config['water_budget_ratio'], year=bundle.planning_year, options=config['options'])
        connection.send(('ok', stable(result)))
    except Exception as exc:
        # Process boundary: preserve failure details, never substitute a scientific result.
        connection.send(('error', f'{type(exc).__name__}: {exc}\n{traceback.format_exc()}'))
    finally:
        connection.close()


def execute(bundle, timeout=300):
    context = multiprocessing.get_context('spawn')
    receiving, sending = context.Pipe(duplex=False)
    process = context.Process(target=_worker, args=(bundle,sending), daemon=True)
    process.start()
    sending.close()
    try:
        if not receiving.poll(timeout):
            raise TimeoutError('Scientific analysis exceeded the execution limit.')
        status, value = receiving.recv()
        if status != 'ok':
            raise RuntimeError(value)
        return value
    finally:
        receiving.close()
        process.join(timeout=2)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
