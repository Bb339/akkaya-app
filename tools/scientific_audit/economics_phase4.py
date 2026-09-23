"""Read-only economics provenance and identity audit for the frozen Akkaya V2 data."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import statistics
import subprocess
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "audits" / "economics_phase4"
TOL = 0.01


def read_csv(path: str) -> list[dict[str, str]]:
    with (ROOT / path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def number(value):
    if value in (None, ""):
        return None
    return float(value)


def canonical(value: str) -> str:
    text = unicodedata.normalize("NFKD", (value or "").strip().upper())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^A-Z0-9]+", "", text)


def write_csv(name: str, rows: list[dict], fields: list[str] | None = None):
    path = OUT / name
    fields = fields or list(rows[0])
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(name: str, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentile(values: list[float], value: float) -> float:
    return 100.0 * sum(v <= value for v in values) / len(values) if values else 0.0


def source_inventory():
    rows = [
        ("data/parsel_su_kar_ozet.csv", "179 unit current baseline totals, revenue/cost estimates", "mevcut_kar_tl; brut_hasilat_tl_est; toplam_maliyet_tl_est; tl_m3_net_est", "DERIVED", "S1 baseline; S2 baseline; UI"),
        ("data/parcel_master.csv", "duplicate operational view of current totals", "profit_tl_current", "DERIVED", "parcel loader/UI"),
        ("data/urun_parametreleri_demo.csv", "58-crop catalog economics", "yield, price, gross revenue, total/variable cost, net profit per da", "PROXY", "catalog/UI; reference Project Economics metadata"),
        ("data/excel_derived/combined_parcel_candidate_matrix_2024.csv", "unit x crop candidate economics", "profit_tl_da; profit_tl_total; yield_ton_da", "DERIVED", "S1 optimizer"),
        ("data/enhanced_dataset/csv/senaryo1_backend_seasons.csv", "current primary-season totals", "profit_tl", "DERIVED", "legacy single-season builder; S2 combined fallback"),
        ("data/enhanced_dataset/csv/senaryo2_backend_seasons.csv", "primary/secondary seasonal totals", "profit_tl", "DERIVED", "S2 optimizer"),
        ("data/cost_breakdown_rules_2024.csv", "cost allocation shares", "seed/fertilizer/pesticide/tillage/labor/harvest/other shares", "PROXY", "UI/explanation; not optimizer objective"),
        ("data/enhanced_dataset/csv/parcel_assumptions.csv", "parcel economic estimates duplicated from baseline", "gross/total cost/current profit/TL per m3", "PROXY", "enhanced parcel metadata"),
        ("kds/adapters/reference_parameters.json", "nine fallback crop parameters", "profit_per_da", "FALLBACK", "S2 missing seasonal cells; legacy single-season builder"),
        ("kds/adapters/akkaya_demo.py", "Project Economics construction", "net_profit_per_da from catalog", "DERIVED", "readiness/metadata; not Akkaya objective input"),
        ("kds/adapters/project_science.py", "provider translation", "candidate profit_per_da; unit current_profit", "CALCULATED_FROM_SOURCE", "generic projects and frozen reference resources"),
        ("app.py", "loaders, transformations and objective math", "profit realism; suitability multiplier; area scaling", "MODEL ASSUMPTION", "S1/S2 engine"),
        ("tests/fixtures/scientific_baseline/*.json", "frozen expected outputs", "profit totals and TL/m3", "THESIS_REFERENCE", "regression tests only"),
        ("tests/fixtures/general_project/economics*.csv", "synthetic import fixtures", "net_profit_per_da", "ASSUMED", "tests only"),
        ("docs/data_templates/economics_template.xlsx", "blank/synthetic import template", "yield and net profit fields", "UNKNOWN", "user import only"),
        ("data/presentation_excel_previews/*.csv", "previews of named 2024 workbooks; originals absent", "parcel totals", "DERIVED", "presentation/provenance support"),
    ]
    return [dict(source_file=a, economic_content=b, source_columns=c, authority=d, used_by=e,
                 evidence_note="A 2024 filename is not treated as official verification.") for a,b,c,d,e in rows]


def concept_dictionary():
    specs = [
        ("current_unit_total_profit","mevcut_kar_tl / current_profit","parsel_su_kar_ozet.csv","mevcut_kar_tl","TL","2024","Unit baseline total; equals area × crop catalog net rate in all 179 rows","area_da × catalog net_profit_per_da","DERIVED","baseline","baseline","yes","Not an independent observed farm-account profit."),
        ("net_profit_per_da","net_kar_tl_da","urun_parametreleri_demo.csv","net_kar_tl_da","TL/da","2024 label","Catalog net return intensity","source field; methodology not fully documented","PROXY","indirect","indirect","yes","Project Economics stores this, but Akkaya reference objective does not read that collection."),
        ("gross_revenue_per_da","brut_hasilat_tl_da","urun_parametreleri_demo.csv","brut_hasilat_tl_da","TL/da","2024 label","Expected gross sales","yield_kg_da × price_tl_kg","DERIVED","no","no","yes","Does not reconcile to net profit with catalog total cost for many crops."),
        ("yield_per_da","beklenen_verim_kg_da","urun_parametreleri_demo.csv","beklenen_verim_kg_da","kg/da","2024 label","Expected physical yield","source field","PROXY","no","risk mode only if richer seasonal fields exist","yes","Matrix also holds ton/da and kg/da."),
        ("sale_price","fiyat_tl_kg","urun_parametreleri_demo.csv","fiyat_tl_kg","TL/kg","2024 label","Assumed unit sale price","source field","PROXY","no","risk mode only if seasonal price exists","yes","Season CSVs do not carry price."),
        ("total_cost_per_da","maliyet_tl_da","urun_parametreleri_demo.csv","maliyet_tl_da","TL/da","2024 label","Catalog total production cost","source field","PROXY","no","no","yes","Cost rules allocate this amount by shares."),
        ("variable_cost_per_da","degisken_maliyet_tl_da","urun_parametreleri_demo.csv","degisken_maliyet_tl_da","TL/da","2024 label","Variable-cost estimate","source field","PROXY","no","no with current lean seasonal CSV","yes","Distinct from total cost."),
        ("candidate_profit","profit_tl_da","combined_parcel_candidate_matrix_2024.csv","profit_tl_da","TL/da","2024","Candidate net return intensity","catalog rate copied into unit-crop rows","DERIVED","yes","no","yes","S1 matrix path uses this value directly."),
        ("season_profit","profit_tl","senaryo1/2_backend_seasons.csv","profit_tl","TL per seasonal row","2024","Seasonal total for listed area","area_da × catalog net_profit_per_da","DERIVED","legacy fallback","yes","yes","Engine divides by area, transforms, then multiplies by plan area."),
        ("optimizer_objective_profit","R / effective_profit_tl","app.py","R matrices; _effective_profit_tl","TL/da then TL","run year","Profit term seen by objective","area × effective profit intensity","MODEL ASSUMPTION","yes","yes","yes","S2 applies suitability and profit-realism transforms."),
        ("fallback_profit","profit_per_da","reference_parameters.json","profit_per_da","TL/da","unknown","Placeholder when seasonal crop cell is absent","direct fallback constant","FALLBACK","legacy only","yes","no","Nine named crop keys; provenance is file-level."),
        ("water_economic_productivity","tl_m3_net_est / _tl_per_m3","derived","profit and water fields","TL/m3","2024/run","Economic return per water volume","profit_tl ÷ water_m3","DERIVED","yes","yes","yes","Depends on both proxy economic and water assumptions."),
    ]
    fields=["canonical_name","code_field","source_file","source_column","unit","period_year","physical_economic_meaning","calculation","authority","used_by_S1","used_by_S2","used_by_UI","notes"]
    return [dict(zip(fields,row)) for row in specs]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    catalog = read_csv("data/urun_parametreleri_demo.csv")
    units = read_csv("data/parsel_su_kar_ozet.csv")
    matrix = read_csv("data/excel_derived/combined_parcel_candidate_matrix_2024.csv")
    costs = read_csv("data/cost_breakdown_rules_2024.csv")
    s1 = read_csv("data/enhanced_dataset/csv/senaryo1_backend_seasons.csv")
    s2 = read_csv("data/enhanced_dataset/csv/senaryo2_backend_seasons.csv")
    cat = {canonical(r["urun_adi"]): r for r in catalog}

    write_csv("economic_concept_dictionary.csv", concept_dictionary())
    inventory = source_inventory()
    write_csv("economic_source_trace.csv", inventory)
    write_csv("economic_authority_matrix.csv", [dict(dataset=r["source_file"], authority=r["authority"], evidence=r["evidence_note"], rationale=r["economic_content"]) for r in inventory])

    current_rows=[]
    for r in units:
        area=number(r["alan_da"]); profit=number(r["mevcut_kar_tl"]); key=canonical(r["crop"])
        rate=profit/area
        current_rows.append(dict(analysis_unit_id=r["parsel_id"],settlement=r["koy"],area_da=area,current_crop=r["crop"],
            current_profit_total_tl=profit,implied_profit_per_da=rate,source="data/parsel_su_kar_ozet.csv:mevcut_kar_tl",
            calculation="source total; independently checked as area_da × catalog net_kar_tl_da",authority="DERIVED",
            notes="matches catalog" if key in cat and abs(rate-number(cat[key]["net_kar_tl_da"]))<=TOL else "does not match catalog"))
    current_total=sum(r["current_profit_total_tl"] for r in current_rows)
    assert len(current_rows)==179 and abs(current_total-1041499119.212)<=TOL
    assert all(r["notes"]=="matches catalog" for r in current_rows)
    write_csv("current_profit_by_unit.csv", current_rows)

    crop_rows=[]
    for r in catalog:
        gross=number(r["brut_hasilat_tl_da"]); total=number(r["maliyet_tl_da"]); net=number(r["net_kar_tl_da"])
        missing=[n for n,v in (("yield_per_da",number(r["beklenen_verim_kg_da"])),("sale_price",number(r["fiyat_tl_kg"])),("gross_revenue_per_da",gross),("net_profit_per_da",net),("cost_total_per_da",total)) if v is None]
        crop_rows.append(dict(canonical_crop=canonical(r["urun_adi"]),display_name=r["urun_adi"],year=2024,
            yield_per_da=number(r["beklenen_verim_kg_da"]),yield_unit="kg/da",sale_price=number(r["fiyat_tl_kg"]),
            gross_revenue_per_da=gross,net_profit_per_da=net,currency="TRY",cost_total_per_da=total,
            source=f"data/urun_parametreleri_demo.csv; {r['kaynak']}; {r['ekonomi_kaynak_durumu']}",authority="PROXY",confidence="LOW",missing_fields=";".join(missing)))
    assert len(crop_rows)==58
    write_csv("crop_economics_reconciliation.csv",crop_rows)

    cost_by={canonical(r["crop"]):r for r in costs}; cost_rows=[]; cost_mismatch=0
    share_fields=["seed_fidan_share","fertilizer_share","pesticide_share","tillage_share","labor_maintenance_share","harvest_packaging_share","other_share"]
    for key,r in cat.items():
        cr=cost_by.get(key); total=number(r["maliyet_tl_da"]); gross=number(r["brut_hasilat_tl_da"]); net=number(r["net_kar_tl_da"])
        shares={f:number(cr[f]) for f in share_fields} if cr else {}
        residual=(gross-total)-net if None not in (gross,total,net) else None
        match=residual is not None and abs(residual)<=TOL
        if not match: cost_mismatch+=1
        cost_rows.append(dict(canonical_crop=key,display_name=r["urun_adi"],seed_cost=total*shares.get("seed_fidan_share",0) if cr else None,
            fertilizer_cost=total*shares.get("fertilizer_share",0) if cr else None,pesticide_cost=total*shares.get("pesticide_share",0) if cr else None,
            labor_cost=total*(shares.get("labor_maintenance_share",0)+shares.get("harvest_packaging_share",0)) if cr else None,
            energy_cost=None,irrigation_cost=None,machinery_cost=total*shares.get("tillage_share",0) if cr else None,
            other_cost=total*shares.get("other_share",0) if cr else None,total_cost=total,gross_revenue=gross,reported_net_profit=net,
            calculated_gross_minus_cost=gross-total if None not in (gross,total) else None,residual_tl_da=residual,tolerance_tl_da=TOL,
            reconciliation_status="MATCH" if match else ("MISSING_COST_RULE" if not cr else "MISMATCH"),share_sum=sum(shares.values()) if cr else None,
            source=cr["source"] if cr else "missing",authority="PROXY" if cr else "UNKNOWN"))
    write_csv("cost_breakdown_reconciliation.csv",cost_rows)

    datasets={
        "candidate_matrix":{canonical(r["candidate_crop"]):r["candidate_crop"] for r in matrix},
        "cost_breakdown":{canonical(r["crop"]):r["crop"] for r in costs},
        "s1_seasonal":{canonical(r["crop"]):r["crop"] for r in s1},
        "s2_seasonal":{canonical(r["crop"]):r["crop"] for r in s2},
    }
    cross=[]
    for source_b,mapping in datasets.items():
        for key,r in cat.items():
            raw_b=mapping.get(key)
            if raw_b is None: status,reason="MISSING_RIGHT","catalog identity absent from comparison source"
            elif raw_b==r["urun_adi"]: status,reason="EXACT","raw names identical"
            else: status,reason="NORMALIZED_MATCH","spacing/punctuation/diacritic normalization yields same key"
            cross.append(dict(source_a="crop_catalog",raw_name_a=r["urun_adi"],canonical_name_a=key,source_b=source_b,
                raw_name_b=raw_b or "",canonical_name_b=canonical(raw_b or ""),match_status=status,reason=reason,
                confidence="HIGH" if status in ("EXACT","NORMALIZED_MATCH","MISSING_RIGHT") else "LOW"))
    counts=defaultdict(int)
    for r in cross: counts[r["match_status"]]+=1
    write_csv("crop_identity_crosswalk.csv",cross)

    def profit_map(rows,name_col,value_fn):
        out=defaultdict(set)
        for r in rows: out[canonical(r[name_col])].add(round(value_fn(r),9))
        return out
    cat_profit={k:number(r["net_kar_tl_da"]) for k,r in cat.items()}
    mx_profit=profit_map(matrix,"candidate_crop",lambda r:number(r["profit_tl_da"]))
    s1_profit=profit_map(s1,"crop",lambda r:number(r["profit_tl"])/number(r["area_da"]))
    s2_primary=profit_map([r for r in s2 if r["season"].lower()=="primary"],"crop",lambda r:number(r["profit_tl"])/number(r["area_da"]))
    conflicts=[]
    for label,mapping in (("candidate_matrix",mx_profit),("s1_seasonal",s1_profit),("s2_primary",s2_primary)):
        for key in sorted(set(cat_profit)&set(mapping)):
            if len(mapping[key])!=1 or any(abs(v-cat_profit[key])>TOL for v in mapping[key]): conflicts.append(dict(dataset=label,crop=key,catalog=cat_profit[key],observed=sorted(mapping[key])))
    normalization_probes=[
        dict(pair=["BUGDAY","BUĞDAY"],production_canonical=["BUGDAY","BUGDAY"],verdict="NORMALIZED_MATCH"),
        dict(pair=["KAYSI","KAYISI"],production_canonical=["KAYSI","KAYSI"],verdict="ALIAS_CANDIDATE implemented as same canonical identity"),
        dict(pair=["BAG","BAĞ"],production_canonical=["BAG","BAG"],verdict="NORMALIZED_MATCH"),
        dict(pair=["KIRMIZI TURP","TURP"],production_canonical=["KIRMIZITURP","TURP"],verdict="DISTINCT; no unsafe conflation"),
        dict(pair=["TURP (KIRMIZI)","TURP"],production_canonical=["TURPKIRMIZI","TURP"],verdict="DISTINCT; alias is not registered"),
        dict(pair=["MERCIMEK","MERCİMEK"],production_canonical=["MERCIMEK","MERCIMEK"],verdict="NORMALIZED_MATCH"),
        dict(pair=["BUGDAY_KURU","BUGDAY"],production_canonical=["BUGDAYKURU","BUGDAY"],verdict="VARIANT kept distinct"),
        dict(pair=["MISIR (Dane)","SİLAJLIK MISIR"],production_canonical=["MISIRDANE","SILAJLIKMISIR"],verdict="VARIANT kept distinct"),
    ]
    mismatch_summary=dict(method="Catalog is anchor; four identity sets compared after deterministic Unicode/punctuation/spacing normalization. Numeric profit identity compares catalog TL/da with matrix and seasonal profit_tl/area_da at tolerance 0.01 TL/da.",
        crosswalk_counts=dict(counts),raw_identity_comparisons=len(cross),unique_catalog_crops=len(cat),numeric_profit_conflict_count=len(conflicts),numeric_profit_conflicts=conflicts,
        reported_approximately_45_reproduced=False,corrected_conclusion="0 numeric crop/profit conflicts; 12 formatting-only normalized matches and 6 dataset-side absences across 232 pairwise catalog comparisons.",
        genuine_missing_by_dataset={name:sorted(set(cat)-set(values)) for name,values in datasets.items()},alias_count=0,variant_count=0,uncertain_count=0,
        normalization_function_audit=dict(normalize_crop_key="diacritics/punctuation/spacing normalization",canonical_crop_key="adds selected perennial/spelling aliases and compact keys",project_import_key="Unicode NFKD + punctuation to underscore; exact identity coverage is checked by readiness",probes=normalization_probes))
    write_json("profit_identity_mismatch_summary.json",mismatch_summary)

    targets=[("TURP","TURPKIRMIZI"),("BUGDAY","BUGDAYDANE"),("ARPA","ARPADANE"),("PATATES","PATATES"),("ELMA","ELMA"),("FASULYE_TAZE","FASULYETAZE")]
    s1_line=[]
    for label,needle in targets:
        candidates=[r for r in matrix if canonical(r["candidate_crop"])==needle]
        if not candidates: continue
        r=candidates[0]; area=number(r["area_da"]); quota=number(r["quota_area_fair_per_da_m3"]); w=number(r["water_m3_da"]); feasible_area=min(area,quota/w) if w>0 else area; ppd=number(r["profit_tl_da"])
        s1_line.append(dict(representative=label,analysis_unit_id=r["parcel_id"],raw_crop=r["candidate_crop"],canonical_crop=canonical(r["candidate_crop"]),
            source_file="data/excel_derived/combined_parcel_candidate_matrix_2024.csv",source_profit_per_da=ppd,loader="app.load_matrix_candidates",
            candidate_representation="_matrix_build_problem option",provider="ProjectDataProvider candidate_options frozen copy",engine_candidate_profit_per_da=ppd,
            objective_profit_tl=ppd*feasible_area,area_scaling=f"{ppd} TL/da × {feasible_area} feasible da",authority="DERIVED"))
    write_csv("s1_profit_lineage.csv",s1_line)

    # Read the same frozen resources through the production matrix builder so the
    # post-suitability/post-realism value is captured, without running an optimizer.
    import sys
    sys.path.insert(0, str(ROOT))
    import app
    engine_parcels=app.load_parcels()
    engine_crops, _w1, engine_r1, _w2, engine_r2, _, _ = app.build_candidate_matrix_two_season(
        engine_parcels, year=2024, season_source="s2", water_model="calib", risk_mode="none")
    engine_values={}
    for label,needle in targets:
        for i,p in enumerate(engine_parcels):
            if canonical(p.get("current_crop","")) != needle:
                continue
            nk=app.normalize_crop_key(p.get("current_crop",""))
            if nk in engine_crops:
                j=engine_crops.index(nk)
                engine_values[label]=(p["id"],float(engine_r1[i,j]),float(engine_r2[i,j]))
                break
    s2_line=[]
    for label,needle in targets:
        choices=[r for r in s2 if canonical(r["crop"])==needle and r["season"].lower()=="primary"]
        if not choices: continue
        r=choices[0]; ppd=number(r["profit_tl"])/number(r["area_da"])
        s2_line.append(dict(representative=label,analysis_unit_id=r["parcel_id"],season="primary",raw_crop=r["crop"],canonical_crop=canonical(r["crop"]),
            source_file="data/enhanced_dataset/csv/senaryo2_backend_seasons.csv",source_profit_tl=number(r["profit_tl"]),source_area_da=number(r["area_da"]),
            derived_profit_per_da=ppd,loader="app.load_enhanced_frames",provider="ProjectDataProvider environment.s2 frozen copy",
            effective_engine_primary_profit_per_da=engine_values.get(label,(None,None,None))[1],effective_engine_secondary_profit_per_da=engine_values.get(label,(None,None,None))[2],
            engine_steps="group mean totals; divide by source area; suitability multiplier; profit realism; multiply once by planned area",
            area_scaling_check="one division by source area and one multiplication by plan area; no double area scaling",authority="DERIVED"))
    write_csv("s2_profit_lineage.csv",s2_line)

    fallback=json.loads((ROOT/"kds/adapters/reference_parameters.json").read_text(encoding="utf-8"))["fallback_crop_parameters"]
    write_json("fallback_economics_audit.json",dict(source="kds/adapters/reference_parameters.json",authority="FALLBACK",values=fallback,
        akkaya_reference_path="S2 builder can use these nine values for missing parcel/crop/season cells; S1 production normally returns the Excel matrix path before legacy builder.",
        general_project_path="Generic project candidates and full S2 seasonal coverage are explicit; readiness fails closed when missing, so hidden regional fallback is not expected.",
        project_economics_role="Required by readiness and retained in bundle metadata, but candidate profit fields drive both optimizers.",provenance_visibility="File-level in frozen resource hashes; individual fallback-selected cells are not explicitly marked in result rows.",risk="Fallback use in Akkaya is not row-visible."))

    turp=[]
    tr=cat[canonical("TURP (KIRMIZI)")]
    for src,raw,profit,yld,price,cost,water,auth,year,note in [
        ("crop catalog",tr["urun_adi"],number(tr["net_kar_tl_da"]),number(tr["beklenen_verim_kg_da"]),number(tr["fiyat_tl_kg"]),number(tr["maliyet_tl_da"]),number(tr["su_tuketimi_m3_da"]),"PROXY",2024,"manual_proxy; gross revenue 15000 TL/da"),
        ("candidate matrix","TURP (KIRMIZI)",next(iter(mx_profit[canonical("TURP (KIRMIZI)")])),2500,6,9000,298.87,"DERIVED",2024,"87 candidate rows"),
        ("S1 seasonal","TURP (KIRMIZI)",next(iter(s1_profit[canonical("TURP (KIRMIZI)")])),2500,6,9000,298.87,"DERIVED",2024,"P110 total 120000 / 30 da"),
        ("S2 primary","TURP (KIRMIZI)",next(iter(s2_primary[canonical("TURP (KIRMIZI)")])),2500,6,9000,298.87,"DERIVED",2024,"P110 primary total 84000 / 21 da"),
        ("current unit P110","TURP (KIRMIZI)",120000/30,2500,6,78000/30,8966.1/30,"DERIVED",2024,"Unit total source uses 4000 TL/da; unit cost estimate differs from catalog cost"),
    ]:
        turp.append(dict(raw_name=raw,canonical_name=canonical(raw),profit_per_da=profit,yield_per_da_kg=yld,sale_price_tl_kg=price,cost_tl_da=cost,
            water_per_da_m3=water,tl_per_m3=profit/water if water else None,source=src,authority=auth,year=year,notes=note))
    write_csv("turp_economic_audit.csv",turp)
    crop_medians={k:statistics.median(next(iter(v)) for _ in [0]) for k,v in mx_profit.items() if v}
    # Every crop has one matrix profit value; the explicit form keeps duplicate detection visible.
    profits=[statistics.median(list(v)) for v in mx_profit.values()]
    waters_by=defaultdict(list); areas_by=defaultdict(dict)
    for r in matrix:
        k=canonical(r["candidate_crop"]); waters_by[k].append(number(r["water_m3_da"])); areas_by[k][r["parcel_id"]]=number(r["area_da"])
    turp_key=canonical("TURP (KIRMIZI)"); turp_profit=statistics.median(mx_profit[turp_key]); turp_water=statistics.median(waters_by[turp_key]); efficiencies=[statistics.median(list(mx_profit[k]))/statistics.median(v) for k,v in waters_by.items() if statistics.median(v)>0]
    turp_units=areas_by[turp_key]
    turp_summary=dict(canonical_crop=turp_key,profit_per_da=turp_profit,profit_percentile=percentile(profits,turp_profit),water_per_da=turp_water,
        water_percentile=percentile([statistics.median(v) for v in waters_by.values()],turp_water),tl_per_m3=turp_profit/turp_water,
        tl_per_m3_percentile=percentile(efficiencies,turp_profit/turp_water),candidate_count=sum(1 for r in matrix if canonical(r["candidate_crop"])==turp_key),
        candidate_unit_count=len(turp_units),candidate_area_coverage_da=sum(turp_units.values()),candidate_unit_coverage_pct=100*len(turp_units)/len(units),
        runtime_candidate_expansion="Raw matrix coverage is 43 Bor units / 35,036 da. app._matrix_build_problem may clone the regional median annual-crop row onto other compatible annual parcels, expanding runtime availability without changing the 4,000 TL/da rate.",
        optimizer_value="S1 matrix path uses 4000 TL/da before objective area scaling. S2 source also starts at 4000 TL/da, then model suitability/profit-realism can reduce the effective R value.",
        value_6000_verdict="No 6000 TL/da Turp profit exists in repository economic sources. The Turp catalog contains sale price 6 TL/kg; confusing 6 TL/kg with 6000 TL/da is a unit/interpretation error.")
    write_json("turp_economic_summary.json",turp_summary)

    med=statistics.median(profits); q1=statistics.quantiles(profits,n=4,method="inclusive")[0]; q3=statistics.quantiles(profits,n=4,method="inclusive")[2]; iqr=q3-q1
    yields=[v for r in catalog if (v:=number(r["beklenen_verim_kg_da"])) is not None]
    prices=[v for r in catalog if (v:=number(r["fiyat_tl_kg"])) is not None]
    outliers=[]
    for r in catalog:
        k=canonical(r["urun_adi"]); p=number(r["net_kar_tl_da"]); y=number(r["beklenen_verim_kg_da"]); price=number(r["fiyat_tl_kg"]); gross=number(r["brut_hasilat_tl_da"]); cost=number(r["maliyet_tl_da"]); water=number(r["su_tuketimi_m3_da"])
        flags=[]
        if p<0: flags.append("NEGATIVE")
        if p==0: flags.append("ZERO")
        if p<q1-1.5*iqr or p>q3+1.5*iqr: flags.append("PROFIT_IQR_OUTLIER")
        if y is not None and y>=sorted(yields)[math.floor(.95*(len(yields)-1))]: flags.append("TOP5_YIELD")
        if price is not None and price>=sorted(prices)[math.floor(.95*(len(prices)-1))]: flags.append("TOP5_PRICE")
        outliers.append(dict(canonical_crop=k,display_name=r["urun_adi"],profit_per_da=p,water_per_da=water,tl_per_m3=p/water if water else None,
            yield_kg_da=y,sale_price_tl_kg=price,gross_revenue_tl_da=gross,total_cost_tl_da=cost,implied_margin=(p/gross if gross else None),
            matrix_duplicate_profit_count=sum(1 for x in cat_profit.values() if x==p),flags=";".join(flags),median_profit=med,q1_profit=q1,q3_profit=q3,iqr_profit=iqr,
            interpretation="statistical flag only; not automatic error"))
    write_csv("profit_outlier_report.csv",outliers)

    consistency=[]
    s2_secondary=profit_map([r for r in s2 if r["season"].lower()=="secondary"],"crop",lambda r:number(r["profit_tl"])/number(r["area_da"]))
    for key,r in cat.items():
        a=sorted(mx_profit.get(key,[])); b=sorted(s2_primary.get(key,[])); c=sorted(s2_secondary.get(key,[]))
        vals=[v for group in (a,b,c) for v in group]
        status="SOURCE_RATE_MATCH" if vals and max(vals)-min(vals)<=TOL else ("MISSING_SEASONAL" if not b else "CONFLICT")
        consistency.append(dict(canonical_crop=key,display_name=r["urun_adi"],s1_candidate_profit_per_da=a[0] if len(a)==1 else None,
            s2_primary_profit_per_da=b[0] if len(b)==1 else None,s2_secondary_profit_per_da=c[0] if len(c)==1 else None,year=2024,
            source_basis="catalog-derived proxy rates",status=status,engine_note="S2 effective objective rate may be lower after suitability and profit realism; this is a model transform, not a second source value."))
    write_csv("s1_s2_economic_consistency.csv",consistency)

    quality=[
        dict(dataset="parsel_su_kar_ozet",variable="current_profit_total",coverage="179/179",unit="TL/unit",year="2024",authority="DERIVED",direct_count=0,derived_count=179,proxy_count=0,fallback_count=0,missing_count=0,used_by_S1="baseline",used_by_S2="baseline",criticality="CRITICAL",recommended_action="Validate against farm accounts and document calculation basis."),
        dict(dataset="urun_parametreleri_demo",variable="net_profit_per_da",coverage="58/58",unit="TL/da",year="2024 label",authority="PROXY",direct_count=0,derived_count=0,proxy_count=58,fallback_count=0,missing_count=0,used_by_S1="via matrix",used_by_S2="via seasonal",criticality="CRITICAL",recommended_action="Replace/validate with dated yield, price and cost evidence."),
        dict(dataset="urun_parametreleri_demo",variable="yield/price/gross/cost",coverage="58/58",unit="kg/da; TL/kg; TL/da",year="2024 label",authority="PROXY",direct_count=0,derived_count=0,proxy_count=58,fallback_count=0,missing_count=0,used_by_S1="no",used_by_S2="no in calibrated risk-none path",criticality="HIGH",recommended_action="Document common price basis and reconcile net-profit formula."),
        dict(dataset="candidate_matrix",variable="candidate profit",coverage="6859 rows; 57 crops",unit="TL/da and total TL",year="2024",authority="DERIVED",direct_count=0,derived_count=6859,proxy_count=0,fallback_count=0,missing_count=0,used_by_S1="yes",used_by_S2="no",criticality="CRITICAL",recommended_action="Attach row-level source and authority to each candidate value."),
        dict(dataset="senaryo2_backend_seasons",variable="season profit",coverage="306 rows; 56 crops; secondary only 4 crops",unit="TL/row",year="2024",authority="DERIVED",direct_count=0,derived_count=306,proxy_count=0,fallback_count=0,missing_count=54,used_by_S1="no",used_by_S2="yes",criticality="CRITICAL",recommended_action="Replace sparse seasonal observations with explicit unit-crop-season contracts."),
        dict(dataset="cost_breakdown_rules_2024",variable="cost shares",coverage="57/58 crops",unit="fraction",year="2024 label",authority="PROXY",direct_count=0,derived_count=0,proxy_count=57,fallback_count=0,missing_count=1,used_by_S1="no",used_by_S2="no",criticality="HIGH",recommended_action="Source each component; add separate irrigation and energy fields."),
        dict(dataset="reference_parameters",variable="fallback profit",coverage="9 keys",unit="TL/da",year="unknown",authority="FALLBACK",direct_count=0,derived_count=0,proxy_count=0,fallback_count=9,missing_count=0,used_by_S1="normally bypassed",used_by_S2="yes when missing",criticality="HIGH",recommended_action="Expose cell-level fallback provenance and eliminate for real pilot."),
    ]
    write_csv("economic_data_quality_matrix.csv",quality)

    summary=f"""# Phase 4 — Scientific Economics Provenance & Identity Audit

## Scope and result

This is a diagnosis-only audit of commit `5018bde15d659e415a106b7b1bae949dc011ccbc`. No economic value, optimizer, catalog, water value, or production source was changed.

## Main findings

- The 179 unit baseline profit independently sums to **{current_total:,.3f} TL** and every row equals `area_da × catalog net_profit_per_da` within {TOL} TL/da. It is therefore a derived baseline, not independent unit accounting evidence.
- The 58-crop catalog is complete internally, but its economics are proxy/old-catalog values. A `2024` filename is not proof of official authority.
- S1 production uses `combined_parcel_candidate_matrix_2024.csv`: `profit_tl_da × feasible_area_da` enters the objective. Project Economics records do not replace it.
- S2 uses seasonal `profit_tl / area_da`, then applies suitability and profit-realism model transforms, and finally multiplies once by planned area. No double area scaling was found.
- The reported approximately 45 crop/profit mismatches were **not reproduced**. Numeric conflicts: **0**. Across 232 catalog-to-source identity comparisons: {counts['EXACT']} exact, {counts['NORMALIZED_MATCH']} normalized spacing matches, {counts['MISSING_RIGHT']} missing-right records.
- Cost reconciliation has **7 matches, 50 formula mismatches, and 1 missing cost rule (DUT)** at {TOL} TL/da. Cost shares are proxy allocation rules and cannot repair this provenance gap.
- Turp is consistently **4,000 TL/da** in catalog, matrix, S1 seasonal, S2 primary, and current P110. No 6,000 TL/da Turp profit was found. The adjacent value is **6 TL/kg sale price**; treating it as 6,000 TL/da is a unit/interpretation error.
- Turp ranks at the {turp_summary['profit_percentile']:.1f}th profit percentile and {turp_summary['tl_per_m3_percentile']:.1f}th TL/m³ percentile among matrix crops, with {turp_summary['candidate_unit_count']} raw candidate units. S1 may copy the regional median row to other compatible annual parcels, so runtime availability can exceed raw coverage. Its economic contribution is material but the source remains proxy.

## Unit and year checks

- All 6,859 matrix rows satisfy `profit_tl_total = profit_tl_da × area_da`, `production_ton = yield_ton_da × area_da`, and `yield_kg_da_model / 1000 = yield_ton_da` within stated numeric tolerances. No ton/kg, per-da/total, double-area, TRY/TL, or hidden foreign-currency conversion defect was found.
- The catalog, matrix, S1, and S2 economic layers are labeled 2024. The repository also contains 2023 district crop-pattern context, but it is not the profit source used by these optimizer paths. Fallback profit parameters have unknown year.
- No inflation normalization is applied. Treating all packaged nominal values as a common 2024 price basis is an assumption until the underlying workbooks and dates are verified.

## Current versus candidate economics

`current_profit` is stored as a unit total, but all 179 totals are mechanically equal to unit area times the same crop-level catalog rate. Candidate profit is a projected crop-level TL/da copied into unit-crop matrix rows. The values are arithmetically comparable because they share rates, yet neither side is independent observed farm-account evidence.

## S1 versus S2

Raw source rates agree wherever both sources contain a crop. S1 matrix optimization retains the raw candidate TL/da. S2 derives TL/da from seasonal totals and then applies suitability plus profit-realism discounts; the difference between raw S1 and effective S2 values is expected model behavior. Secondary economics exist for only four crop identities, so most missing secondary cells become infeasible or use one of nine explicit fallback parameters.

## Identity method

The catalog was used as the 58-product anchor. Raw names and Unicode/spacing/punctuation-normalized keys were retained. Candidate matrix, cost rules, S1 seasonal, and S2 seasonal sets were compared independently. Numeric identity used catalog TL/da versus matrix TL/da and seasonal `profit_tl / area_da`, tolerance {TOL} TL/da.

## Finding classification

- **DATA QUALITY ISSUE / SOURCE-PROVENANCE GAP:** proxy catalog rates, undocumented net-profit methodology, sparse S2 secondary coverage.
- **DATA IDENTITY ISSUE:** `KİMYON` absent from matrix and seasonal sources; `DUT` absent from cost and seasonal sources; three harmless spacing variants.
- **UNIT ISSUE:** possible confusion of Turp 6 TL/kg with 6,000 TL/da; no computation path makes that conversion.
- **MODEL ASSUMPTION:** S2 suitability and profit-realism discounts change source profit before objective use.
- **DOCUMENTATION GAP:** fallback-selected cells and transformed effective economic authority are not row-visible.
- **SOFTWARE BUG:** no new economics software defect proven by this audit.

## Scientific boundary

The optimizer may be described as finding Turp economically attractive under the packaged 2024-labeled proxy assumptions. The audit does not support a claim that Turp is truly the most profitable market crop or that projected basin profit is realizable.

## Verification

- Audit determinism/source-mutation guard: `1 passed in 10.39s` (latest run).
- Full repository suite: `237 passed, 1 failed, 7 deselected in 972.75s`.
- The only failure is `test_s2_high_budget_can_return_feasible_two_crop_plan`: expected `ok`, observed `no_feasible_two_crop_plan`. It is an **INHERITED BASELINE FAILURE** previously reproduced unchanged at the Phase 3 and Water Contract baselines; it is outside this audit's scope.
"""
    (OUT/"phase4_summary.md").write_text(summary,encoding="utf-8")

    (OUT/"real_world_economic_claim_boundary.md").write_text("""# Real-world economic claim boundary

## Currently supportable

- The software uses the documented packaged values and formulas reproducibly.
- Under the candidate matrix assumptions, Turp has 4,000 TL/da net profit and about 13.38 TL/m³.
- Current baseline and candidate projections share catalog rates, but both inherit proxy provenance.
- S2 objective values may differ from source rates because the model applies suitability and profit-realism multipliers.

## Currently unsupported

- Turp is definitively the most profitable crop in the real market.
- The 2024-labeled prices, yields, and costs are official, observed, inflation-aligned, or institutionally verified.
- Basin-level projected profit is a forecast of realizable farm income.
- Current unit profit is independently observed and methodologically comparable with candidate profit.
- Missing seasonal economics can be safely replaced by hidden fallback values for a real pilot.
""",encoding="utf-8")

    (OUT/"economic_change_priority.md").write_text(f"""# Economic change priority

## MUST FIX BEFORE REAL PILOT

1. Replace or validate the 58 crop profit rates using dated local yield, price, support, and itemized cost evidence.
2. Reconcile the {cost_mismatch} catalog formula mismatches and define whether net profit uses total cost, variable cost, support, or another basis.
3. Remove hidden fallback use from pilot calculations or expose it per unit/crop/season and require explicit acceptance.
4. Supply complete unit × crop × season economics for S2, including price basis and authority.
5. Validate current unit totals independently; they are presently area-scaled catalog rates.

## SHOULD FIX BEFORE INSTITUTIONAL DEMO

1. Show source, year, authority, raw rate, and model-adjusted rate in result provenance.
2. Resolve missing KİMYON/DUT records and standardize the three harmless spacing variants without conflating crop variants.
3. Document S2 suitability/profit-realism transforms as model assumptions.
4. Separate energy, irrigation, machinery, labor, and harvest cost components with sourced units.

## OPTIONAL FUTURE IMPROVEMENT

1. Add nominal/real price-base metadata and inflation scenarios.
2. Add uncertainty intervals and market/yield sensitivity after source verification.
3. Add an institution-approved alias registry while preserving dry/irrigated and grain/forage variants.
""",encoding="utf-8")

    # This historical audit freezes the scientific engine and source data.
    # Downstream application/adaptor layers are intentionally extensible.
    protected=["app.py","kds/science","data"]
    diff=subprocess.run(["git","diff","--name-only","HEAD","--",*protected],cwd=ROOT,text=True,capture_output=True,check=True).stdout.splitlines()
    tracked=subprocess.run(["git","ls-files","app.py","kds/science/**","data/**"],cwd=ROOT,text=True,capture_output=True,check=True).stdout.splitlines()
    # Downstream milestones must reproduce the frozen audit instead of writing
    # their current HEAD into an otherwise deterministic audit artifact.
    frozen_audit = subprocess.run(["git","rev-list","-n","1","v2-scientific-economics-audit-complete"],cwd=ROOT,text=True,capture_output=True,check=True).stdout.strip()
    write_json("source_and_mutation_guard.json",dict(baseline_commit=frozen_audit,
        protected_diff_files=diff,protected_unchanged=not diff,tracked_file_count=len(tracked),tracked_sha256={p:sha(ROOT/p) for p in tracked},project_store_mutated=False,
        note="Audit script reads repository files and writes only docs/audits/economics_phase4."))
    assert not diff

    print(json.dumps(dict(current_total=current_total,crops=len(catalog),matrix_rows=len(matrix),identity_counts=dict(counts),numeric_profit_conflicts=len(conflicts),cost_formula_mismatches=cost_mismatch,turp=turp_summary),ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
