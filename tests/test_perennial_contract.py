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


def test_before_fix_candidate_pear_incorrectly_locks_wheat_field():
    # Recorded defect on 3d12895; the next fix changes this expectation.
    assert lock('BUGDAY') == 2


@pytest.mark.parametrize('crop, expected', [('ARMUT', 2), ('ELMA', 3)])
def test_observed_orchard_is_protected(crop, expected):
    assert lock(crop, 'orchard') == expected
