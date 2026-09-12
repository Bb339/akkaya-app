"""Explicit, opt-in reference capture; never run during tests."""
import ast
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import app as engine

OUTPUT = ROOT / 'tests/fixtures/scientific_baseline'
OPTIONS = dict(popSize=8, generations=4, foodSources=8, cycles=4, limit=4,
               ants=8, iterations=4, cxRate=.7, mutRate=.08, rho=.25, q=1.,
               envFlowRatio=.10, enforceDeliveryCaps=True, waterModel='calib',
               riskMode='none', riskLambda=0., riskSamples=120,
               waterQualityFilter=True, simpleMode=False)


def stable(value):
    if isinstance(value, dict):
        return {str(k): stable(v) for k, v in value.items()
                if not any(word in str(k).lower() for word in ('runtime', 'elapsed', 'timestamp', 'duration'))}
    if isinstance(value, (list, tuple)):
        return [stable(v) for v in value]
    if hasattr(value, 'tolist'):
        return stable(value.tolist())
    return value


def execute(scenario, algorithm, seed, ids):
    opts = {**OPTIONS, 'seed': seed, 'seasonSource': scenario.lower(),
            'scenarioType': 'single' if scenario == 'S1' else 'double',
            'twoSeason': scenario == 'S2'}
    return stable(engine.optimize(ids, algorithm, 'water_saving', 1., year=2024, options=opts))


if __name__ == '__main__':
    if OUTPUT.exists():
        raise SystemExit('Refusing to overwrite frozen references.')
    OUTPUT.mkdir(parents=True)
    metadata = dict(source_version='v1.0.0-thesis-final',
        source_commit='7d47d296acbc89d9f172e7113e3bdc2ef1ab6ca0',
        objective='water_saving', water_budget_ratio=1., planning_year=2024,
        water_budget_reference_m3=100700080.81, configuration=OPTIONS,
        tolerance={'float_rel': 1e-10, 'float_abs': 1e-7, 'identities_and_choices': 'exact'},
        seed_policy='Explicit single engine runs; no HTTP repeat/algorithm seed offsets.',
        input_hashes={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in sorted((ROOT/'data').rglob('*')) if p.is_file() and p.suffix in ('.csv', '.json')},
        weights='Existing engine objective formula; full function hashes recorded below.',
        engine_definitions={n.name: hashlib.sha256(ast.dump(n).encode()).hexdigest()
                            for n in ast.parse((ROOT/'app.py').read_text(encoding='utf-8-sig')).body
                            if isinstance(n, ast.FunctionDef)},
        cases=[])
    for scenario in ('S1', 'S2'):
        for algorithm in ('GA', 'ACO', 'ABC'):
            cases = []
            for seed in (123, 456, 789):
                ids = ['P1', 'P23', 'P149']
                result = execute(scenario, algorithm, seed, ids)
                cases.append(dict(seed=seed, selected_ids=ids, result=result))
                print(scenario, algorithm, seed, 'captured', flush=True)
            name = f'{scenario.lower()}_{algorithm.lower()}.json'
            (OUTPUT/name).write_text(json.dumps(cases, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
            metadata['cases'].append(dict(scenario=scenario, algorithm=algorithm, file=name, seeds=[123,456,789]))
    (OUTPUT/'baseline_metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
