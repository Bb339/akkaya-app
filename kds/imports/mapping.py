"""Canonical-to-source mapping. Ambiguous suggestions are never auto-selected."""
import re
import unicodedata
from typing import Any


def key(value: str) -> str:
    value = value.translate(str.maketrans({"ı": "i", "İ": "I"})).casefold()
    value = "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_")


ALIASES = {
    "external_id": ["analiz_birimi_id", "analiz birimi", "parsel_id", "parcel_id", "unit_id", "id"],
    "settlement": ["yerlesim", "yerleşim", "koy", "köy", "village"],
    "area_da": ["alan_da", "alan (da)", "dekar", "area"],
    "current_crop": ["urun", "ürün", "mevcut_urun", "mevcut ürün", "crop"],
    "name_or_code": ["ad", "kod", "name"], "irrigation_method": ["sulama_yontemi"],
    "latitude": ["lat", "enlem"], "longitude": ["lon", "boylam"], "notes": ["not", "notlar"],
    "crop_name": ["urun", "ürün", "urun_adi", "ürün adı", "crop", "name"],
    "crop_group": ["urun_grubu", "ürün grubu", "kategori"],
    "perennial": ["cok_yillik", "çok yıllık", "cok_yillik_mi"],
    "kc_initial": ["kc_ini", "baslangic_kc"], "kc_mid": ["orta_kc"], "kc_end": ["son_kc"],
    "stage_initial_days": ["baslangic_gun"], "stage_development_days": ["gelisme_gun"],
    "stage_mid_days": ["orta_donem_gun"], "stage_late_days": ["son_donem_gun"],
    "planting_date": ["ekim_tarihi"], "harvest_date": ["hasat_tarihi"],
    "source": ["kaynak"], "confidence_level": ["guven", "güven düzeyi", "veri_guveni"],
    "year": ["yil", "yıl"], "yield_per_da": ["verim", "verim_kg_da", "yield"],
    "net_profit_per_da": ["net_kar_tl_da", "net_kâr", "net_kar", "net_profit"],
    "currency": ["para_birimi", "para birimi"], "yield_unit": ["verim_birimi"],
    "active": ["aktif"], "geometry": ["geometri"],
}
FIELDS = {
    "analysis_units": ["external_id", "settlement", "area_da", "current_crop", "name_or_code", "irrigation_method", "latitude", "longitude", "geometry", "notes"],
    "crops": ["crop_name", "crop_group", "perennial", "kc_initial", "kc_mid", "kc_end", "stage_initial_days", "stage_development_days", "stage_mid_days", "stage_late_days", "planting_date", "harvest_date", "source", "confidence_level", "active"],
    "economics": ["crop_name", "year", "yield_per_da", "net_profit_per_da", "currency", "source", "yield_unit"],
    "geometries": ["external_id", "geometry"],
}
FIELDS.update(
    candidates=['analysis_unit_id','crop','water_requirement_m3_da','profit_per_da','yield_ton_da','allowed','rotation_status','suitability','risk','source'],
    scientific_inputs=['section','record_id','field','value_type','value','source'],
    water_budget=['amount','unit','kind','source'])

WATER_SOURCE_FIELDS = [
    'authority_class', 'source_authority', 'source_institution', 'source_reference',
    'source_document', 'source_date', 'data_period', 'measurement_method', 'notes',
]
FIELDS.update(
    annual_water_supply=['planning_year','amount','unit',*WATER_SOURCE_FIELDS],
    monthly_water_supply=['planning_year','month','amount','unit',*WATER_SOURCE_FIELDS],
    delivery_capacity=['planning_year','month','capacity','source_unit','canonical_unit','capacity_basis',
                       'conversion_method','operating_hours_per_day','operating_days_in_month',*WATER_SOURCE_FIELDS],
    environmental_release=['planning_year','month','release_form','value','source_unit','canonical_unit',*WATER_SOURCE_FIELDS],
    conveyance_efficiency=['planning_year','period','efficiency','scope',*WATER_SOURCE_FIELDS],
    perennial_irrigation_requirement=['planning_year','crop','analysis_unit_id','month','value','source_unit',
                                      'canonical_unit','confidence','method',*WATER_SOURCE_FIELDS],
)
REQUIRED = {"analysis_units": ["external_id", "settlement", "area_da", "current_crop"],
            "crops": ["crop_name"], "economics": ["crop_name", "year", "yield_per_da", "net_profit_per_da"],
            "geometries": ["external_id", "geometry"]}


def suggest(columns: list[str], data_type: str) -> tuple[dict[str, str], dict[str, list[str]]]:
    mapping, ambiguous = {}, {}
    for canonical in FIELDS[data_type]:
        aliases = {key(v) for v in [canonical, *ALIASES.get(canonical, [])]}
        matches = [col for col in columns if key(col) in aliases]
        if len(matches) == 1:
            mapping[canonical] = matches[0]
        elif len(matches) > 1:
            ambiguous[canonical] = matches
    return mapping, ambiguous


def check_mapping(mapping: Any, columns: list[str], data_type: str) -> None:
    if not isinstance(mapping, dict) or any(k not in FIELDS[data_type] or v not in columns for k, v in mapping.items()):
        raise ValueError("Mapping must associate canonical fields with detected column names.")
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("A source column cannot populate multiple fields.")

REQUIRED.update({name:[field for field in FIELDS[name] if field!='risk'] for name in ('candidates','scientific_inputs','water_budget')})
REQUIRED.update({
    'annual_water_supply':['planning_year','amount','unit','authority_class'],
    'monthly_water_supply':['planning_year','month','amount','unit','authority_class'],
    'delivery_capacity':['planning_year','month','capacity','source_unit','canonical_unit','capacity_basis','authority_class'],
    'environmental_release':['planning_year','release_form','value','source_unit','canonical_unit','authority_class'],
    'conveyance_efficiency':['planning_year','period','efficiency','scope','authority_class'],
    'perennial_irrigation_requirement':['planning_year','crop','value','source_unit','canonical_unit','confidence','method','authority_class'],
})
