"""Minimal observed/current versus alternative-season boundary reproduction."""
from copy import deepcopy
import pandas as pd
import pytest
import app
from kds.science.providers import using_provider


class AlternativeSeasons:
    def read(self, name, reader):
        assert name == 'environment'
        return {'s2': pd.DataFrame([
            dict(parcel_id='X', crop=crop, area_da=10., year=2025)
            for crop in ['ARPA', 'ARMUT']
        ])}


def lock(current_crop, parcel_type='field'):
    unit = dict(id='X', current_crop=current_crop, parcel_type=parcel_type)
    before = deepcopy(unit)
    with using_provider(AlternativeSeasons()):
        result = app._compute_perennial_locks([unit], 2025, ['NADAS', 'ARPA', 'ARMUT', 'ELMA'], 's2')
    assert unit == before
    return int(result[0])


@pytest.mark.parametrize('crop', ['BUGDAY', 'ARPA', 'NOHUT', 'MERCIMEK'])
def test_candidate_pear_does_not_lock_observed_annual_field(crop):
    assert lock(crop) == -1


@pytest.mark.parametrize('crop, expected', [('ARMUT', 2), ('ELMA', 3)])
def test_observed_orchard_is_protected(crop, expected):
    assert lock(crop, 'orchard') == expected


def test_observed_perennial_protected_even_if_parcel_type_label_is_field():
    assert lock('ARMUT', 'field') == 2


def test_missing_observed_perennial_fails_instead_of_silently_unlocking():
    with pytest.raises(ValueError, match='Observed perennial crop'):
        app._compute_perennial_locks([dict(id='X', current_crop='ARMUT')], 2025, ['NADAS', 'ARPA'], 's2')


def test_lock_does_not_read_season_or_candidate_resources():
    class Forbidden:
        def read(self, name, reader):
            pytest.fail('Perennial lock tried to read alternative inputs: '+name)
    with using_provider(Forbidden()):
        assert app._compute_perennial_locks([dict(id='X', current_crop='BUGDAY')], 2025, ['NADAS', 'ARMUT'], 's2').tolist() == [-1]


def test_current_crop_spelling_alias_remains_protected():
    assert app._compute_perennial_locks([dict(id='X', current_crop='KAYISI')], 2025, ['NADAS', 'KAYSI'], 's2').tolist() == [1]


def test_after_minimal_evidence_matches_current_behavior():
    import json
    from pathlib import Path
    evidence = json.loads((Path(__file__).parent/'fixtures/scientific_fix_phase1/after_minimal.json').read_text())
    for crop, expected in evidence['cases'].items():
        assert lock(crop) == expected['lock_index']
        assert (expected['lock_index'] >= 0) is expected['locked']


def test_public_synthetic_units_have_only_six_real_locks(tmp_path):
    from general_project_support import client_for, import_project, config
    from kds.adapters.project_science import build_bundle
    from kds.application.optimization import configuration
    from kds.science.providers import ProjectDataProvider
    client, repository = client_for(tmp_path/'projects')
    pid = import_project(client)
    document = repository.get(pid); original = deepcopy(document)
    bundle = build_bundle(document, configuration(config('S2'), document))
    provider = ProjectDataProvider(bundle)
    with using_provider(provider):
        units = app.load_parcels()
        crops = app.build_candidate_matrix_two_season(units, year=2025, season_source='s2')[0]
        locks = app._compute_perennial_locks(units, 2025, crops, 's2')
    actual = {p['id'] for p, index in zip(units, locks) if index >= 0}
    expected = {p['id'] for p in units if p['parcel_type'] == 'orchard'}
    assert len(units) == 24 and len(expected) == 6 and actual == expected
    assert len([p for p in units if p['parcel_type'] == 'field']) == 18
    assert document == original


def test_akkaya_observed_orchard_set_matches_audit():
    import json
    from pathlib import Path
    expected = json.loads((Path(__file__).parent/'fixtures/scientific_fix_phase1/akkaya_locks.json').read_text())['unit_ids']
    units = app.load_parcels()
    crops = app.build_candidate_matrix_two_season(units, year=2024, season_source='s2')[0]
    locks = app._compute_perennial_locks(units, 2024, crops, 's2')
    actual = sorted(p['id'] for p, index in zip(units, locks) if index >= 0)
    assert actual == expected and len(actual) == 52
    assert all(app.canonical_crop_key(p['current_crop']) in app.PERENNIAL_CROPS for p,index in zip(units, locks) if index >= 0)
