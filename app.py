from __future__ import annotations

import json
import csv
import os
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

import pandas as pd
import numpy as np
from flask import Flask, jsonify, request, send_from_directory
import time
import statistics

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
APP_BUILD = "v1.0-tez-prototipi-diversity-soft"
APP_TITLE = "Tarımsal Karar Destek Sistemi"
APP_GENERATED_AT = datetime.now(timezone.utc).isoformat()

app = Flask(__name__, static_folder=None)

@app.after_request
def add_no_cache_headers(response):
    """Avoid stale JS/GeoJSON/index files while drawing parcels."""
    try:
        path = request.path or ""
        if path.endswith((".js", ".css", ".json", ".geojson")) or path.startswith("/api/geojson_files") or path.startswith("/api/geojson_bundle") or path.startswith("/data/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
    except Exception:
        pass
    return response

# Print the real file path so you can verify which project folder is running.
print(f"[Akkaya {APP_BUILD}] Running app from: {__file__}")

# -----------------------------
# Data loading helpers
# -----------------------------
_cache: Dict[str, Any] = {}


def safe_float(x, default: float = 0.0) -> float:
    """Convert input to float safely (handles None, '', '1,23', '1.234,56')."""
    try:
        if x is None:
            return float(default)
        try:
            import numpy as _np
            if isinstance(x, (_np.integer, _np.floating)):
                return float(x)
        except Exception:
            pass
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip()
        if s == "" or s.lower() in ("none", "nan", "null"):
            return float(default)
        s = s.replace(" ", "").replace("\u00a0","")
        if s.count(",") == 1 and s.count(".") >= 1:
            s = s.replace(".", "").replace(",", ".")
        elif s.count(",") == 1 and s.count(".") == 0:
            s = s.replace(",", ".")
        return float(s)
    except Exception:
        return float(default)

def safe_int(x, default: int = 0) -> int:
    try:
        if x is None:
            return int(default)
        try:
            import numpy as _np
            if isinstance(x, (_np.integer,)):
                return int(x)
        except Exception:
            pass
        if isinstance(x, int):
            return int(x)
        s = str(x).strip()
        if s == "" or s.lower() in ("none", "nan", "null"):
            return int(default)
        return int(float(s.replace(",", ".")))
    except Exception:
        return int(default)


def normalize_parcel_id(pid: Any) -> str:
    """Normalize parcel ids across old/new files.

    Examples:
      P001 -> P1
      SAZ_P001 -> P1
      BAH_P001 -> BAH_P1
    """
    s = str(pid or "").strip().upper()
    if not s:
        return ""
    s = s.replace(" ", "")
    # Historic Sazlıca ids in season CSVs used SAZ_P### while the active project uses P#.
    m = re.match(r'^SAZ[_-]?P0*([0-9]+)$', s)
    if m:
        return f"P{int(m.group(1))}"
    m = re.match(r'^([A-Z]+[_-]?P)0*([0-9]+)$', s)
    if m:
        pref = m.group(1).replace('-', '_')
        return f"{pref}{int(m.group(2))}"
    m = re.match(r'^P0*([0-9]+)$', s)
    if m:
        return f"P{int(m.group(1))}"
    return s


def normalize_parcel_id_series(df: pd.DataFrame, cols: Optional[List[str]] = None) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    cols = cols or [c for c in ("parcel_id", "parsel_id", "id") if c in df.columns]
    for col in cols:
        if col in df.columns:
            df[col] = df[col].astype(str).map(normalize_parcel_id)
    return df


# -----------------------------
# Minimal CSV loaders used by 15Y impact endpoints
# -----------------------------

def load_parcels_csv() -> pd.DataFrame:
    """Load legacy per-parcel baseline summary.

    Expected: data/parsel_su_kar_ozet.csv
    Must provide columns:
      - parsel_id (string)
      - alan_da (float)
      - mevcut_su_m3 (float)
      - mevcut_kar_tl (float)
    If columns are missing, we try to infer/rename common alternatives.
    """
    path = DATA_DIR / "parsel_su_kar_ozet.csv"
    if not path.exists():
        return pd.DataFrame(columns=["parsel_id", "alan_da", "mevcut_su_m3", "mevcut_kar_tl"])
    df = pd.read_csv(path)
    df = df.copy()
    # Normalize column names
    cols = {c.lower().strip(): c for c in df.columns}
    # id
    if "parsel_id" not in df.columns:
        if "parcel_id" in df.columns:
            df["parsel_id"] = df["parcel_id"]
        elif "id" in df.columns:
            df["parsel_id"] = df["id"]
        elif "parsel" in df.columns:
            df["parsel_id"] = df["parsel"]
    # area
    if "alan_da" not in df.columns:
        if "area_da" in df.columns:
            df["alan_da"] = df["area_da"]
        elif "alan" in df.columns:
            df["alan_da"] = df["alan"]
    # baseline water
    if "mevcut_su_m3" not in df.columns:
        for cand in ("water_m3", "su_m3", "yillik_su_m3", "water"):
            if cand in df.columns:
                df["mevcut_su_m3"] = df[cand]
                break
    # baseline profit
    if "mevcut_kar_tl" not in df.columns:
        for cand in ("profit_tl", "kar_tl", "yillik_kar_tl", "profit"):
            if cand in df.columns:
                df["mevcut_kar_tl"] = df[cand]
                break

    # Type normalize
    if "parsel_id" in df.columns:
        df["parsel_id"] = df["parsel_id"].astype(str).map(normalize_parcel_id)
    for c in ("alan_da", "mevcut_su_m3", "mevcut_kar_tl"):
        if c in df.columns:
            df[c] = df[c].apply(lambda x: safe_float(x, 0.0))
        else:
            df[c] = 0.0

    return df[["parsel_id", "alan_da", "mevcut_su_m3", "mevcut_kar_tl"]].copy()


def load_crops_csv() -> pd.DataFrame:
    """Load crop parameter table used for water and profit calculations.

    Primary expected: data/urun_parametreleri_demo.csv
    Fallback: data/enhanced_dataset/csv/crop_params_assumed.csv

    Required columns:
      - urun_adi
      - su_tuketimi_m3_da
      - beklenen_verim_kg_da (optional for profit)
      - fiyat_tl_kg (optional for profit)
      - maliyet_tl_da (optional for profit)
    """
    primary = DATA_DIR / "urun_parametreleri_demo.csv"
    fallback = DATA_DIR / "enhanced_dataset" / "csv" / "crop_params_assumed.csv"
    path = primary if primary.exists() else fallback
    if not path.exists():
        return pd.DataFrame(columns=[
            "urun_adi",
            "su_tuketimi_m3_da",
            "beklenen_verim_kg_da",
            "fiyat_tl_kg",
            "maliyet_tl_da",
        ])
    df = pd.read_csv(path)
    df = df.copy()
    # Normalize common alternative headers
    if "urun_adi" not in df.columns:
        for cand in ("crop", "crop_name", "urun", "name"):
            if cand in df.columns:
                df["urun_adi"] = df[cand]
                break
    if "su_tuketimi_m3_da" not in df.columns:
        for cand in ("water_m3_da", "su_m3_da", "water_per_da"):
            if cand in df.columns:
                df["su_tuketimi_m3_da"] = df[cand]
                break
    for need in ("beklenen_verim_kg_da", "fiyat_tl_kg", "maliyet_tl_da"):
        if need not in df.columns:
            # common aliases
            alias_map = {
                "beklenen_verim_kg_da": ("yield_kg_da", "verim_kg_da"),
                "fiyat_tl_kg": ("price_tl_kg", "fiyat"),
                "maliyet_tl_da": ("cost_tl_da", "maliyet"),
            }
            for cand in alias_map.get(need, ( )):
                if cand in df.columns:
                    df[need] = df[cand]
                    break
        if need not in df.columns:
            df[need] = 0.0

    df["urun_adi"] = df["urun_adi"].astype(str)
    for c in ("su_tuketimi_m3_da", "beklenen_verim_kg_da", "fiyat_tl_kg", "maliyet_tl_da"):
        df[c] = df[c].apply(lambda x: safe_float(x, 0.0))
    return df[["urun_adi", "su_tuketimi_m3_da", "beklenen_verim_kg_da", "fiyat_tl_kg", "maliyet_tl_da"]].copy()


def load_area_overrides() -> Dict[str, Dict[str, float]]:
    """Optional parcel area overrides derived from GeoJSON area calculations.

    Expected file: data/excel_derived/parcel_area_overrides.csv
    Columns: parcel_id, geojson_file_no, area_m2, area_da, area_ha
    """
    key = "area_overrides"
    if key in _cache:
        return _cache[key]

    path = DATA_DIR / "excel_derived" / "parcel_area_overrides.csv"
    out: Dict[str, Dict[str, float]] = {}
    if path.exists():
        try:
            df = pd.read_csv(path)
            if "parcel_id" in df.columns:
                df["parcel_id"] = df["parcel_id"].astype(str).str.strip()
                for _, r in df.iterrows():
                    pid = normalize_parcel_id(r.get("parcel_id",""))
                    if not pid:
                        continue
                    # Be tolerant to Turkish/European numeric formats (e.g. "46.799,5")
                    out[pid] = {
                        "geojson_file_no": safe_float(r.get("geojson_file_no", 0), 0.0),
                        "area_m2": safe_float(r.get("area_m2", 0), 0.0),
                        "area_da": safe_float(r.get("area_da", 0), 0.0),
                        "area_ha": safe_float(r.get("area_ha", 0), 0.0),
                    }
        except Exception:
            out = {}
    _cache[key] = out
    return out

def normalize_crop_key(name: str) -> str:
    s = (name or "").strip().upper()
    # Turkish -> ASCII-like
    tr_map = str.maketrans({"Ç":"C","Ğ":"G","İ":"I","Ö":"O","Ş":"S","Ü":"U","\u00c2":"A","Û":"U","Î":"I",
                            "ç":"C","ğ":"G","ı":"I","ö":"O","ş":"S","ü":"U"})
    s = s.translate(tr_map)
    for ch in ["-", ".", ",", "(", ")", "[", "]", "{", "}", "/"]:
        s = s.replace(ch, " ")
    s = "_".join([p for p in s.split() if p])
    return s


# Canonical crop aliases used to keep established perennial / orchard crops locked
# even when Excel files use slightly different spellings (e.g. KAYISI vs KAYSI,
# NEKTARIN vs NEKTAR, UZUM vs BAG).
_CANONICAL_CROP_ALIASES = {
    "KAYISI": "KAYSI",
    "NEKTARIN": "NEKTAR",
    "UZUM": "BAG",
    "UZUM_SOFRALIK": "BAG",
    "UZUM_SARAPLIK": "BAG",
    "VISNE": "VISNE",
    "VİSNE": "VISNE",
    "SEFTALI": "SEFTALI",
    "ERIK": "ERIK",
    "CEVIZ": "CEVIZ",
    "CEVİZ": "CEVIZ",
}


def canonical_crop_key(name: str) -> str:
    """Return a stable crop key for cross-file matching.

    The Excel-derived matrix sometimes stores crops as compact ids such as
    BUGDAYDANE, while UI/catalog records use names such as BUĞDAY (Dane) or
    BUGDAY_DANE. For decision locking ("mevcut ürün"), perennial protection and
    candidate filtering we compare the compact canonical form.
    """
    nk = normalize_crop_key(name)
    compact = nk.replace("_", "")
    aliases = {
        "KAYISI": "KAYSI",
        "KAYSI": "KAYSI",
        "NEKTARIN": "NEKTAR",
        "NEKTAR": "NEKTAR",
        "UZUM": "BAG",
        "UZUMSOFRALIK": "BAG",
        "UZUMSARAPLIK": "BAG",
        "BAGUZUM": "BAG",
        "BAG": "BAG",
        "CEVIZ": "CEVIZ",
        "VISNE": "VISNE",
        "SEFTALI": "SEFTALI",
        "ERIK": "ERIK",
        "BUGDAYDANE": "BUGDAYDANE",
        "ARPADANE": "ARPADANE",
        "CAVDARDANE": "CAVDARDANE",
        "YULAFDANE": "YULAFDANE",
        "TRITIKALEDANE": "TRITIKALEDANE",
        "MISIRDANE": "MISIRDANE",
        "CAVDARYESILOT": "CAVDARYESILOT",
        "YULAFYESILOT": "YULAFYESILOT",
        "TRITIKALEYESILOT": "TRITIKALEYESILOT",
        "FIGYESILOT": "FIGYESILOT",
        "YONCAYESILOT": "YONCAYESILOT",
        "SILAJLIKMISIR": "SILAJLIKMISIR",
        "KURUFASULYE": "KURUFASULYE",
        "FASULYETAZE": "FASULYETAZE",
        "SEKERPANCARI": "SEKERPANCARI",
        "SOGANKURU": "SOGANKURU",
        "SOGANTAZE": "SOGANTAZE",
        "SALCALIKDOMATES": "SALCALIKDOMATES",
        "SOFRALIKDOMATES": "SOFRALIKDOMATES",
        "SALCALIKBIBER": "SALCALIKBIBER",
        "SIVRIBIBER": "SIVRIBIBER",
        "HIYARSOFRALIK": "HIYARSOFRALIK",
        "LAHANABEYAZ": "LAHANABEYAZ",
        "KABAKCEREZLIK": "KABAKCEREZLIK",
        "KABAKSAKIZ": "KABAKSAKIZ",
        "TURPKIRMIZI": "TURPKIRMIZI",
    }
    old_alias = _CANONICAL_CROP_ALIASES.get(nk)
    if old_alias:
        return normalize_crop_key(old_alias).replace("_", "")
    return aliases.get(compact, compact)


def crop_keys_equivalent(a: str, b: str) -> bool:
    return canonical_crop_key(a) == canonical_crop_key(b)



# Global key for fallow (NADAS). This is always allowed so the solver never needs to fabricate extreme water values.
FALLOW = normalize_crop_key('NADAS')

DIVERSITY_DEFAULTS = {
    "enabled": True,
    "max_crop_share": 0.25,
    "max_top3_share": 0.65,
    "hhi_target": 0.18,
    "soft_penalty_enabled": True,
    "repair_enabled": False,
    "crop_share_penalty_weight": 1.0,
    "top3_penalty_weight": 0.5,
    "hhi_penalty_weight": 0.5,
}

# -----------------------------------------------------------------------------
# Profit realism (thesis-friendly safeguards)
# -----------------------------------------------------------------------------
# Some economic inputs in this demo are assumed / user-generated. Without
# safeguards, a few "high margin" crops can dominate the optimizer and produce
# implausibly high basin-level net profits. To keep recommendations defendable,
# we apply conservative caps and risk discounts on *net profit per da*.

def _is_rainfed_crop(crop_key: str) -> bool:
    ck = str(crop_key or '').upper()
    return ck.endswith('_KURU') or ('KURU' in ck and not ck.startswith('KURU_'))


def _realistic_profit_per_da(crop_key: str, profit_per_da: float) -> float:
    """Clamp/discount profit per da to avoid unrealistic outputs.

    Notes:
      - This is intentionally conservative. The goal is to show *water saving with
        acceptable profit*, not to maximize theoretical income from assumed prices.
      - Caps are on NET profit (after variable costs) per da.
    """
    try:
        v = float(profit_per_da)
    except Exception:
        return 0.0
    if not np.isfinite(v):
        return 0.0
    if v < 0:
        return 0.0

    ck = normalize_crop_key(crop_key)

    # Base caps (TL/da) — conservative to keep thesis outputs defendable.
    # These represent *net* profit per decare and already embed a risk discount.
    cap_default = 8000.0
    cap_rainfed = 4500.0

    # Global risk/uncertainty discount (assumed prices, yield variability, fixed costs not modeled).
    # This keeps basin-level totals from inflating unrealistically.
    v *= 0.55

    # Heuristic crop group handling
    if _is_rainfed_crop(ck):
        cap = cap_rainfed
        # rainfed income is also more volatile
        v *= 0.90
    else:
        cap = cap_default

    # Vegetables / niche crops tend to have higher margins but also higher risk.
    # We keep a slightly higher cap yet apply a stronger discount.
    veg_markers = ('BIBER', 'DOMATES', 'MARUL', 'ISPANAK', 'SOGAN', 'KABAK', 'KARPUZ', 'KAVUN')
    if any(m in ck for m in veg_markers):
        cap = max(cap, 9500.0)
        v *= 0.85

    # Strong discount if per-da profit is extreme (likely from assumed prices)
    if v > 6500.0:
        v *= 0.85

    return float(min(v, cap))


def _apply_profit_realism(R: np.ndarray, crop_list: List[str]) -> np.ndarray:
    """Apply realism transform to a (P x C) profit matrix."""
    try:
        out = R.copy()
        for j, ck in enumerate(crop_list):
            if normalize_crop_key(ck) == FALLOW:
                continue
            col = out[:, j]
            # vectorize via np.frompyfunc-like loop for clarity
            for i in range(col.shape[0]):
                if np.isfinite(col[i]):
                    col[i] = _realistic_profit_per_da(ck, float(col[i]))
            out[:, j] = col
        return out
    except Exception:
        return R

# -----------------------------
# Crop metadata helpers (family + suitability)
# -----------------------------


def normalize_crop_name(name: str) -> str:
    """Backward-compatible alias used by some parts of the codebase.

    We standardize crop keys with normalize_crop_key(). Keeping this alias avoids
    NameError if older code paths still call normalize_crop_name().
    """
    return normalize_crop_key(name)


def infer_parcel_type_for_selection(value: Any) -> str:
    """Infer parcel type as field / vegetable / orchard from parcel dict or crop text."""
    try:
        if isinstance(value, dict):
            raw = str(value.get("parcel_type", "") or value.get("land_type", "") or "").strip().lower()
            if raw in ("field", "vegetable", "orchard"):
                return raw
            raw = str(value.get("current_crop", "") or value.get("name", "") or "").strip()
        else:
            raw = str(value or "").strip()
        nk = normalize_crop_key(raw)
        orchard_hints = {"ELMA","ARMUT","KIRAZ","VISNE","SEFTALI","NEKTARIN","NEKTAR","KAYISI","KAYSI","ERIK","CEVIZ","BAG","UZUM","BADEM","AYVA","DUT","ZERDALI","IGDE","CILEK"}
        vegetable_hints = {"DOMATES","BIBER","LAHANA","PATLICAN","ISPANAK","PIRASA","SOGAN","SARIMSAK","KABAK","KARPUZ","KAVUN","HIYAR","TURP","BAMYA","FASULYE_TAZE","BEZELYE"}
        if any(h in nk for h in orchard_hints):
            return "orchard"
        if any(h in nk for h in vegetable_hints):
            return "vegetable"
    except Exception:
        pass
    return "field"

def catalog_parcel_type(rec: Optional[Dict[str, Any]]) -> str:
    if not isinstance(rec, dict):
        return ""
    for key in ("parcelType", "parcel_type", "type"):
        val = str(rec.get(key, "") or "").strip().lower()
        if val in ("field", "vegetable", "orchard"):
            return val
    cat = str(rec.get("category", "") or rec.get("kategori", "")).strip().lower()
    if "meyve" in cat or "bağ" in cat:
        return "orchard"
    if "sebze" in cat:
        return "vegetable"
    if "tarla" in cat or "yem" in cat:
        return "field"
    return ""


def load_crop_family_map() -> Dict[str, str]:
    """Map normalized crop_key -> crop_family."""
    key = "crop_family_map"
    if key in _cache:
        return _cache[key]
    path = DATA_DIR / "enhanced_dataset" / "csv" / "crop_family_map.csv"
    m: Dict[str, str] = {}
    if path.exists():
        try:
            df = pd.read_csv(path)
            if "crop" in df.columns and "crop_family" in df.columns:
                for _, r in df.iterrows():
                    ck = normalize_crop_key(str(r.get("crop","")))
                    fam = str(r.get("crop_family","") or "").strip().lower()
                    if ck:
                        m[ck] = fam
        except Exception:
            m = {}
    # Ensure a universal fallow option exists.
    # Using a distinct family avoids rotation-rule dead-ends.
    m.setdefault(normalize_crop_key("NADAS"), "fallow")

    _cache[key] = m
    return m


def infer_crop_season_label(crop_name: str, parcel_type: str = "") -> str:
    """Best-effort season label used in UI/report payloads.
    This is transparent heuristic logic, not a hidden model.
    """
    nk = normalize_crop_key(crop_name)
    ptype = str(parcel_type or "").strip().lower()
    if ptype == "orchard":
        return "Çok yıllık / bahçe"
    if any(x in nk for x in ("DOMATES","BIBER","KABAK","PATLICAN","HIYAR","KARPUZ","KAVUN","MISIR","PANCAR","PATATES","AYCICEGI","SOGAN","SARIMSAK","LAHANA","FASULYE_TAZE","CILEK")):
        return "Yazlık"
    if any(x in nk for x in ("BUGDAY","ARPA","CAVDAR","YULAF","TRITIKALE","MERCIMEK","NOHUT","FIG","FIĞ","YEM_BEZELYESI")):
        return "Kışlık / serin dönem"
    return "Ana ürün"


def _soil_rank_from_text(value: Any) -> int:
    """Return 1..8 where 1 is best. Unknown -> 3."""
    try:
        s = str(value or "").strip().upper()
        if not s:
            return 3
        roman = {"I":1,"II":2,"III":3,"IV":4,"V":5,"VI":6,"VII":7,"VIII":8}
        if s in roman:
            return roman[s]
        for k,v in roman.items():
            if k in s:
                return v
        digits = "".join(ch for ch in s if ch.isdigit())
        if digits:
            return max(1, min(8, int(digits[0])))
    except Exception:
        pass
    return 3


def _agronomic_reason_bundle(
    current_crop: str,
    candidate_crop: str,
    parcel_type: str,
    lcc_text: Any,
    quota_m3: float,
    area_da: float,
    water_m3_da: float,
    feasible_area_da: float,
    irrigation_text: str = "",
    peak_month: str = "",
) -> Dict[str, Any]:
    """Transparent rule-based compatibility explanation.
    Only factors available in the project data are used. Disease/nutrient effects are
    represented via crop-family/rotation and high-input crop heuristics, not lab analysis.
    """
    fam_map = load_crop_family_map()
    cand_key = normalize_crop_key(candidate_crop)
    cur_key = normalize_crop_key(current_crop)
    cand_fam = str(fam_map.get(cand_key, "") or "").strip().lower()
    cur_fam = str(fam_map.get(cur_key, "") or "").strip().lower()
    ptype = str(parcel_type or "").strip().lower()
    reasons = []
    cautions = []
    score = 0.0

    season_label = infer_crop_season_label(candidate_crop, ptype)
    reasons.append(f"Mevsim uyumu: {season_label}.")
    score += 0.14

    full_fit = feasible_area_da >= max(0.0, area_da) - 1e-6
    coverage_pct = 100.0 * feasible_area_da / max(1e-9, area_da)
    if full_fit:
        reasons.append("Parsel su kotasına tam sığıyor.")
        score += 0.28
    else:
        reasons.append(f"Su kotası nedeniyle alanın yaklaşık %{coverage_pct:.0f} kadarı güvenli görünüyor.")
        cautions.append("Tam parsel yerine kota kadar ekim önerildi.")
        score += 0.10

    if ptype == "orchard":
        if cand_key == cur_key:
            reasons.append("Çok yıllık parselde kurulu ana ürün korunuyor.")
            score += 0.30
        else:
            cautions.append("Bahçe parselinde ana ürün değişimi uygun değildir.")
            score -= 0.60
    else:
        if cand_fam and cur_fam and cand_fam == cur_fam and cand_key != cur_key:
            cautions.append("Mevcut ürünle aynı familya; hastalık/rotasyon baskısı artabilir.")
            score -= 0.18
        elif cand_fam and cur_fam and cand_fam != cur_fam:
            reasons.append("Farklı familya; rotasyon ve hastalık baskısı açısından daha dengeli.")
            score += 0.16

    soil_rank = _soil_rank_from_text(lcc_text)
    high_input = any(x in cand_key for x in ("DOMATES","BIBER","PATATES","PANCAR","KABAK","KAVUN","KARPUZ","SOGAN","SARIMSAK","LAHANA"))
    if high_input and soil_rank >= 5:
        cautions.append(f"Toprak kabiliyet sınıfı {soil_rank}; yüksek girdi isteyen ürün dikkatle yönetilmeli.")
        score -= 0.12
    elif (not high_input) and soil_rank >= 5:
        reasons.append("Toprak sınıfı zayıf olduğu için daha dayanıklı ürün lehine uyumlu.")
        score += 0.08
    else:
        reasons.append("Toprak sınıfı ürün tipi için kabul edilebilir.")
        score += 0.08

    irr = str(irrigation_text or "").strip()
    if irr:
        if "damla" in irr.lower():
            reasons.append("Önerilen sulama yöntemi damla; su verimliliği açısından güçlü.")
            score += 0.08
        elif "yağmurlama" in irr.lower() or "yagmurlama" in irr.lower():
            reasons.append("Yağmurlama ile uygulanabilir.")
            score += 0.04
        elif "kuru" in irr.lower():
            reasons.append("Yağışa bağlı / destek sulama ile düşünülebilir.")
            score += 0.02

    if peak_month:
        reasons.append(f"Pik su dönemi: {peak_month}.")
        score += 0.02

    modeled_factors = [
        "su kotası", "mevsim etiketi", "ürün familyası / rotasyon",
        "parsel tipi", "toprak kabiliyet sınıfı", "sulama yöntemi", "pik su ayı"
    ]
    if cautions:
        score = max(0.0, min(1.0, score))
    else:
        score = max(0.0, min(1.0, score + 0.08))
    summary = " ; ".join(reasons + cautions[:2])
    return {
        "season_label": season_label,
        "compatibility_score": float(score),
        "reasons": reasons,
        "cautions": cautions,
        "modeled_factors": modeled_factors,
        "summary": summary,
        "coverage_pct": float(coverage_pct),
    }


def load_crop_irrigation_map() -> Dict[str, Dict[str, Any]]:
    """Load crop -> irrigation method mapping from data/crop_irrigation_map.json."""
    key = "crop_irrigation_map"
    if key in _cache:
        return _cache[key]
    path = DATA_DIR / "crop_irrigation_map.json"
    out: Dict[str, Dict[str, Any]] = {}
    try:
        if path.exists():
            out = load_json(path) or {}
    except Exception:
        out = {}
    # Normalize keys so lookups work even if crop names differ in punctuation/case.
    # We keep both raw keys and normalized keys pointing to the same mapping.
    try:
        normed: Dict[str, Dict[str, Any]] = {}
        for k, v in (out or {}).items():
            if not isinstance(v, dict):
                continue
            nk = normalize_crop_key(str(k))
            if nk and nk not in out and nk not in normed:
                normed[nk] = v
        # also allow fallow key
        normed.setdefault(normalize_crop_key("NADAS"), {"current": "fallow", "recommended": "fallow"})
        out.update(normed)
    except Exception:
        pass
    _cache[key] = out
    return out


def load_irrigation_methods() -> Dict[str, Dict[str, Any]]:
    """Load irrigation method efficiencies from enhanced_dataset/csv/irrigation_methods_assumed.csv."""
    key = "irrigation_methods_map"
    if key in _cache:
        return _cache[key]
    out: Dict[str, Dict[str, Any]] = {}
    try:
        frames = load_enhanced_frames()
        df = frames.get("irrigation_methods")
        if df is not None and len(df) > 0:
            cols = list(df.columns)
            for _, r in df.iterrows():
                mth = str(r.get("method","")).strip()
                if not mth:
                    continue
                rec = {}
                for c in cols:
                    if c == "method":
                        continue
                    rec[c] = r.get(c)
                out[mth] = rec
    except Exception:
        out = {}
    # Normalize keys so lookups work even if crop names differ in punctuation/case.
    # We keep both raw keys and normalized keys pointing to the same mapping.
    try:
        normed: Dict[str, Dict[str, Any]] = {}
        for k, v in (out or {}).items():
            if not isinstance(v, dict):
                continue
            nk = normalize_crop_key(str(k))
            if nk and nk not in out and nk not in normed:
                normed[nk] = v
        # also allow fallow key
        normed.setdefault(normalize_crop_key("NADAS"), {"current": "fallow", "recommended": "fallow"})
        out.update(normed)
    except Exception:
        pass
    _cache[key] = out
    return out

def load_crop_suitability_map() -> Dict[Tuple[str, str], float]:
    """Map (land_capability_class, crop_key) -> suitability_score (0..1).

    v18 note: the CSV may contain openly-labeled heuristic/proxy scores. We keep the
    numeric layer separate from provenance, but the report endpoints expose the source mix.
    """
    key = "crop_suitability_map"
    if key in _cache:
        return _cache[key]
    path = DATA_DIR / "enhanced_dataset" / "csv" / "crop_suitability_assumed.csv"
    m: Dict[Tuple[str, str], float] = {}
    if path.exists():
        try:
            df = pd.read_csv(path)
            score_cols = [
                "suitability_score_assumed", "suitability_score", "score",
                "score_assumed", "score_proxy"
            ]
            score_col = next((c for c in score_cols if c in df.columns), None)
            for _, r in df.iterrows():
                lcc = str(r.get("land_capability_class","") or "").strip().upper()
                ck = normalize_crop_key(str(r.get("crop","")))
                raw = r.get(score_col, 0.85) if score_col else 0.85
                sc = safe_float(raw, 0.85)
                if lcc and ck:
                    m[(lcc, ck)] = float(max(0.0, min(1.0, sc)))
        except Exception:
            m = {}
    _cache[key] = m
    return m


def load_rotation_rules() -> pd.DataFrame:
    """Load default crop rotation rules table (CSV)."""
    key = "rotation_rules"
    if key in _cache:
        return _cache[key]
    path = DATA_DIR / "enhanced_dataset" / "csv" / "rotation_rules_default.csv"
    if path.exists():
        try:
            df = pd.read_csv(path)
            _cache[key] = df
            return df
        except Exception:
            pass
    df = pd.DataFrame(columns=["rule_id","type","from_family","to_family","min_year_gap","penalty_weight","note"])
    _cache[key] = df
    return df

LEGUME_FAMILIES = {"fabaceae", "leguminosae"}

# -----------------------------
# Portfolio constraints (project-critical)
# -----------------------------

def _unique_crop_penalty(chosen_keys: List[str], min_unique: int, penalty_weight: float = 5e8) -> float:
    """Penalty if the plan uses fewer than min_unique different crops (excluding fallow)."""
    keys = [k for k in chosen_keys if k and k != FALLOW]
    uniq = len(set(keys))
    if min_unique <= 1:
        return 0.0
    if uniq >= min_unique:
        return 0.0
    gap = (min_unique - uniq)
    return float(gap) * float(penalty_weight)

def _max_share_penalty(chosen_keys: List[str], areas: np.ndarray, max_share: Optional[float], penalty_weight: float = 5e8) -> float:
    """Penalty if any single crop exceeds max_share of total area (excluding fallow)."""
    if max_share is None:
        return 0.0
    ms = float(max_share)
    if not (0.05 < ms < 1.0):
        return 0.0
    total_area = float(np.sum(areas)) if np.sum(areas) > 0 else 1.0
    by = {}
    for k,a in zip(chosen_keys, areas.tolist()):
        if not k or k == FALLOW:
            continue
        by[k] = by.get(k, 0.0) + float(a)
    pen = 0.0
    for k, a in by.items():
        sh = float(a) / total_area
        if sh > ms:
            pen += ((sh - ms) / max(1e-6, ms)) ** 2 * float(penalty_weight)
    return float(pen)


def _diversity_config(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg = dict(DIVERSITY_DEFAULTS)
    if isinstance(overrides, dict):
        for k in cfg.keys():
            if k in overrides:
                cfg[k] = overrides[k]
    return cfg


def _crop_name_for_diversity(name: Any) -> str:
    text = str(name or "").strip()
    return text if text else ""


def _diversity_penalty_from_shares(shares: List[float], cfg: Optional[Dict[str, Any]] = None) -> float:
    cfg = _diversity_config(cfg)
    if not bool(cfg.get("enabled", True)):
        return 0.0
    max_crop = float(cfg.get("max_crop_share", 0.25) or 0.25)
    max_top3 = float(cfg.get("max_top3_share", 0.65) or 0.65)
    hhi_target = float(cfg.get("hhi_target", 0.18) or 0.18)
    clean = []
    for x in shares or []:
        try:
            v = float(x)
        except Exception:
            continue
        if np.isfinite(v):
            clean.append(max(0.0, v))
    clean.sort(reverse=True)
    crop_penalty = sum((s - max_crop) ** 2 for s in clean if s > max_crop)
    top3_share = float(sum(clean[:3]))
    top3_penalty = (top3_share - max_top3) ** 2 if top3_share > max_top3 else 0.0
    hhi = float(sum(s * s for s in clean))
    hhi_penalty = (hhi - hhi_target) ** 2 if hhi > hhi_target else 0.0
    return float(
        float(cfg.get("crop_share_penalty_weight", 1.0) or 1.0) * crop_penalty
        + float(cfg.get("top3_penalty_weight", 0.5) or 0.5) * top3_penalty
        + float(cfg.get("hhi_penalty_weight", 0.5) or 0.5) * hhi_penalty
    )


def _diversity_score_penalty_from_keys(chosen_keys: List[str], areas: np.ndarray, cfg: Optional[Dict[str, Any]] = None) -> float:
    cfg = _diversity_config(cfg)
    if not bool(cfg.get("enabled", True)) or not bool(cfg.get("soft_penalty_enabled", True)):
        return 0.0
    by: Dict[str, float] = {}
    try:
        for k, a in zip(chosen_keys or [], list(areas)):
            name = _crop_name_for_diversity(k)
            if not name or normalize_crop_key(name) == FALLOW:
                continue
            area = safe_float(a, 0.0)
            if area <= 0:
                continue
            by[name] = by.get(name, 0.0) + float(area)
    except Exception:
        return 0.0
    total = float(sum(by.values()))
    if total <= 1e-9:
        return 0.0
    penalty = _diversity_penalty_from_shares([v / total for v in by.values()], cfg)
    return float(penalty * 5.0e8)


def compute_diversity_metrics(plan_rows: List[Dict[str, Any]], total_area_da: float = 0.0,
                              diversity_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg = _diversity_config(diversity_config)
    by: Dict[str, float] = {}
    for row in plan_rows or []:
        if not isinstance(row, dict):
            continue
        name = _crop_name_for_diversity(row.get("crop_name") or row.get("name") or row.get("chosenCrop") or row.get("crop"))
        if not name or normalize_crop_key(name) == FALLOW:
            continue
        area = safe_float(row.get("area_da", row.get("area", row.get("plannedAreaDa", 0.0))), 0.0)
        if area <= 0:
            continue
        by[name] = by.get(name, 0.0) + float(area)

    changed_area = float(sum(by.values()))
    total_area = safe_float(total_area_da, 0.0)
    if total_area <= 0:
        total_area = changed_area
    shares_changed = {k: (float(v) / max(1e-9, changed_area)) for k, v in by.items()}
    shares_total = {k: (float(v) / max(1e-9, total_area)) for k, v in by.items()}
    ordered = sorted(shares_changed.items(), key=lambda x: x[1], reverse=True)
    top_crop = ordered[0][0] if ordered else None
    top_share = float(ordered[0][1]) if ordered else 0.0
    top_area = float(by.get(top_crop, 0.0)) if top_crop else 0.0
    top3_share = float(sum(v for _, v in ordered[:3]))
    top_share_total = float(shares_total.get(top_crop, 0.0)) if top_crop else 0.0
    top3_share_total = float(sum(shares_total.get(k, 0.0) for k, _ in ordered[:3]))
    hhi = float(sum(v * v for v in shares_changed.values()))
    max_crop = float(cfg.get("max_crop_share", 0.25) or 0.25)
    max_top3 = float(cfg.get("max_top3_share", 0.65) or 0.65)
    hhi_target = float(cfg.get("hhi_target", 0.18) or 0.18)
    warnings: List[str] = []
    if top_crop and top_share > max_crop + 1e-9:
        warnings.append(
            f"{top_crop}, değişen öneri alanının %{top_share * 100:.1f}'ini kaplamaktadır. "
            f"Bu değer %{max_crop * 100:.0f} çeşitlilik sınırını aşmaktadır."
        )
    if top3_share > max_top3 + 1e-9:
        warnings.append(
            f"İlk 3 ürün, değişen öneri alanının %{top3_share * 100:.1f}'ini kaplamaktadır. "
            f"Bu değer %{max_top3 * 100:.0f} sınırını aşmaktadır."
        )
    if hhi > hhi_target + 1e-9:
        warnings.append(
            f"HHI ürün yoğunlaşma endeksi {hhi:.3f}; hedef değer {hhi_target:.3f} üzerindedir."
        )
    penalty = _diversity_penalty_from_shares(list(shares_changed.values()), cfg)
    feasible = bool((top_share <= max_crop + 1e-9) and (top3_share <= max_top3 + 1e-9) and (hhi <= hhi_target + 1e-9))
    return {
        "crop_area_by_crop": {k: float(v) for k, v in sorted(by.items(), key=lambda x: x[1], reverse=True)},
        "crop_share_by_crop": {k: float(v) for k, v in ordered},
        "crop_share_changed_by_crop": {k: float(v) for k, v in ordered},
        "crop_share_total_by_crop": {k: float(shares_total.get(k, 0.0)) for k, _ in ordered},
        "changed_area_da": float(changed_area),
        "total_plan_area_da": float(total_area),
        "top_crop": top_crop,
        "top_crop_area_da": float(top_area),
        "top_crop_share": float(top_share),
        "top_crop_share_changed": float(top_share),
        "top_crop_share_total": float(top_share_total),
        "top3_crop_share": float(top3_share),
        "top3_crop_share_changed": float(top3_share),
        "top3_crop_share_total": float(top3_share_total),
        "hhi": float(hhi),
        "max_crop_share_limit": float(max_crop),
        "max_top3_share_limit": float(max_top3),
        "hhi_target": float(hhi_target),
        "diversity_penalty": float(penalty),
        "diversity_feasible": feasible,
        "warnings": warnings,
    }


def compute_agronomic_risk_metrics(plan: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Explanatory agronomic/market risk layer; never changes optimization scores."""
    ctx = context if isinstance(context, dict) else {}
    cfg = _diversity_config(DIVERSITY_DEFAULTS)
    if isinstance(plan, dict):
        rows = plan.get("crops") if isinstance(plan.get("crops"), list) else []
        diversity = plan.get("diversity") if isinstance(plan.get("diversity"), dict) else None
    elif isinstance(plan, list):
        rows = plan
        diversity = None
    else:
        rows = []
        diversity = None
    rows = [r for r in rows if isinstance(r, dict)]
    total_area = safe_float(ctx.get("total_area_da", ctx.get("area_da", 0.0)), 0.0)
    if not isinstance(diversity, dict):
        diversity = compute_diversity_metrics(rows, total_area, cfg)

    def _risk_level(score: float) -> str:
        if score >= 0.67:
            return "high"
        if score >= 0.34:
            return "medium"
        return "low"

    def _level_score(level: str) -> float:
        return {"low": 0.15, "medium": 0.50, "high": 0.85}.get(str(level or "").lower(), 0.0)

    top_crop = str(diversity.get("top_crop") or "")
    top_share = safe_float(diversity.get("top_crop_share_changed", diversity.get("top_crop_share", 0.0)), 0.0)
    top3_share = safe_float(diversity.get("top3_crop_share_changed", diversity.get("top3_crop_share", 0.0)), 0.0)
    hhi = safe_float(diversity.get("hhi", 0.0), 0.0)
    concentration_score = max(
        min(1.0, top_share / max(1e-9, float(cfg.get("max_crop_share", 0.25) or 0.25))),
        min(1.0, top3_share / max(1e-9, float(cfg.get("max_top3_share", 0.65) or 0.65))),
        min(1.0, hhi / max(1e-9, float(cfg.get("hhi_target", 0.18) or 0.18))),
    )
    market_level = _risk_level(concentration_score)

    fam_map = load_crop_family_map()
    catalog = load_crop_catalog()
    family_area: Dict[str, float] = {}
    mapped_area = 0.0
    changed_area = 0.0
    for row in rows:
        crop = str(row.get("crop_name") or row.get("name") or row.get("crop") or "").strip()
        area = max(0.0, safe_float(row.get("area_da", row.get("area", 0.0)), 0.0))
        if not crop or area <= 0:
            continue
        changed_area += area
        ck = normalize_crop_key(crop)
        fam = str(fam_map.get(ck) or (catalog.get(ck, {}) or {}).get("cropFamily") or "").strip().lower()
        if fam and fam != "fallow":
            family_area[fam] = family_area.get(fam, 0.0) + area
            mapped_area += area
    family_shares = {
        fam: float(area / max(1e-9, mapped_area))
        for fam, area in sorted(family_area.items(), key=lambda x: x[1], reverse=True)
    }
    if family_shares:
        top_family, top_family_share = next(iter(family_shares.items()))
        rotation_level = "high" if top_family_share >= 0.50 else ("medium" if top_family_share >= 0.35 else "low")
        rotation_note = f"Ayni urun familyasinda yogunlasma payi %{top_family_share * 100:.1f} duzeyindedir."
        rotation_data_status = "available"
    else:
        top_family, top_family_share = "", 0.0
        rotation_level = "medium" if top_share >= 0.35 else "low"
        rotation_note = "Urun familyasi verisi sinirli; bu risk yogunlasma gostergelerine dayali karar destek notudur."
        rotation_data_status = "limited"

    period_area: Dict[str, float] = {}
    for row in rows:
        area = max(0.0, safe_float(row.get("area_da", row.get("area", 0.0)), 0.0))
        if area <= 0:
            continue
        crop = str(row.get("crop_name") or row.get("name") or "").strip()
        ck = normalize_crop_key(crop)
        cat = catalog.get(ck, {}) or {}
        period = _safe_text(row.get("harvest_date") or row.get("period_note") or row.get("season") or cat.get("season1"))
        if period and period.lower() not in ("belirtilmedi", "veri yok"):
            period_area[period] = period_area.get(period, 0.0) + area
    if period_area:
        period, period_max_area = sorted(period_area.items(), key=lambda x: x[1], reverse=True)[0]
        period_share = float(period_max_area / max(1e-9, changed_area))
        labor_level = "high" if period_share >= 0.55 else ("medium" if period_share >= 0.35 else "low")
        labor_note = f"Hasat/donem bilgisi olan kayitlarda en yogun donem '{period}' ve pay %{period_share * 100:.1f}."
        labor_data_status = "available"
    else:
        period, period_share = "", 0.0
        labor_level = "medium" if top3_share >= 0.75 else "low"
        labor_note = "Hasat donemi verisi sinirli; iscilik yogunlugu yorumu urun yogunlasmasina dayali varsayimsal risk notudur."
        labor_data_status = "limited"

    storage_fields = ("storageClass", "storage_class", "depolama_sinifi", "durabilityClass", "dayaniklilik_sinifi")
    storage_values = []
    for row in rows:
        ck = normalize_crop_key(str(row.get("crop_name") or row.get("name") or ""))
        cat = catalog.get(ck, {}) or {}
        val = next((_safe_text(row.get(k) or cat.get(k)) for k in storage_fields if _safe_text(row.get(k) or cat.get(k))), "")
        if val:
            storage_values.append(val)
    if storage_values:
        storage_level = "medium" if market_level == "high" else "low"
        storage_note = "Depolama/dayaniklilik sinifi verisi olan urunler icin pazarlama hassasiyeti ayrica izlenmelidir."
        storage_data_status = "available"
    else:
        storage_level = "medium" if market_level == "high" else "low"
        storage_note = "Depolama veya dayaniklilik sinifi verisi sinirli; kesin pazarlama tahmini olarak yorumlanmamalidir."
        storage_data_status = "limited"

    baseline_rows = ctx.get("baseline_rows") if isinstance(ctx.get("baseline_rows"), list) else []
    baseline_by_pid = {
        str(r.get("parcel_id") or r.get("id") or ""): normalize_crop_key(r.get("crop_name") or r.get("name") or r.get("crop"))
        for r in baseline_rows if isinstance(r, dict)
    }
    changed_transition_area = 0.0
    comparable_area = 0.0
    for row in rows:
        area = max(0.0, safe_float(row.get("area_da", row.get("area", 0.0)), 0.0))
        if area <= 0:
            continue
        pid = str(row.get("parcel_id") or row.get("id") or "")
        current_key = baseline_by_pid.get(pid) or normalize_crop_key(row.get("current_crop") or row.get("currentCrop"))
        crop_key = normalize_crop_key(row.get("crop_name") or row.get("name") or row.get("crop"))
        if current_key:
            comparable_area += area
            if crop_key and crop_key != current_key:
                changed_transition_area += area
    if comparable_area > 0:
        transition_share = float(changed_transition_area / max(1e-9, comparable_area))
        transition_level = "high" if transition_share >= 0.60 else ("medium" if transition_share >= 0.30 else "low")
        transition_note = f"Mevcut urunden farkli onerilen alan payi %{transition_share * 100:.1f}; gecis ve adaptasyon planlamasi gerekebilir."
        transition_data_status = "available"
    else:
        transition_share = 0.0
        transition_level = "medium" if top3_share >= 0.75 else "low"
        transition_note = "Mevcut urun-parsel eslesmesi sinirli; gecis riski plan farki yerine yogunlasma gostergeleriyle yorumlanmalidir."
        transition_data_status = "limited"

    levels = [market_level, rotation_level, labor_level, storage_level, transition_level]
    overall_score = max(_level_score(x) for x in levels)
    notes = [
        "Bu risk katmani yalnizca karar destek uyarisidir; algoritma skoru, net kar, su, TL/m3, feasible veya selectable alanlarini degistirmez.",
        "Pazar/fiyat baskisi uyarisi gercek fiyat elastikiyeti tahmini degildir; urun yogunlasmasi gostergelerine dayanir.",
    ]
    if rotation_data_status == "limited":
        notes.append("Münavebe/familya verisi sinirli oldugu icin rotasyon riski kesin hastalik tahmini olarak yorumlanmamalidir.")
    if labor_data_status == "limited":
        notes.append("Hasat/iscilik riski, takvim verisi sinirli oldugunda varsayimsal risk notu olarak verilmiştir.")
    if storage_data_status == "limited":
        notes.append("Depolama/pazarlama hassasiyeti icin urun bazli depolama verisi sinirlidir.")

    return {
        "overall_level": _risk_level(overall_score),
        "market_saturation_risk": {
            "level": market_level,
            "top_crop": top_crop,
            "top_crop_share_changed": float(top_share),
            "top3_crop_share_changed": float(top3_share),
            "hhi": float(hhi),
            "basis": "diversity_concentration",
            "message": (
                f"{top_crop} değişen öneri alanında %{top_share * 100:.1f} paya sahiptir; pazar doygunluğu ve fiyat baskısı açısından dikkatli izlenmelidir."
                if top_crop else
                "Ürün yoğunlaşması hesaplanamadı; pazar riski için veri sınırlıdır."
            ),
        },
        "rotation_risk": {
            "level": rotation_level,
            "data_status": rotation_data_status,
            "top_family": top_family,
            "top_family_share": float(top_family_share),
            "family_share_by_family": family_shares,
            "message": rotation_note,
        },
        "labor_harvest_risk": {
            "level": labor_level,
            "data_status": labor_data_status,
            "dominant_period": period,
            "dominant_period_share": float(period_share),
            "message": labor_note,
        },
        "storage_marketing_risk": {
            "level": storage_level,
            "data_status": storage_data_status,
            "message": storage_note,
        },
        "transition_risk": {
            "level": transition_level,
            "data_status": transition_data_status,
            "changed_area_share": float(transition_share),
            "message": transition_note,
        },
        "notes": list(dict.fromkeys(notes)),
    }

def _prev_year_family_map(year: int) -> Dict[str, str]:
    """Infer previous-year primary crop family per parcel from enhanced seasons table."""
    frames = load_enhanced_frames()
    df = frames.get("s1")
    if df is None or df.empty or "year" not in df.columns:
        return {}
    yprev = int(year) - 1
    sub = df[df["year"].astype(int) == yprev].copy()
    if sub.empty:
        return {}
    sub["parcel_id"] = sub["parcel_id"].astype(str)
    sub["crop_key"] = sub["crop"].astype(str).map(normalize_crop_key)
    fam = load_crop_family_map()
    out = {}
    for pid, g in sub.groupby("parcel_id"):
        try:
            ck = g["crop_key"].mode().iloc[0]
        except Exception:
            ck = ""
        out[str(pid)] = fam.get(str(ck), "other")
    return out

def _prev_family_penalty(parcel_ids: List[str], chosen_keys: List[str], year: int, weight: float = 2e8) -> float:
    """Soft penalty: avoid repeating the previous year's primary crop family."""
    prev = _prev_year_family_map(year)
    fam = load_crop_family_map()
    pen = 0.0
    for pid, ck in zip(parcel_ids, chosen_keys):
        if not ck or ck == FALLOW:
            continue
        pf = prev.get(str(pid))
        if not pf:
            continue
        cf = fam.get(str(ck), "other")
        if cf and pf and cf == pf:
            pen += float(weight)
    return float(pen)

def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")

def load_json(path: Path) -> Any:
    key = f"json::{path}"
    if key in _cache:
        return _cache[key]
    obj = json.loads(_read_text(path))
    _cache[key] = obj
    return obj



def load_parcels() -> List[Dict[str, Any]]:
    """
    Loads parcel metadata by MERGING:
      - Enhanced assumptions: data/enhanced_dataset/csv/parcel_assumptions.csv
        (soil codes, village, irrigation efficiency, lat/lon in lat_deg/lon_deg)
      - Legacy parcel summary: data/parsel_su_kar_ozet.csv
        (area_da, baseline water/profit, district, lat/lon)

    If a value is missing in the enhanced file, we fill from legacy.
    If area_da is still missing, we infer it from the seasonal tables.
    """
    key = "parcels"
    if key in _cache:
        return _cache[key]

    
    # GeoJSON-derived parcel area overrides (optional)
    overrides = load_area_overrides()

    enhanced_csv = DATA_DIR / "enhanced_dataset" / "csv" / "parcel_assumptions.csv"
    legacy_csv = DATA_DIR / "parsel_su_kar_ozet.csv"

    df_enh = pd.read_csv(enhanced_csv) if enhanced_csv.exists() else pd.DataFrame()
    # normalize ids
    if not df_enh.empty:
        df_enh["parcel_id"] = df_enh["parcel_id"].astype(str).map(normalize_parcel_id)
        # unify lat/lon
        if "lat_deg" in df_enh.columns and "lat" not in df_enh.columns:
            df_enh["lat"] = df_enh["lat_deg"]
        if "lon_deg" in df_enh.columns and "lon" not in df_enh.columns:
            df_enh["lon"] = df_enh["lon_deg"]

    df_leg = pd.read_csv(legacy_csv) if legacy_csv.exists() else pd.DataFrame()
    if not df_leg.empty:
        df_leg["parsel_id"] = df_leg["parsel_id"].astype(str).map(normalize_parcel_id)
        # rename to common
        df_leg = df_leg.rename(columns={
            "parsel_id":"parcel_id",
            "alan_da":"area_da",
            "mevcut_su_m3":"water_m3",
            "mevcut_kar_tl":"profit_tl",
            "koy":"village",
            "ilce":"district",
        })

    # Merge
    if not df_enh.empty and not df_leg.empty:
        df = pd.merge(df_enh, df_leg, on="parcel_id", how="outer", suffixes=("_enh","_leg"))
    elif not df_enh.empty:
        df = df_enh.copy()
    elif not df_leg.empty:
        df = df_leg.copy()
    else:
        _cache[key] = []
        return _cache[key]

    # Infer area from seasons if needed
    try:
        frames = load_enhanced_frames()
        seasons = pd.concat([frames["s1"], frames["s2"]], ignore_index=True)
        seasons["parcel_id"] = seasons["parcel_id"].astype(str).map(normalize_parcel_id)
        area_map = seasons.groupby("parcel_id")["area_da"].max().to_dict()
    except Exception:
        area_map = {}

    # GeoJSON-derived area overrides (computed externally)

    parcels: List[Dict[str, Any]] = []
    for _, r in df.iterrows():
        pid = str(r.get("parcel_id","") or "").strip()
        if not pid:
            continue

        def _row_first(*names, default=""):
            for name in names:
                try:
                    val = r.get(name, None)
                except Exception:
                    val = None
                if val is None:
                    continue
                s = str(val).strip()
                if s and s.lower() not in ("nan", "none", "null"):
                    return s
            return default

        # resolve values with fallbacks
        name = str(r.get("name","") or "").strip() or pid
        village = str(r.get("village","") or r.get("village_enh","") or r.get("village_leg","") or "").strip()
        district = str(r.get("district","") or r.get("district_enh","") or r.get("district_leg","") or "").strip()

        # area (da) - prefer GeoJSON-derived override if present
        area_da = safe_float(r.get("area_da", 0), 0.0)
        # from seasonal tables if missing
        if area_da <= 0 and pid in area_map:
            area_da = safe_float(area_map.get(pid, 0), 0.0)
        # override from GeoJSON calc (most reliable for this UI)
        if pid in overrides and safe_float(overrides[pid].get("area_da", 0), 0.0) > 0:
            area_da = safe_float(overrides[pid].get("area_da", 0), area_da)

        # lat/lon: prefer legacy if zeros
        lat = safe_float(r.get("lat", 0), 0.0)
        lon = safe_float(r.get("lon", 0), 0.0)
        if (lat == 0 or lon == 0):
            lat2 = r.get("lat_leg", None) if "lat_leg" in df.columns else None
            lon2 = r.get("lon_leg", None) if "lon_leg" in df.columns else None
            if lat2 is not None and lon2 is not None:
                try:
                    lat = float(lat2); lon = float(lon2)
                except Exception:
                    pass

        # baseline water/profit
        water_m3 = float(r.get("water_m3", 0) or 0)
        profit_tl = float(r.get("profit_tl", 0) or 0)

        # --- Data hygiene ---
        # Legacy summaries or external edits may introduce negative placeholders.
        # For the decision-support dashboard, we treat negative baseline water/profit as missing
        # and recompute a conservative baseline from candidate medians.
        if water_m3 < 0:
            water_m3 = 0.0
        if profit_tl < 0:
            profit_tl = 0.0

        # --- Scale sanity checks ---
        # Some legacy parcel summaries contain water/profit values that are orders
        # of magnitude smaller than what the seasonal/crop intensity tables imply.
        # This breaks scenario comparisons ("Su tasarruf" appears to increase water).
        # If intensities look implausibly low/high, treat them as missing and rebuild
        # a conservative baseline from candidate matrices.
        if area_da > 0:
            wpd = water_m3 / area_da if water_m3 > 0 else 0.0
            ppd = profit_tl / area_da if profit_tl > 0 else 0.0
            # Typical annual delivered irrigation demand in this demo ranges roughly
            # ~100–2000 m3/da depending on crop + method. Below 60 is almost certainly wrong.
            if (wpd > 0 and wpd < 60) or (wpd > 6000):
                water_m3 = 0.0
            # Profit intensity sanity: below 200 TL/da is unlikely for the catalog here.
            if (ppd > 0 and ppd < 200) or (ppd > 200000):
                profit_tl = 0.0

        # If still missing, estimate from median intensities
        if (water_m3 <= 0 or profit_tl <= 0) and area_da > 0:
            try:
                crop_list, W, R = build_candidate_matrix([{"id":pid,"name":pid,"area_da":area_da,"water_m3":0,"profit_tl":0}])
                # take median across crops
                wpd = float(np.median(W[0,:]))
                rpd = float(np.median(R[0,:]))
                if water_m3 <= 0:
                    water_m3 = area_da * wpd
                if profit_tl <= 0:
                    profit_tl = area_da * rpd
            except Exception:
                pass

        soil_class = str(r.get("land_capability_class", "") or r.get("soil_class","") or "").strip()
        soil_texture = str(r.get("soil_group","") or r.get("soil_texture","") or "").strip()
        erosion = str(r.get("erosion_risk","") or r.get("erosion","") or "").strip()

        parcels.append({
            "id": pid,
            "name": name,
            "village": village,
            "district": district,
            "area_da": float(area_da),
            "area_m2": float(overrides.get(pid, {}).get("area_m2", 0) or 0),
            "geojson_file_no": int(overrides.get(pid, {}).get("geojson_file_no", 0) or 0),
            "lat": float(lat),
            "lon": float(lon),
            "water_m3": float(water_m3),
            "profit_tl": float(profit_tl),
            "current_crop": str(r.get("current_crop", "") or r.get("main_crop_current", "") or "").strip(),
            "parcel_type": str(r.get("parcel_type", "") or "").strip(),
            "cok_yillik_kilit": str(r.get("cok_yillik_kilit", "") or r.get("orchard_lock", "") or "").strip(),
            "farmer_id": _row_first("farmer_id", "farmer_id_enh", "farmer_id_leg"),
            "farmer_name": _row_first("farmer_name", "farmer_name_enh", "farmer_name_leg"),
            "selected_alternative_id": _row_first("selected_alternative_id", "selected_alternative_id_enh", "selected_alternative_id_leg"),
            "selected_alternative_label": _row_first("selected_alternative_label", "selected_alternative_label_enh", "selected_alternative_label_leg"),
            "selected_pattern": _row_first("selected_pattern", "selected_pattern_enh", "selected_pattern_leg"),
            "assignment_status": _row_first("assignment_status", "assignment_status_enh", "assignment_status_leg"),
            "assignment_note": _row_first("assignment_note", "assignment_note_enh", "assignment_note_leg"),
            "geometry_status": _row_first("geometry_status", "geometry_status_enh", "geometry_status_leg"),
            "geometry_source": _row_first("geometry_source", "geometry_source_enh", "geometry_source_leg"),
            "has_real_geojson": _row_first("has_real_geojson", "has_real_geojson_enh", "has_real_geojson_leg"),
            "drawing_required": _row_first("drawing_required", "drawing_required_enh", "drawing_required_leg"),
            "soil": {"class": soil_class, "texture": soil_texture, "erosion": erosion}
        })

    # If some parcels still have lat/lon missing, assign them on a grid around the mean
    lats = [p["lat"] for p in parcels if p["lat"]!=0]
    lons = [p["lon"] for p in parcels if p["lon"]!=0]
    if lats and lons:
        clat = float(sum(lats)/len(lats)); clon = float(sum(lons)/len(lons))
    else:
        clat, clon = 37.97, 34.68
    missing = [p for p in parcels if p["lat"]==0 or p["lon"]==0]
    if missing:
        step = 0.01
        for k,p in enumerate(missing):
            p["lat"] = clat + (k//5)*step
            p["lon"] = clon + (k%5)*step



    try:
        meta_obj = load_json(DATA_DIR / "parcel_meta_map.json") if (DATA_DIR / "parcel_meta_map.json").exists() else {}
        by_id = (meta_obj or {}).get("by_id", {}) if isinstance(meta_obj, dict) else {}
        for p in parcels:
            meta = by_id.get(str(p.get("id", "")), {}) if isinstance(by_id, dict) else {}
            if isinstance(meta, dict):
                p["current_crop"] = str(meta.get("crop", "") or p.get("current_crop", "") or "").strip()
                p["parcel_type"] = str(meta.get("parcel_type", "") or p.get("parcel_type", "") or ("orchard" if meta.get("orchard") else "")).strip() or infer_parcel_type_for_selection(meta.get("crop", "") or p.get("current_crop", ""))
                p["irrigation_key"] = str(meta.get("irr_key", "") or "").strip()
                p["cok_yillik_kilit"] = str(meta.get("cok_yillik_kilit", "") or p.get("cok_yillik_kilit", "") or ("E" if meta.get("orchard") else "")).strip()
            else:
                p["parcel_type"] = infer_parcel_type_for_selection(p)
    except Exception:
        for p in parcels:
            p["parcel_type"] = infer_parcel_type_for_selection(p)

    parcels = sorted(parcels, key=lambda x: x["id"])
    _cache[key] = parcels
    return _cache[key]





def merge_frontend_custom_parcels(base_parcels: List[Dict[str, Any]], custom_parcels: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Merge user-defined parcels coming from the front-end into the optimizer input.

    Expected fields per custom parcel:
      id, name, village, district, area_da, lat, lon, water_m3, profit_tl,
      current_crop, irrigation_key, soil
    """
    if not custom_parcels:
        return list(base_parcels or [])

    merged = [dict(p) for p in (base_parcels or [])]
    idx = {str(p.get("id")): i for i, p in enumerate(merged) if p.get("id") is not None}

    for raw in custom_parcels:
        if not isinstance(raw, dict):
            continue
        pid = str(raw.get("id", "") or "").strip()
        if not pid:
            continue
        area_da = safe_float(raw.get("area_da", 0.0), 0.0)
        lat = safe_float(raw.get("lat", 0.0), 0.0)
        lon = safe_float(raw.get("lon", 0.0), 0.0)
        water_m3 = safe_float(raw.get("water_m3", 0.0), 0.0)
        profit_tl = safe_float(raw.get("profit_tl", 0.0), 0.0)
        soil = raw.get("soil") if isinstance(raw.get("soil"), dict) else {}
        rec = {
            "id": pid,
            "name": str(raw.get("name", pid) or pid),
            "village": str(raw.get("village", "Sazlıca") or "Sazlıca").strip(),
            "district": str(raw.get("district", "Merkez") or "Merkez").strip(),
            "area_da": float(max(0.0, area_da)),
            "area_m2": float(max(0.0, area_da) * 1000.0),
            "geojson_file_no": 0,
            "lat": float(lat),
            "lon": float(lon),
            "water_m3": float(max(0.0, water_m3)),
            "profit_tl": float(max(0.0, profit_tl)),
            "soil": {
                "class": str(soil.get("class", "") or "").strip(),
                "texture": str(soil.get("texture", "") or "").strip(),
                "erosion": str(soil.get("erosion", "") or "").strip(),
            },
            "current_crop": str(raw.get("current_crop", "") or "").strip(),
            "irrigation_key": str(raw.get("irrigation_key", "") or "").strip(),
            "parcel_type": str(raw.get("parcel_type", "") or "").strip() or infer_parcel_type_for_selection(raw),
            "frontend_custom": True,
        }
        if pid in idx:
            merged[idx[pid]].update(rec)
        else:
            merged.append(rec)
            idx[pid] = len(merged) - 1
    return merged



def load_crop_catalog() -> Dict[str, Dict[str, Any]]:
    """Load Sazlıca crop catalog from CSV.

    Expected columns:
      urun_adi, su_tuketimi_m3_da, beklenen_verim_kg_da, net_kar_tl_da,
      kategori, parcel_type, crop_family, irrigation_current_key,
      irrigation_recommended_key, season1, season2, secondary_options,
      cok_yillik_mi, tamamlama_notu
    """
    key = "crop_catalog"
    if key in _cache:
        return _cache[key]

    path = DATA_DIR / "urun_parametreleri_demo.csv"
    if not path.exists():
        _cache[key] = {}
        return _cache[key]

    first = path.read_text(encoding="utf-8", errors="replace").splitlines()[0]
    sep = ";" if (";" in first and "," not in first) else ","
    try:
        df = pd.read_csv(path, sep=sep)
    except Exception:
        df = pd.read_csv(path, sep=sep, engine="python")

    cat: Dict[str, Dict[str, Any]] = {}
    for _, r in df.iterrows():
        name = str(r.get("urun_adi", "") or r.get("urun", "") or r.get("name", "")).strip()
        if not name:
            continue
        nk = normalize_crop_key(name)

        wpd = safe_float(r.get("su_tuketimi_m3_da", None), np.nan)
        ppd = safe_float(r.get("net_kar_tl_da", None), np.nan)
        if not np.isfinite(wpd) or wpd <= 0:
            ptype = str(r.get("parcel_type", "") or "").strip().lower()
            if ptype == "orchard":
                wpd = 560.0
            elif ptype == "vegetable":
                wpd = 520.0
            else:
                wpd = 230.0
        if not np.isfinite(ppd) or ppd <= 0:
            ptype = str(r.get("parcel_type", "") or "").strip().lower()
            if ptype == "orchard":
                ppd = 9800.0
            elif ptype == "vegetable":
                ppd = 7500.0
            else:
                ppd = 3000.0

        cat[nk] = {
            "name": name,
            "displayName": name,
            "waterPerDa": float(wpd),
            "profitPerDa": float(ppd),
            "yieldKgPerDa": safe_float(r.get("beklenen_verim_kg_da", 0), 0.0),
            "priceTlPerKg": safe_float(r.get("fiyat_tl_kg", 0), 0.0),
            "costTlPerDa": safe_float(r.get("maliyet_tl_da", 0), 0.0),
            "varCostTlPerDa": safe_float(r.get("degisken_maliyet_tl_da", 0), 0.0),
            "supportTlPerDa": safe_float(r.get("destek_tl_da", 0), 0.0),
            "grossRevenueTlPerDa": safe_float(r.get("brut_hasilat_tl_da", 0), 0.0),
            "unitTypeEst": str(r.get("birim_tipi_est", "") or "").strip(),
            "unitsPerDaEst": safe_float(r.get("birim_sayisi_da_est", 0), 0.0),
            "spacingNote": str(r.get("siklik_notu", "") or "").strip(),
            "yieldPerUnitKgEst": safe_float(r.get("birim_basina_verim_kg_est", 0), 0.0),
            "waterLPerUnitEst": safe_float(r.get("birim_basina_su_l_est", 0), 0.0),
            "decisionGroup": str(r.get("karar_grubu", "") or "").strip(),
            "perennialLockRule": str(r.get("cok_yillik_kilit", "") or "").strip(),
            "managementNote": str(r.get("yonetim_notu", "") or "").strip(),
            "netProfitTlPerDa": float(ppd),
            "economySourceStatus": str(r.get("ekonomi_kaynak_durumu", "") or "").strip(),
            "category": str(r.get("kategori", "") or "").strip(),
            "parcelType": str(r.get("parcel_type", "") or "").strip().lower(),
            "cropFamily": str(r.get("crop_family", "") or "").strip().lower(),
            "irrigationCurrentKey": str(r.get("irrigation_current_key", "") or "").strip(),
            "irrigationRecommendedKey": str(r.get("irrigation_recommended_key", "") or "").strip(),
            "season1": str(r.get("season1", "") or "").strip(),
            "season2": str(r.get("season2", "") or "").strip(),
            "secondaryOptions": [s.strip() for s in str(r.get("secondary_options", "") or "").split(",") if s.strip()],
            "isPerennial": str(r.get("cok_yillik_mi", "") or "").strip().lower().startswith("e"),
            "sourceNote": str(r.get("tamamlama_notu", "") or "").strip(),
        }
    _cache[key] = cat
    return _cache[key]


def load_s1_crop_calendar_rules() -> dict:
    """Load Senaryo-1 primary->secondary crop calendar & current irrigation rules from disk.

    Project requirement: **data-driven** (no hardcoded lists). This function reads:
      data/s1_crop_calendar_rules.json
    and builds small derived lookup maps for season/irrigation text.
    """
    key = "s1_crop_calendar_rules"
    if key in _cache:
        return _cache[key]

    rules_path = (DATA_DIR / "s1_crop_calendar_rules.json")
    rules = {}
    err = None
    try:
        if rules_path.exists():
            rules = json.loads(rules_path.read_text(encoding="utf-8"))
        else:
            err = f"rules file missing: {rules_path}" 
    except Exception as e:
        err = f"failed to read rules: {e}" 
        rules = {}

    # Normalize rule crop names to match catalog (handles shorthand like 'Fiğ' vs 'Fiğ (Yeşilot)')
    _aliases = {
        'Fiğ': 'Fiğ (Yeşilot)',
        'Ayçiçeği (Yağlık)': 'Ayçiçeği',
        'Ayçiçeği (Yağlık )': 'Ayçiçeği',
        'Yem Bezelyesi': 'Yem Bezelyesi',
    }
    if isinstance(rules, dict) and rules:
        new_rules = {}
        for pk, pv in rules.items():
            nk = _aliases.get(pk, pk)
            if isinstance(pv, dict):
                opts = pv.get('secondary_options') or []
                pv = dict(pv)
                pv['secondary_options'] = [_aliases.get(o, o) for o in opts]
            new_rules[nk] = pv
        rules = new_rules
    # Build derived maps for quick lookup
    season_map = {}
    irr_current_text_map = {}
    for p, v in (rules or {}).items():
        if not isinstance(v, dict):
            continue
        season_map[p] = v.get("season1") or ""
        irr_current_text_map[p] = v.get("irrigation1_current") or ""
        for s in (v.get("secondary_options") or []):
            if s not in season_map:
                season_map[s] = v.get("season2") or ""
            if s not in irr_current_text_map:
                irr_current_text_map[s] = v.get("irrigation2_current") or ""

    rules["_derived"] = {
        "season_map": season_map,
        "irr_current_text_map": irr_current_text_map,
        "_rules_file": str(rules_path),
        "_rules_file_exists": bool(rules_path.exists()),
        "_rules_file_error": err,
        "_primary_count": int(len([k for k in rules.keys() if k != '_derived'])),
    }

    _cache[key] = rules
    return rules


    path = DATA_DIR / "urun_parametreleri_demo.csv"
    if not path.exists():
        _cache[key] = {}
        return _cache[key]

        # delimiter auto-detect (; or ,)
    first = path.read_text(encoding="utf-8", errors="replace").splitlines()[0]
    sep = ";" if (";" in first and "," not in first) else ","
    df = pd.read_csv(path, sep=sep)
    cat: Dict[str, Dict[str, Any]] = {}
    for _, r in df.iterrows():
        name = str(r.get("urun_adi", "") or r.get("urun", "") or r.get("name", "")).strip()
        if not name:
            continue
        k = normalize_crop_key(name)
        water_per_da = float(r.get("su_tuketimi_m3_da", 0) or 0)
        # net kar öncelikli; yoksa verim*fiyat - maliyet
        if pd.notna(r.get("net_kar_tl_da", None)):
            profit_per_da = float(r.get("net_kar_tl_da", 0) or 0)
        else:
            yld = float(r.get("beklenen_verim_kg_da", 0) or 0)
            price = float(r.get("fiyat_tl_kg", 0) or 0)
            cost = float(r.get("degisken_maliyet_tl_da", 0) or 0)
            profit_per_da = yld * price - cost

        cat[k] = {
            "name": name.upper(),
            "waterPerDa": water_per_da,
            "profitPerDa": profit_per_da,
            "category": str(r.get("kategori", "") or "").strip(),
        }

    _cache[key] = cat
    return cat


def merged_pattern_candidates(village: str, district: str, top_n: int = 12, parcel_type: str = "") -> List[Tuple[str, float]]:
    """Return Sazlıca candidate crops with weights from village/district pattern JSON.

    If parcel_type is provided (field / vegetable / orchard), only that pool is returned.
    """
    village_path = DATA_DIR / "village_crop_patterns.json"
    district_path = DATA_DIR / "district_crop_patterns.json"
    village_obj = load_json(village_path) if village_path.exists() else {}
    district_obj = load_json(district_path) if district_path.exists() else {}

    merged: Dict[str, float] = {}
    type_label = {"field":"Tarla/Yem","vegetable":"Sebze","orchard":"Meyve/Bağ"}.get(str(parcel_type or "").strip().lower(), "")

    def _consume(obj: Any, weight: float) -> None:
        if not isinstance(obj, dict):
            return
        rows = obj.get("top_crops", [])
        if type_label and isinstance(obj.get("top_crops_by_type"), dict):
            rows = obj["top_crops_by_type"].get(type_label, rows)
        for item in rows or []:
            try:
                ck = normalize_crop_key(item.get("crop", ""))
                sh = float(item.get("share", 0) or 0)
            except Exception:
                continue
            if ck:
                merged[ck] = merged.get(ck, 0.0) + weight * sh

    _consume(district_obj.get(normalize_crop_key(district), {}), 0.6)
    _consume(village_obj.get(village, {}) or village_obj.get("Sazlıca", {}), 0.4)

    if not merged:
        cat = load_crop_catalog()
        for ck, rec in cat.items():
            if not type_label or catalog_parcel_type(rec) == str(parcel_type or "").strip().lower():
                merged[ck] = 1.0

    tot = sum(merged.values()) or 1.0
    items = [(c, s / tot) for c, s in merged.items()]
    items.sort(key=lambda x: x[1], reverse=True)
    return items[:top_n]



def recommend_crop_for_parcel(parcel: Dict[str, Any], algo: str = "GA") -> Optional[Dict[str, Any]]:
    """Transparent single-parcel recommendation based on Sazlıca crop pools."""
    catalog = load_crop_catalog()
    if not catalog:
        return None
    ptype = str(parcel.get("parcel_type", "") or "").strip().lower()
    if not ptype or ptype == "auto":
        ptype = infer_parcel_type_for_selection(parcel)
    current_crop = normalize_crop_key(str(parcel.get("current_crop", "") or "").strip())
    candidates = merged_pattern_candidates(parcel.get("village","Sazlıca"), parcel.get("district","MERKEZ"), parcel_type=ptype)
    best = None
    best_score = -1e18
    for crop_name, share in candidates:
        ck = normalize_crop_key(crop_name)
        rec = catalog.get(ck)
        if not rec:
            continue
        if ptype and catalog_parcel_type(rec) and catalog_parcel_type(rec) != ptype:
            continue
        w = float(rec.get("waterPerDa", 0) or 0)
        p = float(rec.get("profitPerDa", 0) or 0)
        eff = p / max(1.0, w)
        current_bonus = 0.08 if current_crop and current_crop == ck else 0.0
        if algo.upper() == "ABC":
            score = 0.84 * eff + 0.16 * share + current_bonus
        elif algo.upper() == "ACO":
            score = 0.80 * eff + 0.20 * share + current_bonus
        else:
            score = 0.88 * eff + 0.12 * share + current_bonus
        if score > best_score:
            best_score = score
            best = {
                "crop": rec.get("displayName", rec.get("name", crop_name)),
                "water_per_da": w,
                "profit_per_da": p,
                "parcel_type": ptype,
                "score": score,
            }
    return best


def enhanced_paths() -> Dict[str, Path]:
    return {
        "parcels": DATA_DIR / "enhanced_dataset" / "csv" / "parcel_assumptions.csv",
        "seasons1": DATA_DIR / "enhanced_dataset" / "csv" / "senaryo1_backend_seasons.csv",
        "seasons2": DATA_DIR / "enhanced_dataset" / "csv" / "senaryo2_backend_seasons.csv",
        "reservoir": DATA_DIR / "enhanced_dataset" / "csv" / "akkaya_reservoir_monthly_backend.csv",
        "irrigation_methods": DATA_DIR / "enhanced_dataset" / "csv" / "irrigation_methods_assumed.csv",
        "delivery": DATA_DIR / "enhanced_dataset" / "csv" / "delivery_capacity_monthly_assumed.csv",
        # Optional / advanced tables (used by FAO-56 water requirement, suitability, and constraints)
        "crop_params": DATA_DIR / "enhanced_dataset" / "csv" / "crop_params_assumed.csv",
        "crop_suitability": DATA_DIR / "enhanced_dataset" / "csv" / "crop_suitability_assumed.csv",
        "crop_family": DATA_DIR / "enhanced_dataset" / "csv" / "crop_family_map.csv",
        "monthly_climate": DATA_DIR / "enhanced_dataset" / "csv" / "monthly_climate_all_parcels.csv",
        "water_quality": DATA_DIR / "enhanced_dataset" / "csv" / "water_quality_monthly_assumed.csv",
        "soil_params": DATA_DIR / "enhanced_dataset" / "csv" / "soil_params_assumed.csv",
        "objective_weights": DATA_DIR / "enhanced_dataset" / "csv" / "objective_weight_sets.csv",
    }


def load_enhanced_frames() -> Dict[str, pd.DataFrame]:
    """Load packaged CSV frames used by the backend.

    Robustness:
    - Missing optional CSVs should NOT crash the backend.
    - Optional frames are returned as empty DataFrames when not present.
    """
    key = "enhanced_frames_v2"
    if key in _cache:
        return _cache[key]
    p = enhanced_paths()
    out: Dict[str, pd.DataFrame] = {}

    def _read_csv_safe(path: Path) -> pd.DataFrame:
        try:
            if path and Path(path).exists():
                return pd.read_csv(path)
        except Exception:
            pass
        return pd.DataFrame()

    # Core frames
    out["parcels"] = normalize_parcel_id_series(_read_csv_safe(p.get("parcels")), ["parcel_id", "parsel_id", "id"])
    out["s1"] = normalize_parcel_id_series(_read_csv_safe(p.get("seasons1")), ["parcel_id"])
    out["s2"] = normalize_parcel_id_series(_read_csv_safe(p.get("seasons2")), ["parcel_id"])
    out["reservoir"] = _read_csv_safe(p.get("reservoir"))
    out["irrigation_methods"] = _read_csv_safe(p.get("irrigation_methods"))
    out["delivery"] = _read_csv_safe(p.get("delivery"))

    # Optional / advanced frames
    out["crop_params"] = _read_csv_safe(p.get("crop_params"))
    out["crop_suitability"] = _read_csv_safe(p.get("crop_suitability"))
    out["crop_family"] = _read_csv_safe(p.get("crop_family"))
    out["monthly_climate"] = _read_csv_safe(p.get("monthly_climate"))
    out["climate"] = out["monthly_climate"].copy()
    out["water_quality"] = _read_csv_safe(p.get("water_quality"))
    out["soil_params"] = _read_csv_safe(p.get("soil_params"))
    out["objective_weights"] = _read_csv_safe(p.get("objective_weights"))

    _cache[key] = out
    return out



# -----------------------------
# FAO-56 style water requirement (ET0-Kc) + effective rainfall + monthly breakdown
# -----------------------------

def _effective_rain_scs_mm(p_mm: float) -> float:
    """USDA-SCS effective rainfall approximation (mm) for a monthly/period total.

    Important: this function expects the rainfall total of the accounting period.
    It should not be applied to an already divided daily rainfall value and then
    summed back to the month, because that would overestimate effective rainfall.
    """
    try:
        p = float(p_mm or 0.0)
    except Exception:
        return 0.0
    if p <= 0:
        return 0.0
    if p <= 250.0:
        pe = p * (125.0 - 0.2 * p) / 125.0
    else:
        pe = 125.0 + 0.1 * p
    return float(max(0.0, min(p, pe)))

def _kc_curve_daily(total_days: int, kc_ini: float, kc_mid: float, kc_end: float,
                    p_ini: float, p_dev: float, p_mid: float, p_late: float) -> List[float]:
    """Build a simple FAO-56 like daily Kc curve.

    The crop parameter table in this project may store growth-stage durations either
    as proportions (0.20, 0.30, ...) or as days (30, 45, 120, 45).  Older code treated
    both as proportions; day-based rows therefore became an unrealistically long
    initial-stage plateau.  This function now detects day-based inputs and rescales
    them to the actual season length.
    """
    total_days = int(max(1, total_days))
    vals = [float(p_ini or 0), float(p_dev or 0), float(p_mid or 0), float(p_late or 0)]

    if any(v > 1.5 for v in vals) or sum(vals) > 4.0:
        raw = [max(0, int(round(v))) for v in vals]
        raw_sum = sum(raw)
        if raw_sum <= 0:
            raw = [20, 30, 30, 20]
            raw_sum = sum(raw)
        scaled = [int(round(total_days * v / raw_sum)) for v in raw]
    else:
        scaled = [int(round(total_days * max(0.0, v))) for v in vals]

    L_ini, L_dev, L_mid, L_late = scaled
    drift = total_days - (L_ini + L_dev + L_mid + L_late)
    L_late = max(0, L_late + drift)

    kc = []
    kc += [float(kc_ini)] * max(0, L_ini)

    if L_dev > 0:
        for t in range(L_dev):
            frac = (t + 1) / max(1, L_dev)
            kc.append(float(kc_ini + (kc_mid - kc_ini) * frac))

    kc += [float(kc_mid)] * max(0, L_mid)

    if L_late > 0:
        for t in range(L_late):
            frac = (t + 1) / max(1, L_late)
            kc.append(float(kc_mid + (kc_end - kc_mid) * frac))

    if len(kc) < total_days:
        kc += [float(kc_end)] * (total_days - len(kc))
    if len(kc) > total_days:
        kc = kc[:total_days]
    return kc

def _load_crop_params_map() -> Dict[str, Dict[str, float]]:
    frames = load_enhanced_frames()
    df = frames.get("crop_params")
    out: Dict[str, Dict[str, float]] = {}
    if df is None or df.empty:
        return out
    def _nz(v, default):
        try:
            if pd.isna(v):
                return float(default)
        except Exception:
            pass
        vv = safe_float(v, default)
        try:
            if np.isnan(vv):
                return float(default)
        except Exception:
            pass
        return float(vv)
    for _, r in df.iterrows():
        ck = normalize_crop_key(str(r.get("crop","")))
        if not ck:
            continue
        out[ck] = {
            "kc_ini": _nz(r.get("kc_ini", 0.6), 0.6),
            "kc_mid": _nz(r.get("kc_mid", 1.0), 1.0),
            "kc_end": _nz(r.get("kc_end", 0.8), 0.8),
            "p_ini": _nz(r.get("p_ini", 0.2), 0.2),
            "p_dev": _nz(r.get("p_dev", 0.3), 0.3),
            "p_mid": _nz(r.get("p_mid", 0.3), 0.3),
            "p_late": _nz(r.get("p_late", 0.2), 0.2),
        }
    return out

def _crop_max_ec_default(ck: str) -> float:
    """Assumed seasonal-average EC tolerance (dS/m) if no measured crop table is available."""
    k = normalize_crop_key(ck)
    # conservative-ish defaults (can be replaced by a real tolerance table later)
    if any(x in k for x in ["PATATES"]):
        return 1.7
    if any(x in k for x in ["FASULYE","NOHUT","MERCIMEK","BEZELYE"]):
        return 1.5
    if any(x in k for x in ["MISIR","SILAJ","BUGDAY","ARPA"]):
        return 3.0
    if any(x in k for x in ["SEKERPANCARI","PANCAR"]):
        return 7.0
    if any(x in k for x in ["DOMATES","BIBER"]):
        return 2.5
    if any(x in k for x in ["KAVUN","KARPUZ","SOGAN"]):
        return 2.0
    # orchard / perennial (generally moderate)
    if k in PERENNIAL_CROPS:
        return 3.0
    return 2.5

def _avg_ec_over_season(planting_date: str, harvest_date: str) -> Optional[float]:
    frames = load_enhanced_frames()
    wq = frames.get("water_quality")
    if wq is None or wq.empty:
        return None
    try:
        d1 = pd.to_datetime(planting_date)
        d2 = pd.to_datetime(harvest_date)
    except Exception:
        return None
    if pd.isna(d1) or pd.isna(d2):
        return None
    if d2 < d1:
        d1, d2 = d2, d1
    wq2 = wq.copy()
    wq2["month"] = pd.to_datetime(wq2["month"], errors="coerce")
    wq2 = wq2.dropna(subset=["month"])
    mask = (wq2["month"] >= pd.Timestamp(d1.year, d1.month, 1)) & (wq2["month"] <= pd.Timestamp(d2.year, d2.month, 1))
    sub = wq2.loc[mask]
    if sub.empty:
        return None
    try:
        return float(sub["ec_dS_m_assumed"].astype(float).mean())
    except Exception:
        return None

def compute_fao56_monthly_irrigation_mm(parcel_id: str, crop_key: str, planting_date: str, harvest_date: str,
                                       irrig_eff: float, climate_df: pd.DataFrame,
                                       crop_params_map: Dict[str, Dict[str,float]]) -> Dict[int, float]:
    """Return dict {month(1-12): gross irrigation mm over that month} for the season."""
    ck = normalize_crop_key(crop_key)
    params = crop_params_map.get(ck)
    if params is None:
        # fallback Kc
        params = {"kc_ini": 0.6, "kc_mid": 1.0, "kc_end": 0.8, "p_ini": 0.2, "p_dev": 0.3, "p_mid": 0.3, "p_late": 0.2}
    try:
        d1 = pd.to_datetime(planting_date)
        d2 = pd.to_datetime(harvest_date)
    except Exception:
        return {}
    if pd.isna(d1) or pd.isna(d2):
        return {}
    if d2 < d1:
        d1, d2 = d2, d1

    total_days = int((d2 - d1).days) + 1
    kc_daily = _kc_curve_daily(total_days, params["kc_ini"], params["kc_mid"], params["kc_end"],
                               params["p_ini"], params["p_dev"], params["p_mid"], params["p_late"])
    eff = float(irrig_eff or 0.75)
    eff = max(0.35, min(0.95, eff))

    # build daily series
    dates = pd.date_range(d1, d2, freq="D")
    # climate_df expected monthly rows with et0_mm and precip_mm for the parcel-year
    # we approximate daily ET0 and P by dividing monthly totals equally by days in month.
    monthly = climate_df.copy()
    monthly["month"] = pd.to_datetime(monthly["month"], errors="coerce")
    monthly = monthly.dropna(subset=["month"])
    monthly = monthly.set_index("month").sort_index()

    out_mm = {m: 0.0 for m in range(1,13)}
    # precompute month day counts
    for idx_day, day in enumerate(dates):
        mstart = pd.Timestamp(day.year, day.month, 1)
        row = monthly.loc[monthly.index == mstart]
        days_in_month = int((mstart + pd.offsets.MonthEnd(0)).day)
        if row.empty:
            et0_d = 0.0
            peff_d = 0.0
        else:
            r = row.iloc[0]
            et0_m = float(r.get("et0_mm", 0.0) or 0.0)
            p_m = float(r.get("precip_mm", r.get("rain_mm", 0.0)) or 0.0)
            et0_d = et0_m / max(1, days_in_month)
            # SCS effective rainfall is a monthly/period relation, so compute it
            # once on the monthly rainfall total and distribute it across days.
            peff_m = _effective_rain_scs_mm(p_m)
            peff_d = peff_m / max(1, days_in_month)
        etc_d = et0_d * float(kc_daily[idx_day])
        nir_d = max(0.0, etc_d - peff_d)
        gross_d = nir_d / eff
        out_mm[int(day.month)] += gross_d

    return {m: float(max(0.0, v)) for m,v in out_mm.items() if v > 0.0}

def _load_monthly_climate_for_parcel_year(parcel_id: str, year: int) -> pd.DataFrame:
    frames = load_enhanced_frames()
    clim = frames.get("climate")
    if clim is None or getattr(clim, "empty", False):
        clim = frames.get("monthly_climate")
    if clim is None or clim.empty:
        return pd.DataFrame(columns=["month","et0_mm","precip_mm"])
    df = clim.copy()
    df["parcel_id"] = df["parcel_id"].astype(str)
    if "year" not in df.columns:
        if "month" in df.columns:
            df["month"] = pd.to_datetime(df["month"], errors="coerce")
            df["year"] = df["month"].dt.year
        else:
            return pd.DataFrame(columns=["month","et0_mm","precip_mm"])
    else:
        df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df_year = df[df["year"].fillna(0).astype(int) == int(year)].copy()
    df_pid = df_year[df_year["parcel_id"] == str(parcel_id)].copy()
    if df_pid.empty and not df_year.empty:
        # Climate/ETo is regional for this study area. If a parcel-specific row is
        # missing, fall back to one regional monthly series rather than returning
        # zero water demand for that parcel.
        df_pid = df_year.drop_duplicates(subset=["month"]).copy()
        df_pid["parcel_id"] = str(parcel_id)
    df = df_pid
    # ensure month column exists as YYYY-MM-01
    if "month" not in df.columns:
        if "month_num" in df.columns:
            df["month"] = pd.to_datetime(dict(year=df["year"].fillna(year).astype(int), month=df["month_num"], day=1), errors="coerce")
        else:
            return pd.DataFrame(columns=["month","et0_mm","precip_mm"])
    else:
        df["month"] = pd.to_datetime(df["month"], errors="coerce")
    if "precip_mm" not in df.columns and "rain_mm" in df.columns:
        df["precip_mm"] = df["rain_mm"]
    if "precip_mm" not in df.columns:
        df["precip_mm"] = 0.0
    if "et0_mm" not in df.columns:
        df["et0_mm"] = 0.0
    return df[["month","et0_mm","precip_mm"]].copy()

def _risk_adjusted_profit_per_da(price_tl_ton: float, yield_ton: float, var_cost_tl: float, area_da: float,
                                 samples: int = 120, risk_mode: str = "mean_std", risk_lambda: float = 0.0) -> float:
    """Return profit per da under simple price/yield uncertainty.
    - risk_mode: 'mean' or 'mean_std' (mean - lambda*std) or 'cvar' (CVaR_10%).
    """
    area = float(area_da or 0.0)
    if area <= 0:
        return 0.0
    # per-da bases
    ypd = float(yield_ton or 0.0) / area
    cpd = float(var_cost_tl or 0.0) / area
    p = float(price_tl_ton or 0.0)

    # default coefficients of variation (can be replaced via history templates)
    cv_price = 0.20
    cv_yield = 0.15

    import numpy as _np
    rng = _np.random.default_rng(42)
    # lognormal for price, normal for yield (clipped)
    price_s = rng.lognormal(mean=_np.log(max(1.0, p)), sigma=cv_price, size=int(samples))
    yield_s = rng.normal(loc=ypd, scale=max(0.01, abs(ypd)*cv_yield), size=int(samples))
    yield_s = _np.clip(yield_s, 0.0, None)
    profits = price_s * yield_s - cpd
    if profits.size == 0:
        return float(p*ypd - cpd)
    mode = (risk_mode or "mean_std").lower()
    lam = float(risk_lambda or 0.0)
    if mode == "mean":
        return float(_np.mean(profits))
    if mode == "cvar":
        q = float(_np.quantile(profits, 0.10))
        tail = profits[profits <= q]
        if tail.size == 0:
            return float(_np.mean(profits))
        return float(_np.mean(tail))
    # mean_std
    return float(_np.mean(profits) - lam * _np.std(profits))

def available_years() -> List[int]:
    """Years available in reservoir series OR enhanced seasons (union)."""
    frames = load_enhanced_frames()
    years: set[int] = set()

    # reservoir
    res = frames["reservoir"].copy()
    if "month" in res.columns:
        res["year"] = res["month"].astype(str).str.slice(0,4).astype(int)
        years.update(int(y) for y in res["year"].dropna().unique().tolist())

    # seasons
    for k in ("s1","s2"):
        df = frames.get(k)
        if df is not None and len(df) and "year" in df.columns:
            years.update(int(y) for y in df["year"].dropna().unique().tolist())

    return sorted(years)


def water_budget_for_year(year: int, selected_parcels: List[Dict[str,Any]]) -> float:
    """Current planning budget derived from the Excel parcel quotas.

    Project rule (2026-04-19 update):
    - No forward projection is used for planning.
    - The *observed current total irrigation water* across the active planning villages is taken as the
      planning ceiling.
    - This total can be split across villages/parcels only as a comparison scenario; the primary model is area-fair.
    - Therefore the effective budget for any screen/request is the sum of the selected parcels'
      equal parcel quotas.

    The ``year`` argument is kept for API compatibility but is intentionally ignored.
    """
    try:
        df = load_matrix_candidates()
        if df is not None and len(df) and "current_quota_m3" in df.columns:
            if selected_parcels:
                sel_ids = [str(p.get("id","") or "").strip() for p in selected_parcels if str(p.get("id","") or "").strip()]
                if sel_ids:
                    q = (
                        df[df["parcel_id"].isin(sel_ids)][["parcel_id", "current_quota_m3"]]
                        .drop_duplicates(subset=["parcel_id"])
                    )
                else:
                    q = df[["parcel_id", "current_quota_m3"]].drop_duplicates(subset=["parcel_id"])
            else:
                q = df[["parcel_id", "current_quota_m3"]].drop_duplicates(subset=["parcel_id"])
            total = float(pd.to_numeric(q["current_quota_m3"], errors="coerce").fillna(0.0).sum())
            if total > 0:
                return total
    except Exception:
        pass
    return sum(float(p.get("water_m3",0) or 0) for p in (selected_parcels or []))


# -----------------------------
# Basin constraints + irrigation method adjustments (must-have v24)
# -----------------------------

def _get_irrigation_method_efficiency(method: str) -> float:
    """Return typical total efficiency for a given method.

    Reads enhanced_dataset/csv/irrigation_methods_assumed.csv if available.
    Falls back to reasonable defaults.
    """
    m = str(method or '').strip().lower()
    defaults = {
        'drip': 0.90,
        'sprinkler': 0.75,
        'surface_furrow': 0.55,
        'surface': 0.55,
        'furrow': 0.55,
    }
    frames = None
    try:
        frames = load_enhanced_frames()
        df = frames.get('irrigation_methods')
        if df is not None and len(df):
            sub = df[df['method'].astype(str).str.lower() == m]
            if len(sub) and 'typical_total_efficiency' in sub.columns:
                v = float(sub.iloc[0]['typical_total_efficiency'])
                if 0.05 <= v <= 0.99:
                    return v
    except Exception:
        pass
    return float(defaults.get(m, 0.75))

def _basin_month_profile(year: int) -> dict:
    """Return {month_str: baseline_share} for the given year using reservoir baseline.

    Used to approximate monthly delivery constraint checks when crop calendars are not explicit.
    """
    frames = load_enhanced_frames()
    res = frames.get('reservoir')
    if res is None or not len(res) or 'month' not in res.columns:
        return {}
    tmp = res.copy()
    tmp['year'] = tmp['month'].astype(str).str.slice(0,4).astype(int)
    sub = tmp[tmp['year'] == int(year)]
    if not len(sub) or 'irrigation_m3_baseline' not in sub.columns:
        return {}
    total = float(sub['irrigation_m3_baseline'].sum())
    if total <= 0:
        return {}
    out = {}
    for _, r in sub.iterrows():
        mo = str(r['month'])[:7]  # YYYY-MM
        out[mo] = float(r['irrigation_m3_baseline']) / total
    return out

def basin_budget_and_delivery_caps(year: int, selected_parcels: list, env_flow_ratio: float = 0.10):
    """Compute (annual_budget_selected, month_weights, month_caps_selected).

    - env_flow_ratio: share of basin irrigation allocation reserved for ecosystem/sulak alan.
    - month_caps come from delivery_capacity_monthly_assumed.csv when available.

    Note: We scale basin-wide series to the selected parcel group using the same share
    logic as water_budget_for_year().
    """
    env = max(0.0, min(0.50, float(env_flow_ratio or 0.0)))
    frames = load_enhanced_frames()

    # basin annual baseline
    res = frames.get('reservoir')
    basin_annual = None
    month_weights = _basin_month_profile(int(year))
    if res is not None and len(res) and 'month' in res.columns:
        tmp = res.copy()
        tmp['year'] = tmp['month'].astype(str).str.slice(0,4).astype(int)
        sub = tmp[tmp['year'] == int(year)]
        if len(sub) and 'irrigation_m3_baseline' in sub.columns:
            basin_annual = float(sub['irrigation_m3_baseline'].sum())

    # scale share to selected parcels
    try:
        all_parcels = load_parcels()
        all_water = sum(float(p.get('water_m3', 0) or 0) for p in all_parcels)
        sel_water = sum(float(p.get('water_m3', 0) or 0) for p in selected_parcels)
        if all_water <= 0:
            all_water = sum(float(p.get('area_da', 0) or 0) for p in all_parcels) * 500.0
        if sel_water <= 0:
            sel_water = sum(float(p.get('area_da', 0) or 0) for p in selected_parcels) * 500.0
        share = max(0.0, min(1.0, sel_water / all_water)) if all_water > 0 else 1.0
    except Exception:
        share = 1.0

    if basin_annual is None or basin_annual <= 0:
        annual_selected = sum(float(p.get('water_m3',0) or 0) for p in selected_parcels)
    else:
        annual_selected = basin_annual * share

    # reserve environmental flow
    annual_selected = annual_selected * (1.0 - env)

    # delivery caps (monthly)
    caps_selected = {}
    try:
        ddf = frames.get('delivery')
        if ddf is not None and len(ddf) and 'month' in ddf.columns and 'max_delivery_m3_assumed' in ddf.columns:
            tmp = ddf.copy()
            tmp['year'] = tmp['month'].astype(str).str.slice(0,4).astype(int)
            sub = tmp[tmp['year'] == int(year)]
            for _, r in sub.iterrows():
                mo = str(r['month'])[:7]
                caps_selected[mo] = float(r['max_delivery_m3_assumed']) * share * (1.0 - env)
    except Exception:
        caps_selected = {}

        # If delivery caps file is missing, build an assumed monthly capacity profile from month_weights.
    if not caps_selected and month_weights:
        try:
            ssum = sum(float(v) for v in month_weights.values())
            if ssum <= 0:
                ssum = 1.0
            for mo, w in month_weights.items():
                # +5% headroom to avoid false "exceed" in assumed mode
                caps_selected[str(mo)[:7]] = float(annual_selected) * (float(w)/ssum) * 1.05
        except Exception:
            caps_selected = {}

    return float(max(1.0, annual_selected)), month_weights, caps_selected




def compute_monthly_delivery_report(total_water_m3: float,
                                   month_weights: Optional[List[float]],
                                   month_caps: Optional[List[float]],
                                   months: int = 12,
                                   monthly_demand_override: Optional[List[float]] = None) -> Optional[Dict[str, Any]]:
    """Build a UI-friendly monthly delivery capacity report.

    If monthly_demand_override is provided, it must be a list of length 12 (m³ per month).
    Otherwise demand is approximated by distributing total_water_m3 using month_weights.
    """
    if month_caps is None or month_weights is None:
        return None
    try:
        mw = np.array(list(month_weights), dtype=float)
        mc = np.array(list(month_caps), dtype=float)
        if mw.size != mc.size or mw.size == 0:
            return None
        # Normalize to 12 months if needed
        if mw.size != months:
            # simple pad/truncate
            mw = np.resize(mw, months)
            mc = np.resize(mc, months)
        if monthly_demand_override is not None and len(monthly_demand_override) == months:
            dem = np.array(monthly_demand_override, dtype=float)
        else:
            dem = float(total_water_m3) * (mw / max(1e-9, float(mw.sum())))
        exceed = np.maximum(0.0, dem - mc)
        feasible_monthly = bool(np.all(exceed <= 1e-6))
        worst_idx = int(np.argmax(exceed)) if months > 0 else 0
        return {
            "months": list(range(1, months + 1)),
            "demand_m3": [float(x) for x in dem.tolist()],
            "cap_m3": [float(x) for x in mc.tolist()],
            "exceed_m3": [float(x) for x in exceed.tolist()],
            "feasible_monthly": feasible_monthly,
            "worst_month": int(worst_idx + 1),
            "worst_exceed_m3": float(exceed[worst_idx]) if months > 0 else 0.0,
        }
    except Exception:
        return None


def _monthly_demand_from_mu(areas_da: np.ndarray,
                           MU1: Optional[np.ndarray],
                           MU2: Optional[np.ndarray],
                           ch1: np.ndarray,
                           ch2: np.ndarray) -> Optional[List[float]]:
    """Compute 12-month demand (m³) using FAO-56 monthly irrigation matrices (m³/da)."""
    try:
        if MU1 is None:
            return None
        P = int(areas_da.shape[0])
        months = 12
        dem = np.zeros((months,), dtype=float)
        # MU arrays expected shape: [P, C, 12]
        for i in range(P):
            j1 = int(ch1[i]) if ch1 is not None else 0
            if MU1.ndim == 3:
                dem += float(areas_da[i]) * np.array(MU1[i, j1, :months], dtype=float)
            if MU2 is not None and ch2 is not None and MU2.ndim == 3:
                j2 = int(ch2[i])
                dem += float(areas_da[i]) * np.array(MU2[i, j2, :months], dtype=float)
        dem = np.nan_to_num(dem, nan=0.0, posinf=0.0, neginf=0.0)
        return [float(x) for x in dem.tolist()]
    except Exception:
        return None
def apply_irrigation_method_to_W(W: np.ndarray, selected_parcels: list, method: str) -> np.ndarray:
    """Adjust gross water intensities W (m3/da) for a chosen irrigation method.

    The seasonal tables store calibrated *gross* water based on each parcel's
    irrig_efficiency_default. If user selects another method, we preserve the
    implied net irrigation requirement and recompute gross.

        gross_new = gross_default * (eff_default / eff_new)

    """
    eff_new = _get_irrigation_method_efficiency(method)
    W2 = W.copy()
    for i, p in enumerate(selected_parcels):
        eff_def = float(p.get('irrig_efficiency_default', 0.75) or 0.75)
        eff_def = max(0.05, min(0.99, eff_def))
        scale = eff_def / max(0.05, min(0.99, eff_new))
        W2[i, :] = W2[i, :] * scale
    return W2


def build_candidate_matrix(selected_parcels: List[Dict[str,Any]], year: Optional[int]=None, season_source: str="both") -> Tuple[List[str], np.ndarray, np.ndarray]:
    """Return crop_list, water_per_da[parcel,crop], profit_per_da[parcel,crop].

    Key improvements (v14):
      - **No global-median imputation**: Missing (parcel,crop) intensities are first filled from
        district-level means (same crop) computed from the enhanced seasons tables. Remaining
        missing cells are treated as *infeasible* (W=1e9, R=0) to avoid misleading "fabricated"
        recommendations.
      - **Hard suitability filter**: If land capability class (LCC) suitability < 0.60, the crop is
        marked infeasible for that parcel.
      - Keeps a transparent profit multiplier for suitability when >= 0.60.
    """
    frames = load_enhanced_frames()
    src = str(season_source or "both").lower()

    if src in ("both", "s1+s2", "combined", "merge", "birlesik"):
        src = "s1"
    # Season-source selection with a robust fallback.
    # Problem observed in field: Senaryo-2 dataset may not contain rows for the selected parcels/year,
    # which previously caused empty candidates and therefore "boş sonuç" in the UI.
    if src == "s1":
        seasons = frames.get("s1", pd.DataFrame()).copy()
    elif src == "s2":
        seasons = frames.get("s2", pd.DataFrame()).copy()
    else:
        seasons = pd.concat([frames.get("s1", pd.DataFrame()), frames.get("s2", pd.DataFrame())], ignore_index=True)

    if year is not None and "year" in seasons.columns and len(seasons):
        try:
            seasons = seasons[seasons["year"].astype(int) == int(year)]
        except Exception:
            # If year parsing fails, keep full table; downstream will still work.
            pass

    # Fallback: if Senaryo-2 is empty for this selection, retry with Senaryo-1.
    if seasons.empty and src == "s2":
        seasons = frames.get("s1", pd.DataFrame()).copy()
        if year is not None and "year" in seasons.columns and len(seasons):
            try:
                seasons = seasons[seasons["year"].astype(int) == int(year)]
            except Exception:
                pass

    # normalize
    seasons = seasons.copy()
    # Backward compatibility for lean scenario CSVs used in the equal-water version.
    # Some derived files do not carry district / seasonal economy columns; create them
    # here so grouping and benchmark code does not fail with KeyError.
    for _col, _default in {
        "district": "",
        "lcc": "",
        "area_da": np.nan,
        "water_m3_calib_gross": np.nan,
        "profit_tl": np.nan,
    }.items():
        if _col not in seasons.columns:
            seasons[_col] = _default
    # Normalise parcel ids aggressively to prevent "Senaryo-2 sonuç yok" issues
    # caused by whitespace / casing inconsistencies between parcel meta and season CSVs.
    seasons["parcel_id"] = seasons["parcel_id"].astype(str).map(normalize_parcel_id)
    seasons["crop_key"] = seasons["crop"].astype(str).map(normalize_crop_key)

    # Join district/LCC for group-level fallbacks and suitability checks
    parcels_df = frames.get("parcels")
    if parcels_df is not None and len(parcels_df):
        meta = parcels_df.copy()
        meta["parcel_id"] = meta["parcel_id"].astype(str).map(normalize_parcel_id).map(normalize_parcel_id)
        meta["district"] = meta["district"].astype(str) if "district" in meta.columns else ""
        meta["lcc"] = meta["land_capability_class"].astype(str).str.strip().str.upper() if "land_capability_class" in meta.columns else ""
        seasons = seasons.merge(meta[["parcel_id","district","lcc"]], on="parcel_id", how="left")
        for _base in ("district", "lcc"):
            if _base not in seasons.columns:
                _x = f"{_base}_x"; _y = f"{_base}_y"
                if _x in seasons.columns or _y in seasons.columns:
                    seasons[_base] = seasons.get(_x, pd.Series([""]*len(seasons))).fillna(seasons.get(_y, pd.Series([""]*len(seasons))))
    else:
        seasons["district"] = ""
        seasons["lcc"] = ""

    # aggregate per (parcel,crop): mean intensity
    agg = seasons.groupby(["parcel_id","crop_key"], dropna=False).agg(
        area_da=("area_da","mean"),
        water_m3=("water_m3_calib_gross","mean"),
        profit_tl=("profit_tl","mean"),
        district=("district","first"),
        lcc=("lcc","first"),
    ).reset_index()

    agg["water_per_da"] = agg["water_m3"] / agg["area_da"].replace(0,np.nan)
    agg["profit_per_da"] = agg["profit_tl"] / agg["area_da"].replace(0,np.nan)
    agg = agg.replace([np.inf,-np.inf], np.nan)

    # district fallback table (district,crop)
    # IMPORTANT: Treat non-positive profits as *missing* so we don't propagate
    # "0 TL/da" values into recommendations (these are usually due to missing
    # economics in the scenario CSVs, not a true zero-profit crop).
    dist = agg.dropna(subset=["water_per_da","profit_per_da"]).copy()
    try:
        dist = dist[(dist["water_per_da"].astype(float) > 0) & (dist["profit_per_da"].astype(float) > 0)]
    except Exception:
        pass
    dist = dist.groupby(["district","crop_key"], dropna=False).agg(
        water_per_da=("water_per_da","mean"),
        profit_per_da=("profit_per_da","mean"),
    ).reset_index()




    crop_list = sorted([c for c in agg["crop_key"].dropna().unique().tolist() if str(c).strip()])
    # Senaryo-1: kullanıcı tarafından eklenen Niğde odaklı ürünler (sezon verisinde yoksa bile aday havuzuna dahil)
    try:
        src_norm = str(season_source or "s1").lower().strip()
        if src_norm in ("s1","senaryo1","scenario1","1"):
            extra_s1 = [
                "SALÇALIK DOMATES","SOFRALIK DOMATES","LAHANA (BEYAZ)","KABAK (ÇEREZLİK)","FASULYE (TAZE)",
                "SOĞAN (KURU)","KAVUN","SALÇALIK BİBER",
                "PATATES","SİLAJLIK MISIR","YONCA (YEŞİLOT)","BUĞDAY (DANE)","ARPA (DANE)","ŞEKER PANCARI","ÇAVDAR (DANE)"
            ,
                "FİĞ (YEŞİLOT)","KORUNGA (YEŞİLOT)","BURÇAK (YEŞİLOT)","YEM BEZELYESİ","YULAF (YEŞİLOT)","NOHUT","YEŞİL MERCİMEK","KURU FASULYE"
            ]
            s = set([str(x).strip() for x in crop_list])
            for c in extra_s1:
                if c not in s:
                    crop_list.append(c); s.add(c)
    except Exception:
        pass

    
    # Always include a "fallow/no-crop" option so the optimizer stays feasible under tight water budgets.
    FALLOW = normalize_crop_key("NADAS")
    if FALLOW not in crop_list:
        crop_list = [FALLOW] + crop_list
    
    # --- Project-aligned low-water crop pool (fallback) ---
    # When scenario tables miss key low-water cereals/legumes, the optimizer over-uses NADAS.
    # These are conservative placeholder candidates. Replace with calibrated local agronomy + market data.
    # NOTE (UI/Thesis): We present "Su (m³)" as a proxy for total crop water demand/consumption
    # (ETc-like), not only "additional irrigation". Therefore, rainfed ("*_KURU") crops should
    # not appear with 0 water in tables/plots.
    # Values below are conservative placeholders (m³/da) and can be calibrated later.
    default_crop_params = {
        normalize_crop_key("ARPA"): {"water_per_da": 180.0, "profit_per_da": 3800.0},
        normalize_crop_key("BUGDAY"): {"water_per_da": 220.0, "profit_per_da": 4200.0},
        normalize_crop_key("NOHUT"): {"water_per_da": 120.0, "profit_per_da": 5200.0},
        normalize_crop_key("MERCIMEK"): {"water_per_da": 110.0, "profit_per_da": 5000.0},
        normalize_crop_key("KURU_FASULYE"): {"water_per_da": 250.0, "profit_per_da": 6500.0},
        normalize_crop_key("ARPA_KURU"): {"water_per_da": 220.0, "profit_per_da": 2600.0},
        normalize_crop_key("BUGDAY_KURU"): {"water_per_da": 250.0, "profit_per_da": 2800.0},
        normalize_crop_key("NOHUT_KURU"): {"water_per_da": 180.0, "profit_per_da": 3400.0},
        normalize_crop_key("MERCIMEK_KURU"): {"water_per_da": 160.0, "profit_per_da": 3200.0},
    }

    # --- Scenario-1 vegetable & high-value crops (Niğde) ---
    # Only activate these candidates when the user selects seasonSource = 's1' (Senaryo-1).
    # Values are conservative defaults: water_per_da in m³/da, profit_per_da in TL/da (net = revenue - cost).
    if src in ("s1", "senaryo-1", "senaryo1", "scenario1", "1"):
        _s1_extras = {
            normalize_crop_key("SALCALIK_DOMATES"): {"water_per_da": 650.0, "profit_per_da": 52000.0},
            normalize_crop_key("SOFRALIK_DOMATES"): {"water_per_da": 700.0, "profit_per_da": 60000.0},
            normalize_crop_key("LAHANA_BEYAZ"): {"water_per_da": 450.0, "profit_per_da": 18000.0},
            normalize_crop_key("KABAK_CEREZLIK"): {"water_per_da": 300.0, "profit_per_da": 6500.0},
            normalize_crop_key("FASULYE_TAZE"): {"water_per_da": 550.0, "profit_per_da": 20000.0},
            normalize_crop_key("SOGAN_KURU"): {"water_per_da": 500.0, "profit_per_da": 24000.0},
            normalize_crop_key("KAVUN"): {"water_per_da": 550.0, "profit_per_da": 12000.0},
            normalize_crop_key("SALCALIK_BIBER"): {"water_per_da": 600.0, "profit_per_da": 25000.0},
       
            normalize_crop_key("FİĞ (YEŞİLOT)"): {"water_per_da": 160.0, "profit_per_da": 6500.0},
            normalize_crop_key("KORUNGA (YEŞİLOT)"): {"water_per_da": 140.0, "profit_per_da": 6000.0},
            normalize_crop_key("BURÇAK (YEŞİLOT)"): {"water_per_da": 140.0, "profit_per_da": 6200.0},
            normalize_crop_key("YEM BEZELYESİ"): {"water_per_da": 150.0, "profit_per_da": 6400.0},
            normalize_crop_key("YULAF (YEŞİLOT)"): {"water_per_da": 160.0, "profit_per_da": 5500.0},
 }
        default_crop_params.update(_s1_extras)
    for ck in list(default_crop_params.keys()):
        if ck not in crop_list:
            crop_list.append(ck)
    
    # Keep deterministic ordering with FALLOW first.
    crop_list = [FALLOW] + sorted([c for c in crop_list if c != FALLOW])

    try:
        cat = load_crop_catalog()
        if cat:
            catalog_keys = [normalize_crop_key(k) for k in cat.keys()]
            crop_list = [FALLOW] + [ck for ck in crop_list if ck != FALLOW and normalize_crop_key(ck) in catalog_keys]
            for ck in sorted(set(catalog_keys)):
                if ck != FALLOW and ck not in crop_list:
                    crop_list.append(ck)
    except Exception:
        pass
    try:
        seen_crop_keys = set()
        deduped_crop_list = []
        for ck in crop_list:
            nk = normalize_crop_key(ck)
            if not nk or nk in seen_crop_keys:
                continue
            seen_crop_keys.add(nk)
            deduped_crop_list.append(nk)
        crop_list = [FALLOW] + sorted([ck for ck in deduped_crop_list if ck != FALLOW])
    except Exception:
        crop_list = [FALLOW] + sorted([ck for ck in crop_list if ck != FALLOW])

    parcel_ids = [str(p.get("id", "")).strip() for p in selected_parcels if str(p.get("id", "")).strip()]
    P = len(parcel_ids); C = len(crop_list)
    W = np.full((P,C), np.nan, dtype=float)
    R = np.full((P,C), np.nan, dtype=float)
    idx_crop = {c:i for i,c in enumerate(crop_list)}
    idx_parcel = {pid:i for i,pid in enumerate(parcel_ids)}

    for _,r in agg.iterrows():
        pid = str(r["parcel_id"])
        ck = str(r["crop_key"])
        if pid in idx_parcel and ck in idx_crop:
            i = idx_parcel[pid]; j = idx_crop[ck]
            W[i,j] = float(r["water_per_da"]) if pd.notna(r["water_per_da"]) else np.nan
            R[i,j] = float(r["profit_per_da"]) if pd.notna(r["profit_per_da"]) else np.nan

    # Fallow is always feasible with zero water/profit per da.
    if crop_list and crop_list[0] == FALLOW:
        W[:, 0] = 0.0
        R[:, 0] = 0.0

    # District fallback fill
    parcel_district = {}
    parcel_lcc = {}
    if parcels_df is not None and len(parcels_df):
        for _,r in parcels_df.iterrows():
            pid = str(r.get("parcel_id",""))
            if not pid:
                continue
            parcel_district[pid] = str(r.get("district","") or "")
            parcel_lcc[pid] = str(r.get("land_capability_class","") or "").strip().upper()

    dist_map = {(str(r["district"] or ""), str(r["crop_key"])): (float(r["water_per_da"]), float(r["profit_per_da"]))
                for _,r in dist.iterrows()}

    for i,pid in enumerate(parcel_ids):
        d = parcel_district.get(pid, "")
        for j,ck in enumerate(crop_list):
            if not np.isfinite(W[i,j]) or not np.isfinite(R[i,j]):
                v = dist_map.get((d, ck))
                if v is not None and np.isfinite(v[0]) and np.isfinite(v[1]):
                    W[i,j] = float(v[0])
                    R[i,j] = float(v[1])
                else:
                    # Fallback: project-aligned default crops (synthetic placeholders)
                    dv = default_crop_params.get(ck)
                    if dv is not None:
                        W[i,j] = float(dv.get("water_per_da", np.nan))
                        R[i,j] = float(dv.get("profit_per_da", np.nan))

    # Apply suitability: hard filter (<0.60) + soft multiplier (>=0.60)
    try:
        suit = load_crop_suitability_map()
        for i,pid in enumerate(parcel_ids):
            lcc = parcel_lcc.get(pid, "")
            if not lcc:
                continue
            for j,ck in enumerate(crop_list):
                if ck == FALLOW:
                    continue
                sc = float(suit.get((lcc, ck), 0.85))
                sc = max(0.0, min(1.0, sc))
                if sc < 0.60:
                    W[i,j] = np.nan
                    R[i,j] = np.nan
                else:
                    if np.isfinite(R[i,j]):
                        R[i,j] = float(R[i,j]) * sc
    except Exception:
        pass

    # Clamp negative profits to 0 (avoid confusing negative totals in farmer UI)
    try:
        R = np.where(np.isfinite(R) & (R < 0), 0.0, R)
    except Exception:
        pass

    # Profit realism: keep per-da net profits in plausible ranges.
    try:
        R = _apply_profit_realism(R, crop_list)
    except Exception:
        pass

    # Final infeasible fill: no fabricated medians
    # NOTE: We keep an explicit fallow crop (NADAS) with W=0,R=0 for every parcel.
    # For other crops, infeasible cells get a very large W penalty so they are
    # never selected over NADAS.

    # Catalog fallback: if still missing (especially for Senaryo-1 newly added crops), fill from urun_parametreleri_demo.csv
    try:
        cat = load_crop_catalog()  # keyed by normalize_crop_key
        for j, ck in enumerate(crop_list):
            k = normalize_crop_key(ck)
            if k in cat:
                wpd = float(cat[k].get("waterPerDa", 0.0))
                ppd = float(cat[k].get("profitPerDa", 0.0))
                # fill only where missing
                miss = ~np.isfinite(W[:, j]) | ~np.isfinite(R[:, j])
                if np.any(miss):
                    W[miss, j] = wpd
                    R[miss, j] = ppd
    except Exception:
        pass


    # Sazlıca parcel-type filter: field / vegetable / orchard pools are kept separate.
    try:
        cat = load_crop_catalog()
        for i, parcel in enumerate(selected_parcels):
            ptype = str(parcel.get("parcel_type", "") or "").strip().lower()
            if not ptype or ptype == "auto":
                ptype = infer_parcel_type_for_selection(parcel)
            current_crop_key = normalize_crop_key(str(parcel.get("current_crop", "") or "").strip())
            for j, ck in enumerate(crop_list):
                if ck == FALLOW:
                    continue
                rec = cat.get(normalize_crop_key(ck)) or cat.get(str(ck), {})
                ctype = catalog_parcel_type(rec)
                if ptype and ctype and ptype != ctype:
                    W[i, j] = np.nan
                    R[i, j] = np.nan
            if current_crop_key and current_crop_key in crop_list:
                jcur = crop_list.index(current_crop_key)
                if np.isfinite(R[i, jcur]) and R[i, jcur] > 0:
                    R[i, jcur] = float(R[i, jcur]) * 1.04
    except Exception:
        pass

    # Prevent zero/unknown-profit crops from being selected by the optimizer.
    # (A 0 TL/da entry almost always means missing economics in the scenario CSV.)
    try:
        for j, ck in enumerate(crop_list):
            if normalize_crop_key(ck) == FALLOW:
                continue
            bad = (~np.isfinite(W[:, j])) | (~np.isfinite(R[:, j])) | (W[:, j] <= 0) | (R[:, j] <= 0)
            if np.any(bad):
                W[bad, j] = np.nan
                R[bad, j] = np.nan
    except Exception:
        pass

    infeasible = (~np.isfinite(W)) | (~np.isfinite(R)) | (W < 0)
    # Keep fallow feasible even though W==0
    if crop_list and crop_list[0] == FALLOW:
        infeasible[:, 0] = False
    W = np.where(infeasible, 1e9, W)
    R = np.where(infeasible, 0.0, R)
    # Ensure NADAS is feasible everywhere.
    # We assign a small non-zero water proxy so UI tables do not show 0 m³ for fallow in totals.
    # (Represents soil evaporation/maintenance; can be calibrated.)
    if len(crop_list) and crop_list[0] == FALLOW:
        W[:, 0] = 50.0
        R[:, 0] = 0.0

    return crop_list, W, R



def build_candidate_matrix_two_season(
    selected_parcels: List[Dict[str, Any]],
    year: Optional[int] = None,
    season_source: str = "both",
    water_model: str = "calib",
    risk_mode: str = "none",
    risk_lambda: float = 0.0,
    risk_samples: int = 120,
    water_quality_filter: bool = True,
) -> Tuple[List[str], np.ndarray, np.ndarray, np.ndarray, np.ndarray, Optional[np.ndarray], Optional[np.ndarray]]:
    """Return seasonal candidate matrices.

    Outputs:
      crop_list, W_primary, R_primary, W_secondary, R_secondary

    v14 changes:
      - No global-median imputation. Missing cells are filled from district-level means **per season**.
        Remaining missing cells become infeasible (W=1e9, R=0).
      - Hard suitability filter (<0.60) applied to both seasons.
      - Shared crop_list across seasons for simpler UI.
    """
    frames = load_enhanced_frames()
    src = str(season_source or "both").lower().strip()

    def _pick(src_key: str) -> pd.DataFrame:
        if src_key == "s1":
            return frames.get("s1", pd.DataFrame()).copy()
        if src_key == "s2":
            return frames.get("s2", pd.DataFrame()).copy()
        return pd.concat([frames.get("s1", pd.DataFrame()), frames.get("s2", pd.DataFrame())], ignore_index=True)

    seasons = _pick("both" if src not in ("s1", "s2") else src)

    if year is not None and "year" in seasons.columns:
        seasons = seasons[seasons["year"].astype(int) == int(year)]

    # Robust fallback: if the requested season source yields no rows
    # (common when the enhanced S2 file doesn't contain all selected parcels/years),
    # automatically fall back to S1, then to BOTH.
    if seasons.empty and src == "s2":
        seasons = _pick("s1")
        if year is not None and "year" in seasons.columns:
            seasons = seasons[seasons["year"].astype(int) == int(year)]
    if seasons.empty and src in ("s1", "s2"):
        seasons = _pick("both")
        if year is not None and "year" in seasons.columns:
            seasons = seasons[seasons["year"].astype(int) == int(year)]

    if seasons.empty:
        # Final fallback to the simpler single-season matrix builder.
        crop_list, W, R = build_candidate_matrix(selected_parcels, year=year, season_source=season_source)
        return crop_list, W, R, W.copy(), R.copy(), None, None

    seasons = seasons.copy()
    # Backward compatibility for lean scenario CSVs used in the equal-water version.
    # Create missing columns so benchmark/optimizer can still aggregate safely.
    for _col, _default in {
        "district": "",
        "lcc": "",
        "area_da": np.nan,
        "water_m3_calib_gross": np.nan,
        "profit_tl": np.nan,
        "planting_date": "",
        "harvest_date": "",
        "yield_ton": np.nan,
        "price_tl_ton": np.nan,
        "variable_cost_tl": np.nan,
    }.items():
        if _col not in seasons.columns:
            seasons[_col] = _default
    # Normalize parcel_id keys to avoid hidden whitespace mismatches ("P1" vs "P1 ").
    seasons["parcel_id"] = seasons["parcel_id"].astype(str).map(normalize_parcel_id)
    seasons["crop_key"] = seasons["crop"].astype(str).map(normalize_crop_key)
    seasons["season_key"] = seasons["season"].astype(str).str.lower().str.strip()
    seasons.loc[seasons["season_key"].str.contains("primary", na=False), "season_key"] = "primary"
    seasons.loc[seasons["season_key"].str.contains("secondary", na=False), "season_key"] = "secondary"

    parcels_df = frames.get("parcels")
    if parcels_df is not None and len(parcels_df):
        meta = parcels_df.copy()
        meta["parcel_id"] = meta["parcel_id"].astype(str).map(normalize_parcel_id)
        meta["district"] = meta["district"].astype(str) if "district" in meta.columns else ""
        meta["lcc"] = meta["land_capability_class"].astype(str).str.strip().str.upper() if "land_capability_class" in meta.columns else ""
        seasons = seasons.merge(meta[["parcel_id","district","lcc"]], on="parcel_id", how="left")
        for _base in ("district", "lcc"):
            if _base not in seasons.columns:
                _x = f"{_base}_x"; _y = f"{_base}_y"
                if _x in seasons.columns or _y in seasons.columns:
                    seasons[_base] = seasons.get(_x, pd.Series([""]*len(seasons))).fillna(seasons.get(_y, pd.Series([""]*len(seasons))))
    else:
        seasons["district"] = ""
        seasons["lcc"] = ""

    agg = seasons.groupby(["parcel_id", "crop_key", "season_key"], dropna=False).agg(
        area_da=("area_da", "mean"),
        water_m3=("water_m3_calib_gross", "mean"),
        profit_tl=("profit_tl", "mean"),
        # for FAO-56 and risk-adjusted economics
        planting_date=("planting_date", "first"),
        harvest_date=("harvest_date", "first"),
        yield_ton=("yield_ton", "mean"),
        price_tl_ton=("price_tl_ton", "mean"),
        variable_cost_tl=("variable_cost_tl", "mean"),
        district=("district","first"),
        lcc=("lcc","first"),
    ).reset_index()
    agg["water_per_da"] = agg["water_m3"] / agg["area_da"].replace(0, np.nan)
    agg["profit_per_da"] = agg["profit_tl"] / agg["area_da"].replace(0, np.nan)
    agg = agg.replace([np.inf, -np.inf], np.nan)

    crop_list = sorted([c for c in agg["crop_key"].dropna().unique().tolist() if str(c).strip()])

    # Always include a "fallow/no-crop" option so the optimizer stays feasible.
    FALLOW = normalize_crop_key("NADAS")
    if FALLOW not in crop_list:
        crop_list = [FALLOW] + crop_list
    
    # Project-aligned low-water crop pool (fallback placeholders)
    default_crop_params = {
        normalize_crop_key("ARPA"): {"water_per_da": 180.0, "profit_per_da": 3800.0},
        normalize_crop_key("BUGDAY"): {"water_per_da": 220.0, "profit_per_da": 4200.0},
        normalize_crop_key("NOHUT"): {"water_per_da": 120.0, "profit_per_da": 5200.0},
        normalize_crop_key("MERCIMEK"): {"water_per_da": 110.0, "profit_per_da": 5000.0},
        normalize_crop_key("KURU_FASULYE"): {"water_per_da": 250.0, "profit_per_da": 6500.0},
        # Rainfed ("*_KURU") crops should not show 0 water in UI.
        normalize_crop_key("ARPA_KURU"): {"water_per_da": 220.0, "profit_per_da": 2600.0},
        normalize_crop_key("BUGDAY_KURU"): {"water_per_da": 250.0, "profit_per_da": 2800.0},
        normalize_crop_key("NOHUT_KURU"): {"water_per_da": 180.0, "profit_per_da": 3400.0},
        normalize_crop_key("MERCIMEK_KURU"): {"water_per_da": 160.0, "profit_per_da": 3200.0},
    }
    for ck in list(default_crop_params.keys()):
        if ck not in crop_list:
            crop_list.append(ck)
    crop_list = [FALLOW] + sorted([c for c in crop_list if c != FALLOW])
    try:
        seen_crop_keys = set()
        deduped_crop_list = []
        for ck in crop_list:
            nk = normalize_crop_key(ck)
            if not nk or nk in seen_crop_keys:
                continue
            seen_crop_keys.add(nk)
            deduped_crop_list.append(nk)
        crop_list = [FALLOW] + sorted([ck for ck in deduped_crop_list if ck != FALLOW])
    except Exception:
        crop_list = [FALLOW] + sorted([ck for ck in crop_list if ck != FALLOW])
    
    parcel_ids = [str(p["id"]) for p in selected_parcels]
    P, C = len(parcel_ids), len(crop_list)
    idx_crop = {c: i for i, c in enumerate(crop_list)}
    idx_parcel = {pid: i for i, pid in enumerate(parcel_ids)}

    # district fallbacks per season
    dist = agg.dropna(subset=["water_per_da","profit_per_da"]).groupby(["district","crop_key","season_key"], dropna=False).agg(
        water_per_da=("water_per_da","mean"),
        profit_per_da=("profit_per_da","mean"),
    ).reset_index()
    dist_map = {(str(r["district"] or ""), str(r["crop_key"]), str(r["season_key"])): (float(r["water_per_da"]), float(r["profit_per_da"]))
                for _,r in dist.iterrows()}

    parcel_district = {}
    parcel_lcc = {}
    if parcels_df is not None and len(parcels_df):
        for _,r in parcels_df.iterrows():
            pid = str(r.get("parcel_id",""))
            if not pid:
                continue
            parcel_district[pid] = str(r.get("district","") or "")
            parcel_lcc[pid] = str(r.get("land_capability_class","") or "").strip().upper()

    def _matrix_for(season_name: str) -> Tuple[np.ndarray, np.ndarray]:
        sub = agg[agg["season_key"] == season_name]
        W = np.full((P, C), np.nan, dtype=float)
        R = np.full((P, C), np.nan, dtype=float)
        for _, r in sub.iterrows():
            pid = str(r["parcel_id"])
            ck = str(r["crop_key"])
            if pid in idx_parcel and ck in idx_crop:
                i, j = idx_parcel[pid], idx_crop[ck]
                W[i, j] = float(r["water_per_da"]) if pd.notna(r["water_per_da"]) else np.nan
                R[i, j] = float(r["profit_per_da"]) if pd.notna(r["profit_per_da"]) else np.nan

        # district fallback
        for i,pid in enumerate(parcel_ids):
            d = parcel_district.get(pid, "")
            for j,ck in enumerate(crop_list):
                if not np.isfinite(W[i,j]) or not np.isfinite(R[i,j]):
                    v = dist_map.get((d, ck, season_name))
                    if v is not None and np.isfinite(v[0]) and np.isfinite(v[1]):
                        W[i,j] = float(v[0]); R[i,j] = float(v[1])
                    else:
                        dv = default_crop_params.get(ck)
                        if dv is not None:
                            W[i,j] = float(dv.get("water_per_da", np.nan))
                            R[i,j] = float(dv.get("profit_per_da", np.nan))
        return W, R

    W1, R1 = _matrix_for("primary")
    W2, R2 = _matrix_for("secondary")

    # Fallow always feasible
    if crop_list and crop_list[0] == FALLOW:
        W1[:, 0] = 0.0; R1[:, 0] = 0.0
        W2[:, 0] = 0.0; R2[:, 0] = 0.0


    # --- Optional FAO-56 (ET0-Kc) water model + monthly irrigation matrices ---
    month_use1 = None
    month_use2 = None
    wm = str(water_model or "calib").lower().strip()
    rm = str(risk_mode or "none").lower().strip()

    # Build lookup maps from the raw seasons table (with dates/economics)
    date_map = {}
    econ_map = {}  # (pid, ck, season) -> (price, yield_ton, var_cost, area)
    eff_map = {}
    try:
        for _, r in seasons.iterrows():
            pid = str(r.get("parcel_id",""))
            ck = str(r.get("crop_key",""))
            sk = str(r.get("season_key",""))
            if not pid or not ck or not sk:
                continue
            date_map[(pid, ck, sk)] = (str(r.get("planting_date","")), str(r.get("harvest_date","")))
            econ_map[(pid, ck, sk)] = (
                float(r.get("price_tl_ton", 0.0) or 0.0),
                float(r.get("yield_ton", 0.0) or 0.0),
                float(r.get("variable_cost_tl", 0.0) or 0.0),
                float(r.get("area_da", 0.0) or 0.0),
            )
            eff_map[(pid, ck, sk)] = float(r.get("irrig_efficiency", 0.75) or 0.75)
    except Exception:
        pass

    # Risk-adjusted profit per da (optional)
    if rm != "none":
        try:
            def _risk_profit(pid: str, ck: str, sk: str, fallback_profit_per_da: float) -> float:
                k = (pid, ck, sk)
                if k not in econ_map:
                    return float(fallback_profit_per_da)
                price, y_ton, cost, area = econ_map[k]
                if area <= 0:
                    return float(fallback_profit_per_da)
                return float(_risk_adjusted_profit_per_da(price, y_ton, cost, area, samples=int(risk_samples or 120),
                                                          risk_mode=(rm if rm != "none" else "mean_std"),
                                                          risk_lambda=float(risk_lambda or 0.0)))
        except Exception:
            _risk_profit = None
    else:
        _risk_profit = None

    if wm == "fao56" and year is not None:
        # Precompute monthly per-da irrigation (mm == m3/da) for each parcel-crop-season
        crop_params_map = _load_crop_params_map()
        month_use1 = np.zeros((P, C, 12), dtype=float)
        month_use2 = np.zeros((P, C, 12), dtype=float)

        for i, pid in enumerate(parcel_ids):
            clim = _load_monthly_climate_for_parcel_year(pid, int(year))
            for j, ck in enumerate(crop_list):
                if ck == FALLOW:
                    continue
                # primary
                d = date_map.get((pid, ck, "primary"))
                if d:
                    peff = eff_map.get((pid, ck, "primary"), 0.75)
                    mm_by_m = compute_fao56_monthly_irrigation_mm(pid, ck, d[0], d[1], peff, clim, crop_params_map)
                    for mo, mm in mm_by_m.items():
                        month_use1[i, j, int(mo)-1] = float(mm)
                    W1[i, j] = float(sum(mm_by_m.values()))  # mm == m3/da
                # secondary
                d2 = date_map.get((pid, ck, "secondary"))
                if d2:
                    peff2 = eff_map.get((pid, ck, "secondary"), 0.75)
                    mm_by_m2 = compute_fao56_monthly_irrigation_mm(pid, ck, d2[0], d2[1], peff2, clim, crop_params_map)
                    for mo, mm in mm_by_m2.items():
                        month_use2[i, j, int(mo)-1] = float(mm)
                    W2[i, j] = float(sum(mm_by_m2.values()))
        # Replace/refresh district fallback after overrides (keep existing W where FAO data missing)
        # (No extra action: already filled earlier; FAO override only where dates exist.)

    # Water quality hard filter (optional)
    if bool(water_quality_filter):
        try:
            for i, pid in enumerate(parcel_ids):
                for j, ck in enumerate(crop_list):
                    if ck == FALLOW:
                        continue
                    # Use primary season dates if available, else skip
                    d = date_map.get((pid, ck, "primary"))
                    if not d:
                        continue
                    avg_ec = _avg_ec_over_season(d[0], d[1])
                    if avg_ec is None:
                        continue
                    if float(avg_ec) > float(_crop_max_ec_default(ck)):
                        W1[i, j] = np.nan; R1[i, j] = np.nan
                        W2[i, j] = np.nan; R2[i, j] = np.nan
        except Exception:
            pass

    # Apply risk adjustment into R matrices (after FAO override)
    if _risk_profit is not None:
        try:
            for i, pid in enumerate(parcel_ids):
                for j, ck in enumerate(crop_list):
                    if ck == FALLOW:
                        continue
                    if np.isfinite(R1[i, j]):
                        R1[i, j] = float(_risk_profit(pid, ck, "primary", float(R1[i, j])))
                    if np.isfinite(R2[i, j]):
                        R2[i, j] = float(_risk_profit(pid, ck, "secondary", float(R2[i, j])))
        except Exception:
            pass

    # Suitability hard filter + multiplier on both seasons
    try:
        suit = load_crop_suitability_map()
        for i,pid in enumerate(parcel_ids):
            lcc = parcel_lcc.get(pid, "")
            if not lcc:
                continue
            for j,ck in enumerate(crop_list):
                if ck == FALLOW:
                    continue
                sc = float(suit.get((lcc, ck), 0.85))
                sc = max(0.0, min(1.0, sc))
                if sc < 0.60:
                    W1[i,j]=np.nan; R1[i,j]=np.nan
                    W2[i,j]=np.nan; R2[i,j]=np.nan
                else:
                    if np.isfinite(R1[i,j]): R1[i,j] = float(R1[i,j]) * sc
                    if np.isfinite(R2[i,j]): R2[i,j] = float(R2[i,j]) * sc
    except Exception:
        pass

    # Clamp negative profits to 0 (avoid confusing negative totals in farmer UI)
    try:
        R1 = np.where(np.isfinite(R1) & (R1 < 0), 0.0, R1)
        R2 = np.where(np.isfinite(R2) & (R2 < 0), 0.0, R2)
    except Exception:
        pass

    # Profit realism: cap/discount per-da net profits to avoid "too good to be true" plans
    # when economics are assumed. This keeps totals closer to defendable ranges.
    try:
        R1 = _apply_profit_realism(R1, crop_list)
        R2 = _apply_profit_realism(R2, crop_list)
    except Exception:
        pass

    # Final infeasible fill (no fabricated medians)
    inf1 = (~np.isfinite(W1)) | (~np.isfinite(R1)) | (W1 < 0)
    inf2 = (~np.isfinite(W2)) | (~np.isfinite(R2)) | (W2 < 0)
    if crop_list and crop_list[0] == FALLOW:
        inf1[:, 0] = False
        inf2[:, 0] = False
    W1 = np.where(inf1, 1e9, W1); R1 = np.where(inf1, 0.0, R1)
    W2 = np.where(inf2, 1e9, W2); R2 = np.where(inf2, 0.0, R2)

    return crop_list, W1, R1, W2, R2, month_use1, month_use2


# -----------------------------
# Amaç normalizasyonu ve açıklanabilir ekonomik metrikler
# -----------------------------

def _normalize_objective_key(objective: Optional[str]) -> str:
    obj = str(objective or "water_efficiency").strip().lower()
    if obj in ("su_tasarruf", "su tasarruf", "water_saving", "tasarruf"):
        return "water_saving"
    if obj in ("water_efficiency", "su_verimliligi", "su verimliligi", "etkin_su", "etkin su", "su_etkin", "su etkin", "balanced", "denge", "onerilen", "recommended"):
        return "water_efficiency"
    if obj in ("maks_kar", "maks kar", "max_profit", "profit", "kar", "kâr"):
        return "max_profit"
    if obj in ("mevcut", "current"):
        return "current"
    return "water_efficiency"


def _objective_score_value(total_profit: float, total_water: float, objective: str) -> float:
    mode = _normalize_objective_key(objective)
    efficiency = float(total_profit) / max(float(total_water), 1.0)
    if mode == "water_saving":
        # Su tasarrufu: once en az su, kucuk bir karlilik/etkinlik baglayicisi.
        return (efficiency * 350_000.0) + (0.18 * float(total_profit)) - (1.35 * float(total_water) * 500.0)
    if mode == "water_efficiency":
        # Su etkin kullanim: su + kar + TL/m3 birlikte dengelenir.
        return (1.00 * float(total_profit)) + (efficiency * 1_600_000.0) - (0.55 * float(total_water) * 500.0)
    if mode == "max_profit":
        return (1.35 * float(total_profit)) + (efficiency * 250_000.0) - (0.35 * float(total_water) * 500.0)
    return (1.10 * float(total_profit)) + (efficiency * 800_000.0) - (0.60 * float(total_water) * 500.0)


def _decision_metrics_for_crop(crop_name: str, area_da: float, water_per_da: float, profit_per_da: float) -> Dict[str, Any]:
    catalog = load_crop_catalog() or {}
    rec = catalog.get(normalize_crop_key(str(crop_name or "")), {}) if isinstance(catalog, dict) else {}
    units_per_da = safe_float(rec.get("unitsPerDaEst", 0), 0.0)
    yield_kg_da = safe_float(rec.get("yieldKgPerDa", 0), 0.0)
    price_tl_kg = safe_float(rec.get("priceTlPerKg", 0), 0.0)
    cost_tl_da = safe_float(rec.get("costTlPerDa", 0), 0.0)
    gross_rev_da = safe_float(rec.get("grossRevenueTlPerDa", yield_kg_da * price_tl_kg), 0.0)
    estimated_units = float(area_da) * units_per_da if units_per_da > 0 else 0.0
    total_yield_kg = float(area_da) * yield_kg_da
    gross_revenue_tl = float(area_da) * gross_rev_da
    total_cost_tl = float(area_da) * cost_tl_da
    net_profit_tl = float(area_da) * float(profit_per_da)
    total_water_m3 = float(area_da) * float(water_per_da)
    return {
        "unitType": rec.get("unitTypeEst") or None,
        "unitsPerDaEst": float(units_per_da) if units_per_da else 0.0,
        "estimatedUnitsTotal": float(estimated_units) if estimated_units else 0.0,
        "spacingNote": rec.get("spacingNote") or None,
        "yieldPerUnitKgEst": float(rec.get("yieldPerUnitKgEst", 0) or 0),
        "estimatedYieldKg": float(total_yield_kg),
        "grossRevenueTl": float(gross_revenue_tl),
        "estimatedCostTl": float(total_cost_tl),
        "estimatedNetProfitTl": float(net_profit_tl),
        "waterTotalM3": float(total_water_m3),
        "waterLPerUnitEst": float((total_water_m3 * 1000.0) / max(estimated_units, 1.0)) if estimated_units else 0.0,
        "waterEfficiencyTlPerM3": float(net_profit_tl / max(total_water_m3, 1.0)),
        "decisionGroup": rec.get("decisionGroup") or None,
        "perennialLockRule": rec.get("perennialLockRule") or None,
        "managementNote": rec.get("managementNote") or None,
        "selectionBasis": "alan × verim × fiyat × maliyet × su yoğunluğu × su bütçesi × aylık kapasite",
    }


# -----------------------------
# Senaryo-2 (bahçe/perennial) kısıtı ve sulama ayarı
# -----------------------------

PERENNIAL_CROPS = {
    canonical_crop_key(x) for x in [
        "CEVIZ","BADEM","UZUM","UZUM_SOFRALIK","UZUM_SARAPLIK","ELMA","ARMUT","KAYISI","KAYSI",
        "SEFTALI","NAR","KIRAZ","ZEYTIN","FISTIK","FINDIK","INCIR","AYVA","ERIK","NEKTAR","NEKTARIN","VISNE","CILEK","BAG",
    ]
}


def candidate_crop_land_type(candidate_crop: str) -> str:
    """Classify a candidate as field / vegetable / orchard for hard agronomic filtering."""
    ck_norm = normalize_crop_key(candidate_crop)
    ck_canon = canonical_crop_key(candidate_crop)
    catalog = load_crop_catalog() if "load_crop_catalog" in globals() else {}
    rec = {}
    if isinstance(catalog, dict):
        rec = catalog.get(ck_norm) or catalog.get(ck_canon) or {}
    ptype = catalog_parcel_type(rec)
    if ptype in ("field", "vegetable", "orchard"):
        return ptype
    if ck_canon in PERENNIAL_CROPS:
        return "orchard"
    inferred = infer_parcel_type_for_selection(candidate_crop)
    if inferred in ("field", "vegetable", "orchard"):
        return inferred
    return "field"


def candidate_allowed_for_parcel(parcel_type: str, current_crop: str, candidate_crop: str) -> Tuple[bool, str]:
    """Hard ziraat rule used before optimization.

    - Established orchard/perennial parcels keep their main crop; the planner may only
      show inter-row/management alternatives separately.
    - Field parcels must not be converted into orchard/perennial crops inside the normal
      annual product-pattern scenario.
    - Vegetable parcels can compare vegetable/field crops, but not orchard installation
      unless a separate "tesis dönüşümü" scenario is explicitly built.
    """
    ptype = str(parcel_type or "").strip().lower() or "field"
    cand_type = candidate_crop_land_type(candidate_crop)
    cur_canon = canonical_crop_key(current_crop)
    cand_canon = canonical_crop_key(candidate_crop)

    if cand_canon == FALLOW:
        return True, "nadas/boş bırakma güvenlik seçeneği"

    if ptype == "orchard":
        if cur_canon and cand_canon == cur_canon:
            return True, "kurulu bahçede mevcut ana ürün korunur"
        return False, "kurulu bahçe/çok yıllık parselde ana ürün değişimi normal optimizasyonda yasak"

    if ptype == "field" and cand_type == "orchard" and cand_canon != cur_canon:
        return False, "tarla parseline bahçe/çok yıllık ürün önerisi ayrı tesis dönüşümü senaryosu gerektirir"

    if ptype == "vegetable" and cand_type == "orchard" and cand_canon != cur_canon:
        return False, "sebze parseline bahçe/çok yıllık ürün önerisi ayrı tesis dönüşümü senaryosu gerektirir"

    return True, "parsel tipi ile ürün tipi uyumlu"

def is_annual_field_vegetable_candidate(candidate_crop: str) -> bool:
    """Return True for the annual field/vegetable scope used by annual ranking."""
    ck = normalize_crop_key(candidate_crop)
    if not ck or ck == FALLOW or canonical_crop_key(candidate_crop) in PERENNIAL_CROPS:
        return False
    if candidate_crop_land_type(candidate_crop) not in ("field", "vegetable"):
        return False
    vegetable = (
        "DOMATES", "BIBER", "KABAK", "PATLICAN", "HIYAR", "KARPUZ", "KAVUN",
        "SOGAN", "SARIMSAK", "LAHANA", "MARUL", "ISPANAK", "HAVUC", "TURP",
        "BAMYA", "FASULYE"
    )
    field = (
        "BUGDAY", "ARPA", "CAVDAR", "YULAF", "TRITIKALE", "MERCIMEK", "NOHUT",
        "FIG", "YEM", "BEZELYE", "AYCICEGI", "MISIR", "PANCAR", "PATATES",
        "KIMYON"
    )
    return any(x in ck for x in vegetable) or any(x in ck for x in field)


def normalize_crop_category_mode(value: Any) -> str:
    raw = str(value or "mixed").strip().lower()
    raw = raw.replace("-", "_").replace(" ", "_")
    aliases = {
        "same": "same_category",
        "same_category": "same_category",
        "mevcut": "same_category",
        "field": "field_cereal",
        "field_cereal": "field_cereal",
        "cereal": "field_cereal",
        "tahil": "field_cereal",
        "tarla": "field_cereal",
        "forage": "forage",
        "yem": "forage",
        "legume": "legume",
        "baklagil": "legume",
        "vegetable": "vegetable",
        "sebze": "vegetable",
        "industrial": "industrial_oil",
        "industrial_oil": "industrial_oil",
        "oil": "industrial_oil",
        "endustri": "industrial_oil",
        "orchard": "orchard",
        "bahce": "orchard",
        "mixed": "mixed",
        "karisik": "mixed",
        "all": "mixed",
    }
    return aliases.get(raw, "mixed")


def annual_crop_category(candidate_crop: str) -> str:
    ck = normalize_crop_key(candidate_crop)
    canon = canonical_crop_key(candidate_crop)
    if canon in PERENNIAL_CROPS or candidate_crop_land_type(candidate_crop) == "orchard":
        return "orchard"
    if any(x in ck for x in ("SILAJ", "YESILOT", "YEM", "FIG")):
        return "forage"
    if any(x in ck for x in ("MERCIMEK", "NOHUT", "FASULYE", "BAKLA", "BEZELYE")):
        return "legume"
    if any(x in ck for x in ("BUGDAY", "ARPA", "CAVDAR", "YULAF", "TRITIKALE")):
        return "field_cereal"
    if any(x in ck for x in ("AYCICEGI", "KIMYON", "PATATES", "PANCAR", "SARIMSAK", "LAVANTA", "COREK", "ASPIR")):
        return "industrial_oil"
    if any(x in ck for x in ("DOMATES", "BIBER", "KABAK", "PATLICAN", "HIYAR", "KARPUZ", "KAVUN", "SOGAN", "LAHANA", "MARUL", "ISPANAK", "HAVUC", "TURP", "BAMYA")):
        return "vegetable"
    if "MISIR" in ck:
        return "forage" if "SILAJ" in ck else "field_cereal"
    return "field_cereal" if candidate_crop_land_type(candidate_crop) == "field" else "vegetable"


def annual_crop_category_label(category: str) -> str:
    return {
        "same_category": "Mevcut kategori",
        "field_cereal": "Tahıl / tarla",
        "forage": "Yem bitkisi",
        "legume": "Baklagil",
        "vegetable": "Sebze",
        "industrial_oil": "Endüstri / yağ / özel",
        "orchard": "Bahçe / çok yıllık",
        "mixed": "Karışık mod",
    }.get(str(category or ""), str(category or "Genel"))


def annual_category_fit_score(candidate_category: str, mode: str, current_category: str = "") -> float:
    cat = str(candidate_category or "").strip()
    mode = normalize_crop_category_mode(mode)
    current = str(current_category or "").strip()
    if mode == "mixed":
        return 0.72
    if mode == "orchard":
        return 1.0 if cat == "orchard" else 0.0
    if mode == "same_category":
        if cat == current:
            return 1.0
        near = {
            "field_cereal": {"forage": 0.72, "legume": 0.64, "industrial_oil": 0.55},
            "forage": {"field_cereal": 0.70, "legume": 0.58},
            "legume": {"field_cereal": 0.62, "forage": 0.55},
            "vegetable": {"industrial_oil": 0.46, "legume": 0.42},
            "industrial_oil": {"field_cereal": 0.58, "vegetable": 0.52},
        }
        return near.get(current, {}).get(cat, 0.20)
    if cat == mode:
        return 1.0
    near_mode = {
        "field_cereal": {"forage": 0.62, "legume": 0.52, "industrial_oil": 0.45},
        "forage": {"field_cereal": 0.58, "legume": 0.46},
        "legume": {"field_cereal": 0.52, "forage": 0.46},
        "vegetable": {"industrial_oil": 0.42, "legume": 0.34},
        "industrial_oil": {"field_cereal": 0.50, "vegetable": 0.42},
    }
    return near_mode.get(mode, {}).get(cat, 0.08)


def _compute_perennial_locks(selected_parcels: List[Dict[str,Any]], year: int, crop_list: List[str], season_source: str) -> np.ndarray:
    """For Senaryo-2, if a parcel is a fruit-orchard/perennial in that year, lock crop choice to that crop.

    This prevents unrealistic switching of an established orchard to a different product.
    """
    P = len(selected_parcels)
    locks = np.full(P, -1, dtype=int)
    src = str(season_source or "both").lower()
    # Bahçe / çok yıllık parsellerde ana ürün her modda korunur.
    if P == 0:
        return locks

    frames = load_enhanced_frames()
    seasons = frames["s2"].copy()
    if "year" in seasons.columns:
        seasons = seasons[seasons["year"].astype(int) == int(year)]

    dom_map = {}
    if not seasons.empty:
        seasons["parcel_id"] = seasons["parcel_id"].astype(str)
        seasons["crop_key"] = seasons["crop"].astype(str).map(normalize_crop_key)
        # dominant crop by area
        dom = seasons.groupby(["parcel_id","crop_key"], dropna=False).agg(area=("area_da","sum")).reset_index()
        dom = dom.sort_values(["parcel_id","area"], ascending=[True, False])
        dom = dom.drop_duplicates(subset=["parcel_id"], keep="first")
        dom_map = {str(r["parcel_id"]): str(r["crop_key"]) for _, r in dom.iterrows()}

    idx_crop = {c:i for i,c in enumerate(crop_list)}
    for i, p in enumerate(selected_parcels):
        pid = str(p.get("id"))
        ck = dom_map.get(pid)
        parcel_type = str(p.get('parcel_type','') or '').strip().lower()
        current_crop = normalize_crop_key(str(p.get('current_crop') or p.get('crop') or ''))
        orchard_like = (parcel_type == 'orchard') or (current_crop in PERENNIAL_CROPS)
        # Eğer parsel bahçe/çok yıllıksa, sezon tablosu eksik olsa bile mevcut ürünü kilitle.
        if orchard_like and current_crop in idx_crop:
            ck = current_crop
        if (not ck) and orchard_like and current_crop in idx_crop:
            ck = current_crop
        if ck and (ck in PERENNIAL_CROPS) and (ck in idx_crop):
            locks[i] = int(idx_crop[ck])
    return locks




def _orchard_interrow_alternatives(main_crop: str) -> List[Dict[str, Any]]:
    main = str(main_crop or '').strip() or 'Bahçe ürünü'
    csv_path = DATA_DIR / 'orchard_interrow_alternatives.csv'
    if csv_path.exists():
        try:
            df = pd.read_csv(csv_path)
            rows: List[Dict[str, Any]] = []
            for _, r in df.iterrows():
                rows.append({
                    'name': str(r.get('name', '') or '').strip(),
                    'kind': str(r.get('kind', '') or '').strip(),
                    'waterLevel': str(r.get('water_level', '') or '').strip(),
                    'note': str(r.get('note', '') or '').replace('{MAIN}', main).strip(),
                })
            rows = [x for x in rows if x.get('name')]
            if rows:
                return rows
        except Exception:
            pass
    return [
        {'name': 'Mercimek', 'kind': 'Sıra arası / baklagil', 'waterLevel': 'Düşük su', 'note': f'{main} ana ürün olarak korunur. Mercimek; düşük su tüketimi, baklagil etkisi ve kısa dönemli sıra arası değerlendirme için uygundur. Ana ürün yerine yazılmaz.'},
        {'name': 'Nohut', 'kind': 'Sıra arası / baklagil', 'waterLevel': 'Düşük-orta su', 'note': f'{main} bahçesinde sıra arası ticari alternatif olarak düşünülebilir. Kök rekabeti ve gölge durumu uygunsa sınırlı alanda uygulanmalıdır; ana ürün yerine geçmez.'},
        {'name': 'Fiğ (Yeşilot)', 'kind': 'Örtü bitkisi / yeşil gübre', 'waterLevel': 'Düşük-orta su', 'note': f'{main} bahçesinde toprağı örtme, organik maddeyi destekleme ve yeşil gübreleme amacıyla uygundur. Ticari ana ürün değil, yönetim amaçlı ara seçenek olarak ele alınmalıdır.'},
        {'name': 'Arpa (Yeşilot)', 'kind': 'Örtü bitkisi / yem', 'waterLevel': 'Düşük-orta su', 'note': f'{main} bahçesinde erozyon kontrolü ve toprak örtüsü amacıyla düşünülebilir. Su açığı yüksek yıllarda düşük yoğunluklu uygulanmalı; ana ürün yerine değerlendirilmemelidir.'},
    ]

def _apply_s2_irrigation_adjustments(objective: str) -> Tuple[float, float, str]:
    """Return (water_mult, profit_mult, label) for perennial/orchard parcels.

    Orchard parcels keep the same crop. What changes is the water-management strategy.
    """
    obj = _normalize_objective_key(objective)
    if obj == "water_saving":
        return 0.72, 0.90, "Aynı bahçe ürünü + damla + sıkı kısıntılı sulama (%28)"
    if obj == "water_efficiency":
        return 0.84, 1.00, "Aynı bahçe ürünü + damla + dengeli kısıntı (%16)"
    if obj == "max_profit":
        return 0.96, 1.06, "Aynı bahçe ürünü + verim odaklı damla sulama"
    return 0.90, 1.00, "Aynı bahçe ürünü + damla + hafif kısıntı (%10)"


# -----------------------------
# UI çıktı formatı (en az 2 ürün + 2 sezon etiketleri)
# -----------------------------


def _objective_alpha_beta(objective: str) -> Tuple[float, float]:
    """Return legacy weights for helper ranking.

    Main optimization now also uses explicit TL/m³ efficiency scoring via
    _objective_score_value().
    """
    obj = _normalize_objective_key(objective)
    if obj == "water_saving":
        return 0.72, 1.35
    if obj == "water_efficiency":
        return 1.12, 0.82
    if obj == "max_profit":
        return 1.40, 0.35
    return 1.10, 0.70
def _build_two_crop_recommendations(
    selected_parcels: List[Dict[str, Any]],
    year: int,
    objective: str,
    season_source: str,
    chosen: Optional[np.ndarray] = None,
    budget_ratio: float = 1.0,
    # v26+ project options
    env_flow_ratio: float = 0.10,
    irrigation_method: Optional[str] = None,
    enforce_delivery_caps: bool = True,
    **_ignored: Any,
) -> Dict[str, Any]:
    """UI-friendly 1. ürün + 2. ürün planı.

    Bu sürümde Senaryo-1 için kritik kurallar:
      1) **Ana ürün** mutlaka 15 ürün havuzundan seçilir.
      2) **İkinci ürün** (hasat sonrası) Niğde'de yaygın ve toprak için faydalı düşük-su havuzundan seçilir.
      3) Yıllık toplam su: (Ana ürün suyu + İkinci ürün suyu) alan ile çarpılarak net şekilde raporlanır.
    """

    crop_list, W, R = build_candidate_matrix(selected_parcels, year=year, season_source=season_source)
    P = len(selected_parcels)
    C = len(crop_list)
    if P == 0 or C == 0:
        return {"parcels": [], "totals": {"water": 0.0, "profit": 0.0}, "feasible": True, "budget": 0.0}

    areas = np.array([float(p.get("area_da", 0) or 0) for p in selected_parcels], dtype=float)

    base_budget, month_weights, month_caps = basin_budget_and_delivery_caps(
        int(year), selected_parcels, env_flow_ratio=float(env_flow_ratio or 0.0)
    )
    budget = max(1.0, float(base_budget) * float(budget_ratio or 1.0))

    if irrigation_method:
        W = apply_irrigation_method_to_W(W, selected_parcels, irrigation_method)
    if not enforce_delivery_caps:
        month_weights, month_caps = None, None

    # Locks for Senaryo-2 orchard parcels
    locks = _compute_perennial_locks(selected_parcels, int(year), crop_list, season_source)
    lock_mask = (locks >= 0)
    irrigation_label = None
    if np.any(lock_mask):
        wmul, pmul, irrigation_label = _apply_s2_irrigation_adjustments(objective)
        W = W.copy(); R = R.copy()
        W[lock_mask, :] = W[lock_mask, :] * float(wmul)
        R[lock_mask, :] = R[lock_mask, :] * float(pmul)

    alpha, beta = _objective_alpha_beta(objective)

    # ---- Feasibility guards ----
    INF_W = 1e8
    feasible_choices: List[np.ndarray] = []
    for i in range(P):
        ok = np.where((W[i, :] < INF_W) & np.isfinite(W[i, :]) & np.isfinite(R[i, :]) & (W[i, :] >= 0.0))[0]
        if ok.size == 0:
            ok = np.array([0], dtype=int)  # fallow only
        feasible_choices.append(ok)

    # Reference bounds for normalization.
    # IMPORTANT: Using the reservoir budget directly as the water reference can
    # make water_n extremely small when the budget is large, which breaks the
    # intended behaviour of the "water_saving" objective (it may look like water
    # is always "cheap"). We therefore compute a data-driven upper bound from
    # feasible crops.
    try:
        profit_upper_bound = 0.0
        water_lower_bound = 0.0
        water_upper_bound = 0.0
        for i in range(P):
            ch = feasible_choices[i]
            profit_upper_bound += float(areas[i]) * float(np.nanmax(R[i, ch]))
            water_lower_bound += float(areas[i]) * float(np.nanmin(W[i, ch]))
            water_upper_bound += float(areas[i]) * float(np.nanmax(W[i, ch]))
        if not np.isfinite(profit_upper_bound) or profit_upper_bound <= 0:
            profit_upper_bound = 1.0
        if not np.isfinite(water_lower_bound) or water_lower_bound <= 0:
            water_lower_bound = 1.0
        if not np.isfinite(water_upper_bound) or water_upper_bound <= 0:
            water_upper_bound = 1.0
    except Exception:
        profit_upper_bound = 1.0
        water_lower_bound = 1.0
        water_upper_bound = 1.0

    def _sanitize_ind(ind: np.ndarray) -> np.ndarray:
        ind = ind.astype(int, copy=True)
        for i in range(len(ind)):
            j = int(ind[i])
            if j < 0 or j >= C or (not np.isfinite(W[i, j])) or (not np.isfinite(R[i, j])) or (W[i, j] >= INF_W) or (W[i, j] < 0):
                ind[i] = int(feasible_choices[i][0])
        return ind

    # Score matrix
    score = alpha * R - beta * W

    # Crop family map and small soil-health bonus for legumes
    family_map = load_crop_family_map()
    try:
        legume_bonus = float(np.nanmedian(R)) * 0.05
        for j, ck in enumerate(crop_list):
            if family_map.get(ck, "") in LEGUME_FAMILIES:
                score[:, j] = score[:, j] + legume_bonus
    except Exception:
        pass

    src_norm = str(season_source or "").lower().strip()

    # ---- Primary crop constraint (Senaryo-1 15 ürün) ----
    primary_allowed_idx: Optional[set] = None
    if src_norm in ("s1", "senaryo1", "senaryo-1", "scenario1", "1"):
        primary_15 = [
            "PATATES","SİLAJLIK MISIR","YONCA (YEŞİLOT)","BUĞDAY (DANE)","ARPA (DANE)","ŞEKER PANCARI","ÇAVDAR (DANE)",
            "SALÇALIK DOMATES","SOFRALIK DOMATES","LAHANA (BEYAZ)","KABAK (ÇEREZLİK)","FASULYE (TAZE)","SOĞAN (KURU)","KAVUN","SALÇALIK BİBER"
        ]
        primary_15 = set([normalize_crop_key(x) for x in primary_15])
        primary_allowed_idx = set([j for j,c in enumerate(crop_list) if c in primary_15])

    # Choose primary
    if chosen is not None and len(chosen) == P:
        primary_idx = _sanitize_ind(chosen.astype(int).copy())
    else:
        primary_idx = np.zeros(P, dtype=int)
        for i in range(P):
            row = score[i, :].copy()
            if primary_allowed_idx:
                mask = np.ones(C, dtype=bool)
                for j in primary_allowed_idx:
                    mask[int(j)] = False
                row[mask] = -1e18
            row[(~np.isfinite(W[i,:])) | (W[i,:] >= INF_W)] = -1e18
            primary_idx[i] = int(np.argmax(row))

    # Apply orchard locks
    if np.any(lock_mask):
        primary_idx[lock_mask] = locks[lock_mask]

    # ---- Secondary crop constraint (Senaryo-1 ikinci sezon havuzu) ----
    second_pool = set([normalize_crop_key(x) for x in [
        "FİĞ (YEŞİLOT)","KORUNGA (YEŞİLOT)","BURÇAK (YEŞİLOT)","YEM BEZELYESİ","NOHUT","YEŞİL MERCİMEK","KURU FASULYE","YULAF (YEŞİLOT)"
    ]])

    secondary_idx = np.zeros(P, dtype=int)
    for i in range(P):
        p_crop = crop_list[int(primary_idx[i])]
        p_fam = family_map.get(p_crop, "")

        cand = []
        for j, cname in enumerate(crop_list):
            if j == int(primary_idx[i]):
                continue
            if (not np.isfinite(W[i, j])) or (W[i, j] >= INF_W):
                continue
            if src_norm in ("s1", "senaryo1", "senaryo-1", "scenario1", "1"):
                if cname not in second_pool:
                    continue
            c_fam = family_map.get(cname, "")
            if p_fam and c_fam and (c_fam == p_fam):
                continue
            cand.append(j)

        # Fallback: any feasible different-family crop
        if len(cand) == 0:
            for j, cname in enumerate(crop_list):
                if j == int(primary_idx[i]):
                    continue
                if (not np.isfinite(W[i, j])) or (W[i, j] >= INF_W):
                    continue
                c_fam = family_map.get(cname, "")
                if p_fam and c_fam and (c_fam == p_fam):
                    continue
                cand.append(j)

        if len(cand) == 0:
            secondary_idx[i] = int(primary_idx[i])
        else:
            def _rank(j: int):
                fam = family_map.get(crop_list[j], "")
                soil = 1 if fam in LEGUME_FAMILIES else 0
                return (soil, -float(W[i, j]), float(score[i, j]))
            secondary_idx[i] = int(max(cand, key=_rank))

        # Orchard: cover crop = minimum water feasible
        if bool(lock_mask[i]):
            feas = np.where(np.isfinite(W[i,:]) & (W[i,:] < INF_W))[0]
            lw = int(feas[np.argmin(W[i, feas])]) if feas.size else int(primary_idx[i])
            if lw != int(primary_idx[i]):
                secondary_idx[i] = lw


    # Decide whether to actually use a secondary crop (show at most 2 options to user).
    # UI kararı:
    #   - S1: tek ürün ana plan
    #   - S2: tarla için münavebe / yazlık+kışlık, bahçe için ana ürün koruma
    use_second = np.ones(P, dtype=bool)
    if src_norm in ("s1", "senaryo1", "senaryo-1", "scenario1", "1"):
        use_second[:] = False
    # WATER-SAVING POLICY:
    # In "water_saving" objective we do NOT recommend a second crop (double-cropping) for annual parcels,
    # because farmers explicitly want lower total water use; a second crop often increases seasonal water demand.
    # Scenario-2 orchard/perennial parcels (lock_mask) can still keep a cover crop if locked by rules.
    if _normalize_objective_key(objective) == "water_saving":
        for i in range(P):
            if not bool(lock_mask[i]):
                use_second[i] = False
    for i in range(P):
        if bool(lock_mask[i]):
            continue  # orchards: keep a cover crop
        w1 = float(W[i, primary_idx[i]]); w2 = float(W[i, secondary_idx[i]])
        r1 = float(R[i, primary_idx[i]]); r2 = float(R[i, secondary_idx[i]])
        fam2 = family_map.get(crop_list[int(secondary_idx[i])], "")
        soil_ok = fam2 in LEGUME_FAMILIES
        water_ok = (np.isfinite(w2) and np.isfinite(w1) and (w2 <= w1 * 0.95))
        profit_ok = (np.isfinite(r2) and np.isfinite(r1) and (r2 >= r1 * 0.40))
        # If neither water saving nor soil benefit, skip second crop
        if not (water_ok or soil_ok):
            use_second[i] = False
        # If it saves water but destroys profit, skip
        if (water_ok or soil_ok) and (not profit_ok) and (r1 > 0):
            use_second[i] = False
        if not use_second[i]:
            secondary_idx[i] = int(primary_idx[i])

    # Area split (same parcel içinde iki sezon)
    # If use_second[i] is False, keep only one crop (a2=0).
    a1 = np.maximum(0.0, np.round(areas.copy(), 1))
    a2 = np.zeros(P, dtype=float)
    a1[use_second] = np.maximum(0.0, np.round(areas[use_second] * 0.70, 1))
    a2[use_second] = np.maximum(0.0, np.round(areas[use_second] - a1[use_second], 1))
    for i in range(P):
        if bool(lock_mask[i]):
            a2[i] = np.round(max(0.1, areas[i] * 0.1), 1)
            a1[i] = np.round(max(0.1, areas[i] - a2[i]), 1)

    def totals(a1_, a2_):
        water = float(np.sum(a1_ * W[np.arange(P), primary_idx] + a2_ * W[np.arange(P), secondary_idx]))
        profit = float(np.sum(a1_ * R[np.arange(P), primary_idx] + a2_ * R[np.arange(P), secondary_idx]))
        return water, profit

    # Water budget repair: shift area from higher-water to lower-water within parcel
    max_iter = 500
    it = 0
    w_tot, p_tot = totals(a1, a2)
    while w_tot > budget + 1e-6 and it < max_iter:
        changed = False
        for i in range(P):
            w1 = float(W[i, primary_idx[i]]); w2 = float(W[i, secondary_idx[i]])
            step = max(0.1, float(areas[i]) * 0.05)
            if w1 > w2 and a1[i] > step:
                a1[i] = np.round(a1[i] - step, 1)
                a2[i] = np.round(a2[i] + step, 1)
                changed = True
            elif w2 > w1 and a2[i] > step:
                a2[i] = np.round(a2[i] - step, 1)
                a1[i] = np.round(a1[i] + step, 1)
                changed = True
        if not changed:
            for i in range(P):
                if a2[i] > 0.1:
                    red = max(0.1, a2[i] * 0.1)
                    a2[i] = np.round(max(0.1, a2[i] - red), 1)
                    a1[i] = np.round(areas[i] - a2[i], 1)
                    changed = True
            if not changed:
                break
        w_tot, p_tot = totals(a1, a2)
        it += 1

    feasible = bool(w_tot <= budget + 1e-6)

    delivery_report = compute_monthly_delivery_report(
        total_water_m3=float(w_tot),
        month_weights=month_weights,
        month_caps=month_caps,
        months=12,
        monthly_demand_override=None,
    )
    if delivery_report is not None and (not delivery_report.get("feasible_monthly", True)):
        feasible = False

    # --- Irrigation suggestion + transparent saving ---
    s1_rules = {}
    try:
        _p_rules = DATA_DIR / "s1_crop_calendar_rules.json"
        if _p_rules.exists():
            s1_rules = load_json(_p_rules) or {}
    except Exception:
        s1_rules = {}

    crop_irrig_map = {}
    try:
        _p = DATA_DIR / "crop_irrigation_map.json"
        if _p.exists():
            crop_irrig_map = load_json(_p) or {}
    except Exception:
        crop_irrig_map = {}

    eff_map = {"sprinkler_pivot": 0.68, "sprinkler": 0.68, "surface_furrow": 0.47, "drip": 0.83, "rainfed": 1.0}
    try:
        _im = load_enhanced_frames().get("irrigation_methods")
        if _im is not None and len(_im) > 0 and "method" in _im.columns and "typical_total_efficiency" in _im.columns:
            for _, rr in _im.iterrows():
                eff_map[str(rr["method"]).strip()] = float(rr["typical_total_efficiency"])
    except Exception:
        pass

    def _irrig_block(crop_name: str, area_da: float, water_per_da: float) -> Dict[str, Any]:
        info = crop_irrig_map.get(crop_name, {}) if isinstance(crop_irrig_map, dict) else {}
        cur = str(info.get("default", "")) if info else ""
        recm = str(info.get("recommended", "")) if info else ""
        if cur == "" and recm == "":
            return {"irrigationCurrent": None, "irrigationRecommended": None, "irrigationCurrentKey": None, "irrigationSuggestedKey": None, "waterSavingPct": 0.0, "waterSavingPerDa": 0.0, "waterSavingTotal": 0.0}
        if recm == "":
            recm = cur
        eff_cur = float(eff_map.get(cur, 1.0)) if cur else 1.0
        eff_rec = float(eff_map.get(recm, eff_cur)) if recm else eff_cur
        if eff_cur <= 0 or eff_rec <= 0:
            return {"irrigationCurrent": cur or None, "irrigationRecommended": recm or None, "irrigationCurrentKey": cur or None, "irrigationSuggestedKey": recm or None, "waterSavingPct": 0.0, "waterSavingPerDa": 0.0, "waterSavingTotal": 0.0}
        new_water_per_da = float(water_per_da) * (eff_cur / eff_rec)
        saving_per_da = max(0.0, float(water_per_da) - new_water_per_da)
        saving_pct = 0.0 if float(water_per_da) <= 0 else min(1.0, saving_per_da / float(water_per_da))
        return {
            "irrigationCurrent": cur or None,
            "irrigationRecommended": recm or None,
            "irrigationCurrentKey": cur or None,
            "irrigationSuggestedKey": recm or None,
            "waterSavingPct": float(saving_pct),
            "waterSavingPerDa": float(saving_per_da),
            "waterSavingTotal": float(saving_per_da * float(area_da)),
        }

    parcels_out = []
    for i, p in enumerate(selected_parcels):
        c1 = crop_list[int(primary_idx[i])]
        c2 = crop_list[int(secondary_idx[i])]
        w1 = float(W[i, int(primary_idx[i])]); w2 = float(W[i, int(secondary_idx[i])])
        p1 = float(R[i, int(primary_idx[i])]); p2 = float(R[i, int(secondary_idx[i])])
        wt1 = float(a1[i] * w1); wt2 = float(a2[i] * w2)
        pt1 = float(a1[i] * p1); pt2 = float(a2[i] * p2)

        # Season labels from Scenario-1 calendar rules (data-driven)
        rule1 = s1_rules.get(c1, {}) if isinstance(s1_rules, dict) else {}
        # Season labels from Scenario-1 calendar rules (if available)
        rule1 = (s1_rules.get(c1, {}) if isinstance(s1_rules, dict) else {})
        season1 = (rule1.get("primary_season") or rule1.get("season") or "—")
        rule2 = (s1_rules.get(c2, {}) if isinstance(s1_rules, dict) else {})
        season2 = (rule1.get("secondary_season") if (rule1.get("secondary_crop") == c2) else (rule2.get("primary_season") or rule2.get("season") or "—"))

        rec = [
            {
                "name": c1,
                "season": season1,
                "area": float(a1[i]),
                "waterPerDa": w1,
                "waterTotal": wt1,
                "profitPerDa": p1,
                "profitTotal": pt1,
                **_irrig_block(c1, float(a1[i]), w1),
                "reason": ("Tek ürün ana plan: seçili hedef, su-kâr dengesi ve parsel uygunluğu") if src_norm in ("s1","senaryo1","senaryo-1","scenario1","1") else "Ana ürün: seçili hedef, su-kâr dengesi ve parsel uygunluğu"
            },
        ]
        if float(a2[i]) > 0.05:
            rec.append({
                "name": c2,
                "season": season2,
                "area": float(a2[i]),
                "waterPerDa": w2,
                "waterTotal": wt2,
                "profitPerDa": p2,
                "profitTotal": pt2,
                **_irrig_block(c2, float(a2[i]), w2),
                "reason": "İkinci ürün / münavebe: yazlık-kışlık geçişi, toprak ve su dengesi için"
            })
        if irrigation_label is not None and bool(lock_mask[i]):
            for r in rec:
                r["irrigation_plan"] = irrigation_label
                r["reason"] = "Bahçe ürünü kilitli (Senaryo-2): ürün değişmez; sulama planı uygulanır."

        parcel_annual = {
            "annualWaterTotal": float(wt1 + wt2),
            "annualProfitTotal": float(pt1 + pt2),
        }

        # Optional transparency list for Senaryo-1 primary candidates
        all_options = None
        if src_norm in ("s1","senaryo1","senaryo-1","scenario1","1") and primary_allowed_idx:
            try:
                opts = []
                for j in sorted(list(primary_allowed_idx)):
                    cname = crop_list[j]
                    wpd = float(W[i, j]); ppd = float(R[i, j])
                    blk = _irrig_block(cname, float(areas[i]), wpd)
                    opts.append({
                        "name": cname,
                        "area": float(areas[i]),
                        "waterPerDa": wpd,
                        "profitPerDa": ppd,
                        "waterTotal": float(wpd * float(areas[i])),
                        "profitTotal": float(ppd * float(areas[i])),
                        **blk
                    })
                opts.sort(key=lambda r: (r.get("profitPerDa",0.0) - 0.0001*r.get("waterPerDa",0.0)), reverse=True)
                all_options = opts
            except Exception:
                all_options = None

        parcels_out.append({
            "id": str(p.get("id")),
            "result": {"recommended": rec, "all_options": all_options, **parcel_annual},
        })

    return {
        "parcels": parcels_out,
        "budget": float(budget),
        "delivery_report": delivery_report,
        "totals": {"water": float(w_tot), "profit": float(p_tot)},
        "feasible": feasible,
        "iterations": int(it),
        "formula": {
            "water_m3": "Su (m³) = Alan(da) × SuYoğunluğu(m³/da) (1. sezon + 2. sezon)",
            "profit_tl": "Kâr (TL) = Alan(da) × NetKârYoğunluğu(TL/da) (1. sezon + 2. sezon)",
            "score": "Skor = α·Kâr - β·Su (bütçe aşımı cezası)",
        },
        "weights": {"alpha": float(alpha), "beta": float(beta)},
    }


def _build_two_season_recommendations(
    selected_parcels: List[Dict[str, Any]],
    year: int,
    objective: str,
    season_source: str,
    chosen_primary: np.ndarray,
    chosen_secondary: np.ndarray,
    budget_ratio: float = 1.0,
    # v26+ project options
    env_flow_ratio: float = 0.10,
    irrigation_method: Optional[str] = None,
    enforce_delivery_caps: bool = True,
    water_model: str = "calib",
    risk_mode: str = "none",
    risk_lambda: float = 0.0,
    risk_samples: int = 120,
    water_quality_filter: bool = True,
) -> Dict[str, Any]:
    """UI-friendly plan with **two seasons** (primary + secondary).

    Compared to the older '_build_two_crop_recommendations', this represents
    sequential double-cropping on the *same* parcel area within a year.

    Totals:
      water_m3 = Σ(area_da * (W_primary + W_secondary))
      profit_tl = Σ(area_da * (R_primary + R_secondary))
    """
    crop_list, W1, R1, W2, R2, MU1, MU2 = build_candidate_matrix_two_season(
        selected_parcels,
        year=year,
        season_source=season_source,
        water_model=water_model,
        risk_mode=risk_mode,
        risk_lambda=risk_lambda,
        risk_samples=risk_samples,
        water_quality_filter=water_quality_filter,
    )
    P = len(selected_parcels)
    areas = np.array([float(p.get("area_da", 0) or 0) for p in selected_parcels], dtype=float)

    # Basin budget (annual) + optional monthly delivery caps
    base_budget, month_weights, month_caps = basin_budget_and_delivery_caps(int(year), selected_parcels, env_flow_ratio=float(env_flow_ratio or 0.0))
    budget = max(1.0, float(base_budget) * float(budget_ratio or 1.0))

    # Irrigation method efficiency (damla/yağmurlama/yüzey)
    if irrigation_method:
        W = apply_irrigation_method_to_W(W, selected_parcels, irrigation_method)

    if not enforce_delivery_caps:
        month_weights, month_caps = None, None

    # Senaryo-2 orchard locks + irrigation adjustment
    locks = _compute_perennial_locks(selected_parcels, int(year), crop_list, season_source)
    lock_mask = (locks >= 0)
    irrigation_label = None
    if np.any(lock_mask):
        wmul, pmul, irrigation_label = _apply_s2_irrigation_adjustments(objective)
        W1 = W1.copy(); R1 = R1.copy(); W2 = W2.copy(); R2 = R2.copy()
        W1[lock_mask, :] *= float(wmul)
        W2[lock_mask, :] *= float(wmul)
        R1[lock_mask, :] *= float(pmul)
        R2[lock_mask, :] *= float(pmul)

    # Enforce locks on primary season
    ch1 = chosen_primary.astype(int).copy()
    ch2 = chosen_secondary.astype(int).copy()
    fallow_idx = 0
    try:
        fallow_idx = int(crop_list.index(FALLOW))
    except Exception:
        fallow_idx = 0
    if np.any(lock_mask):
        ch1[lock_mask] = locks[lock_mask]
        # Orchard / perennial parcels: keep the established main crop.
        # Do NOT propose uprooting the orchard or replacing it with a second
        # commercial crop. Secondary season stays empty/fallow so the UI can
        # focus on irrigation, timing and inter-row management guidance.
        ch2[lock_mask] = fallow_idx

    total_water = float(np.sum(areas * (W1[np.arange(P), ch1] + W2[np.arange(P), ch2])))
    total_profit = float(np.sum(areas * (R1[np.arange(P), ch1] + R2[np.arange(P), ch2])))
    feasible = bool(total_water <= budget + 1e-6)

    # Monthly delivery caps
    monthly_demand_override = _monthly_demand_from_mu(areas, MU1, MU2, ch1, ch2)
    delivery_report = compute_monthly_delivery_report(
        total_water_m3=float(total_water),
        month_weights=month_weights,
        month_caps=month_caps,
        months=12,
        monthly_demand_override=monthly_demand_override,
    )
    if delivery_report is not None and (not delivery_report.get("feasible_monthly", True)):
        feasible = False

    # --- Season labels + irrigation suggestion (data-driven, like single-season recommender) ---
    s1_rules = {}
    try:
        _p = DATA_DIR / 'scenario1_crop_calendar.json'
        if _p.exists():
            s1_rules = load_json(_p) or {}
    except Exception:
        s1_rules = {}

    crop_irrig_map = {}
    try:
        _p = DATA_DIR / 'crop_irrigation_map.json'
        if _p.exists():
            crop_irrig_map = load_json(_p) or {}
    except Exception:
        crop_irrig_map = {}

    eff_map = {'sprinkler_pivot': 0.68, 'sprinkler': 0.68, 'surface_furrow': 0.47, 'drip': 0.83, 'rainfed': 1.0}
    try:
        _im = load_enhanced_frames().get('irrigation_methods')
        if _im is not None and len(_im) > 0 and 'method' in _im.columns and 'typical_total_efficiency' in _im.columns:
            for _, rr in _im.iterrows():
                eff_map[str(rr['method']).strip()] = float(rr['typical_total_efficiency'])
    except Exception:
        pass

    def _season_label(crop: str, which: str='primary') -> str:
        rule = (s1_rules.get(crop, {}) if isinstance(s1_rules, dict) else {})
        if which == 'primary':
            return str(rule.get('primary_season') or rule.get('season') or '—')
        # secondary
        return str(rule.get('secondary_season') or '—')

    def _irrig_block(crop_name: str, area_da: float, water_per_da: float):
        info = crop_irrig_map.get(crop_name, {}) if isinstance(crop_irrig_map, dict) else {}
        cur = str(info.get('default', '')) if info else ''
        recm = str(info.get('recommended', '')) if info else ''
        if cur == '' and recm == '':
            return {'irrigationCurrent': None, 'irrigationRecommended': None, 'irrigationCurrentKey': None, 'irrigationSuggestedKey': None, 'waterSavingPct': 0.0, 'waterSavingPerDa': 0.0, 'waterSavingTotal': 0.0}
        if recm == '':
            recm = cur
        eff_cur = float(eff_map.get(cur, 1.0)) if cur else 1.0
        eff_rec = float(eff_map.get(recm, eff_cur)) if recm else eff_cur
        if eff_cur <= 0 or eff_rec <= 0:
            return {'irrigationCurrent': cur or None, 'irrigationRecommended': recm or None, 'irrigationCurrentKey': cur or None, 'irrigationSuggestedKey': recm or None, 'waterSavingPct': 0.0, 'waterSavingPerDa': 0.0, 'waterSavingTotal': 0.0}
        new_water_per_da = float(water_per_da) * (eff_cur / eff_rec)
        saving_per_da = max(0.0, float(water_per_da) - new_water_per_da)
        saving_pct = 0.0 if float(water_per_da) <= 0 else min(1.0, saving_per_da / float(water_per_da))
        return {
            'irrigationCurrent': cur or None,
            'irrigationRecommended': recm or None,
            'irrigationCurrentKey': cur or None,
            'irrigationSuggestedKey': recm or None,
            'waterSavingPct': float(saving_pct),
            'waterSavingPerDa': float(saving_per_da),
            'waterSavingTotal': float(saving_per_da * float(area_da)),
        }

    parcels_out = []
    for i, p in enumerate(selected_parcels):
        c1 = crop_list[int(ch1[i])]
        c2 = crop_list[int(ch2[i])]
        recommended = [
            {
                "name": c1,
                "season": ('Ana ürün' if str(season_source).lower() == 's1' else _season_label(c1, 'primary')),
                "area": float(areas[i]),
                "waterPerDa": float(W1[i, int(ch1[i])]),
                "waterTotal": float(areas[i]) * float(W1[i, int(ch1[i])]),
                "profitPerDa": float(R1[i, int(ch1[i])]),
                "profitTotal": float(areas[i]) * float(R1[i, int(ch1[i])]),
                **_decision_metrics_for_crop(c1, float(areas[i]), float(W1[i, int(ch1[i])]), float(R1[i, int(ch1[i])])),
                **_irrig_block(c1, float(areas[i]), float(W1[i, int(ch1[i])])),
                "reason": ("Tek ürün ana plan: seçili hedef, su bütçesi, aylık kapasite ve ticari parametreler birlikte puanlandı." if str(season_source).lower() == 's1' else "Ana ürün: iki-sezon çözümü (su bütçesi + parsel uygunluğu + ticari parametreler)")
            }
        ]
        is_locked_orchard = bool(lock_mask[i]) if np.any(lock_mask) else False
        if is_locked_orchard:
            orchard_alternatives = _orchard_interrow_alternatives(c1)
            recommended[0]["reason"] = "Mevcut bahçe ürünü korunur; kayısı/elma/armut gibi kurulmuş bahçelerde mercimek-nohut gibi tek yıllık ürüne geçiş önerilmez. İyileştirme sulama yöntemi, sulama zamanı, kısıntılı sulama ve sıra arası/örtü bitkisi yönetimi üzerinden yapılır."
            recommended[0]["season"] = recommended[0].get("season") or "Bahçe (çok yıllık)"
            recommended[0]["interrowAlternatives"] = orchard_alternatives
        if str(season_source).lower() != 's1' and (not is_locked_orchard) and str(c2).strip().upper() != FALLOW:
            recommended.append({
                "name": c2,
                "season": _season_label(c2, 'secondary'),
                "area": float(areas[i]),
                "waterPerDa": float(W2[i, int(ch2[i])]),
                "waterTotal": float(areas[i]) * float(W2[i, int(ch2[i])]),
                "profitPerDa": float(R2[i, int(ch2[i])]),
                "profitTotal": float(areas[i]) * float(R2[i, int(ch2[i])]),
                **_decision_metrics_for_crop(c2, float(areas[i]), float(W2[i, int(ch2[i])]), float(R2[i, int(ch2[i])])),
                **_irrig_block(c2, float(areas[i]), float(W2[i, int(ch2[i])])),
                "reason": "İkinci ürün: rotasyon + düşük su + kârlılık dengesi"
            })
        parcels_out.append({
            "id": p.get("id"),
            "result": {
                "parcel": {
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "village": p.get("village"),
                    "district": p.get("district"),
                    "area_da": float(p.get("area_da", 0) or 0),
                },
                "recommended": recommended,
                "irrigationLabel": irrigation_label,
                "orchardAlternative": (recommended[0].get("interrowAlternatives", [{}])[0] if (recommended and isinstance(recommended[0], dict) and recommended[0].get("interrowAlternatives")) else None),
                "orchardAlternatives": (recommended[0].get("interrowAlternatives", []) if (recommended and isinstance(recommended[0], dict)) else []),
            }
        })

    return {
        "parcels": parcels_out,
        "totals": {"water": float(total_water), "profit": float(total_profit)},
        "feasible": feasible,
        "budget": float(budget),
        "delivery_report": delivery_report,
        "formula": {
            "water_m3": "Su (m³) = Σ[Alan(da) × (SuYoğunluğu1 + SuYoğunluğu2)]",
            "profit_tl": "Kâr (TL) = Σ[Alan(da) × (NetKârYoğunluğu1 + NetKârYoğunluğu2)]",
        }
    }

def ga_optimize(selected_parcels: List[Dict[str,Any]], year: int, objective: str, pop_size: int=60, generations: int=120,
                cx_rate: float=0.7, mut_rate: float=0.08, seed: Optional[int]=None, budget_ratio: float=1.0,
                season_source: str="both", env_flow_ratio: float = 0.10, irrigation_method: Optional[str] = None, enforce_delivery_caps: bool = True) -> Dict[str,Any]:
    """GA for single-crop-per-parcel assignment under water budget."""
    if seed is not None:
        random.seed(seed); np.random.seed(seed)
    crop_list, W, R = build_candidate_matrix(selected_parcels, year=year, season_source=season_source)

    # ---- core dimensions + constraints ----
    P = len(selected_parcels)
    C = len(crop_list)
    areas = np.array([float(p.get("area_da", 0) or 0) for p in selected_parcels], dtype=float)
    parcel_ids = [str(p.get('id')) for p in selected_parcels]

    # Basin budget (annual) + optional monthly delivery caps
    base_budget, month_weights, month_caps = basin_budget_and_delivery_caps(int(year), selected_parcels, env_flow_ratio=env_flow_ratio)
    budget = max(1.0, float(base_budget) * float(budget_ratio or 1.0))
    if irrigation_method:
        W = apply_irrigation_method_to_W(W, selected_parcels, irrigation_method)
    if not enforce_delivery_caps:
        month_weights, month_caps = None, None

    # ---- Feasible crop choices per parcel (single-season GA) ----
    # Some matrices contain placeholder values (e.g., 1e9) for crops that are not
    # suitable/available on a given parcel. If GA samples those, totals explode
    # and efficiency collapses to ~0. We hard-filter those indices.
    INF_W = 1e8
    feasible_choices: List[np.ndarray] = []
    for i in range(P):
        ok = np.where((W[i, :] < INF_W) & np.isfinite(W[i, :]) & np.isfinite(R[i, :]) & (W[i, :] >= 0.0) )[0]
        if ok.size == 0:
            ok = np.array([0], dtype=int)  # fallow-only fallback
        feasible_choices.append(ok)

    # Data-driven normalization bounds keep the single-season benchmark stable.
    try:
        profit_upper_bound = 0.0
        water_upper_bound = 0.0
        for i in range(P):
            ch = feasible_choices[i]
            profit_upper_bound += float(areas[i]) * float(np.nanmax(R[i, ch]))
            water_upper_bound += float(areas[i]) * float(np.nanmax(W[i, ch]))
        if (not np.isfinite(profit_upper_bound)) or profit_upper_bound <= 0:
            profit_upper_bound = 1.0
        if (not np.isfinite(water_upper_bound)) or water_upper_bound <= 0:
            water_upper_bound = max(1.0, float(budget))
    except Exception:
        profit_upper_bound = 1.0
        water_upper_bound = max(1.0, float(budget))

    def _sanitize_ind(ind: np.ndarray) -> np.ndarray:
        for i in range(len(ind)):
            j = int(ind[i])
            if j < 0 or j >= C or (not np.isfinite(W[i, j])) or (not np.isfinite(R[i, j])) or (W[i, j] >= INF_W) or (W[i, j] < 0):
                ind[i] = int(feasible_choices[i][0])
        return ind

    if P == 0 or C == 0:
        return {
            "algorithm": "GA",
            "objective": objective,
            "year": int(year),
            "budget_ratio": float(budget_ratio or 1.0),
            "water_budget_m3": float(budget),
            "feasible": True,
            "total_water_m3": 0.0,
            "total_profit_tl": 0.0,
            "efficiency_tl_per_m3": 0.0,
            "details": [],
            "meta": {"note": "no parcels/crops", "season_source": season_source},
        }
    locks = _compute_perennial_locks(selected_parcels, year, crop_list, season_source)
    lock_mask = (locks >= 0)
    irrigation_label = None
    if np.any(lock_mask):
        wmul, pmul, irrigation_label = _apply_s2_irrigation_adjustments(objective)
        W = W.copy(); R = R.copy()
        W[lock_mask, :] = W[lock_mask, :] * float(wmul)
        R[lock_mask, :] = R[lock_mask, :] * float(pmul)
    def _enforce_locks(sol: np.ndarray) -> np.ndarray:
        if np.any(lock_mask):
            sol[lock_mask] = locks[lock_mask]
        return sol
    alpha, beta = _objective_alpha_beta(objective)

    def eval_ind(ind: np.ndarray) -> Tuple[float,float,float]:
        # ind: crop index for each parcel
        ind = _sanitize_ind(ind.copy())
        water = float(np.sum(areas * W[np.arange(len(ind)), ind]))
        profit = float(np.sum(areas * R[np.arange(len(ind)), ind]))

        # ---- Normalization (critical!) ----
        # Profit is in TL, water is in m3; their magnitudes differ by orders.
        # We normalize both so objective weights (alpha/beta) behave as intended.
        profit_ref = max(1.0, float(profit_upper_bound))
        # Use a tighter, data-driven reference so water minimization remains
        # meaningful even when the reservoir budget is very large.
        water_ref = max(1.0, float(min(budget, water_upper_bound)))
        profit_n = profit / profit_ref
        water_n = water / water_ref

        # ---- Budget penalty on normalized scale ----
        over_n = max(0.0, water_n - 1.0)
        penalty = over_n * (max(beta, 0.2) * 10.0)
        chosen_keys = [crop_list[int(j)] for j in ind]
        diversity_penalty = _diversity_score_penalty_from_keys(chosen_keys, areas, DIVERSITY_DEFAULTS) / max(1.0, profit_ref)

        # Fitness: maximize profit while minimizing water
        fitness = alpha * profit_n - beta * water_n - penalty - diversity_penalty
        return fitness, water, profit


    def rand_ind():
        # sample only from feasible crops for each parcel
        ind = np.zeros(P, dtype=int)
        for i in range(P):
            choices = feasible_choices[i]
            ind[i] = int(np.random.choice(choices))
        ind = _sanitize_ind(ind)
        return _enforce_locks(ind)

    pop = [rand_ind() for _ in range(pop_size)]
    best = None; best_fit = -1e99; best_water=0; best_profit=0

    for g in range(generations):
        fits = []
        for ind in pop:
            f,w,pf = eval_ind(ind)
            fits.append(f)
            if f > best_fit:
                best_fit, best_water, best_profit = f,w,pf
                best = ind.copy()
        fits_np = np.array(fits, dtype=float)
        # tournament selection
        def select_one():
            k = 3
            idx = np.random.randint(0, pop_size, size=k)
            best_i = idx[np.argmax(fits_np[idx])]
            return pop[best_i].copy()

        new_pop = []
        while len(new_pop) < pop_size:
            p1 = select_one(); p2 = select_one()
            # crossover
            if np.random.rand() < cx_rate:
                mask = np.random.rand(P) < 0.5
                c1 = p1.copy(); c2 = p2.copy()
                c1[mask] = p2[mask]
                c2[mask] = p1[mask]
            else:
                c1, c2 = p1, p2

            # Senaryo-2 kilitleri uygula (bahçe ürünü değişmesin)
            c1 = _enforce_locks(c1)
            c2 = _enforce_locks(c2)
            # mutation
            for c in (c1,c2):
                mut_mask = np.random.rand(P) < mut_rate
                if np.any(mut_mask):
                    # mutate each selected gene using that parcel's feasible crop pool
                    idxs = np.where(mut_mask)[0]
                    for ii in idxs:
                        c[ii] = int(np.random.choice(feasible_choices[int(ii)]))
                c = _sanitize_ind(c)
                _enforce_locks(c)
            new_pop.append(c1)
            if len(new_pop) < pop_size:
                new_pop.append(c2)
        pop = new_pop

    # Build per-parcel plan (100% area to chosen crop)
    chosen = best if best is not None else pop[0]
    chosen = _sanitize_ind(chosen.copy())
    plan = []
    total_water = 0.0; total_profit = 0.0
    for i,p in enumerate(selected_parcels):
        j = int(chosen[i])
        crop_key = crop_list[j]
        water = float(areas[i] * W[i,j])
        profit = float(areas[i] * R[i,j])
        plan.append({
            "parcelId": p["id"],
            "parcelName": p["name"],
            "chosenCrop": crop_key,
            "area_da": float(areas[i]),
            "water_m3": water,
            "profit_tl": profit
        })
        if irrigation_label is not None and bool(lock_mask[i]):
            plan[-1]["irrigation_plan"] = irrigation_label
        total_water += water
        total_profit += profit

    feasible = total_water <= budget + 1e-6
    eff = (total_profit/total_water) if total_water>0 else 0.0
    return {
        "algorithm": "GA",
        "objective": objective,
        "year": int(year),
        "budget_ratio": float(budget_ratio or 1.0),
        "water_budget_m3": float(budget),
        "feasible": bool(feasible),
        "total_water_m3": float(total_water),
        "total_profit_tl": float(total_profit),
        "efficiency_tl_per_m3": float(eff),
        "details": plan,
        "meta": {"popSize": pop_size, "generations": generations, "alpha": alpha, "beta": beta, "season_source": season_source}
    }




def _score_solution(chosen: np.ndarray, areas: np.ndarray, W: np.ndarray, R: np.ndarray, budget: float, objective: str,
                  crop_list: Optional[List[str]] = None,
                  month_weights: Optional[dict]=None, month_caps: Optional[dict]=None,
    month_use1: Optional[np.ndarray]=None,
    month_use2: Optional[np.ndarray]=None,
                  min_unique_crops: int = 1, max_share_per_crop: Optional[float] = None,
                  year: Optional[int] = None, parcel_ids: Optional[List[str]] = None) -> Tuple[float, float, float]:
    """Return (fitness, total_water, total_profit). Higher fitness is better.

    Fitness = profit_weight * profit  - water_weight * water * 500  - budget_penalty
    Budget penalty is quadratic and dominates when the solution exceeds the basin budget.
    """
    total_water = float(np.sum(areas * W[np.arange(len(areas)), chosen]))
    total_profit = float(np.sum(areas * R[np.arange(len(areas)), chosen]))

    profit_w, water_w = _objective_alpha_beta(objective)

    exceed = max(0.0, total_water - float(budget))
    penalty = (exceed / max(1.0, float(budget))) ** 2 * 1e9


    # Monthly delivery capacity penalty (approximate)
    monthly_pen = 0.0
    if month_weights and month_caps:
        for mo, w in month_weights.items():
            cap = float(month_caps.get(mo, 0) or 0)
            if cap > 0 and w > 0:
                dem = float(total_water) * float(w)
                if dem > cap:
                    monthly_pen += ((dem - cap) / max(1.0, cap)) ** 2 * 5e8

        # Diversity / portfolio penalties
    chosen_keys = []
    if crop_list is not None:
        try:
            chosen_keys = [str(crop_list[int(j)]) for j in chosen]
        except Exception:
            chosen_keys = []
    div_pen = _unique_crop_penalty(chosen_keys, int(min_unique_crops or 1)) if chosen_keys else 0.0
    share_pen = _max_share_penalty(chosen_keys, areas, max_share_per_crop) if chosen_keys else 0.0
    prev_pen = 0.0
    if year is not None and parcel_ids is not None and chosen_keys:
        prev_pen = _prev_family_penalty([str(x) for x in parcel_ids], chosen_keys, int(year))
    diversity_pen = _diversity_score_penalty_from_keys(chosen_keys, areas, DIVERSITY_DEFAULTS) if chosen_keys else 0.0

    core_score = _objective_score_value(total_profit, total_water, objective)
    fitness = core_score - penalty - monthly_pen - div_pen - share_pen - prev_pen - diversity_pen
    return float(fitness), float(total_water), float(total_profit)



def _score_solution_two_season(
    chosen_primary: np.ndarray,
    chosen_secondary: np.ndarray,
    areas: np.ndarray,
    W1: np.ndarray,
    R1: np.ndarray,
    W2: np.ndarray,
    R2: np.ndarray,
    budget: float,
    objective: str,
    crop_list: List[str],
    crop_family: Dict[str,str],
    rotation_rules: Optional[pd.DataFrame] = None,
    month_weights: Optional[dict]=None,
    month_caps: Optional[dict]=None,
    month_use1: Optional[np.ndarray]=None,
    month_use2: Optional[np.ndarray]=None,
    min_unique_crops: int = 2,
    max_share_per_crop: Optional[float] = 0.75,
    year: Optional[int] = None,
    parcel_ids: Optional[List[str]] = None,
) -> Tuple[float, float, float]:
    """Two-season objective with rotation constraints.

    - Total water/profit are summed across seasons.
    - Rotation rules:
        R1 (hard): consecutive seasons cannot be the same family (within the same year).
        R2 (soft): legumes at least once per year => small bonus.
    """
    P = int(len(areas))
    idx = np.arange(P)

    w1 = areas * W1[idx, chosen_primary]
    p1 = areas * R1[idx, chosen_primary]
    w2 = areas * W2[idx, chosen_secondary]
    p2 = areas * R2[idx, chosen_secondary]

    total_water = float(np.sum(w1) + np.sum(w2))
    total_profit = float(np.sum(p1) + np.sum(p2))

    profit_w, water_w = _objective_alpha_beta(objective)

    # --- Rotation penalties/bonuses ---
    hard_penalty = 0.0
    soft_bonus = 0.0

    fam_p = [crop_family.get(crop_list[int(j)], "other") for j in chosen_primary]
    fam_s = [crop_family.get(crop_list[int(j)], "other") for j in chosen_secondary]

    chosen_primary_keys = [crop_list[int(j)] for j in chosen_primary]
    chosen_secondary_keys = [crop_list[int(j)] for j in chosen_secondary]

    # R1: hard - no same family back-to-back
    for i in range(P):
        if fam_p[i] and fam_s[i] and fam_p[i] == fam_s[i]:
            hard_penalty += 1e10
        if chosen_primary_keys[i] == chosen_secondary_keys[i] and chosen_primary_keys[i] != FALLOW:
            hard_penalty += 1.2e10

    # R2: soft - legumes (low input, soil N benefit) at least once per year
    legume_fams = {"fabaceae", "legume", "legumes"}
    heavy_feeders = {"solanaceae", "brassicaceae", "allium", "cucurbitaceae"}
    for i in range(P):
        fp = fam_p[i]
        fs = fam_s[i]
        # stronger encouragement if the secondary crop is a legume after a heavy feeder
        if (fs in legume_fams) and (fp in heavy_feeders):
            soft_bonus += 4500.0
        elif (fp in legume_fams) or (fs in legume_fams):
            soft_bonus += 2500.0  # baseline bonus

    # Allow external rule tuning (if provided)
    if rotation_rules is not None and len(rotation_rules):
        try:
            rr = rotation_rules.copy()
            rr["rule_id"] = rr["rule_id"].astype(str)
            for _, r in rr.iterrows():
                rid = str(r.get("rule_id", "")).strip().upper()
                rtype = str(r.get("type", "")).strip().lower()
                pw = float(r.get("penalty_weight", 1.0) or 1.0)
                bw = float(r.get("bonus_weight", 1.0) or 1.0)
                from_family = str(r.get("from_family", "") or "").strip().lower()
                to_family = str(r.get("to_family", "") or "").strip().lower()
                ptype_req = str(r.get("applies_to_parcel_type", "all") or "all").strip().lower()
                same_crop_forbidden = str(r.get("same_crop_forbidden", "False")).strip().lower() in ("1", "true", "evet", "yes")

                if rid == "R1" and rtype == "hard":
                    continue  # already applied above
                if rid == "R2" and rtype == "soft":
                    continue  # already applied above

                for i in range(P):
                    parcel_type_i = None
                    if parcel_ids is not None and i < len(parcel_ids):
                        parcel_type_i = None
                    if ptype_req not in ("", "all"):
                        # parcel-type filtering is handled in candidate generation; rules without explicit parcel type still apply.
                        pass
                    fp = fam_p[i]
                    fs = fam_s[i]
                    cp = chosen_primary_keys[i]
                    cs = chosen_secondary_keys[i]
                    match = False
                    if same_crop_forbidden and cp == cs and cp != FALLOW:
                        match = True
                    elif to_family == "same_family" and fp and fs and fp == fs:
                        match = True
                    elif from_family == "heavy_feeder" and fp in heavy_feeders and fs in legume_fams and rtype == "soft":
                        soft_bonus += 3000.0 * bw
                        continue
                    elif from_family and to_family and from_family not in ("*", "heavy_feeder", "perennial_lock"):
                        match = (fp == from_family and fs == to_family)

                    if not match:
                        continue
                    if rtype == "hard":
                        hard_penalty += 1.0e10 * max(0.1, pw)
                    elif rtype == "soft":
                        soft_bonus += 2000.0 * max(0.1, bw)
        except Exception:
            pass

    # --- Fallow (NADAS) control ---
    # NADAS is always allowed as a last resort, but too much fallow usually means the model is
    # over-repairing instead of suggesting alternative low-water/low-input crops.
    try:
        fallow_idx = int(crop_list.index(FALLOW))
    except Exception:
        fallow_idx = 0

    total_area = float(np.sum(areas)) if areas is not None else 1.0
    # Count fallow separately for primary/secondary; normalize by (2 * total_area) for a two-season plan.
    fallow_area = float(np.sum(areas[chosen_primary == fallow_idx]) + np.sum(areas[chosen_secondary == fallow_idx]))
    fallow_share = fallow_area / max(1e-9, (2.0 * total_area))

    # Soft discouragement beyond a reasonable threshold; and a hard cap to prevent "all fallow" solutions.
    # We make thresholds stricter because we now have multiple low-water/low-input alternatives (legumes, cereals, aspir).
    if _normalize_objective_key(objective) in ("water_efficiency",):
        fallow_thr = 0.07
        fallow_cap = 0.22
    else:
        fallow_thr = 0.05
        fallow_cap = 0.18

    fallow_penalty = 0.0
    if fallow_share > fallow_thr:
        # quadratic growth after threshold
        fallow_penalty += ((fallow_share - fallow_thr) / max(1e-6, (1.0 - fallow_thr))) ** 2 * 4.0e9
    if fallow_share > fallow_cap:
        # effectively infeasible: make it extremely unattractive
        fallow_penalty += ((fallow_share - fallow_cap) / max(1e-6, (1.0 - fallow_cap))) ** 2 * 4.0e10

    # --- Low-input / soil-balance bonus ---
    low_input_bonus = 0.0
    for i in range(P):
        fam_p_i = fam_p[i]
        fam_s_i = fam_s[i]
        if fam_s_i in legume_fams:
            # stronger encouragement if the secondary crop is a legume after a heavy feeder
            if fam_p_i in heavy_feeders:
                low_input_bonus += 6000.0
            else:
                low_input_bonus += 3500.0
# --- Budget penalty ---
    exceed = max(0.0, total_water - float(budget))
    budget_penalty = (exceed / max(1.0, float(budget))) ** 2 * 1e9

    # Monthly delivery capacity penalty
    monthly_penalty = 0.0
    if month_caps:
        try:
            # If we have per-crop monthly irrigation matrices (FAO-56), enforce caps using the actual phenology.
            if (month_use1 is not None) and (month_use2 is not None):
                for mo_raw, cap_raw in dict(month_caps).items():
                    cap = float(cap_raw or 0.0)
                    if cap <= 0:
                        continue
                    mo = int(mo_raw)
                    dem = float(np.sum(areas * month_use1[idx, chosen_primary, mo-1]) + np.sum(areas * month_use2[idx, chosen_secondary, mo-1]))
                    if dem > cap:
                        monthly_penalty += ((dem - cap) / max(1.0, cap)) ** 2 * 1e8
            # else fall back to proportional weights
            elif month_weights:
                for mo, w in month_weights.items():
                    cap = float(month_caps.get(mo, 0) or 0)
                    if cap > 0 and w > 0:
                        dem = float(total_water) * float(w)
                        if dem > cap:
                            monthly_penalty += ((dem - cap) / max(1.0, cap)) ** 2 * 1e8
        except Exception:
            pass


        # Diversity / portfolio penalties (across both seasons)
    chosen_keys_all = []
    try:
        chosen_keys_all = [crop_list[int(j)] for j in chosen_primary] + [crop_list[int(j)] for j in chosen_secondary]
    except Exception:
        chosen_keys_all = []
    div_pen = _unique_crop_penalty(chosen_keys_all, int(min_unique_crops or 2)) if chosen_keys_all else 0.0
    chosen_keys_primary = [crop_list[int(j)] for j in chosen_primary]
    share_pen = _max_share_penalty(chosen_keys_primary, areas, max_share_per_crop) if chosen_keys_primary else 0.0
    prev_pen = 0.0
    if year is not None and parcel_ids is not None and chosen_keys_primary:
        prev_pen = _prev_family_penalty([str(x) for x in parcel_ids], chosen_keys_primary, int(year))
    diversity_pen = 0.0
    if chosen_keys_all:
        try:
            diversity_pen = _diversity_score_penalty_from_keys(
                chosen_keys_all,
                np.concatenate([areas, areas]),
                DIVERSITY_DEFAULTS,
            )
        except Exception:
            diversity_pen = 0.0


    # --- Fallow (NADAS) penalties ---
    # Use the fallow_penalty computed above (share-based with threshold + hard cap),
    # plus a targeted penalty when NADAS appears in the primary season despite having feasible alternatives.
    try:
        fallow_idx = int(crop_list.index(FALLOW))
    except Exception:
        fallow_idx = 0

    nadas_pen = float(fallow_penalty)
    primary_nadas_pen = 0.0

    # If NADAS is chosen in primary season while any non-fallow option is feasible, add a strong penalty.
    try:
        for i in range(P):
            if int(chosen_primary[i]) == int(fallow_idx):
                row = W1[i, :]
                mask = (np.arange(len(row)) != fallow_idx)
                if np.any(np.isfinite(row) & (row < 1e8) & mask):
                    primary_nadas_pen += 8e7
    except Exception:
        pass

    core_score = _objective_score_value(total_profit, total_water, objective)
    fitness = core_score - budget_penalty - monthly_penalty - hard_penalty + soft_bonus + low_input_bonus - div_pen - share_pen - prev_pen - diversity_pen - nadas_pen - primary_nadas_pen
    return float(fitness), float(total_water), float(total_profit)



def _score_components_two_season(
    sol1: np.ndarray, sol2: np.ndarray,
    areas: np.ndarray, W1: np.ndarray, R1: np.ndarray, W2: np.ndarray, R2: np.ndarray,
    budget: float, objective: str,
    crop_list: List[str], crop_family: Dict[str, str], rotation_rules: Optional[pd.DataFrame] = None,
    month_weights: Optional[dict] = None,
    month_caps: Optional[dict] = None,
    month_use1: Optional[np.ndarray] = None,
    month_use2: Optional[np.ndarray] = None,
    min_unique_crops: int = 2,
    max_share_per_crop: Optional[float] = 0.75,
    year: Optional[int] = None,
    parcel_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Farmer-facing breakdown of the fitness result."""
    fitness, total_water, total_profit = _score_solution_two_season(
        sol1, sol2, areas, W1, R1, W2, R2, budget, objective, crop_list, crop_family, rotation_rules,
        month_weights=month_weights, month_caps=month_caps,
        month_use1=month_use1, month_use2=month_use2,
        min_unique_crops=min_unique_crops, max_share_per_crop=max_share_per_crop,
        year=year, parcel_ids=parcel_ids,
    )
    comp: Dict[str, Any] = {
        "fitness": float(fitness),
        "total_water_m3": float(total_water),
        "total_profit_tl": float(total_profit),
        "budget_m3": float(budget),
        "over_budget_m3": float(max(0.0, total_water - budget)),
    }
    try:
        crops = [crop_list[int(x)] for x in list(sol1) + list(sol2)]
        comp["unique_crops_total"] = int(len(set(crops)))
    except Exception:
        pass
    try:
        total_area = float(np.sum(areas))
        if total_area > 0:
            share = {}
            for i in range(len(areas)):
                for s in (int(sol1[i]), int(sol2[i])):
                    ck = crop_list[s]
                    share[ck] = share.get(ck, 0.0) + float(areas[i])
            for k in list(share.keys()):
                share[k] = float(share[k] / (2.0 * total_area))
            top = sorted(share.items(), key=lambda x: x[1], reverse=True)[:10]
            comp["top_crop_shares"] = [{"crop": k, "share": float(v)} for k, v in top]
    except Exception:
        pass
    return comp


def ga_optimize_two_season(
    selected_parcels: List[Dict[str, Any]],
    year: int,
    objective: str,
    pop_size: int = 60,
    generations: int = 140,
    cx_rate: float = 0.7,
    mut_rate: float = 0.08,
    seed: Optional[int] = None,
    budget_ratio: float = 1.0,
    season_source: str = "both",
    env_flow_ratio: float = 0.10,
    irrigation_method: Optional[str] = None,
    enforce_delivery_caps: bool = True,
    min_unique_crops: int = 2,
    max_share_per_crop: Optional[float] = 0.75,
    water_model: str = "calib",
    risk_mode: str = "none",
    risk_lambda: float = 0.0,
    risk_samples: int = 120,
    water_quality_filter: bool = True,
) -> Dict[str, Any]:
    """Genetic Algorithm (GA) for **two-season** planning (primary + secondary crop per parcel)."""
    if seed is not None:
        random.seed(int(seed))
        np.random.seed(int(seed) % (2**32 - 1))

    crop_list, W1, R1, W2, R2, MU1, MU2 = build_candidate_matrix_two_season(
        selected_parcels, year=year, season_source=season_source,
        water_model=water_model, risk_mode=risk_mode, risk_lambda=risk_lambda, risk_samples=risk_samples,
        water_quality_filter=water_quality_filter,
    )
    P = len(selected_parcels)
    C = len(crop_list)
    areas = np.array([float(p.get("area_da", 0) or 0) for p in selected_parcels], dtype=float)
    parcel_ids = [str(p.get('id')) for p in selected_parcels]

    # Basin budget (annual) + optional monthly delivery caps
    base_budget, month_weights, month_caps = basin_budget_and_delivery_caps(int(year), selected_parcels, env_flow_ratio=env_flow_ratio)
    budget = max(1.0, float(base_budget) * float(budget_ratio or 1.0))
    if irrigation_method:
        W = apply_irrigation_method_to_W(W, selected_parcels, irrigation_method)
    if not enforce_delivery_caps:
        month_weights = {}
        month_caps = {}

    # ---- Feasibility guards (two-season GA) ----
    # Prevent sampling infeasible matrix cells (often encoded with huge water like 1e9)
    # and repair individuals to satisfy the yearly water budget.
    INF_W = 1e8
    feasible1 = []
    feasible2 = []
    for i in range(P):
        ok1 = np.where((W1[i, :] < INF_W) & np.isfinite(W1[i, :]) & np.isfinite(R1[i, :]) & (W1[i, :] >= 0.0) & (R1[i, :] >= 0.0))[0]
        ok2 = np.where((W2[i, :] < INF_W) & np.isfinite(W2[i, :]) & np.isfinite(R2[i, :]) & (W2[i, :] >= 0.0) & (R2[i, :] >= 0.0))[0]
        if ok1.size == 0:
            ok1 = np.array([0], dtype=int)
        if ok2.size == 0:
            ok2 = np.array([0], dtype=int)
        feasible1.append(ok1)
        feasible2.append(ok2)

    try:
        fallow_idx = int(crop_list.index(FALLOW))
    except Exception:
        fallow_idx = 0

    def _sanitize_pair(s1: np.ndarray, s2: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        s1 = s1.astype(int, copy=True)
        s2 = s2.astype(int, copy=True)
        for i in range(P):
            j1 = int(s1[i]); j2 = int(s2[i])
            if (j1 < 0) or (j1 >= C) or (W1[i, j1] >= INF_W) or (not np.isfinite(W1[i, j1])) or (not np.isfinite(R1[i, j1])):
                s1[i] = int(feasible1[i][0])
            if (j2 < 0) or (j2 >= C) or (W2[i, j2] >= INF_W) or (not np.isfinite(W2[i, j2])) or (not np.isfinite(R2[i, j2])):
                s2[i] = int(feasible2[i][0])
        return s1, s2

    def _total_water_pair(s1: np.ndarray, s2: np.ndarray) -> float:
        idx = np.arange(P)
        return float(np.sum(areas * W1[idx, s1]) + np.sum(areas * W2[idx, s2]))

    def _repair_budget(s1: np.ndarray, s2: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Hard repair: drop crops to FALLOW until total water fits budget."""
        s1, s2 = _sanitize_pair(s1, s2)
        for _ in range(P * 2):
            w = _total_water_pair(s1, s2)
            if w <= float(budget) * 1.0001:
                break
            contrib = areas * (W1[np.arange(P), s1] + W2[np.arange(P), s2])
            order = np.argsort(-contrib)
            changed = False
            for i in order:
                i = int(i)
                # Prefer changing secondary first (rotation crop)
                if int(s2[i]) != fallow_idx:
                    cur = int(s2[i])
                    # Prefer a low-water, different-family secondary crop (legumes first) before NADAS
                    fam = crop_family.get(crop_list[int(s1[i])], "other")
                    best = None
                    best_w = float(W2[i, cur]) if np.isfinite(W2[i, cur]) else 1e99
                    legume_fams = {"fabaceae", "legume", "legumes"}
                    # First pass: legumes
                    for j, ck in enumerate(crop_list):
                        if j == fallow_idx:
                            continue
                        if crop_family.get(ck, "other") not in legume_fams:
                            continue
                        if crop_family.get(ck, "other") == fam:
                            continue
                        wj = float(W2[i, j])
                        if (not np.isfinite(wj)) or (wj >= INF_W):
                            continue
                        if wj < best_w - 1e-9:
                            best_w = wj
                            best = j
                    # Second pass: any different family
                    if best is None:
                        for j, ck in enumerate(crop_list):
                            if j == fallow_idx:
                                continue
                            if crop_family.get(ck, "other") == fam:
                                continue
                            wj = float(W2[i, j])
                            if (not np.isfinite(wj)) or (wj >= INF_W):
                                continue
                            if wj < best_w - 1e-9:
                                best_w = wj
                                best = j
                    if best is not None:
                        s2[i] = int(best)
                    else:
                        s2[i] = fallow_idx
                    changed = True
                    break
                # Only change primary if not locked/perennial
                if (not bool(lock_mask[i])) and int(s1[i]) != fallow_idx:
                    cur = int(s1[i])
                    # Prefer switching primary to a lower-water crop before NADAS
                    best = None
                    best_w = float(W1[i, cur]) if np.isfinite(W1[i, cur]) else 1e99
                    for j, ck in enumerate(crop_list):
                        if j == fallow_idx:
                            continue
                        wj = float(W1[i, j])
                        if (not np.isfinite(wj)) or (wj >= INF_W):
                            continue
                        if wj < best_w - 1e-9:
                            best_w = wj
                            best = j
                    if best is not None:
                        s1[i] = int(best)
                    else:
                        s1[i] = fallow_idx
                    changed = True
                    break
            if changed:
                continue
            break
        return s1, s2

    if P == 0 or C == 0:
        return {"algorithm": "GA", "objective": objective, "year": int(year),
                "water_budget_m3": float(budget), "feasible": True,
                "total_water_m3": 0.0, "total_profit_tl": 0.0, "efficiency_tl_per_m3": 0.0,
                "details": [], "meta": {"note": "no parcels/crops", "season_source": season_source}}

    # Perennial locks (orchard/perennials): lock PRIMARY crop to observed/perennial crop
    locks = _compute_perennial_locks(selected_parcels, year, crop_list, season_source)
    lock_mask = (locks >= 0)

    irrigation_label = None
    if np.any(lock_mask):
        # If scenario-2 irrigation improvements are selected by the UI, adjust irrigated crops
        wmul, pmul, irrigation_label = _apply_s2_irrigation_adjustments(objective)
        W1 = W1.copy(); W2 = W2.copy(); R1 = R1.copy(); R2 = R2.copy()
        W1[lock_mask, :] *= float(wmul)
        W2[lock_mask, :] *= float(wmul)
        R1[lock_mask, :] *= float(pmul)
        R2[lock_mask, :] *= float(pmul)

    crop_family = load_crop_family_map()
    rotation_rules = load_rotation_rules()

    def _pick_secondary_diff_family(i: int, fam: str) -> int:
        # Pick a low-water secondary crop whose family differs.
        # Preference order:
        #   1) Low-input legumes (soil N benefit, typically lower fertilizer need)
        #   2) Any other different-family low-water crop
        legume_fams = {"fabaceae", "legume", "legumes"}
        best = None
        best_w = 1e99

        # 1) legumes first
        for j, ck in enumerate(crop_list):
            if crop_family.get(ck, "other") not in legume_fams:
                continue
            if crop_family.get(ck, "other") == fam:
                continue
            w = float(W2[i, j])
            if (not np.isfinite(w)) or (w >= INF_W):
                continue
            if w < best_w:
                best_w = w
                best = j

        # 2) any other different family
        if best is None:
            for j, ck in enumerate(crop_list):
                if crop_family.get(ck, "other") == fam:
                    continue
                w = float(W2[i, j])
                if (not np.isfinite(w)) or (w >= INF_W):
                    continue
                if w < best_w:
                    best_w = w
                    best = j

        if best is not None:
            return int(best)
        # fallback: first feasible secondary choice
        return int(feasible2[i][0])

    def enforce(sol1: np.ndarray, sol2: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        sol1, sol2 = _sanitize_pair(sol1, sol2)

        if np.any(lock_mask):
            sol1 = sol1.copy()
            sol1[lock_mask] = locks[lock_mask]

        # Rotation hard rule: family(primary) != family(secondary)
        for i in range(P):
            fam = crop_family.get(crop_list[int(sol1[i])], "other")
            fam2 = crop_family.get(crop_list[int(sol2[i])], "other")
            if fam == fam2:
                sol2 = sol2.copy()
                sol2[i] = _pick_secondary_diff_family(i, fam)

        # Also avoid suggesting the exact same crop in both seasons for a parcel.
        for i in range(P):
            if int(sol1[i]) == int(sol2[i]):
                sol2 = sol2.copy()
                fam = crop_family.get(crop_list[int(sol1[i])], "other")
                sol2[i] = _pick_secondary_diff_family(i, fam)

        # Hard feasibility repair: ensure yearly budget is satisfied
        sol1, sol2 = _repair_budget(sol1, sol2)
        return sol1, sol2

    def rand_pair() -> Tuple[np.ndarray, np.ndarray]:
        s1 = np.zeros(P, dtype=int)
        s2 = np.zeros(P, dtype=int)
        for i in range(P):
            s1[i] = int(np.random.choice(feasible1[i]))
            s2[i] = int(np.random.choice(feasible2[i]))
        return enforce(s1, s2)

    def eval_pair(s1: np.ndarray, s2: np.ndarray) -> Tuple[float, float, float]:
        return _score_solution_two_season(s1, s2, areas, W1, R1, W2, R2, budget, objective, crop_list, crop_family, rotation_rules,
                              month_weights=month_weights, month_caps=month_caps,
                              min_unique_crops=min_unique_crops, max_share_per_crop=max_share_per_crop,
                              year=int(year), parcel_ids=parcel_ids)

    # init population
    pop = [rand_pair() for _ in range(pop_size)]
    best_s1 = None
    best_s2 = None
    best_fit = -1e99
    best_w = 0.0
    best_p = 0.0

    for _g in range(generations):
        scored = [(eval_pair(s1, s2)[0], s1, s2) for (s1, s2) in pop]
        scored.sort(key=lambda x: x[0], reverse=True)

        if scored and scored[0][0] > best_fit:
            best_fit = float(scored[0][0])
            best_s1 = scored[0][1].copy()
            best_s2 = scored[0][2].copy()
            _, best_w, best_p = eval_pair(best_s1, best_s2)

        # elitism
        elite_n = max(2, int(0.15 * pop_size))
        next_pop = [(scored[i][1].copy(), scored[i][2].copy()) for i in range(elite_n)]

        # breeding
        while len(next_pop) < pop_size:
            # tournament selection
            def pick_parent():
                k = 4
                cand = random.sample(scored[:max(10, elite_n*2)], k=min(k, len(scored)))
                cand.sort(key=lambda x: x[0], reverse=True)
                return cand[0][1].copy(), cand[0][2].copy()

            p1a, p1b = pick_parent()
            p2a, p2b = pick_parent()

            c1a, c1b = p1a.copy(), p1b.copy()
            c2a, c2b = p2a.copy(), p2b.copy()

            if random.random() < float(cx_rate):
                cut = random.randint(1, max(1, P-1))
                c1a[:cut], c2a[:cut] = p2a[:cut], p1a[:cut]
                c1b[:cut], c2b[:cut] = p2b[:cut], p1b[:cut]

            # mutation: randomly change some parcel choices (season-specific)
            for child_a, child_b in ((c1a, c1b), (c2a, c2b)):
                if random.random() < float(mut_rate):
                    i = random.randrange(P)
                    if random.random() < 0.5:
                        child_a[i] = random.randrange(C)
                    else:
                        child_b[i] = random.randrange(C)
                sa, sb = enforce(child_a, child_b)
                next_pop.append((sa, sb))
                if len(next_pop) >= pop_size:
                    break

        pop = next_pop

    if best_s1 is None:
        best_s1, best_s2 = rand_pair()
        best_fit, best_w, best_p = eval_pair(best_s1, best_s2)

    # build plan
    plan = []
    total_water = 0.0
    total_profit = 0.0
    for i, p in enumerate(selected_parcels):
        j1 = int(best_s1[i]); j2 = int(best_s2[i])
        crop1 = crop_list[j1]; crop2 = crop_list[j2]
        water1 = float(areas[i] * W1[i, j1]); prof1 = float(areas[i] * R1[i, j1])
        water2 = float(areas[i] * W2[i, j2]); prof2 = float(areas[i] * R2[i, j2])
        item = {
            "parcelId": p["id"],
            "parcelName": p["name"],
            "area_da": float(areas[i]),
            "primary": {"crop": crop1, "water_m3": water1, "profit_tl": prof1},
            "secondary": {"crop": crop2, "water_m3": water2, "profit_tl": prof2},
        }
        if irrigation_label is not None and bool(lock_mask[i]):
            item["irrigation_plan"] = irrigation_label
        plan.append(item)
        total_water += water1 + water2
        total_profit += prof1 + prof2

    feasible = total_water <= budget + 1e-6
    effv = (total_profit / total_water) if total_water > 0 else 0.0

    return {
        "mode": "two_season",
        "algorithm": "GA",
        "objective": objective,
        "year": int(year),
        "budget_ratio": float(budget_ratio or 1.0),
        "water_budget_m3": float(budget),
        "feasible": bool(feasible),
        "total_water_m3": float(total_water),
        "total_profit_tl": float(total_profit),
        "efficiency_tl_per_m3": float(effv),
        "details": plan,
        "meta": {
            "pop_size": int(pop_size),
            "generations": int(generations),
            "cx_rate": float(cx_rate),
            "mut_rate": float(mut_rate),
            "season_source": season_source,
            "rotation_rules_applied": True,
        },
    }


def abc_optimize_two_season(
    selected_parcels: List[Dict[str, Any]],
    year: int,
    objective: str,
    food_sources: int = 40,
    cycles: int = 120,
    limit: int = 25,
    seed: Optional[int] = None,
    budget_ratio: float = 1.0,
    season_source: str = "both",
    env_flow_ratio: float = 0.10,
    irrigation_method: Optional[str] = None,
    enforce_delivery_caps: bool = True,
    min_unique_crops: int = 2,
    max_share_per_crop: Optional[float] = 0.75,
    water_model: str = "calib",
    risk_mode: str = "none",
    risk_lambda: float = 0.0,
    risk_samples: int = 120,
    water_quality_filter: bool = True,
) -> Dict[str, Any]:
    """Artificial Bee Colony (ABC) for two-season planning."""
    if seed is not None:
        random.seed(int(seed))
        np.random.seed(int(seed) % (2**32 - 1))

    crop_list, W1, R1, W2, R2, MU1, MU2 = build_candidate_matrix_two_season(
        selected_parcels, year=year, season_source=season_source,
        water_model=water_model, risk_mode=risk_mode, risk_lambda=risk_lambda, risk_samples=risk_samples,
        water_quality_filter=water_quality_filter,
    )
    P = len(selected_parcels)
    C = len(crop_list)
    areas = np.array([float(p.get("area_da", 0) or 0) for p in selected_parcels], dtype=float)
    parcel_ids = [str(p.get('id')) for p in selected_parcels]
    # Basin budget (annual) + optional monthly delivery caps
    base_budget, month_weights, month_caps = basin_budget_and_delivery_caps(int(year), selected_parcels, env_flow_ratio=env_flow_ratio)
    budget = max(1.0, float(base_budget) * float(budget_ratio or 1.0))
    if irrigation_method:
        W = apply_irrigation_method_to_W(W, selected_parcels, irrigation_method)
    if not enforce_delivery_caps:
        month_weights = {}
        month_caps = {}

    if P == 0 or C == 0:
        return {"algorithm": "ABC", "objective": objective, "year": int(year),
                "water_budget_m3": float(budget), "feasible": True,
                "total_water_m3": 0.0, "total_profit_tl": 0.0, "efficiency_tl_per_m3": 0.0,
                "details": [], "meta": {"note": "no parcels/crops", "season_source": season_source}}

    locks = _compute_perennial_locks(selected_parcels, year, crop_list, season_source)
    lock_mask = (locks >= 0)
    irrigation_label = None
    if np.any(lock_mask):
        wmul, pmul, irrigation_label = _apply_s2_irrigation_adjustments(objective)
        W1 = W1.copy(); W2 = W2.copy(); R1 = R1.copy(); R2 = R2.copy()
        W1[lock_mask, :] *= float(wmul); W2[lock_mask, :] *= float(wmul)
        R1[lock_mask, :] *= float(pmul); R2[lock_mask, :] *= float(pmul)

    crop_family = load_crop_family_map()
    rotation_rules = load_rotation_rules()

    def _pick_secondary_diff_family(i: int, fam: str) -> int:
        best = None; best_w = 1e99
        for j, ck in enumerate(crop_list):
            if crop_family.get(ck, "other") == fam:
                continue
            w = float(W2[i, j])
            if w < best_w:
                best_w = w; best = j
        return int(best if best is not None else int(np.argmin(W2[i, :])))

    def enforce(s1: np.ndarray, s2: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        s1 = s1.astype(int, copy=False); s2 = s2.astype(int, copy=False)
        if np.any(lock_mask):
            s1 = s1.copy(); s1[lock_mask] = locks[lock_mask]
        for i in range(P):
            fam1 = crop_family.get(crop_list[int(s1[i])], "other")
            fam2 = crop_family.get(crop_list[int(s2[i])], "other")
            if fam1 == fam2:
                s2 = s2.copy()
                s2[i] = _pick_secondary_diff_family(i, fam1)
        return s1, s2

    def fitness(s1: np.ndarray, s2: np.ndarray) -> float:
        return _score_solution_two_season(s1, s2, areas, W1, R1, W2, R2, budget, objective, crop_list, crop_family, rotation_rules,
                              month_weights=month_weights, month_caps=month_caps,
                              min_unique_crops=min_unique_crops, max_share_per_crop=max_share_per_crop,
                              year=int(year), parcel_ids=parcel_ids)[0]

    # init food sources
    foods = []
    for _ in range(int(food_sources)):
        a = np.random.randint(0, C, size=P, dtype=int)
        b = np.random.randint(0, C, size=P, dtype=int)
        a, b = enforce(a, b)
        foods.append((a, b))
    trial = [0 for _ in foods]

    best = foods[0]
    best_fit = fitness(best[0], best[1])

    def neighbor(sol: Tuple[np.ndarray, np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
        a, b = sol[0].copy(), sol[1].copy()
        i = random.randrange(P)
        if random.random() < 0.5:
            a[i] = random.randrange(C)
        else:
            b[i] = random.randrange(C)
        return enforce(a, b)

    for _c in range(int(cycles)):
        # employed bees
        for k in range(len(foods)):
            cand = neighbor(foods[k])
            f_cand = fitness(cand[0], cand[1])
            f_old = fitness(foods[k][0], foods[k][1])
            if f_cand > f_old:
                foods[k] = cand
                trial[k] = 0
            else:
                trial[k] += 1

        # onlooker bees: probability proportional to normalized fitness
        fits = np.array([fitness(a,b) for (a,b) in foods], dtype=float)
        fmin = float(np.min(fits))
        probs = (fits - fmin + 1e-9)
        probs = probs / float(np.sum(probs))

        for _ in range(len(foods)):
            k = int(np.random.choice(np.arange(len(foods)), p=probs))
            cand = neighbor(foods[k])
            f_cand = fitness(cand[0], cand[1])
            f_old = fitness(foods[k][0], foods[k][1])
            if f_cand > f_old:
                foods[k] = cand
                trial[k] = 0
            else:
                trial[k] += 1

        # scout bees
        for k in range(len(foods)):
            if trial[k] >= int(limit):
                a = np.random.randint(0, C, size=P, dtype=int)
                b = np.random.randint(0, C, size=P, dtype=int)
                foods[k] = enforce(a, b)
                trial[k] = 0

        # best
        for (a,b) in foods:
            f = fitness(a,b)
            if f > best_fit:
                best_fit = f
                best = (a.copy(), b.copy())

    # build output like GA
    chosen1, chosen2 = best
    # Repair: never allow missing/unsupported cells (filled with huge water) to be selected.
    # If a crop-season cell is infeasible (NaN/inf or W>=1e8), force NADAS (index 0) for that season.
    try:
        bad1 = (~np.isfinite(W1[np.arange(P), chosen1])) | (W1[np.arange(P), chosen1] >= 1e8)
        bad2 = (~np.isfinite(W2[np.arange(P), chosen2])) | (W2[np.arange(P), chosen2] >= 1e8)
        if np.any(bad1):
            chosen1 = chosen1.copy(); chosen1[bad1] = 0
        if np.any(bad2):
            chosen2 = chosen2.copy(); chosen2[bad2] = 0
    except Exception:
        pass

    plan = []
    total_water = 0.0; total_profit = 0.0
    for i,p in enumerate(selected_parcels):
        j1 = int(chosen1[i]); j2 = int(chosen2[i])
        crop1 = crop_list[j1]; crop2 = crop_list[j2]
        water1 = float(areas[i] * W1[i, j1]); prof1 = float(areas[i] * R1[i, j1])
        water2 = float(areas[i] * W2[i, j2]); prof2 = float(areas[i] * R2[i, j2])
        item = {
            "parcelId": p["id"],
            "parcelName": p["name"],
            "area_da": float(areas[i]),
            "primary": {"crop": crop1, "water_m3": water1, "profit_tl": prof1},
            "secondary": {"crop": crop2, "water_m3": water2, "profit_tl": prof2,
                 "score_components": _score_components_two_season(chosen1, chosen2, areas, W1, R1, W2, R2, budget, objective, crop_list, crop_family, rotation_rules, month_weights=month_weights, month_caps=month_caps, month_use1=MU1, month_use2=MU2, min_unique_crops=min_unique_crops, max_share_per_crop=max_share_per_crop, year=int(year), parcel_ids=parcel_ids)
                 },
        }
        if irrigation_label is not None and bool(lock_mask[i]):
            item["irrigation_plan"] = irrigation_label
        plan.append(item)
        total_water += water1 + water2
        total_profit += prof1 + prof2

    feasible = total_water <= budget + 1e-6
    effv = (total_profit / total_water) if total_water > 0 else 0.0
    return {
        "mode": "two_season",
        "algorithm": "ABC",
        "objective": objective,
        "year": int(year),
        "budget_ratio": float(budget_ratio or 1.0),
        "water_budget_m3": float(budget),
        "feasible": bool(feasible),
        "total_water_m3": float(total_water),
        "total_profit_tl": float(total_profit),
        "efficiency_tl_per_m3": float(effv),
        "details": plan,
        "meta": {"food_sources": int(food_sources), "cycles": int(cycles), "limit": int(limit),
                 "season_source": season_source, "rotation_rules_applied": True},
    }


def aco_optimize_two_season(
    selected_parcels: List[Dict[str, Any]],
    year: int,
    objective: str,
    ants: int = 40,
    iterations: int = 120,
    rho: float = 0.25,
    q: float = 1.0,
    seed: Optional[int] = None,
    budget_ratio: float = 1.0,
    season_source: str = "both",
    env_flow_ratio: float = 0.10,
    irrigation_method: Optional[str] = None,
    enforce_delivery_caps: bool = True,
    min_unique_crops: int = 2,
    max_share_per_crop: Optional[float] = 0.75,
    water_model: str = "calib",
    risk_mode: str = "none",
    risk_lambda: float = 0.0,
    risk_samples: int = 120,
    water_quality_filter: bool = True,
) -> Dict[str, Any]:
    """Ant Colony Optimization (ACO) for two-season planning."""
    if seed is not None:
        random.seed(int(seed))
        np.random.seed(int(seed) % (2**32 - 1))

    crop_list, W1, R1, W2, R2, MU1, MU2 = build_candidate_matrix_two_season(
        selected_parcels, year=year, season_source=season_source,
        water_model=water_model, risk_mode=risk_mode, risk_lambda=risk_lambda, risk_samples=risk_samples,
        water_quality_filter=water_quality_filter,
    )
    locks = _compute_perennial_locks(selected_parcels, year, crop_list, season_source)
    lock_mask = (locks >= 0)

    irrigation_label = None
    if np.any(lock_mask):
        wmul, pmul, irrigation_label = _apply_s2_irrigation_adjustments(objective)
        W1 = W1.copy(); W2 = W2.copy(); R1 = R1.copy(); R2 = R2.copy()
        W1[lock_mask, :] *= float(wmul); W2[lock_mask, :] *= float(wmul)
        R1[lock_mask, :] *= float(pmul); R2[lock_mask, :] *= float(pmul)

    P = len(selected_parcels); C = len(crop_list)
    areas = np.array([float(p.get("area_da", 0) or 0) for p in selected_parcels], dtype=float)
    parcel_ids = [str(p.get('id')) for p in selected_parcels]
    # Basin budget (annual) + optional monthly delivery caps
    base_budget, month_weights, month_caps = basin_budget_and_delivery_caps(int(year), selected_parcels, env_flow_ratio=env_flow_ratio)
    budget = max(1.0, float(base_budget) * float(budget_ratio or 1.0))
    if irrigation_method:
        W = apply_irrigation_method_to_W(W, selected_parcels, irrigation_method)
    if not enforce_delivery_caps:
        month_weights = {}
        month_caps = {}

    crop_family = load_crop_family_map()
    rotation_rules = load_rotation_rules()

    if P == 0 or C == 0:
        return {"algorithm": "ACO", "objective": objective, "year": int(year),
                "water_budget_m3": float(budget), "feasible": True,
                "total_water_m3": 0.0, "total_profit_tl": 0.0, "efficiency_tl_per_m3": 0.0,
                "details": [], "meta": {"note": "no parcels/crops", "season_source": season_source}}

    def _pick_secondary_diff_family(i: int, fam: str) -> int:
        best = None; best_w = 1e99
        for j, ck in enumerate(crop_list):
            if crop_family.get(ck, "other") == fam:
                continue
            w = float(W2[i, j])
            if w < best_w:
                best_w = w; best = j
        return int(best if best is not None else int(np.argmin(W2[i, :])))

    # heuristic: use efficiency and profit per season
    profit1 = np.maximum(0.0, R1)
    profit2 = np.maximum(0.0, R2)
    eff1 = np.divide(profit1, np.maximum(1.0, W1))
    eff2 = np.divide(profit2, np.maximum(1.0, W2))

    if objective == "water_saving":
        eta1 = np.power(1.0 / np.maximum(1.0, W1), 1.6) * np.power(np.maximum(1e-9, eff1), 0.35)
        eta2 = np.power(1.0 / np.maximum(1.0, W2), 1.6) * np.power(np.maximum(1e-9, eff2), 0.35)
    elif objective == "max_profit":
        eta1 = np.power(np.maximum(1e-9, profit1), 1.1)
        eta2 = np.power(np.maximum(1e-9, profit2), 1.1)
    else:
        eta1 = np.power(np.maximum(1e-9, eff1), 1.0) * np.power(np.maximum(1e-9, profit1), 0.2)
        eta2 = np.power(np.maximum(1e-9, eff2), 1.0) * np.power(np.maximum(1e-9, profit2), 0.2)

    tau1 = np.ones((P, C), dtype=float)
    tau2 = np.ones((P, C), dtype=float)
    alpha = 1.0
    beta = 2.0

    best_s1 = None
    best_s2 = None
    best_fit = -1e99

    for _it in range(int(iterations)):
        sols = []
        fits = []
        for _a in range(int(ants)):
            s1 = np.zeros(P, dtype=int)
            s2 = np.zeros(P, dtype=int)
            for i in range(P):
                # primary
                if bool(lock_mask[i]):
                    s1[i] = int(locks[i])
                else:
                    w = np.power(tau1[i], alpha) * np.power(eta1[i], beta)
                    sw = float(np.sum(w))
                    s1[i] = int(np.random.randint(0, C)) if (not np.isfinite(sw) or sw <= 0) else int(np.random.choice(np.arange(C), p=w/sw))

                # secondary with rotation constraint
                fam = crop_family.get(crop_list[int(s1[i])], "other")
                w2 = np.power(tau2[i], alpha) * np.power(eta2[i], beta)
                # zero out same-family options
                mask = np.array([crop_family.get(ck, "other") != fam for ck in crop_list], dtype=bool)
                w2 = w2 * mask
                sw2 = float(np.sum(w2))
                if (not np.isfinite(sw2)) or sw2 <= 0:
                    s2[i] = _pick_secondary_diff_family(i, fam)
                else:
                    s2[i] = int(np.random.choice(np.arange(C), p=w2/sw2))

            f = _score_solution_two_season(s1, s2, areas, W1, R1, W2, R2, budget, objective, crop_list, crop_family, rotation_rules,
                              month_weights=month_weights, month_caps=month_caps,
                              min_unique_crops=min_unique_crops, max_share_per_crop=max_share_per_crop,
                              year=int(year), parcel_ids=parcel_ids)[0]
            sols.append((s1, s2))
            fits.append(float(f))

        # evaporate
        tau1 *= (1.0 - float(rho))
        tau2 *= (1.0 - float(rho))

        # best of iteration
        k = int(np.argmax(fits))
        s1b, s2b = sols[k]
        fb = float(fits[k])

        if fb > best_fit:
            best_fit = fb
            best_s1 = s1b.copy()
            best_s2 = s2b.copy()

        # deposit pheromone
        fmin = float(np.min(fits))
        deposit = float(q) * max(0.0, fb - fmin + 1e-9) / 1e6
        for i in range(P):
            tau1[i, int(s1b[i])] += deposit
            tau2[i, int(s2b[i])] += deposit

        tau1 = np.clip(tau1, 1e-9, 1e9)
        tau2 = np.clip(tau2, 1e-9, 1e9)

    if best_s1 is None:
        best_s1 = np.random.randint(0, C, size=P, dtype=int)
        best_s2 = np.random.randint(0, C, size=P, dtype=int)

    # output
    # Repair: avoid infeasible cells (missing/unsupported -> W>=1e8). Force NADAS (index 0).
    try:
        b1 = (~np.isfinite(W1[np.arange(P), best_s1])) | (W1[np.arange(P), best_s1] >= 1e8)
        b2 = (~np.isfinite(W2[np.arange(P), best_s2])) | (W2[np.arange(P), best_s2] >= 1e8)
        if np.any(b1):
            best_s1 = best_s1.copy(); best_s1[b1] = 0
        if np.any(b2):
            best_s2 = best_s2.copy(); best_s2[b2] = 0
    except Exception:
        pass

    # output
    plan = []
    total_water = 0.0; total_profit = 0.0
    for i,p in enumerate(selected_parcels):
        j1 = int(best_s1[i]); j2 = int(best_s2[i])
        crop1 = crop_list[j1]; crop2 = crop_list[j2]
        water1 = float(areas[i] * W1[i, j1]); prof1 = float(areas[i] * R1[i, j1])
        water2 = float(areas[i] * W2[i, j2]); prof2 = float(areas[i] * R2[i, j2])
        item = {
            "parcelId": p["id"],
            "parcelName": p["name"],
            "area_da": float(areas[i]),
            "primary": {"crop": crop1, "water_m3": water1, "profit_tl": prof1},
            "secondary": {"crop": crop2, "water_m3": water2, "profit_tl": prof2,
                 "score_components": _score_components_two_season(best_s1, best_s2, areas, W1, R1, W2, R2, budget, objective, crop_list, crop_family, rotation_rules, month_weights=month_weights, month_caps=month_caps, month_use1=MU1, month_use2=MU2, min_unique_crops=min_unique_crops, max_share_per_crop=max_share_per_crop, year=int(year), parcel_ids=parcel_ids)
                 },
        }
        if irrigation_label is not None and bool(lock_mask[i]):
            item["irrigation_plan"] = irrigation_label
        plan.append(item)
        total_water += water1 + water2
        total_profit += prof1 + prof2

    feasible = total_water <= budget + 1e-6
    effv = (total_profit / total_water) if total_water > 0 else 0.0
    return {
        "mode": "two_season",
        "algorithm": "ACO",
        "objective": objective,
        "year": int(year),
        "budget_ratio": float(budget_ratio or 1.0),
        "water_budget_m3": float(budget),
        "feasible": bool(feasible),
        "total_water_m3": float(total_water),
        "total_profit_tl": float(total_profit),
        "efficiency_tl_per_m3": float(effv),
        "details": plan,
        "meta": {"ants": int(ants), "iterations": int(iterations), "rho": float(rho), "q": float(q),
                 "season_source": season_source, "rotation_rules_applied": True},
    }



def abc_optimize(selected_parcels: List[Dict[str, Any]], year: int, objective: str,
                 food_sources: int = 40, cycles: int = 120, limit: int = 25,
                 seed: Optional[int] = None, budget_ratio: float = 1.0, season_source: str = "both",
                 env_flow_ratio: float = 0.10, irrigation_method: Optional[str] = None, enforce_delivery_caps: bool = True,
                 min_unique_crops: int = 1, max_share_per_crop: Optional[float] = None,
                 water_model: str = "calib", risk_mode: str = "none", risk_lambda: float = 0.0,
                 risk_samples: int = 120, water_quality_filter: bool = True) -> Dict[str, Any]:
    """Artificial Bee Colony optimizer (discrete crop choice per parcel)."""
    if seed is not None:
        random.seed(int(seed))
        np.random.seed(int(seed) % (2**32 - 1))

    crop_list, W, R = build_candidate_matrix(selected_parcels, year=year, season_source=season_source)
    locks = _compute_perennial_locks(selected_parcels, year, crop_list, season_source)
    lock_mask = (locks >= 0)
    irrigation_label = None
    if np.any(lock_mask):
        wmul, pmul, irrigation_label = _apply_s2_irrigation_adjustments(objective)
        W = W.copy(); R = R.copy()
        W[lock_mask, :] = W[lock_mask, :] * float(wmul)
        R[lock_mask, :] = R[lock_mask, :] * float(pmul)

    def _enforce_locks(ind: np.ndarray) -> np.ndarray:
        if np.any(lock_mask):
            ind[lock_mask] = locks[lock_mask]
        return ind

    P = len(selected_parcels); C = len(crop_list)
    areas = np.array([float(p.get("area_da", 0) or 0) for p in selected_parcels], dtype=float)

    # Basin budget (annual) + optional monthly delivery caps
    base_budget, month_weights, month_caps = basin_budget_and_delivery_caps(int(year), selected_parcels, env_flow_ratio=env_flow_ratio)
    budget = max(1.0, float(base_budget) * float(budget_ratio or 1.0))
    if irrigation_method:
        W = apply_irrigation_method_to_W(W, selected_parcels, irrigation_method)

    if not enforce_delivery_caps:
        month_weights = {}
        month_caps = {}

    if P == 0 or C == 0:
        return {"algorithm": "ABC", "objective": objective, "year": int(year),
                "water_budget_m3": float(budget), "feasible": True,
                "total_water_m3": 0.0, "total_profit_tl": 0.0, "efficiency_tl_per_m3": 0.0,
                "details": [], "meta": {"note": "no parcels/crops"}}

    # initialize food sources
    foods = np.random.randint(0, C, size=(food_sources, P))
    if np.any(lock_mask):
        foods[:, lock_mask] = locks[lock_mask]
    trials = np.zeros(food_sources, dtype=int)

    def neighbor(sol: np.ndarray) -> np.ndarray:
        v = sol.copy()
        i = np.random.randint(0, P)  # parcel index to change
        if np.any(lock_mask) and bool(lock_mask[i]):
            return v
        v[i] = np.random.randint(0, C)
        return _enforce_locks(v)

    best_sol = foods[0].copy()
    best_fit, best_w, best_p = _score_solution(
        best_sol, areas, W, R, budget, objective,
        crop_list=crop_list, month_weights=month_weights, month_caps=month_caps,
        min_unique_crops=min_unique_crops, max_share_per_crop=max_share_per_crop,
    )

    for _ in range(cycles):
        # employed bees
        for k in range(food_sources):
            v = neighbor(foods[k])
            fit_v, _, _ = _score_solution(
                v, areas, W, R, budget, objective,
                crop_list=crop_list, month_weights=month_weights, month_caps=month_caps,
                min_unique_crops=min_unique_crops, max_share_per_crop=max_share_per_crop,
            )
            fit_k, _, _ = _score_solution(
                foods[k], areas, W, R, budget, objective,
                crop_list=crop_list, month_weights=month_weights, month_caps=month_caps,
                min_unique_crops=min_unique_crops, max_share_per_crop=max_share_per_crop,
            )
            if fit_v > fit_k:
                foods[k] = v
                trials[k] = 0
            else:
                trials[k] += 1

        # onlooker probabilities (normalize positive)
        fits = np.array([
            _score_solution(
                foods[k], areas, W, R, budget, objective,
                crop_list=crop_list, month_weights=month_weights, month_caps=month_caps,
                min_unique_crops=min_unique_crops, max_share_per_crop=max_share_per_crop,
            )[0] for k in range(food_sources)
        ], dtype=float)
        # shift to positive
        fmin = float(np.min(fits))
        probs = fits - fmin + 1e-9
        probs = probs / float(np.sum(probs))

        # onlookers count equals food_sources (common choice)
        for _o in range(food_sources):
            k = int(np.random.choice(np.arange(food_sources), p=probs))
            v = neighbor(foods[k])
            fit_v, _, _ = _score_solution(
                v, areas, W, R, budget, objective,
                crop_list=crop_list, month_weights=month_weights, month_caps=month_caps,
                min_unique_crops=min_unique_crops, max_share_per_crop=max_share_per_crop,
            )
            fit_k, _, _ = _score_solution(
                foods[k], areas, W, R, budget, objective,
                crop_list=crop_list, month_weights=month_weights, month_caps=month_caps,
                min_unique_crops=min_unique_crops, max_share_per_crop=max_share_per_crop,
            )
            if fit_v > fit_k:
                foods[k] = v
                trials[k] = 0
            else:
                trials[k] += 1

        # scouts
        for k in range(food_sources):
            if trials[k] >= limit:
                foods[k] = _enforce_locks(np.random.randint(0, C, size=P))
                trials[k] = 0

        # update best
        for k in range(food_sources):
            fit_k, w_k, p_k = _score_solution(
                foods[k], areas, W, R, budget, objective,
                crop_list=crop_list, month_weights=month_weights, month_caps=month_caps,
                min_unique_crops=min_unique_crops, max_share_per_crop=max_share_per_crop,
            )
            if fit_k > best_fit:
                best_fit, best_w, best_p = fit_k, w_k, p_k
                best_sol = foods[k].copy()

    chosen = best_sol
    plan = []
    total_water = 0.0; total_profit = 0.0
    for i, p in enumerate(selected_parcels):
        j = int(chosen[i])
        crop_key = crop_list[j]
        water = float(areas[i] * W[i, j])
        profit = float(areas[i] * R[i, j])
        plan.append({
            "parcelId": p["id"],
            "parcelName": p["name"],
            "chosenCrop": crop_key,
            "area_da": float(areas[i]),
            "water_m3": water,
            "profit_tl": profit
        })
        if irrigation_label is not None and bool(lock_mask[i]):
            plan[-1]["irrigation_plan"] = irrigation_label
        total_water += water
        total_profit += profit

    feasible = total_water <= budget + 1e-6
    eff = (total_profit / total_water) if total_water > 0 else 0.0
    return {
        "algorithm": "ABC",
        "objective": objective,
        "year": int(year),
        "budget_ratio": float(budget_ratio or 1.0),
        "water_budget_m3": float(budget),
        "feasible": bool(feasible),
        "total_water_m3": float(total_water),
        "total_profit_tl": float(total_profit),
        "efficiency_tl_per_m3": float(eff),
        "details": plan,
        "meta": {"foodSources": int(food_sources), "cycles": int(cycles), "limit": int(limit), "season_source": season_source}
    }


def aco_optimize(selected_parcels: List[Dict[str, Any]], year: int, objective: str,
                 ants: int = 40, iterations: int = 120, rho: float = 0.25, q: float = 1.0,
                 seed: Optional[int] = None, budget_ratio: float = 1.0, season_source: str = "both",
                 env_flow_ratio: float = 0.10, irrigation_method: Optional[str] = None, enforce_delivery_caps: bool = True,
                 min_unique_crops: int = 1, max_share_per_crop: Optional[float] = None) -> Dict[str, Any]:
    """Ant Colony Optimization (discrete crop choice per parcel)."""
    if seed is not None:
        random.seed(int(seed))
        np.random.seed(int(seed) % (2**32 - 1))

    crop_list, W, R = build_candidate_matrix(selected_parcels, year=year, season_source=season_source)
    locks = _compute_perennial_locks(selected_parcels, year, crop_list, season_source)
    lock_mask = (locks >= 0)
    irrigation_label = None
    if np.any(lock_mask):
        wmul, pmul, irrigation_label = _apply_s2_irrigation_adjustments(objective)
        W = W.copy(); R = R.copy()
        W[lock_mask, :] = W[lock_mask, :] * float(wmul)
        R[lock_mask, :] = R[lock_mask, :] * float(pmul)

    P = len(selected_parcels); C = len(crop_list)
    areas = np.array([float(p.get("area_da", 0) or 0) for p in selected_parcels], dtype=float)

    # Basin budget (annual) + optional monthly delivery caps
    base_budget, month_weights, month_caps = basin_budget_and_delivery_caps(int(year), selected_parcels, env_flow_ratio=env_flow_ratio)
    budget = max(1.0, float(base_budget) * float(budget_ratio or 1.0))
    if irrigation_method:
        W = apply_irrigation_method_to_W(W, selected_parcels, irrigation_method)

    if not enforce_delivery_caps:
        month_weights = {}
        month_caps = {}

    if P == 0 or C == 0:
        return {"algorithm": "ACO", "objective": objective, "year": int(year),
                "water_budget_m3": float(budget), "feasible": True,
                "total_water_m3": 0.0, "total_profit_tl": 0.0, "efficiency_tl_per_m3": 0.0,
                "details": [], "meta": {"note": "no parcels/crops"}}

    # heuristic matrix eta: prefer higher profit and/or efficiency
    profit = np.maximum(0.0, R)
    eff = np.divide(profit, np.maximum(1.0, W))
    if objective == "water_saving":
        eta = np.power(1.0 / np.maximum(1.0, W), 1.6) * np.power(np.maximum(1e-9, eff), 0.35)
    elif objective == "max_profit":
        eta = np.power(np.maximum(1e-9, profit), 1.1)
    else:
        eta = np.power(np.maximum(1e-9, eff), 1.0) * np.power(np.maximum(1e-9, profit), 0.2)

    tau = np.ones((P, C), dtype=float)  # pheromone
    alpha = 1.0  # pheromone influence
    beta = 2.0   # heuristic influence

    best_sol = None
    best_fit = -1e30
    best_w = 0.0
    best_p = 0.0

    for _it in range(iterations):
        sols = []
        fits = []
        for _a in range(ants):
            chosen = np.zeros(P, dtype=int)
            for i in range(P):
                if np.any(lock_mask) and bool(lock_mask[i]):
                    chosen[i] = int(locks[i])
                    continue
                weights = np.power(tau[i], alpha) * np.power(eta[i], beta)
                s = float(np.sum(weights))
                if not np.isfinite(s) or s <= 0:
                    chosen[i] = int(np.random.randint(0, C))
                else:
                    probs = weights / s
                    chosen[i] = int(np.random.choice(np.arange(C), p=probs))
            fit, tw, tp = _score_solution(
                chosen, areas, W, R, budget, objective,
                crop_list=crop_list, month_weights=month_weights, month_caps=month_caps,
                min_unique_crops=min_unique_crops, max_share_per_crop=max_share_per_crop,
            )
            sols.append(chosen)
            fits.append((fit, tw, tp))

        # evaporation
        tau *= (1.0 - float(rho))

        # deposit pheromone from best ant of this iteration
        idx = int(np.argmax([f[0] for f in fits]))
        fit_i, tw_i, tp_i = fits[idx]
        sol_i = sols[idx]

        if fit_i > best_fit:
            best_fit, best_w, best_p = fit_i, tw_i, tp_i
            best_sol = sol_i.copy()

        # deposit: better fitness -> more pheromone
        deposit = float(q) * max(0.0, fit_i - min(f[0] for f in fits) + 1e-9) / 1e6
        for i in range(P):
            tau[i, int(sol_i[i])] += deposit

        # numerical stability
        tau = np.clip(tau, 1e-9, 1e9)

    chosen = best_sol if best_sol is not None else np.random.randint(0, C, size=P)
    plan = []
    total_water = 0.0; total_profit = 0.0
    for i, p in enumerate(selected_parcels):
        j = int(chosen[i])
        crop_key = crop_list[j]
        water = float(areas[i] * W[i, j])
        profit = float(areas[i] * R[i, j])
        plan.append({
            "parcelId": p["id"],
            "parcelName": p["name"],
            "chosenCrop": crop_key,
            "area_da": float(areas[i]),
            "water_m3": water,
            "profit_tl": profit
        })
        if irrigation_label is not None and bool(lock_mask[i]):
            plan[-1]["irrigation_plan"] = irrigation_label
        total_water += water
        total_profit += profit

    feasible = total_water <= budget + 1e-6
    effv = (total_profit / total_water) if total_water > 0 else 0.0
    return {
        "algorithm": "ACO",
        "objective": objective,
        "year": int(year),
        "budget_ratio": float(budget_ratio or 1.0),
        "water_budget_m3": float(budget),
        "feasible": bool(feasible),
        "total_water_m3": float(total_water),
        "total_profit_tl": float(total_profit),
        "efficiency_tl_per_m3": float(effv),
        "details": plan,
        "meta": {"ants": int(ants), "iterations": int(iterations), "rho": float(rho), "season_source": season_source}
    }







def load_matrix_candidates() -> pd.DataFrame:
    key = "matrix_candidates_2024"
    if key in _cache:
        return _cache[key]
    p = DATA_DIR / "excel_derived" / "combined_parcel_candidate_matrix_2024.csv"
    if not p.exists():
        _cache[key] = pd.DataFrame()
        return _cache[key]
    df = pd.read_csv(p)

    # normalize key columns
    if "candidate_crop" not in df.columns:
        if "crop" in df.columns:
            df["candidate_crop"] = df["crop"]
        else:
            df["candidate_crop"] = ""
    if "candidate_crop_id" not in df.columns:
        df["candidate_crop_id"] = df["candidate_crop"]

    for col in ["parcel_id", "candidate_crop", "candidate_crop_id", "current_crop", "village", "district"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip() if col != "parcel_id" else df[col].astype(str).map(normalize_parcel_id)

    for col in [
        "area_da","water_m3_da","net_water_m3_da","water_m3_total","net_water_m3_total",
        "profit_tl_da","profit_tl_total","current_quota_m3","yield_ton_da","production_ton",
        "quota_equal_village_equal_parcel_m3","quota_area_fair_per_da_m3",
        "quota_current_demand_reference_m3","quota_hybrid_area70_current30_m3"
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    if "is_feasible_under_current_quota" in df.columns:
        df["is_feasible_under_current_quota"] = df["is_feasible_under_current_quota"].apply(lambda v: 1 if safe_int(v, 0) == 1 else 0)
    else:
        if "current_quota_m3" in df.columns and "water_m3_total" in df.columns:
            df["is_feasible_under_current_quota"] = (df["water_m3_total"] <= df["current_quota_m3"] + 1e-9).astype(int)
        else:
            df["is_feasible_under_current_quota"] = 0

    _cache[key] = df
    return _cache[key]


def _matrix_objective_from_scenario(scenario: str) -> str:
    s = str(scenario or "").strip().lower()
    if s in ("current", "mevcut"):
        return "current"
    if s in ("su_tasarruf", "su tasarruf", "water_saving", "tasarruf"):
        return "water_saving"
    if s in ("water_efficiency", "su_verimliligi", "su verimliligi", "etkin_su", "etkin su", "su_etkin", "su etkin", "balanced", "denge", "onerilen", "recommended"):
        return "water_efficiency"
    if s in ("maks_kar", "maks kar", "max_profit", "kar", "kâr"):
        return "max_profit"
    return "water_efficiency"





def _normalize_allocation_model(model: Any) -> str:
    """Normalize water-allocation model names used by UI/API.

    v42 default is dekar/area fairness: every parcel receives the same m³/da right.
    Equal-village is retained as a comparison scenario, not the default planning rule.
    """
    m = str(model or "").strip().lower()
    m = m.replace("ı", "i").replace("ğ", "g").replace("ü", "u").replace("ş", "s").replace("ö", "o").replace("ç", "c")
    m = m.replace("-", "_").replace(" ", "_")
    if not m or m in ("default", "area", "alan", "dekar", "da", "adil", "area_fair", "dekar_bazli", "dekar_bazli_adil", "area_weighted", "area_weighted_per_da", "area_fair_per_da"):
        return "area_fair_per_da"
    if m in ("equal", "equal_village", "equal_village_equal_parcel", "esit", "esit_koy", "esit_koy_esit_parsel", "idari_esitlik"):
        return "equal_village_equal_parcel"
    if m in ("current", "current_demand", "mevcut", "mevcut_talep", "current_demand_reference"):
        return "current_demand_reference"
    if m in ("hybrid", "karma", "area70_current30", "hybrid_area70_current30", "alan70_mevcut30"):
        return "hybrid_area70_current30"
    return "area_fair_per_da"


def _quota_column_for_allocation_model(model: Any) -> str:
    m = _normalize_allocation_model(model)
    return {
        "area_fair_per_da": "quota_area_fair_per_da_m3",
        "equal_village_equal_parcel": "quota_equal_village_equal_parcel_m3",
        "current_demand_reference": "quota_current_demand_reference_m3",
        "hybrid_area70_current30": "quota_hybrid_area70_current30_m3",
    }.get(m, "quota_area_fair_per_da_m3")


def _allocation_model_label(model: Any) -> str:
    m = _normalize_allocation_model(model)
    return {
        "area_fair_per_da": "Dekar bazlı adil kota: toplam mevcut su / toplam alan; her parsel alanı kadar su hakkı alır.",
        "equal_village_equal_parcel": "Eşit köy + eşit parsel kotası: her köye aynı su, köy içinde her parsele aynı kota.",
        "current_demand_reference": "Mevcut talep referansı: her parselin mevcut ürün desenindeki su tüketimi kadar kota.",
        "hybrid_area70_current30": "Karma kota: %70 alan bazlı adil kota + %30 mevcut talep referansı.",
    }.get(m, "Dekar bazlı adil kota")

def _matrix_build_problem(selected_parcels: List[Dict[str, Any]], scenario: str,
                          water_budget_ratio: float, year: Optional[int]=None,
                          options: Optional[Dict[str, Any]]=None) -> Optional[Dict[str, Any]]:
    df = load_matrix_candidates()
    if df is None or df.empty:
        return None
    all_matrix_df = df.copy()

    sel_ids = [normalize_parcel_id(p.get("id")) for p in (selected_parcels or []) if str(p.get("id", "")).strip()]
    if sel_ids:
        df = df[df["parcel_id"].isin(sel_ids)].copy()
    if df.empty:
        return None

    objective = _matrix_objective_from_scenario(scenario)
    y = int(year) if year is not None else 2024
    ratio = max(0.0, float(water_budget_ratio or 1.0))
    opts = options or {}
    crop_category_mode = normalize_crop_category_mode(opts.get("cropCategoryMode") or opts.get("crop_category_mode") or "mixed")
    allocation_model = _normalize_allocation_model(opts.get("allocationModel") or opts.get("waterAllocationModel") or opts.get("quotaModel") or "area_fair_per_da")
    quota_col = _quota_column_for_allocation_model(allocation_model)
    if quota_col not in df.columns:
        quota_col = "current_quota_m3"
    parcel_info_map = {str(p.get("id")): p for p in (selected_parcels or []) if str(p.get("id", "")).strip()}

    quota_df = df[["parcel_id", quota_col]].drop_duplicates(subset=["parcel_id"]).copy()
    quota_df["current_quota_m3"] = pd.to_numeric(quota_df[quota_col], errors="coerce").fillna(0.0) * ratio
    quota_map = quota_df.set_index("parcel_id")["current_quota_m3"].to_dict()
    budget = float(quota_df["current_quota_m3"].sum())

    parcels = []
    total_area = 0.0
    profit_upper = 0.0
    water_lower = 0.0
    eff_upper = 0.0

    def _safe_series(g: pd.DataFrame, col: str) -> pd.Series:
        if col in g.columns:
            return pd.to_numeric(g[col], errors="coerce").fillna(0.0)
        return pd.Series([0.0] * len(g), index=g.index)

    def _norm_series(s: pd.Series) -> pd.Series:
        s = pd.to_numeric(s, errors="coerce").fillna(0.0)
        lo = float(s.min()) if len(s) else 0.0
        hi = float(s.max()) if len(s) else 0.0
        if (hi - lo) < 1e-9:
            return pd.Series([1.0] * len(s), index=s.index)
        return (s - lo) / (hi - lo)

    def _augment_annual_regional_candidates(g: pd.DataFrame, pid: str, parcel_info: Dict[str, Any], parcel_type: str, current_crop: str) -> pd.DataFrame:
        """Expand annual field/vegetable choices from the full five-village matrix.

        The matrix file stores real crop observations per parcel. Some parcels do not
        contain every annual crop seen in the five villages, so limiting candidates to
        selected-parcel rows makes recommendations repeat the same narrow set. This
        augmentation clones regional annual crop intensities onto the selected parcel
        area/quota, then the normal compatibility, quota and ranking logic evaluates
        them for that parcel.
        """
        try:
            if g is None or g.empty or all_matrix_df is None or all_matrix_df.empty:
                return g
            current_canon = canonical_crop_key(current_crop)
            perennial_flag = str((parcel_info or {}).get("cok_yillik_kilit", "") or "").strip().lower()
            orchard_locked = bool(
                str(parcel_type or "").strip().lower() == "orchard"
                or perennial_flag.startswith("e")
                or perennial_flag.startswith("y")
                or (current_canon in PERENNIAL_CROPS)
            )
            if orchard_locked:
                return g

            area0 = float(pd.to_numeric(g.get("area_da", pd.Series([0.0])).iloc[0], errors="coerce") or 0.0)
            if area0 <= 0:
                return g
            existing = set(g["candidate_crop"].astype(str).map(canonical_crop_key).tolist())
            base = g.iloc[0].copy()
            additions = []

            region = all_matrix_df.copy()
            region["_cand_canon_tmp"] = region["candidate_crop"].astype(str).map(canonical_crop_key)
            for cand_canon, grp in region.groupby("_cand_canon_tmp", sort=False):
                if not cand_canon or cand_canon in existing or cand_canon in PERENNIAL_CROPS or cand_canon == FALLOW:
                    continue
                sample_name = str(grp["candidate_crop"].dropna().astype(str).iloc[0] if len(grp) else cand_canon).strip()
                if not is_annual_field_vegetable_candidate(sample_name):
                    continue
                allowed, _rule = candidate_allowed_for_parcel(parcel_type, current_crop, sample_name)
                if not allowed:
                    continue

                w_vals = pd.to_numeric(grp.get("water_m3_da", pd.Series(dtype=float)), errors="coerce").dropna()
                p_vals = pd.to_numeric(grp.get("profit_tl_da", pd.Series(dtype=float)), errors="coerce").dropna()
                if w_vals.empty or p_vals.empty:
                    continue
                water_da0 = float(w_vals.median())
                profit_da0 = float(p_vals.median())
                if water_da0 < 0 or profit_da0 <= 0:
                    continue

                row = base.copy()
                row["parcel_id"] = str(pid)
                row["candidate_crop"] = sample_name
                row["candidate_crop_id"] = cand_canon
                row["candidate_crop_norm"] = cand_canon
                row["current_crop"] = current_crop
                row["area_da"] = area0
                row["water_m3_da"] = water_da0
                row["net_water_m3_da"] = water_da0
                row["water_m3_total"] = water_da0 * area0
                row["net_water_m3_total"] = water_da0 * area0
                row["profit_tl_da"] = profit_da0
                row["profit_tl_total"] = profit_da0 * area0
                if "yield_ton_da" in row.index:
                    row["yield_ton_da"] = float(pd.to_numeric(grp.get("yield_ton_da", pd.Series([0.0])), errors="coerce").dropna().median() if "yield_ton_da" in grp.columns and not pd.to_numeric(grp.get("yield_ton_da"), errors="coerce").dropna().empty else 0.0)
                if "production_ton" in row.index:
                    row["production_ton"] = float(row.get("yield_ton_da", 0.0) or 0.0) * area0
                row["source_workbook"] = str(row.get("source_workbook", "") or "") + " | regional_5_village_candidate"
                row["_candidate_source_type"] = "regional_5_village_crop"
                row["_candidate_village_count"] = int(grp["village"].astype(str).str.strip().replace("", np.nan).dropna().nunique()) if "village" in grp.columns else 0
                additions.append(row)
                existing.add(cand_canon)

            if additions:
                g = pd.concat([g, pd.DataFrame(additions)], ignore_index=True)
        except Exception:
            return g
        return g

    for pid, g in df.groupby("parcel_id", sort=True):
        g = g.copy()
        parcel_info = parcel_info_map.get(str(pid), {})
        parcel_type = str((parcel_info or {}).get("parcel_type", "") or "").strip().lower()
        quota = float(quota_map.get(pid, 0.0))
        current_crop_for_aug = str((parcel_info or {}).get("current_crop") or g["current_crop"].iloc[0] or "").strip()
        g = _augment_annual_regional_candidates(g, str(pid), parcel_info, parcel_type, current_crop_for_aug)

        area = _safe_series(g, "area_da")
        water_da = _safe_series(g, "water_m3_da")
        profit_da = _safe_series(g, "profit_tl_da")
        yld_ton_da = _safe_series(g, "yield_ton_da")

        feas_area = []
        full_feasible = []
        for a, w in zip(area.tolist(), water_da.tolist()):
            a = max(0.0, float(a or 0.0))
            w = max(0.0, float(w or 0.0))
            if a <= 0 or quota <= 0:
                feas_area.append(0.0); full_feasible.append(0); continue
            if w <= 0:
                feas_area.append(a); full_feasible.append(1); continue
            max_area = min(a, quota / w)
            feas_area.append(max_area)
            full_feasible.append(1 if (w * a) <= quota + 1e-9 else 0)

        g["_quota_m3"] = quota
        g["_feasible_area_da"] = feas_area
        g["_coverage_pct"] = np.where(area > 0, 100.0 * g["_feasible_area_da"] / area, 0.0)
        g["_effective_water_m3"] = water_da * g["_feasible_area_da"]
        g["_effective_profit_tl"] = profit_da * g["_feasible_area_da"]
        g["_effective_production_ton"] = yld_ton_da * g["_feasible_area_da"]
        g["_tl_per_m3"] = np.where(g["_effective_water_m3"] > 0, g["_effective_profit_tl"] / g["_effective_water_m3"], 0.0)
        g["_quota_adjusted"] = (pd.Series(full_feasible, index=g.index) == 0).astype(int)
        g["_full_feasible"] = full_feasible

        current_crop = str((parcel_info or {}).get("current_crop") or g["current_crop"].iloc[0] or "").strip()
        current_crop_canon = canonical_crop_key(current_crop)
        current_category = annual_crop_category(current_crop)

        # transparent agronomic compatibility bundle (based only on available project data)
        compat_scores = []
        compat_seasons = []
        compat_summaries = []
        compat_reasons = []
        compat_cautions = []
        peak_col = g["peak_month"] if "peak_month" in g.columns else pd.Series([""] * len(g), index=g.index)
        for (_idx, r_row), feas_a, w_da, irr_txt, peak_val in zip(g.iterrows(), feas_area, water_da.tolist(), g.get("irrigation_text", pd.Series([""]*len(g), index=g.index)).tolist(), peak_col.tolist()):
            info = _agronomic_reason_bundle(
                current_crop=current_crop,
                candidate_crop=str(r_row.get("candidate_crop", "") or ""),
                parcel_type=parcel_type,
                lcc_text=parcel_info.get("soil", {}).get("class", "") or parcel_info.get("lcc", "") or r_row.get("land_capability_class", "") or r_row.get("soil_text", ""),
                quota_m3=quota,
                area_da=float(r_row.get("area_da", 0.0) or 0.0),
                water_m3_da=float(w_da or 0.0),
                feasible_area_da=float(feas_a or 0.0),
                irrigation_text=str(irr_txt or ""),
                peak_month=str(peak_val or ""),
            )
            compat_scores.append(float(info.get("compatibility_score", 0.0) or 0.0))
            compat_seasons.append(str(info.get("season_label", "") or ""))
            compat_summaries.append(str(info.get("summary", "") or ""))
            compat_reasons.append(list(info.get("reasons", []) or []))
            compat_cautions.append(list(info.get("cautions", []) or []))
        g["_compat_score"] = compat_scores
        g["_season_label"] = compat_seasons
        g["_compat_summary"] = compat_summaries
        g["_compat_reasons"] = compat_reasons
        g["_compat_cautions"] = compat_cautions
        g["_crop_category"] = g["candidate_crop"].astype(str).apply(annual_crop_category)
        g["_category_fit"] = g["_crop_category"].apply(lambda c: annual_category_fit_score(c, crop_category_mode, current_category))

        # local utility guides all algorithms, while the final choice remains a global portfolio search
        cov_n = _norm_series(g["_coverage_pct"])
        prof_n = _norm_series(g["_effective_profit_tl"])
        eff_n = _norm_series(g["_tl_per_m3"])
        water_low_n = 1.0 - _norm_series(g["_effective_water_m3"])
        compat_n = _norm_series(g["_compat_score"])
        category_n = pd.to_numeric(g["_category_fit"], errors="coerce").fillna(0.0).clip(0.0, 1.0)

        if objective == "water_saving":
            g["_local_utility"] = 0.44 * water_low_n + 0.14 * eff_n + 0.10 * compat_n + 0.08 * cov_n + 0.08 * prof_n + 0.16 * category_n
        elif objective == "water_efficiency":
            g["_local_utility"] = 0.30 * water_low_n + 0.18 * cov_n + 0.18 * eff_n + 0.12 * prof_n + 0.10 * compat_n + 0.12 * category_n
        elif objective == "max_profit":
            g["_local_utility"] = 0.42 * prof_n + 0.16 * cov_n + 0.08 * eff_n + 0.08 * water_low_n + 0.12 * compat_n + 0.14 * category_n
        else:
            g["_local_utility"] = 0.28 * prof_n + 0.20 * water_low_n + 0.16 * cov_n + 0.14 * eff_n + 0.10 * compat_n + 0.12 * category_n

        # Strongly discourage NADAS when any non-fallow option is agronomically/economically feasible.
        try:
            cand_norm_tmp = g["candidate_crop"].astype(str).map(canonical_crop_key)
            has_viable_non_fallow = bool(((cand_norm_tmp != FALLOW) & (g["_feasible_area_da"] > 0.0) & (g["_effective_profit_tl"] > 0.0)).any())
            if has_viable_non_fallow:
                fallow_mask = (cand_norm_tmp == FALLOW)
                if fallow_mask.any():
                    g.loc[fallow_mask, "_local_utility"] = g.loc[fallow_mask, "_local_utility"] - 100.0
        except Exception:
            pass

        perennial_flag = str((parcel_info or {}).get("cok_yillik_kilit", "") or "").strip().lower()
        orchard_locked = bool(
            parcel_type == "orchard"
            or perennial_flag.startswith("e")
            or perennial_flag.startswith("y")
            or (current_crop_canon in PERENNIAL_CROPS)
        )
        cand_norm_col = "candidate_crop_norm" if "candidate_crop_norm" in g.columns else None
        if cand_norm_col:
            cand_norm = g[cand_norm_col].astype(str).map(canonical_crop_key)
        else:
            cand_norm = g["candidate_crop"].astype(str).map(canonical_crop_key)
        g["__cand_norm"] = cand_norm

        locked = False
        lock_kind = ""
        if objective == "current" and current_crop_canon:
            cur_pool = g[g["__cand_norm"] == current_crop_canon]
            if not cur_pool.empty:
                g = cur_pool.copy()
                locked = True
                lock_kind = "current"
        elif orchard_locked and current_crop_canon:
            cur_pool = g[g["__cand_norm"] == current_crop_canon]
            if not cur_pool.empty:
                g = cur_pool.copy()
                if current_crop:
                    g["candidate_crop"] = current_crop
                locked = True
                lock_kind = "orchard"
            else:
                # If spelling differs between source files, synthesize a locked option from the
                # current perennial crop so the orchard is never switched to a different main crop.
                base_row = g.iloc[[0]].copy()
                row = base_row.iloc[0].copy()
                row["candidate_crop"] = current_crop
                row["candidate_crop_id"] = current_crop_canon
                row["candidate_crop_norm"] = current_crop_canon
                row["__cand_norm"] = current_crop_canon
                row["current_crop"] = current_crop
                area0 = max(0.0, float(row.get("area_da", 0.0) or 0.0))
                # try catalog first, then fall back to parcel baseline intensities
                cat = load_crop_catalog().get(current_crop_canon, {}) if 'load_crop_catalog' in globals() else {}
                water_da0 = float(cat.get("water_per_da", cat.get("waterPerDa", 0.0)) or 0.0)
                profit_da0 = float(cat.get("profit_per_da", cat.get("profitPerDa", 0.0)) or 0.0)
                if water_da0 <= 0:
                    water_da0 = float(row.get("water_m3_da", 0.0) or 320.0)
                if profit_da0 <= 0:
                    profit_da0 = float(row.get("profit_tl_da", 0.0) or 9000.0)
                feas_area0 = min(area0, (quota / water_da0) if water_da0 > 0 else area0)
                row["water_m3_da"] = water_da0
                row["profit_tl_da"] = profit_da0
                row["_feasible_area_da"] = feas_area0
                row["_coverage_pct"] = (100.0 * feas_area0 / area0) if area0 > 0 else 0.0
                row["_effective_water_m3"] = water_da0 * feas_area0
                row["_effective_profit_tl"] = profit_da0 * feas_area0
                row["_effective_production_ton"] = 0.0
                row["_tl_per_m3"] = (row["_effective_profit_tl"] / row["_effective_water_m3"]) if row["_effective_water_m3"] > 0 else 0.0
                row["_quota_adjusted"] = int(feas_area0 + 1e-9 < area0)
                row["_full_feasible"] = int(feas_area0 + 1e-9 >= area0)
                row["_local_utility"] = 1.0
                g = pd.DataFrame([row])
                locked = True
                lock_kind = "orchard"

        if not locked:
            # Hard agronomic filter: prevent normal annual planning from suggesting
            # orchard/perennial installation on field/vegetable parcels.  This keeps
            # outputs defendable for ziraat review (tarla ≠ bahçe dönüşümü).
            try:
                allow_mask = g["candidate_crop"].astype(str).apply(
                    lambda c: candidate_allowed_for_parcel(parcel_type, current_crop, c)[0]
                    and is_annual_field_vegetable_candidate(c)
                )
                if bool(allow_mask.any()):
                    dropped_count = int((~allow_mask).sum())
                    if dropped_count > 0:
                        g = g[allow_mask].copy()
                        g["_compat_cautions"] = g["_compat_cautions"].apply(lambda xs: list(xs or []) + [f"{dropped_count} uyumsuz bahçe/çok yıllık aday normal senaryodan elendi."])
            except Exception:
                pass

            try:
                hard_modes = {"field_cereal", "forage", "legume", "vegetable", "industrial_oil", "orchard"}
                if crop_category_mode in hard_modes:
                    exact_mask = g["_crop_category"].astype(str) == crop_category_mode
                    cur_mask = g["candidate_crop"].astype(str).map(canonical_crop_key) == current_crop_canon
                    if bool(exact_mask.any()):
                        g = g[exact_mask | (cur_mask & (crop_category_mode == "orchard"))].copy()
                    else:
                        cur_only = g[cur_mask].copy()
                        if not cur_only.empty:
                            g = cur_only
                        g["_compat_cautions"] = g["_compat_cautions"].apply(lambda xs: list(xs or []) + ["Seçilen ürün grubunda bu parsel için güvenilir aday bulunamadı; kategori dışı ürünler ana öneri yapılmadı."])
                        g["_local_utility"] = -10.0
                elif crop_category_mode != "mixed":
                    cur_mask = g["candidate_crop"].astype(str).map(canonical_crop_key) == current_crop_canon
                    exact_mask = g["_crop_category"].astype(str) == current_category
                    if bool(exact_mask.any()):
                        g = g[exact_mask | cur_mask].copy()
                        g["_category_fit"] = 1.0
                    else:
                        strong_mask = pd.to_numeric(g["_category_fit"], errors="coerce").fillna(0.0) >= 0.70
                        near_mask = pd.to_numeric(g["_category_fit"], errors="coerce").fillna(0.0) >= 0.40
                        if int(strong_mask.sum()) >= min(4, max(1, len(g))):
                            g = g[strong_mask | cur_mask].copy()
                        elif int(near_mask.sum()) >= 3:
                            g = g[near_mask | cur_mask].copy()
                    if g.empty:
                        g = pd.DataFrame()
            except Exception:
                pass

            # keep a compact but varied candidate pool so algorithms can produce distinct patterns
            keep = []
            keep.extend(list(g.sort_values(["_local_utility", "_effective_profit_tl"], ascending=[False, False]).index[:10]))
            keep.extend(list(g.sort_values(["_effective_profit_tl", "_coverage_pct"], ascending=[False, False]).index[:4]))
            keep.extend(list(g.sort_values(["_effective_water_m3", "_tl_per_m3"], ascending=[True, False]).index[:4]))
            keep.extend(list(g.sort_values(["_coverage_pct", "_effective_profit_tl"], ascending=[False, False]).index[:4]))
            if current_crop:
                cur_pool = g[g["candidate_crop"].astype(str).map(canonical_crop_key) == current_crop_canon]
                if not cur_pool.empty:
                    keep.append(cur_pool.index[0])
            # dedupe while keeping order
            seen = set()
            keep2 = []
            for ix in keep:
                if ix in seen:
                    continue
                seen.add(ix)
                keep2.append(ix)
            g = g.loc[keep2].copy()

        if g.empty:
            continue

        options = []
        for _, r in g.iterrows():
            source_type = str(r.get("_candidate_source_type", "") or "").strip()
            if (not source_type) or source_type.lower() == "nan":
                source_type = "local_village_crop"
            options.append({
                "name": str(r.get("candidate_crop", "") or "").strip(),
                "candidate_crop_id": str(r.get("candidate_crop_id", "") or "").strip(),
                "current_crop": current_crop,
                "village": str(r.get("village", "") or "").strip(),
                "district": str(r.get("district", "") or "").strip(),
                "soil_text": str(r.get("soil_text", "") or "").strip(),
                "irrigation_text": str(r.get("irrigation_text", "") or "").strip(),
                "source_workbook": str(r.get("source_workbook", "") or "").strip(),
                "season_label": str(r.get("_season_label", "") or "").strip(),
                "compatibilityScore": float(r.get("_compat_score", 0.0) or 0.0),
                "compatibilitySummary": str(r.get("_compat_summary", "") or "").strip(),
                "reasonDetails": list(r.get("_compat_reasons", []) or []),
                "cautionDetails": list(r.get("_compat_cautions", []) or []),
                "fullAreaDa": float(r.get("area_da", 0.0) or 0.0),
                "area_da": float(r.get("_feasible_area_da", 0.0) or 0.0),
                "plannedAreaDa": float(r.get("_feasible_area_da", 0.0) or 0.0),
                "coverage_pct": float(r.get("_coverage_pct", 0.0) or 0.0),
                "water_m3_da": float(r.get("water_m3_da", 0.0) or 0.0),
                "profit_tl_da": float(r.get("profit_tl_da", 0.0) or 0.0),
                "yield_ton_da": float(r.get("yield_ton_da", 0.0) or 0.0),
                "totalWater": float(r.get("_effective_water_m3", 0.0) or 0.0),
                "totalProfit": float(r.get("_effective_profit_tl", 0.0) or 0.0),
                "tlPerM3": float(r.get("_tl_per_m3", 0.0) or 0.0),
                "parcelQuotaM3": quota,
                "quotaAdjusted": bool(int(r.get("_quota_adjusted", 0) or 0)),
                "fullFeasible": bool(int(r.get("_full_feasible", 0) or 0)),
                "localUtility": float(r.get("_local_utility", 0.0) or 0.0),
                "isCurrent": bool(canonical_crop_key(str(r.get("candidate_crop", "") or "")) == current_crop_canon),
                "candidateLandType": candidate_crop_land_type(str(r.get("candidate_crop", "") or "")),
                "compatibilityRule": candidate_allowed_for_parcel(parcel_type, current_crop, str(r.get("candidate_crop", "") or ""))[1],
                "sourceType": source_type,
                "candidateVillageCount": safe_int(r.get("_candidate_village_count", 0), 0),
                "cropCategory": str(r.get("_crop_category", "") or "").strip(),
                "cropCategoryLabel": annual_crop_category_label(str(r.get("_crop_category", "") or "")),
                "cropCategoryMode": crop_category_mode,
                "categoryFitScore": float(r.get("_category_fit", 0.0) or 0.0),
            })

        if not options:
            continue

        local_profit_max = max((o["totalProfit"] for o in options), default=0.0)
        local_water_min = min((o["totalWater"] for o in options), default=0.0)
        local_eff_max = max((o["tlPerM3"] for o in options), default=0.0)

        parcels.append({
            "id": str(pid),
            "parcelName": str(parcel_info.get("name") or pid),
            "parcel_type": str(parcel_type or "").strip(),
            "village": str((options[0].get("village") or parcel_info.get("village") or "")).strip(),
            "area_da": float(options[0].get("fullAreaDa", 0.0) or 0.0),
            "quota_m3": quota,
            "current_crop": current_crop,
            "locked": bool(locked),
            "lock_kind": str(lock_kind or ""),
            "options": options,
            "best_local_idx": int(np.argmax([o["localUtility"] for o in options])),
            "min_water_idx": int(np.argmin([o["totalWater"] for o in options])),
            "max_profit_idx": int(np.argmax([o["totalProfit"] for o in options])),
        })

        total_area += float(options[0].get("fullAreaDa", 0.0) or 0.0)
        profit_upper += float(local_profit_max)
        water_lower += float(local_water_min)
        eff_upper += float(local_eff_max)

    if not parcels:
        return None

    return {
        "objective": objective,
        "year": y,
        "ratio": ratio,
        "budget": float(budget),
        "total_area": float(total_area),
        "profit_upper": max(1.0, float(profit_upper)),
        "water_lower": max(0.0, float(water_lower)),
        "eff_upper": max(1.0, float(eff_upper / max(1, len(parcels)))),
        "allocation_model": allocation_model,
        "quota_column": quota_col,
        "planning_rule": _allocation_model_label(allocation_model),
        "crop_category_mode": crop_category_mode,
        "parcels": parcels,
    }


def _matrix_random_solution(problem: Dict[str, Any], rng: random.Random, mode: str = "mixed") -> List[int]:
    sol: List[int] = []
    for p in problem["parcels"]:
        opts = p["options"]
        if not opts:
            sol.append(0)
            continue
        if p.get("locked"):
            idx = 0
        else:
            if mode == "greedy":
                idx = int(p.get("best_local_idx", 0))
            elif mode == "profit":
                idx = int(p.get("max_profit_idx", 0))
            elif mode == "water":
                idx = int(p.get("min_water_idx", 0))
            else:
                weights = []
                for j, opt in enumerate(opts):
                    base = max(0.01, float(opt.get("localUtility", 0.0)) + 0.02)
                    if j == int(p.get("best_local_idx", 0)):
                        base *= 1.15
                    if j == int(p.get("max_profit_idx", 0)):
                        base *= 1.05
                    weights.append(base)
                idx = rng.choices(range(len(opts)), weights=weights, k=1)[0]
        sol.append(int(idx))
    return sol


def _matrix_eval_solution(problem: Dict[str, Any], sol: List[int]) -> Tuple[float, Dict[str, float]]:
    objective = str(problem.get("objective") or "balanced")
    budget = float(problem.get("budget", 0.0) or 0.0)
    total_area = float(problem.get("total_area", 0.0) or 0.0)
    profit_upper = float(problem.get("profit_upper", 1.0) or 1.0)
    water_lower = float(problem.get("water_lower", 0.0) or 0.0)
    eff_upper = float(problem.get("eff_upper", 1.0) or 1.0)

    total_profit = 0.0
    total_water = 0.0
    total_planted_area = 0.0
    total_coverage = 0.0
    full_count = 0
    crop_area: Dict[str, float] = {}

    for i, p in enumerate(problem["parcels"]):
        opts = p["options"]
        if not opts:
            continue
        idx = int(sol[i]) if i < len(sol) else 0
        if idx < 0 or idx >= len(opts):
            idx = 0
        opt = opts[idx]
        total_profit += float(opt.get("totalProfit", 0.0) or 0.0)
        total_water += float(opt.get("totalWater", 0.0) or 0.0)
        area = float(opt.get("area_da", 0.0) or 0.0)
        total_planted_area += area
        total_coverage += float(opt.get("coverage_pct", 0.0) or 0.0)
        if bool(opt.get("fullFeasible")):
            full_count += 1
        crop = str(opt.get("name", "") or "").strip()
        if crop:
            crop_area[crop] = crop_area.get(crop, 0.0) + area

    parcel_count = max(1, len(problem["parcels"]))
    coverage = max(0.0, min(1.0, total_planted_area / max(1e-9, total_area)))
    full_share = float(full_count) / float(parcel_count)
    profit_norm = max(0.0, min(1.0, total_profit / max(1e-9, profit_upper)))
    water_score = 1.0 - max(0.0, min(1.0, (total_water - water_lower) / max(1e-9, budget - water_lower if budget > water_lower else budget + 1.0)))
    eff = total_profit / max(1.0, total_water)
    eff_norm = max(0.0, min(1.0, eff / max(1e-9, eff_upper)))

    planted = max(1e-9, total_planted_area)
    shares = [a / planted for a in crop_area.values() if a > 0]
    if shares:
        dominance = max(shares)
        if len(shares) > 1:
            shannon = -sum(s * np.log(max(s, 1e-12)) for s in shares) / np.log(len(shares))
        else:
            shannon = 0.0
        unique_ratio = min(1.0, len(shares) / max(6.0, min(12.0, float(parcel_count) / 8.0)))
    else:
        dominance = 1.0
        shannon = 0.0
        unique_ratio = 0.0
    diversity = 0.55 * shannon + 0.45 * unique_ratio
    concentration_penalty = max(0.0, dominance - 0.35)
    diversity_soft_penalty = _diversity_penalty_from_shares(shares, DIVERSITY_DEFAULTS) if shares else 0.0

    if objective == "water_saving":
        score = (
            0.54 * water_score
            + 0.14 * eff_norm
            + 0.10 * profit_norm
            + 0.10 * coverage
            + 0.08 * diversity
            + 0.04 * full_share
            - 0.10 * concentration_penalty
        )
    elif objective == "water_efficiency":
        score = (
            0.36 * water_score
            + 0.20 * coverage
            + 0.16 * eff_norm
            + 0.10 * profit_norm
            + 0.12 * diversity
            + 0.06 * full_share
            - 0.10 * concentration_penalty
        )
    elif objective == "max_profit":
        score = (
            0.48 * profit_norm
            + 0.12 * water_score
            + 0.14 * coverage
            + 0.08 * eff_norm
            + 0.10 * diversity
            + 0.08 * full_share
            - 0.08 * concentration_penalty
        )
    else:
        score = (
            0.30 * profit_norm
            + 0.24 * water_score
            + 0.18 * coverage
            + 0.12 * eff_norm
            + 0.10 * diversity
            + 0.06 * full_share
            - 0.08 * concentration_penalty
        )

    # Parcel-level fallow control: if a parcel is left as NADAS while it still has a viable
    # non-fallow option, penalize the solution heavily so algorithms only use fallow as a last resort.
    fallow_penalty = 0.0
    for i, p in enumerate(problem["parcels"]):
        opts = p.get("options") or []
        if not opts:
            continue
        idx = int(sol[i]) if i < len(sol) else 0
        idx = max(0, min(idx, len(opts)-1))
        chosen = opts[idx]
        chosen_name = canonical_crop_key(str(chosen.get("name", "") or ""))
        if chosen_name != FALLOW:
            continue
        viable = [o for o in opts if canonical_crop_key(str(o.get("name", "") or "")) != FALLOW and float(o.get("area_da", 0.0) or 0.0) > 0.0 and float(o.get("totalProfit", 0.0) or 0.0) > 0.0]
        if viable:
            fallow_penalty += 0.55

    score -= fallow_penalty
    score -= 0.12 * diversity_soft_penalty

    metrics = {
        "total_profit": float(total_profit),
        "total_water": float(total_water),
        "coverage": float(coverage),
        "full_share": float(full_share),
        "efficiency": float(eff),
        "diversity": float(diversity),
        "dominance": float(dominance),
    }
    return float(score), metrics


def _matrix_option_dominates_v8(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    aw = float(a.get("totalWater", 0.0) or 0.0)
    bw = float(b.get("totalWater", 0.0) or 0.0)
    ap = float(a.get("totalProfit", 0.0) or 0.0)
    bp = float(b.get("totalProfit", 0.0) or 0.0)
    ae = float(a.get("tlPerM3", 0.0) or 0.0)
    be = float(b.get("tlPerM3", 0.0) or 0.0)
    apen = (
        float(a.get("rotationPenalty", 0.0) or 0.0)
        + float(a.get("fieldToVegetablePenalty", 0.0) or 0.0)
        + max(0.0, 1.0 - float(a.get("categoryFitScore", 0.0) or 0.0)) * 0.35
    )
    bpen = (
        float(b.get("rotationPenalty", 0.0) or 0.0)
        + float(b.get("fieldToVegetablePenalty", 0.0) or 0.0)
        + max(0.0, 1.0 - float(b.get("categoryFitScore", 0.0) or 0.0)) * 0.35
    )
    if apen > bpen + 1e-9:
        return False
    water_ok = aw <= bw + max(1.0, bw * 0.002)
    profit_ok = ap >= bp - max(1.0, bp * 0.002)
    eff_ok = ae >= be - max(0.01, be * 0.002)
    strict = (
        aw < bw - max(1.0, bw * 0.005)
        or ap > bp + max(1.0, bp * 0.005)
        or ae > be + max(0.01, be * 0.005)
    )
    return bool(water_ok and profit_ok and eff_ok and strict)


def _matrix_rank_options_v8(opts: List[Dict[str, Any]], objective: str) -> List[Dict[str, Any]]:
    viable = [
        o for o in (opts or [])
        if float(o.get("area_da", 0.0) or 0.0) > 0.0
        and float(o.get("totalProfit", 0.0) or 0.0) > 0.0
    ]
    if not viable:
        return list(opts or [])

    obj = str(objective or "water_efficiency")
    current = next((o for o in viable if bool(o.get("isCurrent"))), None)
    baseline_profit = float((current or {}).get("totalProfit", 0.0) or 0.0)
    baseline_water = float((current or {}).get("totalWater", 0.0) or 0.0)
    baseline_eff = float((current or {}).get("tlPerM3", 0.0) or 0.0)
    fam_map = load_crop_family_map()
    def annual_family(name: str) -> str:
        fam = str(fam_map.get(normalize_crop_key(str(name or "")), "") or "").strip().lower()
        if fam:
            return fam
        k = normalize_crop_key(str(name or ""))
        if any(x in k for x in ("DOMATES", "BIBER", "PATATES", "PATLICAN")):
            return "solanaceae"
        if any(x in k for x in ("BUGDAY", "ARPA", "YULAF", "CAVDAR", "TRITIKALE", "MISIR")):
            return "tahil"
        if any(x in k for x in ("NOHUT", "MERCIMEK", "FASULYE", "FIG", "BEZELYE")):
            return "baklagil"
        if any(x in k for x in ("LAHANA", "TURP", "KARNABAHAR", "BROKOLI")):
            return "brassicaceae"
        if any(x in k for x in ("SOGAN", "SARIMSAK")):
            return "allium"
        if any(x in k for x in ("KABAK", "KAVUN", "KARPUZ", "HIYAR")):
            return "cucurbitaceae"
        if any(x in k for x in ("MARUL", "AYCICEGI")):
            return "asteraceae"
        return ""
    current_family = annual_family(str((current or {}).get("name", "") or ""))

    waters = [float(o.get("totalWater", 0.0) or 0.0) for o in viable]
    profits = [float(o.get("totalProfit", 0.0) or 0.0) for o in viable]
    effs = [float(o.get("tlPerM3", 0.0) or 0.0) for o in viable]
    def norm(v: float, arr: List[float], invert: bool=False) -> float:
        lo, hi = min(arr), max(arr)
        n = 0.5 if abs(hi - lo) < 1e-9 else max(0.0, min(1.0, (v - lo) / (hi - lo)))
        return 1.0 - n if invert else n
    def source_score(o: Dict[str, Any]) -> float:
        st = str(o.get("sourceType", "") or "").strip()
        if bool(o.get("isCurrent")):
            return 0.12
        if st == "local_village_crop":
            return 0.10
        if st == "regional_5_village_crop":
            return 0.03
        return -0.04
    def rotation_penalty(o: Dict[str, Any]) -> float:
        fam = annual_family(str(o.get("name", "") or ""))
        return 0.16 if fam and current_family and fam == current_family and not bool(o.get("isCurrent")) else 0.0
    def field_to_vegetable_penalty(o: Dict[str, Any]) -> float:
        fam = annual_family(str(o.get("name", "") or ""))
        current_is_field_row = any(x in str(current_family or "").lower() for x in ("tahil", "tahıl", "yem", "cereal", "poaceae"))
        candidate_is_field_row = any(x in str(fam or "").lower() for x in ("tahil", "tahıl", "yem", "baklagil", "cereal", "legume", "poaceae"))
        return 0.50 if current_is_field_row and (not candidate_is_field_row) and not bool(o.get("isCurrent")) else 0.0
    def category_penalty(o: Dict[str, Any]) -> float:
        return max(0.0, 1.0 - float(o.get("categoryFitScore", 0.0) or 0.0)) * 0.32
    def objective_score(o: Dict[str, Any]) -> float:
        water = float(o.get("totalWater", 0.0) or 0.0)
        profit = float(o.get("totalProfit", 0.0) or 0.0)
        eff = float(o.get("tlPerM3", 0.0) or 0.0)
        quota = 1.0 if bool(o.get("fullFeasible")) else 0.0
        cat = max(0.0, min(1.0, float(o.get("categoryFitScore", 0.0) or 0.0)))
        rot = rotation_penalty(o)
        transition = field_to_vegetable_penalty(o)
        cat_penalty = category_penalty(o)
        if obj == "water_saving":
            low_profit = 0.34 if baseline_profit > 0 and profit < baseline_profit * 0.35 and not bool(o.get("isCurrent")) else 0.0
            return 0.42 * norm(water, waters, True) + 0.14 * norm(max(0.0, baseline_water - water), [max(0.0, baseline_water - w) for w in waters]) + 0.11 * norm(profit, profits) + 0.07 * norm(eff, effs) + 0.05 * quota + 0.16 * cat + source_score(o) - rot - transition - cat_penalty - low_profit
        if obj == "max_profit":
            return 0.52 * norm(profit, profits) + 0.13 * norm(eff, effs) + 0.07 * norm(water, waters, True) + 0.07 * quota + 0.16 * cat + source_score(o) - rot - transition - cat_penalty
        weak = 0.42 if baseline_profit > 0 and baseline_eff > 0 and profit < baseline_profit * 0.75 and eff < baseline_eff * 0.95 and not bool(o.get("isCurrent")) else 0.0
        return 0.42 * norm(eff, effs) + 0.23 * norm(profit, profits) + 0.15 * norm(water, waters, True) + 0.05 * quota + 0.12 * cat + source_score(o) - rot - transition - cat_penalty - weak

    for o in viable:
        profit = float(o.get("totalProfit", 0.0) or 0.0)
        water = float(o.get("totalWater", 0.0) or 0.0)
        eff = float(o.get("tlPerM3", 0.0) or 0.0)
        o["cropFamily"] = annual_family(str(o.get("name", "") or ""))
        o["rotationPenalty"] = rotation_penalty(o)
        o["fieldToVegetablePenalty"] = field_to_vegetable_penalty(o)
        o["categoryPenalty"] = category_penalty(o)
        o["objectiveScore"] = objective_score(o)
        o["finalScore"] = o["objectiveScore"]
        o["waterSavingPct"] = (100.0 * (baseline_water - water) / baseline_water) if baseline_water > 0 else 0.0
        o["profitDelta"] = profit - baseline_profit

    if obj == "water_saving":
        ranked = sorted(
            viable,
            key=lambda o: (
                -int(bool(o.get("fullFeasible"))),
                -int(float(o.get("categoryFitScore", 0.0) or 0.0) >= 0.70),
                -int(float(o.get("totalProfit", 0.0) or 0.0) >= max(1.0, baseline_profit * 0.35)),
                -float(o.get("finalScore", 0.0) or 0.0),
                float(o.get("totalWater", 0.0) or 0.0),
            )
        )
    elif obj == "max_profit":
        ranked = sorted(
            viable,
            key=lambda o: (
                -int(bool(o.get("fullFeasible"))),
                -int(float(o.get("categoryFitScore", 0.0) or 0.0) >= 0.70),
                -float(o.get("totalProfit", 0.0) or 0.0),
                -float(o.get("tlPerM3", 0.0) or 0.0),
                float(o.get("totalWater", 0.0) or 0.0),
            )
        )
    else:
        ranked = sorted(viable, key=lambda o: (-int(bool(o.get("fullFeasible"))), -int(float(o.get("categoryFitScore", 0.0) or 0.0) >= 0.70), -float(o.get("finalScore", 0.0) or 0.0), -float(o.get("tlPerM3", 0.0) or 0.0)))

    for o in ranked:
        o.pop("lowerWaterReason", None)

    dominator = next((o for o in ranked[1:] if _matrix_option_dominates_v8(o, ranked[0])), None)
    if dominator is not None:
        ranked = [dominator] + [o for o in ranked if o is not dominator]

    current = next((o for o in ranked if bool(o.get("isCurrent"))), None)
    if current is not None and ranked and _matrix_option_dominates_v8(current, ranked[0]):
        ranked = [current] + [o for o in ranked if o is not current]

    if obj == "water_saving" and ranked:
        lower_water = [
            o for o in ranked[1:]
            if bool(o.get("fullFeasible"))
            and float(o.get("totalWater", 0.0) or 0.0) < float(ranked[0].get("totalWater", 0.0) or 0.0) - 1e-6
        ]
        if lower_water:
            ranked[0]["lowerWaterReason"] = "Daha düşük su kullanan adaylar ekonomik alt eşik / kota / uygulanabilirlik nedeniyle geriye alınmıştır."

    return ranked


def _matrix_solution_to_payload(problem: Dict[str, Any], sol: List[int], algorithm: str) -> Dict[str, Any]:
    details = []
    parcels_out = []
    total_water = 0.0
    total_profit = 0.0

    for i, p in enumerate(problem["parcels"]):
        opts = p["options"]
        if not opts:
            continue
        idx = int(sol[i]) if i < len(sol) else 0
        if idx < 0 or idx >= len(opts):
            idx = 0
        ranked_opts = _matrix_rank_options_v8(opts, str(problem.get("objective") or "water_efficiency"))
        chosen = opts[idx]
        ranked_choice_pos = -1
        try:
            ranked_choice_pos = next((k for k, o in enumerate(ranked_opts) if o is chosen), -1)
        except Exception:
            ranked_choice_pos = -1
        objective_name = str(problem.get("objective") or "water_efficiency")
        def _rank_reason(o: Dict[str, Any]) -> str:
            current_opt = next((x for x in ranked_opts if bool(x.get("isCurrent"))), None)
            cat_label = str(o.get("cropCategoryLabel") or annual_crop_category_label(str(o.get("cropCategory", "") or "")))
            fit_pct = round(float(o.get("categoryFitScore", 0.0) or 0.0) * 100.0)
            category_note = f" Ürün grubu uyumu: {cat_label} (%{fit_pct}). Algoritma: {str(algorithm).upper()}."
            if bool(o.get("isCurrent")):
                return "Mevcut desen bu hedefte alternatiflerden daha avantajlı olduğu için korunmuştur."
            if (
                current_opt is not None
                and objective_name == "max_profit"
                and not bool(current_opt.get("fullFeasible"))
                and float(current_opt.get("totalProfit", 0.0) or 0.0) > float(o.get("totalProfit", 0.0) or 0.0)
            ):
                return "Mevcut ürün daha kârlıdır ancak su kotası/uygulanabilirlik riski nedeniyle ana öneri yapılmamıştır."
            if (
                current_opt is not None
                and objective_name == "water_efficiency"
                and not bool(current_opt.get("fullFeasible"))
                and float(current_opt.get("tlPerM3", 0.0) or 0.0) >= float(o.get("tlPerM3", 0.0) or 0.0)
                and float(current_opt.get("totalProfit", 0.0) or 0.0) > float(o.get("totalProfit", 0.0) or 0.0)
            ):
                return "Mevcut desen TL/m³ ve kâr açısından güçlüdür; kota riski olduğu için alternatifler karşılaştırmada tutulmuştur."
            if objective_name == "water_saving":
                if str(o.get("lowerWaterReason", "") or "").strip():
                    return str(o.get("lowerWaterReason"))
                return "Bu aday uygulanabilir ve kota uygun adaylar içinde en düşük toplam su kullanımına sahip olduğu için seçilmiştir."
            if objective_name == "max_profit":
                return "Bu aday uygulanabilir ve kota uygun adaylar içinde en yüksek net kârı verdiği için seçilmiştir."
            return "Bu aday TL/m³, net kâr, su kullanımı ve kota uygunluğu birlikte değerlendirildiğinde en güçlü aday olduğu için seçilmiştir."

        def _rank_reason_with_context(o: Dict[str, Any]) -> str:
            cat_label = str(o.get("cropCategoryLabel") or annual_crop_category_label(str(o.get("cropCategory", "") or "")))
            fit_pct = round(float(o.get("categoryFitScore", 0.0) or 0.0) * 100.0)
            return f"{_rank_reason(o)} Ürün grubu uyumu: {cat_label} (%{fit_pct}). Algoritma: {str(algorithm).upper()}."

        def _role_dedup_key(o: Dict[str, Any]) -> str:
            name = re.sub(r"\([^)]*\)", "", str(o.get("name", "") or "")).strip()
            season = str(o.get("season_label", "") or "").strip()
            return f"{normalize_crop_key(name)}|primary|{normalize_crop_key(season)}"

        is_locked_orchard = bool(p.get("locked")) and str(p.get("lock_kind") or "") == "orchard"
        alt_sorted = ranked_opts

        if is_locked_orchard:
            alternatives = []
            _orchard_reference = {
                "name": str(chosen.get("name", "") or p.get("current_crop") or "").strip(),
                "objective": objective_name,
                "rankReason": "Bahçe/çok yıllık ürünlerde tesis sökümü ve yeniden kurulum gerektirdiği için mevcut ana ürün korunmuştur; tek yıllık ürünler ana öneri yapılmaz.",
                "decisionNote": "Bahçe/çok yıllık ürünlerde tesis sökümü ve yeniden kurulum gerektirdiği için mevcut ana ürün korunmuştur; tek yıllık ürünler ana öneri yapılmaz.",
                "is_current_reference": True,
                "lifecycle": "perennial",
                "cropCategory": "orchard",
                "cropCategoryLabel": annual_crop_category_label("orchard"),
                "cropCategoryMode": str(problem.get("crop_category_mode") or "same_category"),
                "categoryFitScore": 1.0,
                "categoryMatch": True,
                "hardFilterPassed": True,
                "fullFeasible": bool(chosen.get("fullFeasible")),
                "quota_ok": bool(chosen.get("fullFeasible")),
                "area_da": float(chosen.get("area_da", 0.0) or 0.0),
                "totalWater": float(chosen.get("totalWater", 0.0) or 0.0),
                "totalProfit": float(chosen.get("totalProfit", 0.0) or 0.0),
                "tlPerM3": float(chosen.get("tlPerM3", 0.0) or 0.0),
            }
            for ar in _orchard_interrow_alternatives(str(chosen.get("name", "") or p.get("current_crop") or "Bahçe ürünü"))[:5]:
                alternatives.append({
                    "name": str(ar.get("name", "") or "").strip(),
                    "kind": str(ar.get("kind", "") or "").strip(),
                    "waterLevel": str(ar.get("waterLevel", "") or "").strip(),
                    "decisionNote": str(ar.get("note", "") or "").strip(),
                    "isInterrow": True,
                    "lifecycle": "annual_interrow",
                    "cropCategory": "interrow",
                    "cropCategoryLabel": "Sıra arası / uzman alternatifi",
                    "cropCategoryMode": str(problem.get("crop_category_mode") or "same_category"),
                    "categoryMatch": False,
                    "hardFilterPassed": False,
                    "requiresExpertApproval": True
                })
        else:
            alternatives = []
            seen_alt_keys = {_role_dedup_key(chosen)}
            for ar in alt_sorted:
                if bool(ar.get("isCurrent")):
                    continue
                dkey = _role_dedup_key(ar)
                if dkey in seen_alt_keys:
                    continue
                seen_alt_keys.add(dkey)
                ar_idx = len(alternatives) + 1
                alt_cat = load_crop_catalog().get(normalize_crop_key(str(ar.get("name", "") or "")), {})
                alt_irr_current = str(alt_cat.get("irrigationCurrentKey") or p.get("irrigation_key") or "").strip()
                alt_irr_suggested = str(alt_cat.get("irrigationRecommendedKey") or alt_irr_current).strip()
                alternatives.append({
                    "name": str(ar.get("name", "") or "").strip(),
                    "objective": objective_name,
                    "rankReason": _rank_reason_with_context(ar),
                    "is_current_reference": bool(ar.get("isCurrent")),
                    "debugRank": {
                        "label": str(ar.get("name", "") or "").strip(),
                        "scenario": "single",
                        "objective": objective_name,
                        "is_current_reference": bool(ar.get("isCurrent")),
                        "totalWater": float(ar.get("totalWater", 0.0) or 0.0),
                        "totalProfit": float(ar.get("totalProfit", 0.0) or 0.0),
                        "tlPerM3": float(ar.get("tlPerM3", 0.0) or 0.0),
                        "waterSavingPct": float(ar.get("waterSavingPct", 0.0) or 0.0),
                        "profitDelta": float(ar.get("profitDelta", 0.0) or 0.0),
                        "fullFeasible": bool(ar.get("fullFeasible")),
                        "quota_ok": bool(ar.get("fullFeasible")),
                        "cropFamily": str(ar.get("cropFamily", "") or ""),
                        "rotationPenalty": float(ar.get("rotationPenalty", 0.0) or 0.0),
                        "fieldToVegetablePenalty": float(ar.get("fieldToVegetablePenalty", 0.0) or 0.0),
                        "categoryFitScore": float(ar.get("categoryFitScore", 0.0) or 0.0),
                        "categoryPenalty": float(ar.get("categoryPenalty", 0.0) or 0.0),
                        "cropCategory": str(ar.get("cropCategory", "") or ""),
                        "cropCategoryMode": str(ar.get("cropCategoryMode", "") or ""),
                        "objectiveScore": float(ar.get("objectiveScore", 0.0) or 0.0),
                        "finalScore": float(ar.get("finalScore", 0.0) or 0.0),
                        "rank": int(ar_idx),
                        "rankReason": _rank_reason_with_context(ar),
                        "dominatedBy": ""
                    },
                    "season": str(ar.get("season_label", "") or infer_crop_season_label(str(ar.get("name", "") or ""), str(p.get("parcel_type", "") or ""))).strip(),
                    "area_da": float(ar.get("area_da", 0.0) or 0.0),
                    "coverage_pct": float(ar.get("coverage_pct", 0.0) or 0.0),
                    "totalWater": float(ar.get("totalWater", 0.0) or 0.0),
                    "totalProfit": float(ar.get("totalProfit", 0.0) or 0.0),
                    "tlPerM3": float(ar.get("tlPerM3", 0.0) or 0.0),
                    "parcelQuotaM3": float(ar.get("parcelQuotaM3", 0.0) or 0.0),
                    "quotaAdjusted": bool(ar.get("quotaAdjusted")),
                    "fullFeasible": bool(ar.get("fullFeasible")),
                    "quota_ok": bool(ar.get("fullFeasible")),
                    "sourceType": str(ar.get("sourceType", "") or ""),
                    "cropCategory": str(ar.get("cropCategory", "") or ""),
                    "cropCategoryLabel": str(ar.get("cropCategoryLabel", "") or ""),
                    "cropCategoryMode": str(ar.get("cropCategoryMode", "") or ""),
                    "categoryFitScore": float(ar.get("categoryFitScore", 0.0) or 0.0),
                    "categoryMatch": float(ar.get("categoryFitScore", 0.0) or 0.0) >= 0.999,
                    "hardFilterPassed": float(ar.get("categoryFitScore", 0.0) or 0.0) >= 0.999 or str(ar.get("cropCategoryMode", "") or "") in ("mixed", "same_category"),
                    "lifecycle": "perennial" if str(ar.get("cropCategory", "") or "") == "orchard" else "annual",
                    "candidateVillageCount": safe_int(ar.get("candidateVillageCount", 0), 0),
                    "candidateLandType": str(ar.get("candidateLandType", "") or candidate_crop_land_type(str(ar.get("name", "") or ""))),
                    "compatibilityRule": str(ar.get("compatibilityRule", "") or candidate_allowed_for_parcel(str(p.get("parcel_type", "") or ""), str(p.get("current_crop", "") or ""), str(ar.get("name", "") or ""))[1]),
                    "compatibilityScore": float(ar.get("compatibilityScore", 0.0) or 0.0),
                    "reasonDetails": list(ar.get("reasonDetails", []) or []),
                    "cautionDetails": list(ar.get("cautionDetails", []) or []),
                    "decisionNote": _rank_reason_with_context(ar),
                    "irrigationCurrentKey": alt_irr_current,
                    "irrigationSuggestedKey": alt_irr_suggested,
                    **_decision_metrics_for_crop(str(ar.get("name", "") or ""), float(ar.get("area_da", 0.0) or 0.0), float(ar.get("water_m3_da", 0.0) or 0.0), float(ar.get("profit_tl_da", 0.0) or 0.0)),
                })
                if len(alternatives) >= 5:
                    break

        chosen_cat = load_crop_catalog().get(normalize_crop_key(str(chosen.get("name", "") or "")), {})
        irr_current_key = str(chosen_cat.get("irrigationCurrentKey") or p.get("irrigation_key") or "").strip()
        irr_suggested_key = str(chosen_cat.get("irrigationRecommendedKey") or irr_current_key).strip()
        rec = {
            "name": str(chosen.get("name", "") or "").strip(),
            "objective": objective_name,
            "rankReason": _rank_reason_with_context(chosen),
            "is_current_reference": bool(chosen.get("isCurrent")),
            "debugRank": {
                "label": str(chosen.get("name", "") or "").strip(),
                "scenario": "single",
                "objective": objective_name,
                "is_current_reference": bool(chosen.get("isCurrent")),
                "algorithmChoiceIndex": int(idx),
                "rankedChoicePosition": int(ranked_choice_pos),
                "algorithmChoicePreserved": True,
                "totalWater": float(chosen.get("totalWater", 0.0) or 0.0),
                "totalProfit": float(chosen.get("totalProfit", 0.0) or 0.0),
                "tlPerM3": float(chosen.get("tlPerM3", 0.0) or 0.0),
                "waterSavingPct": float(chosen.get("waterSavingPct", 0.0) or 0.0),
                "profitDelta": float(chosen.get("profitDelta", 0.0) or 0.0),
                "fullFeasible": bool(chosen.get("fullFeasible")),
                "quota_ok": bool(chosen.get("fullFeasible")),
                "cropFamily": str(chosen.get("cropFamily", "") or ""),
                "rotationPenalty": float(chosen.get("rotationPenalty", 0.0) or 0.0),
                "fieldToVegetablePenalty": float(chosen.get("fieldToVegetablePenalty", 0.0) or 0.0),
                "categoryFitScore": float(chosen.get("categoryFitScore", 0.0) or 0.0),
                "categoryPenalty": float(chosen.get("categoryPenalty", 0.0) or 0.0),
                "cropCategory": str(chosen.get("cropCategory", "") or ""),
                "cropCategoryMode": str(chosen.get("cropCategoryMode", "") or ""),
                "objectiveScore": float(chosen.get("objectiveScore", 0.0) or 0.0),
                "finalScore": float(chosen.get("finalScore", 0.0) or 0.0),
                "rank": 1,
                "rankReason": _rank_reason_with_context(chosen),
                "dominatedBy": ""
            },
            "season": str(chosen.get("season_label", "") or infer_crop_season_label(str(chosen.get("name", "") or ""), str(p.get("parcel_type", "") or ""))).strip(),
            "area_da": float(chosen.get("area_da", 0.0) or 0.0),
            "plannedAreaDa": float(chosen.get("plannedAreaDa", 0.0) or 0.0),
            "coverage_pct": float(chosen.get("coverage_pct", 0.0) or 0.0),
            "water_m3_da": float(chosen.get("water_m3_da", 0.0) or 0.0),
            "waterPerDa": float(chosen.get("water_m3_da", 0.0) or 0.0),
            "profit_tl_da": float(chosen.get("profit_tl_da", 0.0) or 0.0),
            "profitPerDa": float(chosen.get("profit_tl_da", 0.0) or 0.0),
            "totalWater": float(chosen.get("totalWater", 0.0) or 0.0),
            "totalProfit": float(chosen.get("totalProfit", 0.0) or 0.0),
            "tlPerM3": float(chosen.get("tlPerM3", 0.0) or 0.0),
            "parcelQuotaM3": float(chosen.get("parcelQuotaM3", 0.0) or 0.0),
            "quotaAdjusted": bool(chosen.get("quotaAdjusted")),
            "fullFeasible": bool(chosen.get("fullFeasible")),
            "quota_ok": bool(chosen.get("fullFeasible")),
            "sourceType": str(chosen.get("sourceType", "") or ""),
            "cropCategory": str(chosen.get("cropCategory", "") or ""),
            "cropCategoryLabel": str(chosen.get("cropCategoryLabel", "") or ""),
            "cropCategoryMode": str(chosen.get("cropCategoryMode", "") or ""),
            "categoryFitScore": float(chosen.get("categoryFitScore", 0.0) or 0.0),
            "categoryMatch": bool(is_locked_orchard) or float(chosen.get("categoryFitScore", 0.0) or 0.0) >= 0.999,
            "hardFilterPassed": bool(is_locked_orchard) or float(chosen.get("categoryFitScore", 0.0) or 0.0) >= 0.999 or str(chosen.get("cropCategoryMode", "") or "") in ("mixed", "same_category"),
            "lifecycle": "perennial" if bool(is_locked_orchard) or str(chosen.get("cropCategory", "") or "") == "orchard" else "annual",
            "candidateVillageCount": safe_int(chosen.get("candidateVillageCount", 0), 0),
            "candidateLandType": str(chosen.get("candidateLandType", "") or candidate_crop_land_type(str(chosen.get("name", "") or ""))),
            "compatibilityRule": str(chosen.get("compatibilityRule", "") or candidate_allowed_for_parcel(str(p.get("parcel_type", "") or ""), str(p.get("current_crop", "") or ""), str(chosen.get("name", "") or ""))[1]),
            "orchardLocked": bool(is_locked_orchard),
            "compatibilityScore": float(chosen.get("compatibilityScore", 0.0) or 0.0),
            "reasonDetails": list(chosen.get("reasonDetails", []) or []),
            "cautionDetails": list(chosen.get("cautionDetails", []) or []),
            "modeledFactors": [
                "su kotası", "mevsim etiketi", "ürün familyası / rotasyon",
                "parsel tipi", "toprak kabiliyet sınıfı", "sulama yöntemi", "pik su ayı"
            ],
            "irrigation": {"current": str(chosen.get("irrigation_text", "") or "").strip()},
            "irrigationCurrentKey": irr_current_key,
            "irrigationSuggestedKey": irr_suggested_key,
            **_decision_metrics_for_crop(str(chosen.get("name", "") or ""), float(chosen.get("area_da", 0.0) or 0.0), float(chosen.get("water_m3_da", 0.0) or 0.0), float(chosen.get("profit_tl_da", 0.0) or 0.0)),
            "decisionNote": ("Kurulu çok yıllık/bahçe parselinde ana ürün korunmuştur; yalnızca ara ürün ve yönetim alternatifleri gösterilir." if is_locked_orchard else _rank_reason_with_context(chosen))
        }

        total_water += rec["totalWater"]
        total_profit += rec["totalProfit"]
        parcels_out.append({
            "id": str(p.get("id")),
            "area_da": float(p.get("area_da", 0.0) or 0.0),
            "parcel_type": str(p.get("parcel_type", "") or "").strip(),
            "current_crop": str(p.get("current_crop", "") or "").strip(),
            "result": {
                "primaryRecommendation": rec,
                "alternativeRecommendations": [a for a in alternatives if not bool(a.get("isInterrow")) and not bool(a.get("requiresExpertApproval"))],
                "interrowOrExpertAlternatives": [a for a in alternatives if bool(a.get("isInterrow")) or bool(a.get("requiresExpertApproval"))],
                "conversionWarnings": (["Mevcut bahçe/çok yıllık ürün korunmuştur; yıllık ürünler ana öneri yapılmaz ve yalnızca uzman değerlendirmesi gerektirir."] if bool(is_locked_orchard) else []),
                "recommended": [rec],
                "alternatives": alternatives
            }
        })
        details.append({
            "parcelId": str(p.get("id")),
            "parcelName": str(p.get("parcelName") or p.get("id")),
            "chosenCrop": rec["name"],
            "area_da": rec["area_da"],
            "coverage_pct": rec["coverage_pct"],
            "water_m3": rec["totalWater"],
            "profit_tl": rec["totalProfit"],
            "parcel_quota_m3": rec["parcelQuotaM3"],
            "quota_adjusted": rec["quotaAdjusted"]
        })

    return {
        "status": "OK",
        "algorithm": str(algorithm).upper(),
        "objective": str(problem.get("objective") or "balanced"),
        "year": int(problem.get("year") or 2024),
        "water_budget_m3": float(problem.get("budget", 0.0) or 0.0),
        "feasible": bool(total_water <= float(problem.get("budget", 0.0) or 0.0) + 1e-6),
        "total_water_m3": float(total_water),
        "total_profit_tl": float(total_profit),
        "efficiency_tl_per_m3": float((total_profit / total_water) if total_water > 0 else 0.0),
        "parcels": parcels_out,
        "details": details,
        "meta": {
            "mode": "excel_area_fair_water_real_optimization_v42_agro_guarded",
            "allocation_model": str(problem.get("allocation_model") or "area_fair_per_da"),
            "cropCategoryMode": str(problem.get("crop_category_mode") or "mixed"),
            "quota_column": str(problem.get("quota_column") or "quota_area_fair_per_da_m3"),
            "planning_rule": str(problem.get("planning_rule") or "Dekar bazlı adil kota: toplam mevcut su / toplam alan; her parsel alanı kadar su hakkı alır."),
            "objective_explanation": {
                "current": "Mevcut desen referanstır; öneri üretmez.",
                "water_efficiency": "Parsel kotası altında daha düşük/etkin su, alan kapsaması, TL/m³ ve ziraat uygunluğu birlikte puanlanır.",
                "max_profit": "Parsel kotası aşılmadan etkin ekilebilir alan için en yüksek net kâr ve uygunluk skoru aranır.",
                "balanced": "Su, kâr, kapsama, TL/m³, ürün çeşitliliği ve ziraat uygunluğu birlikte dengelenir."
            },
            "water_allocation": build_water_allocation_logic(),
            "agronomic_guards": [
                "tarla/sebze parselinde bahçe veya çok yıllık ürün normal senaryoda önerilmez",
                "kurulu bahçe/çok yıllık parselde ana ürün korunur",
                "mevcut ürün adları kompakt kanonik anahtarla eşleştirilir",
                "kota yetmezse tam parsel yerine güvenli ekilebilir alan raporlanır"
            ],
            "note": "İleri projeksiyon kaldırıldı. Excel türevi parsel×ürün matrisi üzerinde gerçek algoritmik arama çalıştırıldı."
        }
    }


def _matrix_ga_optimize(problem: Dict[str, Any], seed: Optional[int]=None, pop_size: int=36, generations: int=36,
                        cx_rate: float=0.72, mut_rate: float=0.05) -> Tuple[List[int], Dict[str, Any]]:
    rng = random.Random(seed)
    fast_benchmark = bool((problem or {}).get("benchmark_fast", False))
    pop_floor = 4 if fast_benchmark else 12
    generation_floor = 3 if fast_benchmark else 10
    pop_size = max(pop_floor, min(120, int(pop_size or 36)))
    generations = max(generation_floor, min(160, int(generations or 36)))
    cx_rate = max(0.1, min(0.95, float(cx_rate or 0.72)))
    mut_rate = max(0.01, min(0.35, float(mut_rate or 0.05)))

    population = [
        _matrix_random_solution(problem, rng, "greedy"),
        _matrix_random_solution(problem, rng, "profit"),
        _matrix_random_solution(problem, rng, "water"),
    ]
    while len(population) < pop_size:
        population.append(_matrix_random_solution(problem, rng, "mixed"))

    best_sol = population[0][:]
    best_score, best_metrics = _matrix_eval_solution(problem, best_sol)

    def _tournament() -> List[int]:
        k = min(4, len(population))
        cand = rng.sample(population, k=k)
        cand.sort(key=lambda s: _matrix_eval_solution(problem, s)[0], reverse=True)
        return cand[0][:]

    for _ in range(generations):
        scored = [(_matrix_eval_solution(problem, s)[0], s) for s in population]
        scored.sort(key=lambda x: x[0], reverse=True)
        if scored[0][0] > best_score:
            best_score = float(scored[0][0])
            best_sol = scored[0][1][:]
            _, best_metrics = _matrix_eval_solution(problem, best_sol)

        next_pop = [scored[0][1][:], scored[1][1][:]]
        while len(next_pop) < pop_size:
            p1 = _tournament()
            p2 = _tournament()
            c1, c2 = p1[:], p2[:]
            if rng.random() < cx_rate and len(p1) > 1:
                cut = rng.randint(1, len(p1) - 1)
                c1 = p1[:cut] + p2[cut:]
                c2 = p2[:cut] + p1[cut:]
            for child in (c1, c2):
                for i, pr in enumerate(problem["parcels"]):
                    if pr.get("locked"):
                        child[i] = 0
                        continue
                    if rng.random() < mut_rate:
                        child[i] = rng.randrange(len(pr["options"]))
            next_pop.append(c1)
            if len(next_pop) < pop_size:
                next_pop.append(c2)
        population = next_pop[:pop_size]

    return best_sol, {"bestScore": float(best_score), **best_metrics, "popSize": int(pop_size), "generations": int(generations)}


def _matrix_abc_optimize(problem: Dict[str, Any], seed: Optional[int]=None, food_sources: int=28, cycles: int=42,
                         limit: int=10) -> Tuple[List[int], Dict[str, Any]]:
    rng = random.Random(seed)
    fast_benchmark = bool((problem or {}).get("benchmark_fast", False))
    source_floor = 4 if fast_benchmark else 10
    cycle_floor = 3 if fast_benchmark else 10
    limit_floor = 2 if fast_benchmark else 4
    food_sources = max(source_floor, min(120, int(food_sources or 28)))
    cycles = max(cycle_floor, min(180, int(cycles or 42)))
    limit = max(limit_floor, min(50, int(limit or 10)))

    foods = [_matrix_random_solution(problem, rng, mode) for mode in (["greedy", "profit", "water"] + ["mixed"] * max(0, food_sources - 3))]
    foods = foods[:food_sources]
    trials = [0] * len(foods)
    scored = [_matrix_eval_solution(problem, f) for f in foods]
    best_idx = int(np.argmax([s[0] for s in scored]))
    best_sol = foods[best_idx][:]
    best_score, best_metrics = scored[best_idx]

    def _neighbor(sol: List[int]) -> List[int]:
        v = sol[:]
        moves = rng.randint(1, 4)
        unlocked = [i for i, p in enumerate(problem["parcels"]) if not p.get("locked")]
        if not unlocked:
            return v
        for i in rng.sample(unlocked, k=min(moves, len(unlocked))):
            v[i] = rng.randrange(len(problem["parcels"][i]["options"]))
        return v

    for _ in range(cycles):
        for k in range(len(foods)):
            cand = _neighbor(foods[k])
            sc_cand, m_cand = _matrix_eval_solution(problem, cand)
            sc_old, _ = scored[k]
            if sc_cand > sc_old:
                foods[k] = cand
                scored[k] = (sc_cand, m_cand)
                trials[k] = 0
            else:
                trials[k] += 1

        fit_vals = np.array([max(1e-9, s[0] + 1.5) for s in scored], dtype=float)
        probs = fit_vals / fit_vals.sum()
        for _ in range(len(foods)):
            k = int(rng.choices(range(len(foods)), weights=probs, k=1)[0])
            cand = _neighbor(foods[k])
            sc_cand, m_cand = _matrix_eval_solution(problem, cand)
            sc_old, _ = scored[k]
            if sc_cand > sc_old:
                foods[k] = cand
                scored[k] = (sc_cand, m_cand)
                trials[k] = 0
            else:
                trials[k] += 1

        for k in range(len(foods)):
            if trials[k] >= limit:
                foods[k] = _matrix_random_solution(problem, rng, "mixed")
                scored[k] = _matrix_eval_solution(problem, foods[k])
                trials[k] = 0

        k = int(np.argmax([s[0] for s in scored]))
        if scored[k][0] > best_score:
            best_score = float(scored[k][0])
            best_sol = foods[k][:]
            best_metrics = scored[k][1]

    return best_sol, {"bestScore": float(best_score), **best_metrics, "foodSources": int(food_sources), "cycles": int(cycles), "limit": int(limit)}


def _matrix_aco_optimize(problem: Dict[str, Any], seed: Optional[int]=None, ants: int=28, iterations: int=42,
                         rho: float=0.22, q: float=1.0) -> Tuple[List[int], Dict[str, Any]]:
    rng = random.Random(seed)
    fast_benchmark = bool((problem or {}).get("benchmark_fast", False))
    ant_floor = 4 if fast_benchmark else 10
    iteration_floor = 3 if fast_benchmark else 10
    ants = max(ant_floor, min(120, int(ants or 28)))
    iterations = max(iteration_floor, min(180, int(iterations or 42)))
    rho = max(0.05, min(0.8, float(rho or 0.22)))
    q = max(0.1, min(5.0, float(q or 1.0)))

    pher = [np.ones(len(p["options"]), dtype=float) for p in problem["parcels"]]
    heur = [np.array([max(1e-6, float(o.get("localUtility", 0.0)) + 0.02) for o in p["options"]], dtype=float) for p in problem["parcels"]]

    best_sol = _matrix_random_solution(problem, rng, "greedy")
    best_score, best_metrics = _matrix_eval_solution(problem, best_sol)

    for _ in range(iterations):
        iter_best_sol = None
        iter_best_score = -1e18
        iter_best_metrics = None

        for _a in range(ants):
            sol = []
            for i, p in enumerate(problem["parcels"]):
                if p.get("locked"):
                    sol.append(0)
                    continue
                weights = (pher[i] ** 1.0) * (heur[i] ** 2.1)
                s = float(np.sum(weights))
                if (not np.isfinite(s)) or s <= 0:
                    idx = rng.randrange(len(p["options"]))
                else:
                    idx = int(rng.choices(range(len(p["options"])), weights=weights.tolist(), k=1)[0])
                sol.append(idx)

            sc, mt = _matrix_eval_solution(problem, sol)
            if sc > iter_best_score:
                iter_best_score = float(sc)
                iter_best_sol = sol[:]
                iter_best_metrics = mt
            if sc > best_score:
                best_score = float(sc)
                best_sol = sol[:]
                best_metrics = mt

        for i in range(len(pher)):
            pher[i] *= (1.0 - rho)
            pher[i] = np.clip(pher[i], 1e-6, 1e6)

        if iter_best_sol is not None:
            deposit = max(0.05, float(q) * max(0.05, iter_best_score + 1.0))
            for i, idx in enumerate(iter_best_sol):
                pher[i][int(idx)] += deposit
            best_metrics = iter_best_metrics or best_metrics

    return best_sol, {"bestScore": float(best_score), **best_metrics, "ants": int(ants), "iterations": int(iterations), "rho": float(rho), "q": float(q)}


def optimize_from_excel_matrix(selected_parcels: List[Dict[str, Any]], algorithm: str, scenario: str,
                               water_budget_ratio: float, year: Optional[int]=None,
                               options: Optional[Dict[str,Any]]=None) -> Optional[Dict[str, Any]]:
    problem = _matrix_build_problem(selected_parcels, scenario, water_budget_ratio, year=year, options=options)
    if problem is None:
        return None

    objective = str(problem.get("objective") or "balanced")
    algo = str(algorithm or "GA").upper()
    opts = options or {}

    if objective == "current":
        sol = [0 for _ in problem["parcels"]]
        out = _matrix_solution_to_payload(problem, sol, algo)
        out.setdefault("meta", {})["run_params"] = {"algorithm": algo, "seed": opts.get("seed", None), "mode": "current_baseline"}
        return out

    if algo in ("AUTO", "OTOMATIK", "OTOMATİK"):
        trials: List[Tuple[str, List[int], Dict[str, Any], float]] = []
        auto_opts = {**opts, "popSize": min(int(opts.get("popSize", 18) or 18), 18), "generations": min(int(opts.get("generations", 18) or 18), 18), "ants": min(int(opts.get("ants", 14) or 14), 14), "iterations": min(int(opts.get("iterations", 18) or 18), 18), "foodSources": min(int(opts.get("foodSources", 14) or 14), 14), "cycles": min(int(opts.get("cycles", 18) or 18), 18)}
        for a in ("GA", "ACO", "ABC"):
            seed0 = opts.get("seed", None)
            if a == "ABC":
                sol0, meta0 = _matrix_abc_optimize(problem, seed=seed0, food_sources=int(auto_opts.get("foodSources", 14) or 14), cycles=int(auto_opts.get("cycles", 18) or 18), limit=int(auto_opts.get("limit", 10) or 10))
            elif a == "ACO":
                sol0, meta0 = _matrix_aco_optimize(problem, seed=seed0, ants=int(auto_opts.get("ants", 14) or 14), iterations=int(auto_opts.get("iterations", 18) or 18), rho=float(opts.get("rho", 0.22) or 0.22), q=float(opts.get("q", 1.0) or 1.0))
            else:
                sol0, meta0 = _matrix_ga_optimize(problem, seed=seed0, pop_size=int(auto_opts.get("popSize", 18) or 18), generations=int(auto_opts.get("generations", 18) or 18), cx_rate=float(opts.get("cxRate", 0.72) or 0.72), mut_rate=float(opts.get("mutRate", 0.05) or 0.05))
            score0, eval0 = _matrix_eval_solution(problem, sol0)
            trials.append((a, sol0, {**meta0, **eval0}, float(score0)))
        trials.sort(key=lambda x: x[3], reverse=True)
        best_algo, best_sol, best_meta, best_score = trials[0]
        out = _matrix_solution_to_payload(problem, best_sol, best_algo)
        out.setdefault("meta", {})["auto_algorithm"] = {
            "selected": best_algo,
            "score": best_score,
            "candidates": [{"algorithm": a, "score": s, "total_profit": m.get("total_profit"), "total_water": m.get("total_water"), "efficiency": m.get("efficiency")} for a, _sol, m, s in trials],
            "cropCategoryMode": str(problem.get("crop_category_mode") or "mixed"),
        }
        out.setdefault("meta", {})["run_params"] = {"algorithm": "AUTO", "selected_algorithm": best_algo, "seed": opts.get("seed", None)}
        return out

    if algo == "ABC":
        sol, meta = _matrix_abc_optimize(
            problem,
            seed=opts.get("seed", None),
            food_sources=int(opts.get("foodSources", 28) or 28),
            cycles=int(opts.get("cycles", 42) or 42),
            limit=int(opts.get("limit", 10) or 10),
        )
    elif algo == "ACO":
        sol, meta = _matrix_aco_optimize(
            problem,
            seed=opts.get("seed", None),
            ants=int(opts.get("ants", 28) or 28),
            iterations=int(opts.get("iterations", 42) or 42),
            rho=float(opts.get("rho", 0.22) or 0.22),
            q=float(opts.get("q", 1.0) or 1.0),
        )
    else:
        sol, meta = _matrix_ga_optimize(
            problem,
            seed=opts.get("seed", None),
            pop_size=int(opts.get("popSize", 36) or 36),
            generations=int(opts.get("generations", 36) or 36),
            cx_rate=float(opts.get("cxRate", 0.72) or 0.72),
            mut_rate=float(opts.get("mutRate", 0.05) or 0.05),
        )
        algo = "GA"

    out = _matrix_solution_to_payload(problem, sol, algo)
    out.setdefault("meta", {}).update({
        "run_params": {"algorithm": algo, "seed": opts.get("seed", None), **meta},
        "optimization_model": "tek ürün / eşit parsel kotası / küresel portföy araması",
    })
    return out


def optimize(selected_ids: List[str], algorithm: str, scenario: str, water_budget_ratio: float, year: Optional[int]=None, options: Optional[Dict[str,Any]]=None) -> Dict[str, Any]:
    base_parcels = load_parcels()
    custom_parcels = []
    try:
        if isinstance(options, dict):
            cp = options.get("customParcels") or options.get("custom_parcels") or []
            if isinstance(cp, list):
                custom_parcels = cp
    except Exception:
        custom_parcels = []
    parcels = merge_frontend_custom_parcels(base_parcels, custom_parcels)
    selected_ids = [normalize_parcel_id(x) for x in (selected_ids or [])]
    selected = [p for p in parcels if (not selected_ids) or (normalize_parcel_id(p["id"]) in selected_ids)]

    opts = options or {}
    season_source = str((opts.get("seasonSource") if isinstance(opts, dict) else None) or "s1").strip().lower()
    two_season = bool(opts.get("twoSeason", False)) if isinstance(opts, dict) else False
    scenario_type = str((opts.get("scenarioType") if isinstance(opts, dict) else None) or ("double" if two_season else "single")).strip().lower()
    if season_source == "s2":
        two_season = True
        scenario_type = "double"
    elif scenario_type in ("double", "iki", "cift", "çift", "desen"):
        two_season = True
    else:
        two_season = False
        scenario_type = "single"

    # IMPORTANT:
    # Excel-derived matrix optimizer is intentionally limited to tek ürün / tek sezon mantığı.
    # Senaryo-2 ise çift ürün / desen mantığı içerir; bu nedenle S2 isteklerinde matrix motorunu
    # kullanmak yanlış sonuçlara yol açıyordu ve S1/S2 farkı kayboluyordu. Aşağıda matrix motoru
    # yalnızca gerçek tek-ürün senaryolarda devreye alınır.
    category_mode = normalize_crop_category_mode(opts.get("cropCategoryMode") or opts.get("crop_category_mode") or "mixed") if isinstance(opts, dict) else "mixed"
    hard_category_mode = category_mode in {"field_cereal", "forage", "legume", "vegetable", "industrial_oil", "orchard", "same_category"}
    orchard_guard_required = any(
        str(p.get("parcel_type", "") or "").strip().lower() == "orchard"
        or str(p.get("cok_yillik_kilit", "") or p.get("perennial_lock", "") or "").strip().lower().startswith(("e", "y"))
        or canonical_crop_key(str(p.get("current_crop", "") or p.get("crop", "") or "")) in PERENNIAL_CROPS
        for p in selected
    )
    prefer_matrix = (season_source != "s2") and (not two_season) and (scenario_type == "single")

    if prefer_matrix:
        try:
            matrix_out = optimize_from_excel_matrix(selected, algorithm, scenario, water_budget_ratio, year=year, options=options)
            if matrix_out is not None:
                matrix_out.setdefault("meta", {})["planner_mode"] = "matrix_category_guarded"
                matrix_out.setdefault("meta", {})["seasonSource"] = season_source
                matrix_out.setdefault("meta", {})["scenarioType"] = scenario_type
                matrix_out.setdefault("meta", {})["twoSeason"] = bool(two_season)
                if two_season:
                    matrix_out.setdefault("meta", {})["category_guard_note"] = "Kategori filtresi seçili olduğu için eski çift ürün fallback yerine kategori-korumalı karar hattı kullanıldı."
                return matrix_out
        except Exception:
            pass

    # Baseline totals
    total_water_current = sum(float(p.get("water_m3", 0) or 0) for p in selected)
    total_profit_current = sum(float(p.get("profit_tl", 0) or 0) for p in selected)
    if total_water_current <= 0:
        total_water_current = sum(float(p.get("area_da", 0) or 0) for p in selected) * 500.0
    if total_profit_current <= 0:
        total_profit_current = sum(float(p.get("area_da", 0) or 0) for p in selected) * 5000.0

    y = int(year) if year is not None else (available_years()[-1] if available_years() else 2024)

    # CURRENT scenario simply returns observed parcel summary
    if str(scenario).lower() in ("current","mevcut"):
        eff = (total_profit_current/total_water_current) if total_water_current>0 else 0.0
        return {
            "status": "OK",
            "algorithm": str(algorithm),
            "objective": "current",
            "year": y,
            "water_budget_m3": float(water_budget_for_year(y, selected)),
            "feasible": True,
            "total_water_m3": float(total_water_current),
            "total_profit_tl": float(total_profit_current),
            "efficiency_tl_per_m3": float(eff),
            "details": [{
                "parcelId": p["id"],
                "parcelName": p["name"],
                "chosenCrop": None,
                "area_da": float(p.get("area_da",0) or 0),
                "water_m3": float(p.get("water_m3",0) or 0),
                "profit_tl": float(p.get("profit_tl",0) or 0),
            } for p in selected],
            "meta": {"note":"current totals from parcel summary"}
        }

    # Supported optimization objectives:
    # - current / mevcut: observed baseline only
    # - water_efficiency: use available water effectively (maximize TL/m³ under constraints)
    # - max_profit: prioritize profit, but still apply realism / feasibility guards
    # - old balanced/recommended aliases are treated as water_efficiency
    obj_raw = str(scenario or objective or "water_efficiency").lower()
    if obj_raw in ("su_tasarruf", "su tasarruf", "water_saving", "tasarruf"):
        objective = "water_saving"
    elif obj_raw in ("water_efficiency", "su_verimliligi", "su verimliligi", "su_etkin", "su etkin", "balanced", "denge", "onerilen", "recommended"):
        objective = "water_efficiency"
    elif obj_raw in ("maks_kar", "maks kar", "max_profit", "kar", "kâr"):
        objective = "max_profit"
    elif obj_raw in ("mevcut", "current"):
        objective = "current"
    else:
        objective = "water_efficiency"


    # --- v51 CLEAN: Simple 2-crop optimizer (always on unless options.simpleMode==False) ---
    simple_mode = False
    if isinstance(options, dict) and ("simpleMode" in options):
        simple_mode = bool(options.get("simpleMode"))
    if simple_mode:
        catalog = load_crop_catalog()
        season_source = str((options or {}).get('seasonSource', 's1') or 's1').strip().lower()
        # --- Scenario-2: perennial lock + single-crop water-saving logic (farmer-friendly) ---
        # Scenario-2 "çok yıllık" ürün havuzu (normalize_crop_key ile normalize ediliyor).
        # Datasetlerde parantez/şapka/İ-Ş-Ğ vb. farklar olabildiği için hem TR hem normalize
        # varyantları ekliyoruz (örn. "BAĞ (ÜZÜM)" -> "BAG").
        SC2_PERENNIAL = [
            'ELMA',
            'KIRAZ','KİRAZ','VİŞNE','VISNE',
            'ARMUT','AYVA',
            'ŞEFTALİ','SEFTALI','NEKTARİN','NEKTARIN','KAYISI','ERIK','ERİK',
            'BAĞ','BAG','ÜZÜM','UZUM','UZUM_SOFRALIK','UZUM_SARAPLIK',
            'CEVIZ','CEVİZ','BADEM',
            'NAR','ZEYTIN','FISTIK','FINDIK','INCIR'
        ]
        SC2_ANNUAL = [
            'PATATES','SİLAJLIK MISIR','SILAJLIK MISIR','YONCA','BUĞDAY (DANE)','BUGDAY (DANE)','ŞEKER PANCARI','SEKER PANCARI'
        ]
        def _sc2_norm(x: str) -> str:
            try:
                return normalize_crop_key(str(x))
            except Exception:
                return str(x).strip().upper()
        SC2_PERENNIAL_N = set(_sc2_norm(x) for x in SC2_PERENNIAL)
        SC2_ANNUAL_N = set(_sc2_norm(x) for x in SC2_ANNUAL)
        def _ensure_catalog_key(key: str, default_water: float, default_profit: float):
            k = _sc2_norm(key)
            if k not in catalog:
                catalog[k] = {'water_per_da': float(default_water), 'profit_per_da': float(default_profit)}
        # Çok yıllık/bahçe ürünleri, kullanıcı S1 veya S2 seçse bile katalogda güvenli şekilde bulunabilmeli.
        # Aksi halde kullanıcı beyanıyla gelen mevcut kayısı/elma vb. ürünler basit modda yanlışlıkla yıllık ürüne çevrilebiliyordu.
        for k in SC2_PERENNIAL_N:
            _ensure_catalog_key(k, default_water=320.0, default_profit=9000.0)
        if season_source == 's2':
            # Conservative placeholder params for crops that may not exist in demo catalog.
            for k in SC2_ANNUAL_N:
                _ensure_catalog_key(k, default_water=520.0, default_profit=6500.0)
            # Also ensure a low-water legume option exists
            _ensure_catalog_key('NOHUT_KURU', default_water=260.0, default_profit=3200.0)
            _ensure_catalog_key('ARPA_KURU', default_water=220.0, default_profit=2600.0)
        # fixed crop pools for Senaryo-1 (DATA-DRIVEN)
        s1_rules = load_s1_crop_calendar_rules()
        _derived = (s1_rules or {}).get('_derived', {})
        season_map = _derived.get('season_map', {})
        irr_current_text_map = _derived.get('irr_current_text_map', {})
        primary_crops = [k for k in (s1_rules or {}).keys() if k != '_derived']
        secondary_crops = sorted({c for k in primary_crops for c in ((s1_rules.get(k, {}) or {}).get('secondary_options') or [])})
        if season_source == 's2':
            # Scenario-2 pool: perennial + specified annual field crops (single-crop by default).
            primary_crops = sorted(list(SC2_PERENNIAL_N | SC2_ANNUAL_N))
            secondary_crops = []
        fam_map = load_crop_family_map()
        irr_map = load_crop_irrigation_map()
        irr_eff = load_irrigation_methods()
        # Build current-crop map for locking perennials in Scenario-2.
        current_crop_map: Dict[str, str] = {}
        try:
            frames = load_enhanced_frames()
            seasons_df = frames.get('s2') if (season_source == 's2' and isinstance(frames.get('s2'), pd.DataFrame) and not frames.get('s2').empty) else frames.get('s1')
            if isinstance(seasons_df, pd.DataFrame) and not seasons_df.empty:
                dfy = seasons_df.copy()
                if 'year' in dfy.columns:
                    dfy = dfy[dfy['year'].apply(lambda v: safe_int(v, -1)) == y]
                if 'parcel_id' in dfy.columns:
                    dfy['parcel_id'] = dfy['parcel_id'].astype(str).str.strip()
                if 'crop' in dfy.columns:
                    dfy['crop'] = dfy['crop'].astype(str)
                if 'season' in dfy.columns:
                    prim = dfy[dfy['season'].astype(str).str.lower().str.contains('primary')]
                    if not prim.empty:
                        dfy = prim
                # take first record per parcel as 'current' crop in that year
                if 'parcel_id' in dfy.columns and 'crop' in dfy.columns:
                    current_crop_map = dfy.groupby('parcel_id')['crop'].first().to_dict()
        except Exception:
            current_crop_map = {}
        try:
            for p in selected:
                cc = str(p.get('current_crop', '') or '').strip()
                if cc:
                    current_crop_map[str(p.get('id'))] = cc
        except Exception:
            pass

        def _eff(method: str) -> float:
            if not method:
                return 1.0
            key = str(method).strip().lower()
            key = {"surface":"surface_furrow","furrow":"surface_furrow","salma":"surface_furrow","karik":"surface_furrow",
                   "sprinkler":"sprinkler","yagmurlama":"sprinkler",
                   "drip":"drip","damla":"drip",
                   "pivot":"sprinkler","rainfed":"rainfed","kuru":"rainfed"}.get(key, key)
            if key == "rainfed":
                return 1.0
            rec = irr_eff.get(key) or {}
            try:
                return float(rec.get("typical_total_efficiency") or rec.get("total_efficiency") or 1.0)
            except Exception:
                return 1.0

        def _adj_water(crop: str, water_m3_da: float) -> float:
            m = irr_map.get(crop) or {}
            cur = m.get("current")
            rec = m.get("recommended")
            ecur = _eff(cur)
            erec = _eff(rec)
            if erec <= 0: erec = 1.0
            if ecur <= 0: ecur = 1.0
            if erec > ecur + 1e-9:
                return float(water_m3_da) * (ecur/erec)
            return float(water_m3_da)

        def _soil_class_rank(soil_class: Any) -> int:
            """Return 1..8 where 1 is best soil. Unknown -> 3."""
            try:
                s = str(soil_class or "").strip().upper()
                if not s:
                    return 3
                # allow Roman numerals or digits
                roman = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8}
                if s in roman:
                    return roman[s]
                # sometimes like "1. SINIF" or "II. sınıf"
                for k, v in roman.items():
                    if k in s:
                        return v
                digits = "".join([ch for ch in s if ch.isdigit()])
                if digits:
                    v = int(digits[:1])
                    return max(1, min(8, v))
            except Exception:
                pass
            return 3

        # Rough, farmer-oriented suitability heuristics (no hidden data):
        # - Water-intensive vegetables/industrial crops prefer class I-II.
        # - Cereals/forage tolerate poorer soils.
        HIGH_INPUT = {
            "PATATES", "SEKER_PANCARI", "SALCALIK_DOMATES", "SOFRALIK_DOMATES",
            "SALCALIK_BIBER", "KAVUN", "KABAK_CEREZLIK", "SOGAN_KURU", "FASULYE_TAZE", "LAHANA_BEYAZ"
        }
        TOLERANT = {"BUGDAY_DANE", "ARPA_DANE", "CAVDAR_DANE", "YONCA_YESILOT", "SILAJLIK_MISIR"}

        def _parcel_suitability_bonus(crop: str, parcel: Optional[Dict[str, Any]]) -> float:
            if not parcel:
                return 0.0
            soil = (parcel.get("soil") or {}) if isinstance(parcel, dict) else {}
            rank = _soil_class_rank(soil.get("class"))
            key = normalize_crop_key(crop)
            # good soils: small bonus for high-input crops
            if rank <= 2:
                if key in HIGH_INPUT:
                    return 450.0
                return 80.0
            # medium soils: neutral
            if rank == 3:
                if key in HIGH_INPUT:
                    return 0.0
                return 40.0
            # poor soils: penalize high-input crops, slightly reward tolerant ones
            if key in HIGH_INPUT:
                return -650.0
            if key in TOLERANT:
                return 180.0
            return 0.0

        def _score(crop: str, parcel: Optional[Dict[str, Any]] = None) -> float:
            c = catalog.get(normalize_crop_key(crop)) or catalog.get(crop)
            if not c:
                return -1e18
            w = _adj_water(crop, float(c.get("water_m3_da", 0) or 0))
            p = float(c.get("net_profit_tl_da", 0) or 0)
            # Avoid suggesting loss-making crops unless nothing else exists.
            loss_penalty = 0.0
            if p < 0:
                loss_penalty = 2000.0 + abs(p) * 0.25
            bonus = _parcel_suitability_bonus(crop, parcel)

            # Conservative profit floor derived from the parcel's baseline.
            base_floor = 500.0
            try:
                if parcel:
                    area_da = float(parcel.get("area_da", 0) or 0)
                    base_profit = float(parcel.get("profit_tl", 0) or 0)
                    if area_da > 0 and base_profit > 0:
                        base_p_da = base_profit / area_da
                        base_floor = max(500.0, 0.15 * base_p_da)
            except Exception:
                pass
            profit_floor_penalty = 0.0
            if p < base_floor:
                profit_floor_penalty = (base_floor - p) * 0.55

            obj = str(objective or "balanced").lower()
            if obj == "max_profit":
                # Profit-first, but still discourage extremely thirsty or clearly loss-making crops.
                return (
                    (1.00 * p)
                    - (0.22 * w)
                    - (1.00 * loss_penalty)
                    - (0.30 * profit_floor_penalty)
                    + bonus
                )
            if obj == "balanced":
                return (
                    (0.72 * p)
                    - (0.55 * w)
                    - (0.90 * loss_penalty)
                    - (0.40 * profit_floor_penalty)
                    + bonus
                )
            # water_saving default
            return (
                (-w)
                + 0.0012 * max(p, 0.0)
                - 0.001 * loss_penalty
                - 0.004 * profit_floor_penalty
                + bonus
            )

        def pick_two(parcel: Dict[str, Any]) -> List[Dict[str, Any]]:
            """Pick (primary, secondary) for a given parcel with soil-aware scoring.

            Primary is chosen from the 15 Scenario-1 crops, but scoring is parcel-specific.
            Secondary is chosen from the rule-based secondary options for that primary.
            """
            area_da = float(parcel.get("area_da", 0) or 0)
            # deterministic tie-breaker per parcel to prevent every parcel becoming identical
            pid = str(parcel.get("id", ""))
            try:
                import hashlib
                h = int(hashlib.md5(pid.encode("utf-8")).hexdigest()[:8], 16)
            except Exception:
                h = 0

            # Çok yıllık/bahçe kuralı: kullanıcı S1 veya S2 seçse bile kurulmuş bahçede ana ürün korunur.
            # Kullanıcı beyanı (parsel düzeltmesi) varsa önce onu dikkate al, sonra veri setindeki mevcut ürüne düş.
            curr_raw = (
                parcel.get('current_crop')
                or parcel.get('currentCrop')
                or parcel.get('crop')
                or current_crop_map.get(pid)
                or current_crop_map.get(str(pid))
            )
            curr_key = _sc2_norm(curr_raw) if curr_raw else ''
            parcel_type = str(parcel.get('parcel_type', '') or '').strip().lower()
            perennial_flag = str(parcel.get('cok_yillik_kilit', '') or parcel.get('perennial_lock', '') or '').strip().lower()
            orchard_locked = (
                parcel_type == 'orchard'
                or perennial_flag.startswith('e')
                or perennial_flag.startswith('y')
                or (curr_key in SC2_PERENNIAL_N)
            )
            if orchard_locked and curr_key:
                rec = catalog.get(curr_key, {})
                w1 = float(rec.get('waterPerDa', rec.get('water_per_da', 320.0)) or 0.0)
                p1 = float(rec.get('profitPerDa', rec.get('profit_per_da', 9000.0)) or 0.0)
                return [{
                    'name': curr_key,
                    'area_da': area_da,
                    'water_m3_da': w1, 'waterPerDa': w1,
                    'profit_tl_da': p1, 'profitPerDa': p1,
                    'orchard_locked': True,
                    'decision_note': 'Kurulu bahçe/çok yıllık parsel: ana ürün korunur; iyileştirme sulama ve yönetim üzerinden yapılır.'
                }]

            if season_source == 's2':
                # For field-crop parcels in Scenario-2, water-saving should be single-crop and low-water oriented.
                primary_pool = sorted(list(SC2_ANNUAL_N)) if SC2_ANNUAL_N else primary_crops
            else:
                primary_pool = primary_crops
            forced_primary = None if season_source == 's2' else parcel.get("_forced_primary")
            if forced_primary:
                c1 = str(forced_primary)
            else:
                scores = [(c, _score(c, parcel)) for c in primary_pool]
                # tie-breaker: parcel hash adds slight deterministic noise to avoid identical picks
                scores.sort(key=lambda x: (x[1], (h % 997) / 997.0), reverse=True)
                c1 = scores[0][0] if scores else (primary_pool[0] if primary_pool else "")
            fam1 = fam_map.get(normalize_crop_key(c1))
            cand2 = [] if season_source == 's2' else ((s1_rules.get(c1, {}) or {}).get('secondary_options') or [])
            best2 = None
            best2_score = -1e18
            pool2 = cand2 if cand2 else secondary_crops
            for c2 in pool2:
                if fam1 and fam_map.get(normalize_crop_key(c2)) == fam1:
                    continue
                sc = _score(c2, parcel)
                if sc > best2_score:
                    best2_score = sc
                    best2 = c2
            crops = []
            a1 = area_da * 0.75
            a2 = area_da - a1
            c1_rec = catalog.get(normalize_crop_key(c1)) or {}
            w1 = _adj_water(c1, float(c1_rec.get("waterPerDa", c1_rec.get("water_m3_da",0)) or 0))
            p1 = float(c1_rec.get("profitPerDa", c1_rec.get("net_profit_tl_da",0)) or 0)
            crops.append({"name": c1, "area_da": a1, "water_m3_da": w1, "waterPerDa": w1, "profit_tl_da": p1, "profitPerDa": p1})
            if best2:
                c2_rec = catalog.get(normalize_crop_key(best2)) or {}
                w2 = _adj_water(best2, float(c2_rec.get("waterPerDa", c2_rec.get("water_m3_da",0)) or 0))
                p2 = float(c2_rec.get("profitPerDa", c2_rec.get("net_profit_tl_da",0)) or 0)
                crops.append({"name": best2, "area_da": a2, "water_m3_da": w2, "waterPerDa": w2, "profit_tl_da": p2, "profitPerDa": p2})
            return crops

        # --- Basin-level diversity guard ---
        # Simple mode was previously choosing the *same* best primary for every parcel (global optimum).
        # Here we assign primaries across parcels with a soft per-crop cap to produce diverse, realistic
        # suggestions while still maximizing the objective.
        # Determine a soft cap for how many parcels can get the same primary.
        # With 15 parcels and 15 primaries, this typically becomes 1–3.
        try:
            import math
            if len(primary_crops) >= len(selected) and len(selected) > 0:
                cap = 1  # one primary per parcel for Scenario-1 diversity
            else:
                cap = max(1, int(math.ceil(len(selected) * 0.25)))
        except Exception:
            cap = 3
        if season_source == 's2':
            # In Scenario-2 we allow the same best crop across many parcels (water-saving realism).
            cap = len(selected) + 999
        primary_count: Dict[str, int] = {normalize_crop_key(c): 0 for c in primary_crops}

        # Rank primaries for each parcel (parcel-specific scoring)
        ranked: Dict[str, List[str]] = {}
        for pr in selected:
            pid = str(pr.get("id"))
            sc = [(c, _score(c, pr)) for c in primary_crops]
            sc.sort(key=lambda x: x[1], reverse=True)
            ranked[pid] = [c for c, _ in sc]

        # Assign primaries greedily by larger parcels first.
        selected_sorted = sorted(selected, key=lambda pr: float(pr.get("area_da", 0) or 0), reverse=True)
        for pr in selected_sorted:
            pid = str(pr.get("id"))
            choice = None
            for c in ranked.get(pid, primary_crops):
                k = normalize_crop_key(c)
                if primary_count.get(k, 0) < cap:
                    choice = c
                    break
            if choice is None:
                choice = ranked.get(pid, primary_crops)[0] if ranked.get(pid) else (primary_crops[0] if primary_crops else "")
            primary_count[normalize_crop_key(choice)] = primary_count.get(normalize_crop_key(choice), 0) + 1
            pr["_forced_primary"] = choice

        parcels_out = []
        details_out = []
        tot_w = 0.0
        tot_p = 0.0
        for p in selected:
            crops = pick_two(p)
            rec_list = []
            for c in crops:
                area = float(c["area_da"])
                w_per = float(c["water_m3_da"])
                prof_per = float(c["profit_tl_da"])
                tot = area * w_per
                tprof = area * prof_per
                tot_w += tot
                tot_p += tprof
                row = {
                    "name": c["name"],
                    "area": area,
                    "waterPerDa": w_per,
                    "profitPerDa": prof_per,
                    "totalWater": tot,
                    "totalProfit": tprof,
                    "irrigation": irr_map.get(c["name"], {}),
                    "orchardLocked": bool(c.get('orchard_locked')),
                    "decisionNote": c.get('decision_note')
                }
                rec_list.append(row)
                details_out.append({
                    "parcelId": p.get("id"),
                    "parcelName": p.get("name") or p.get("id"),
                    "chosenCrop": c.get("name"),
                    "area_da": area,
                    "water_m3": tot,
                    "profit_tl": tprof,
                })
            parcels_out.append({"id": p["id"], "result": {"recommended": rec_list}})
        eff2 = (tot_p/tot_w) if tot_w>0 else 0.0
        return {
            "status":"OK",
            "algorithm": str(algorithm),
            "objective": objective,
            "year": y,
            "water_budget_m3": float(water_budget_for_year(y, selected)) * float(water_budget_ratio or 1.0),
            "total_water_m3": float(tot_w),
            "total_profit_tl": float(tot_p),
            "efficiency_tl_per_m3": float(eff2),
            "parcels": parcels_out,
            "details": details_out,
            "meta":{"mode":"simple_v52","note":"Bahçe/çok yıllık parseller tüm modlarda ana ürünü korur; su verimliliği ve kâr birlikte puanlanır."}
        }

    algo = str(algorithm or "GA").upper()

    env_flow_ratio = float(opts.get("envFlowRatio", 0.10)) if isinstance(opts, dict) else 0.10
    irrigation_method = (str(opts.get("irrigationMethod")) if isinstance(opts, dict) and opts.get("irrigationMethod") else None)
    enforce_delivery_caps = bool(opts.get("enforceDeliveryCaps", True)) if isinstance(opts, dict) else True

    water_model = str(opts.get("waterModel", "calib")) if isinstance(opts, dict) else "calib"
    risk_mode = str(opts.get("riskMode", "none")) if isinstance(opts, dict) else "none"
    risk_lambda = float(opts.get("riskLambda", 0.0)) if isinstance(opts, dict) else 0.0
    risk_samples = int(opts.get("riskSamples", 120)) if isinstance(opts, dict) else 120
    water_quality_filter = bool(opts.get("waterQualityFilter", True)) if isinstance(opts, dict) else True

    min_unique_crops = int(opts.get("minUniqueCrops", 2 if two_season else 1)) if isinstance(opts, dict) else (2 if two_season else 1)
    max_share_per_crop = opts.get("maxSharePerCrop", 0.75 if two_season else 0.85) if isinstance(opts, dict) else (0.75 if two_season else 0.85)

    # --- Run the requested optimizer (GA/ABC/ACO) ---
    if algo == "GA":
        raw = ga_optimize_two_season(
            selected_parcels=selected,
            year=y,
            objective=objective,
            pop_size=int(opts.get("popSize", 60)),
            generations=int(opts.get("generations", 140)),
            cx_rate=float(opts.get("cxRate", 0.7)),
            mut_rate=float(opts.get("mutRate", 0.08)),
            seed=opts.get("seed", None),
            budget_ratio=float(water_budget_ratio or 1.0),
            season_source=season_source,
            env_flow_ratio=env_flow_ratio,
            irrigation_method=irrigation_method,
            enforce_delivery_caps=enforce_delivery_caps,
            min_unique_crops=min_unique_crops,
            max_share_per_crop=float(max_share_per_crop),
            water_model=water_model,
            risk_mode=risk_mode,
            risk_lambda=risk_lambda,
            risk_samples=risk_samples,
            water_quality_filter=water_quality_filter,
        )
        if not two_season:
            # caller explicitly requested single-season mode
            raw = ga_optimize(
                selected_parcels=selected,
                year=y,
                objective=objective,
                pop_size=int(opts.get("popSize", 60)),
                generations=int(opts.get("generations", 120)),
                cx_rate=float(opts.get("cxRate", 0.7)),
                mut_rate=float(opts.get("mutRate", 0.08)),
                seed=opts.get("seed", None),
                budget_ratio=float(water_budget_ratio or 1.0),
                season_source=season_source,
                env_flow_ratio=env_flow_ratio,
                irrigation_method=irrigation_method,
                enforce_delivery_caps=enforce_delivery_caps,
            )
        # v72: Attach run parameters for transparent & fair comparison in UI
        try:
            raw.setdefault("meta", {})["run_params"] = {
                "algorithm": "GA",
                "seed": opts.get("seed", None),
                "twoSeason": bool(two_season),
                "generations": int(opts.get("generations", 140)),
                "popSize": int(opts.get("popSize", 60)),
                "cxRate": float(opts.get("cxRate", 0.7)),
                "mutRate": float(opts.get("mutRate", 0.08)),
                "budgetRatio": float(water_budget_ratio or 1.0),
                "seasonSource": season_source,
                "scenarioType": scenario_type,
                "envFlowRatio": float(env_flow_ratio),
                "irrigationMethod": irrigation_method,
                "waterModel": water_model,
                "riskMode": risk_mode,
                "riskLambda": float(risk_lambda),
                "riskSamples": int(risk_samples),
            }
        except Exception:
            pass
        return _to_ui_payload(raw, selected, y, objective, season_source, env_flow_ratio=env_flow_ratio, irrigation_method=irrigation_method, enforce_delivery_caps=enforce_delivery_caps, water_model=water_model, risk_mode=risk_mode, risk_lambda=risk_lambda, risk_samples=risk_samples, water_quality_filter=water_quality_filter)

    if algo == "ABC":
        raw = (abc_optimize_two_season(
            selected_parcels=selected,
            year=y,
            objective=objective,
            food_sources=int(opts.get("foodSources", 40)),
            cycles=int(opts.get("cycles", 120)),
            limit=int(opts.get("limit", 25)),
            seed=opts.get("seed", None),
            budget_ratio=float(water_budget_ratio or 1.0),
            season_source=season_source,
            env_flow_ratio=env_flow_ratio,
            irrigation_method=irrigation_method,
            enforce_delivery_caps=enforce_delivery_caps,
            min_unique_crops=min_unique_crops,
            max_share_per_crop=float(max_share_per_crop),
            water_model=water_model,
            risk_mode=risk_mode,
            risk_lambda=risk_lambda,
            risk_samples=risk_samples,
            water_quality_filter=water_quality_filter,
        ) if two_season else abc_optimize(
            selected_parcels=selected,
            year=y,
            objective=objective,
            food_sources=int(opts.get("foodSources", 40)),
            cycles=int(opts.get("cycles", 120)),
            limit=int(opts.get("limit", 25)),
            seed=opts.get("seed", None),
            budget_ratio=float(water_budget_ratio or 1.0),
            season_source=season_source,
            env_flow_ratio=env_flow_ratio,
            irrigation_method=irrigation_method,
            enforce_delivery_caps=enforce_delivery_caps,
            min_unique_crops=min_unique_crops,
            max_share_per_crop=float(max_share_per_crop),
            water_model=water_model,
            risk_mode=risk_mode,
            risk_lambda=risk_lambda,
            risk_samples=risk_samples,
            water_quality_filter=water_quality_filter,
        ))
        try:
            raw.setdefault("meta", {})["run_params"] = {
                "algorithm": "ABC",
                "seed": opts.get("seed", None),
                "twoSeason": bool(two_season),
                "cycles": int(opts.get("cycles", 120)),
                "foodSources": int(opts.get("foodSources", 40)),
                "limit": int(opts.get("limit", 25)),
                "budgetRatio": float(water_budget_ratio or 1.0),
                "seasonSource": season_source,
                "scenarioType": scenario_type,
                "envFlowRatio": float(env_flow_ratio),
                "irrigationMethod": irrigation_method,
                "waterModel": water_model,
                "riskMode": risk_mode,
                "riskLambda": float(risk_lambda),
                "riskSamples": int(risk_samples),
            }
        except Exception:
            pass
        return _to_ui_payload(raw, selected, y, objective, season_source, env_flow_ratio=env_flow_ratio, irrigation_method=irrigation_method, enforce_delivery_caps=enforce_delivery_caps, water_model=water_model, risk_mode=risk_mode, risk_lambda=risk_lambda, risk_samples=risk_samples, water_quality_filter=water_quality_filter)

    if algo == "ACO":
        raw = (aco_optimize_two_season(
            selected_parcels=selected,
            year=y,
            objective=objective,
            ants=int(opts.get("ants", 40)),
            iterations=int(opts.get("iterations", 120)),
            rho=float(opts.get("rho", 0.25)),
            q=float(opts.get("q", 1.0)),
            seed=opts.get("seed", None),
            budget_ratio=float(water_budget_ratio or 1.0),
            season_source=season_source,
            env_flow_ratio=env_flow_ratio,
            irrigation_method=irrigation_method,
            enforce_delivery_caps=enforce_delivery_caps,
            min_unique_crops=min_unique_crops,
            max_share_per_crop=float(max_share_per_crop),
        ) if two_season else aco_optimize(
            selected_parcels=selected,
            year=y,
            objective=objective,
            ants=int(opts.get("ants", 40)),
            iterations=int(opts.get("iterations", 120)),
            rho=float(opts.get("rho", 0.25)),
            q=float(opts.get("q", 1.0)),
            seed=opts.get("seed", None),
            budget_ratio=float(water_budget_ratio or 1.0),
            season_source=season_source,
            env_flow_ratio=env_flow_ratio,
            irrigation_method=irrigation_method,
            enforce_delivery_caps=enforce_delivery_caps,
            min_unique_crops=min_unique_crops,
            max_share_per_crop=float(max_share_per_crop),
        ))
        try:
            raw.setdefault("meta", {})["run_params"] = {
                "algorithm": "ACO",
                "seed": opts.get("seed", None),
                "twoSeason": bool(two_season),
                "iterations": int(opts.get("iterations", 120)),
                "ants": int(opts.get("ants", 40)),
                "rho": float(opts.get("rho", 0.25)),
                "q": float(opts.get("q", 1.0)),
                "budgetRatio": float(water_budget_ratio or 1.0),
                "seasonSource": season_source,
                "scenarioType": scenario_type,
                "envFlowRatio": float(env_flow_ratio),
                "irrigationMethod": irrigation_method,
                "waterModel": water_model,
                "riskMode": risk_mode,
                "riskLambda": float(risk_lambda),
                "riskSamples": int(risk_samples),
            }
        except Exception:
            pass
        return _to_ui_payload(raw, selected, y, objective, season_source, env_flow_ratio=env_flow_ratio, irrigation_method=irrigation_method, enforce_delivery_caps=enforce_delivery_caps, water_model=water_model, risk_mode=risk_mode, risk_lambda=risk_lambda, risk_samples=risk_samples, water_quality_filter=water_quality_filter)

    # Unknown algorithm -> GA fallback
    raw = ga_optimize(
        selected_parcels=selected,
        year=y,
        objective=objective,
        pop_size=40,
        generations=80,
        budget_ratio=float(water_budget_ratio or 1.0),
        season_source=season_source,
    )
    raw["algorithm"] = algo
    raw.setdefault("meta", {})["note"] = "Unknown algorithm; used GA fallback"
    return _to_ui_payload(raw, selected, y, objective, season_source, env_flow_ratio=env_flow_ratio, irrigation_method=irrigation_method, enforce_delivery_caps=enforce_delivery_caps, water_model=water_model, risk_mode=risk_mode, risk_lambda=risk_lambda, risk_samples=risk_samples, water_quality_filter=water_quality_filter)



def _to_ui_payload(raw: Dict[str, Any], selected_parcels: List[Dict[str, Any]], year: int, objective: str, season_source: str,
                   env_flow_ratio: float = 0.10, irrigation_method: Optional[str] = None, enforce_delivery_caps: bool = True,
                   water_model: str = "calib", risk_mode: str = "none", risk_lambda: float = 0.0, risk_samples: int = 120,
                   water_quality_filter: bool = True) -> Dict[str, Any]:
    """Convert optimizer output into the UI-friendly response.

    Key fixes vs older versions:
      - Tek bir yerden ( _build_two_crop_recommendations ) 1. ürün + 2. ürün önerisi üretilir.
      - Senaryo-2 bahçe/perennial kilitleri burada da tutarlı şekilde uygulanır.
      - Ürün aileleri (crop_family) ile 1. ve 2. ürünün aynı familyadan olmaması tercih edilir.
      - Suitability (LCC x crop) kâr/da değerine çarpan olarak uygulanır (build_candidate_matrix içinde).

    Not: Buradaki 2 ürün, "aynı yıl içinde iki farklı ekim" yaklaşımını temsil eder. 
    Ön yüz aynı anda alan bölüştürme gibi gösterse bile, arka tarafta "su/kâr" hesabı şeffaftır:
      su = Σ(area1*water1 + area2*water2), kâr = Σ(area1*profit1 + area2*profit2).
    """
    # Build candidate matrices (this already applies suitability)
    crop_list, _, _ = build_candidate_matrix(selected_parcels, year=year, season_source=season_source)
    idx = {c:i for i,c in enumerate(crop_list)}

    # Map raw choices -> index array (optional)
    chosen = None
    try:
        chosen = np.full((len(selected_parcels),), -1, dtype=int)
        details = raw.get("details") or []
        by_pid = {str(d.get("parcelId")): d for d in details if d.get("parcelId") is not None}
        for i, p in enumerate(selected_parcels):
            d = by_pid.get(str(p.get("id")))
            ck = (d or {}).get("chosenCrop")
            if ck in idx:
                chosen[i] = int(idx[ck])
        if np.all(chosen < 0):
            chosen = None
    except Exception:
        chosen = None

    # If optimizer ran in two-season mode, build a real primary+secondary plan.
    if str(raw.get("mode") or "").lower() == "two_season":
        # derive arrays from raw.details
        crop_list, _, _, _, _, _, _ = build_candidate_matrix_two_season(selected_parcels, year=year, season_source=season_source)
        idx = {c: i for i, c in enumerate(crop_list)}
        ch1 = np.zeros((len(selected_parcels),), dtype=int)
        ch2 = np.zeros((len(selected_parcels),), dtype=int)
        by_pid = {str(d.get("parcelId")): d for d in (raw.get("details") or [])}
        for i, p in enumerate(selected_parcels):
            d = by_pid.get(str(p.get("id")), {})
            # Support both schema variants:
            #  1) {primary:{crop:..}, secondary:{crop:..}}
            #  2) {chosenPrimary:.., chosenSecondary:..}
            c1 = None
            c2 = None
            if isinstance(d.get("primary"), dict):
                c1 = d.get("primary", {}).get("crop")
            if isinstance(d.get("secondary"), dict):
                c2 = d.get("secondary", {}).get("crop")
            if c1 is None:
                c1 = d.get("chosenPrimary")
            if c2 is None:
                c2 = d.get("chosenSecondary")
            ch1[i] = int(idx.get(c1, 0))
            ch2[i] = int(idx.get(c2, 0))
        rec_pack = _build_two_season_recommendations(
            selected_parcels=selected_parcels,
            year=int(year),
            objective=objective,
            season_source=season_source,
            env_flow_ratio=env_flow_ratio,
            irrigation_method=irrigation_method,
            enforce_delivery_caps=enforce_delivery_caps,
            chosen_primary=ch1,
            chosen_secondary=ch2,
            budget_ratio=float(raw.get("budget_ratio", 1.0) or 1.0),
            water_model=water_model,
            risk_mode=risk_mode,
            risk_lambda=risk_lambda,
            risk_samples=risk_samples,
            water_quality_filter=water_quality_filter,
        )
    else:
        # Fallback: heuristic two-product suggestion.
        rec_pack = _build_two_crop_recommendations(
            selected_parcels=selected_parcels,
            year=int(year),
            objective=objective,
            season_source=season_source,
            env_flow_ratio=env_flow_ratio,
            irrigation_method=irrigation_method,
            enforce_delivery_caps=enforce_delivery_caps,
            chosen=(chosen if chosen is not None else None),
            budget_ratio=float(raw.get("budget_ratio", 1.0) or 1.0),
            water_model=water_model,
            risk_mode=risk_mode,
            risk_lambda=risk_lambda,
            risk_samples=risk_samples,
            water_quality_filter=water_quality_filter,
        )

    parcels_out = []
    for pr in rec_pack["parcels"]:
        parcels_out.append({"id": pr["id"], "result": pr["result"]})

    budget = float(rec_pack.get("budget") or 0.0)
    total_water = float(rec_pack.get("totals", {}).get("water", 0.0))
    total_profit = float(rec_pack.get("totals", {}).get("profit", 0.0))
    feasible = bool(rec_pack.get("feasible", True))
    eff = float(total_profit/total_water) if total_water > 0 else 0.0
    delivery_report = rec_pack.get('delivery_report') if isinstance(rec_pack, dict) else None

    # v72: Baseline + delta (same units as UI output)
    base_water = sum(float(p.get("water_m3", 0) or 0) for p in selected_parcels)
    base_profit = sum(float(p.get("profit_tl", 0) or 0) for p in selected_parcels)
    if base_water <= 0:
        base_water = sum(float(p.get("area_da", 0) or 0) for p in selected_parcels) * 500.0
    if base_profit <= 0:
        base_profit = sum(float(p.get("area_da", 0) or 0) for p in selected_parcels) * 5000.0
    base_eff = (base_profit/base_water) if base_water > 0 else 0.0
    d_water = float(total_water - base_water)
    d_profit = float(total_profit - base_profit)
    d_eff = float(eff - base_eff)

    return {
        "status": "OK",
        "algorithm": str(raw.get("algorithm") or "GA"),
        "objective": objective,
        "year": int(year),
        "water_budget_m3": float(budget),
        "feasible": feasible,
        "total_water_m3": float(total_water),
        "total_profit_tl": float(total_profit),
        "efficiency_tl_per_m3": float(eff),
        "baseline": {
            "total_water_m3": float(base_water),
            "total_profit_tl": float(base_profit),
            "efficiency_tl_per_m3": float(base_eff),
        },
        "delta": {
            "water_m3": float(d_water),
            "profit_tl": float(d_profit),
            "efficiency_tl_per_m3": float(d_eff),
        },
        "parcels": parcels_out,
        "details": raw.get("details", []),
        "meta": {
            **(raw.get("meta") or {}),
            "selected_parcel_ids": [str(p.get("id")) for p in (selected_parcels or [])],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "delivery_report": delivery_report,
            "season_source": season_source,
            "formulas": {
                "water_m3": "Σ(area_da * waterPerDa) (1. ürün + 2. ürün)",
                "profit_tl": "Σ(area_da * profitPerDa) (1. ürün + 2. ürün)",
                "efficiency": "total_profit_tl / total_water_m3",
                "score": "alpha*profitPerDa - beta*waterPerDa",
                "suitability": "profitPerDa = profitPerDa * suitability(LCC, crop)",
            },
            "note": "İkinci ürün seçiminde aynı ürün ailesinden (crop_family) kaçınma + baklagil (Fabaceae) küçük teşvik bonusu eklendi."
        }
    }

def _standard_objective_mode(value: Any) -> str:
    obj = str(value or "balanced").strip().lower()
    if obj in ("current", "mevcut", "reference", "referans"):
        return "current"
    if obj in ("water_saving", "su_tasarruf", "su tasarruf", "tasarruf"):
        return "water_saving"
    if obj in ("max_profit", "maks_kar", "maks kar", "profit", "kar"):
        return "max_profit"
    if obj in ("balanced", "water_efficiency", "su_etkin", "su etkin", "su_verimliligi", "recommended", "onerilen"):
        return "balanced"
    return obj or "balanced"


def _standard_scenario_type(options: Dict[str, Any], payload_meta: Dict[str, Any]) -> str:
    opt = options if isinstance(options, dict) else {}
    meta = payload_meta if isinstance(payload_meta, dict) else {}
    raw = str(opt.get("scenarioType") or meta.get("scenarioType") or "").strip().lower()
    season_source = str(opt.get("seasonSource") or meta.get("seasonSource") or "").strip().lower()
    two_season = bool(opt.get("twoSeason") or meta.get("twoSeason"))
    if season_source == "s2" or two_season or raw in ("double", "iki", "cift", "çift", "desen"):
        return "double"
    return "single"


def _safe_text(value: Any, default: str = "") -> str:
    txt = str(value if value is not None else default).strip()
    return txt if txt else default


def _row_name(row: Dict[str, Any]) -> str:
    return _safe_text(row.get("name") or row.get("crop") or row.get("chosenCrop") or row.get("crop_name"))


def _row_water(row: Dict[str, Any]) -> float:
    return safe_float(row.get("waterTotal", row.get("totalWater", row.get("water_m3", 0.0))), 0.0)


def _row_profit(row: Dict[str, Any]) -> float:
    return safe_float(row.get("profitTotal", row.get("totalProfit", row.get("profit_tl", 0.0))), 0.0)


def _row_area(row: Dict[str, Any]) -> float:
    return safe_float(row.get("area", row.get("area_da", row.get("plannedAreaDa", 0.0))), 0.0)


def _row_quota_m3(row: Dict[str, Any]) -> float:
    return safe_float(row.get("parcelQuotaM3", row.get("quota_m3", row.get("current_quota_m3", 0.0))), 0.0)


def _row_feasible(row: Dict[str, Any], plan_feasible: bool = True) -> bool:
    water = _row_water(row)
    quota = _row_quota_m3(row)
    quota_ok = True if quota <= 0 else water <= quota + 1e-6
    explicit = row.get("fullFeasible", row.get("quota_ok", row.get("feasible", None)))
    if explicit is None:
        return bool(plan_feasible and quota_ok)
    if explicit is False and bool(row.get("quotaAdjusted", row.get("quota_adjusted", False))) and _row_area(row) > 0:
        return bool(plan_feasible and quota_ok)
    return bool(explicit) and bool(quota_ok) and bool(plan_feasible)


def _is_fallow_name(name: str) -> bool:
    return normalize_crop_key(name) in {normalize_crop_key(FALLOW), "nadas", "fallow", ""}


def _standard_close_crop_key(name: str) -> str:
    compact = canonical_crop_key(name)
    for token in ("KURU", "YAS", "TAZE", "SULU"):
        compact = compact.replace(token, "")
    return compact


def _standard_crops_too_close(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return _standard_close_crop_key(a) == _standard_close_crop_key(b)


def _objective_mode_label_tr(mode: str) -> str:
    return {
        "current": "Mevcut",
        "water_saving": "Su tasarrufu",
        "max_profit": "Kar odakli",
        "balanced": "Su-kar dengesi",
        "water_efficiency": "Su-kar dengesi",
    }.get(str(mode or "").strip().lower(), str(mode or "Secili hedef"))


def _standard_crop_from_row(row: Dict[str, Any], parcel: Dict[str, Any], role: str, plan_feasible: bool) -> Dict[str, Any]:
    area = _row_area(row)
    parcel_area = safe_float((parcel or {}).get("area_da", area), area)
    water = _row_water(row)
    profit = _row_profit(row)
    quota = _row_quota_m3(row)
    feasible = _row_feasible(row, plan_feasible=plan_feasible)
    warnings = []
    if quota > 0 and water > quota + 1e-6:
        warnings.append("Parsel su kotasini asiyor; secilebilir degil.")
    if not _safe_text(row.get("planting_date") or row.get("ekim_tarihi") or row.get("harvest_date") or row.get("hasat_tarihi")):
        warnings.append("Takvim verisi eksik; ekim-hasat cakismasi veriyle dogrulanamadi.")
    return {
        "parcel_id": _safe_text((parcel or {}).get("id") or (parcel or {}).get("parcel_id")),
        "crop_name": _row_name(row),
        "name": _row_name(row),
        "role": role,
        "season": _safe_text(row.get("season") or row.get("season_label") or "Belirtilmedi"),
        "planting_date": _safe_text(row.get("planting_date") or row.get("ekim_tarihi")),
        "harvest_date": _safe_text(row.get("harvest_date") or row.get("hasat_tarihi")),
        "period_note": _safe_text(row.get("period_note") or row.get("season")),
        "area_da": float(area),
        "area_share_pct": float((area / parcel_area) * 100.0) if parcel_area > 0 else 0.0,
        "water_m3": float(water),
        "profit_tl": float(profit),
        "tl_per_m3": float(profit / water) if water > 0 else 0.0,
        "irrigation_method": _safe_text(row.get("irrigationSuggestedKey") or row.get("irrigationRecommended") or row.get("irrigationCurrentKey")),
        "quota_m3": float(quota),
        "quota_status": "Uygun" if feasible else "Kota/uygunluk riski var",
        "feasible": bool(feasible),
        "selectable": bool(feasible),
        "warnings": warnings,
        "explanation": _safe_text(row.get("reason") or row.get("decisionNote") or row.get("rankReason")),
    }


def _scale_candidate_to_area(candidate: Dict[str, Any], target_area: float) -> Dict[str, Any]:
    out = dict(candidate or {})
    src_area = safe_float(out.get("area_da", 0.0), 0.0)
    target = max(0.0, safe_float(target_area, src_area))
    wpd = safe_float(out.get("water_m3", 0.0), 0.0) / max(1e-9, src_area)
    ppd = safe_float(out.get("profit_tl", 0.0), 0.0) / max(1e-9, src_area)
    out["area_da"] = float(target)
    out["water_m3"] = float(wpd * target)
    out["profit_tl"] = float(ppd * target)
    out["tl_per_m3"] = float(out["profit_tl"] / out["water_m3"]) if out["water_m3"] > 0 else 0.0
    out["area_share_pct"] = safe_float(out.get("area_share_pct", 100.0), 100.0)
    return out


def repair_plan_for_diversity(plan_rows: List[Dict[str, Any]], candidate_rows: List[Dict[str, Any]],
                              diversity_config: Optional[Dict[str, Any]] = None,
                              water_budget_m3: Optional[float] = None) -> Dict[str, Any]:
    cfg = _diversity_config(diversity_config)
    if not bool(cfg.get("enabled", True)) or not bool(cfg.get("repair_enabled", True)):
        metrics = compute_diversity_metrics(plan_rows, 0.0, cfg)
        return {"plan_rows": plan_rows, "metrics": metrics, "repair_applied": False, "warnings": []}

    rows = [dict(r) for r in (plan_rows or [])]
    candidates = [dict(c) for c in (candidate_rows or []) if isinstance(c, dict)]
    budget = safe_float(water_budget_m3, 0.0)
    repair_warnings: List[str] = []
    max_repair_iterations = 20
    max_candidate_checks_per_parcel = 10
    max_total_replacements = 40
    max_iter = min(max_repair_iterations, max(4, len(rows) * 2))
    applied = False
    improved = False
    replacements = 0

    def _tot_water(items: List[Dict[str, Any]]) -> float:
        return float(sum(safe_float(x.get("water_m3", 0.0), 0.0) for x in items))

    metrics = compute_diversity_metrics(rows, 0.0, cfg)
    start_penalty = safe_float(metrics.get("diversity_penalty", 0.0), 0.0)

    for _ in range(max_iter):
        metrics = compute_diversity_metrics(rows, 0.0, cfg)
        top_crop = metrics.get("top_crop")
        if not top_crop or safe_float(metrics.get("top_crop_share", 0.0), 0.0) <= safe_float(cfg.get("max_crop_share", 0.25), 0.25) + 1e-9:
            break
        best_move = None
        current_water = _tot_water(rows)
        current_penalty = safe_float(metrics.get("diversity_penalty", 0.0), 0.0)
        for idx, old in enumerate(rows):
            old_name = _crop_name_for_diversity(old.get("crop_name") or old.get("name"))
            if normalize_crop_key(old_name) != normalize_crop_key(str(top_crop)):
                continue
            parcel_id = str(old.get("parcel_id") or "").strip()
            old_area = safe_float(old.get("area_da", 0.0), 0.0)
            old_water = safe_float(old.get("water_m3", 0.0), 0.0)
            old_profit = safe_float(old.get("profit_tl", 0.0), 0.0)
            checked_for_parcel = 0
            for cand in candidates:
                if checked_for_parcel >= max_candidate_checks_per_parcel:
                    break
                cand_name = _crop_name_for_diversity(cand.get("crop_name") or cand.get("name"))
                if not cand_name or normalize_crop_key(cand_name) == FALLOW:
                    continue
                if normalize_crop_key(cand_name) == normalize_crop_key(old_name):
                    continue
                if parcel_id and str(cand.get("parcel_id") or "").strip() != parcel_id:
                    continue
                if not bool(cand.get("feasible", True)) or not bool(cand.get("selectable", True)):
                    continue
                checked_for_parcel += 1
                new_row = _scale_candidate_to_area(cand, old_area)
                new_water_total = current_water - old_water + safe_float(new_row.get("water_m3", 0.0), 0.0)
                if budget > 0 and new_water_total > budget + 1e-6:
                    continue
                trial = rows[:idx] + [new_row] + rows[idx + 1:]
                trial_metrics = compute_diversity_metrics(trial, 0.0, cfg)
                trial_penalty = safe_float(trial_metrics.get("diversity_penalty", 0.0), 0.0)
                if trial_penalty >= current_penalty - 1e-12:
                    continue
                profit_loss = max(0.0, old_profit - safe_float(new_row.get("profit_tl", 0.0), 0.0))
                water_increase = max(0.0, safe_float(new_row.get("water_m3", 0.0), 0.0) - old_water)
                score = ((current_penalty - trial_penalty) * 1.0e9) - profit_loss - (10.0 * water_increase)
                move = (score, idx, [new_row], trial_metrics, old_name, cand_name)
                if best_move is None or move[0] > best_move[0]:
                    best_move = move
        if best_move is None:
            repair_warnings.append(f"{top_crop} için çeşitlilik sınırını iyileştirecek uygulanabilir alternatif bulunamadı.")
            break
        _score, idx, replacement_rows, new_metrics, old_name, cand_name = best_move
        rows = rows[:idx] + replacement_rows + rows[idx + 1:]
        replacements += 1
        applied = True
        metrics = new_metrics
        if safe_float(metrics.get("diversity_penalty", 0.0), 0.0) < start_penalty - 1e-12:
            improved = True
        repair_warnings.append(
            f"Ürün çeşitliliği kısıtı nedeniyle {old_name} yerine {cand_name} seçilerek plan yeniden dengelendi."
        )
        if replacements >= max_total_replacements:
            repair_warnings.append("Çeşitlilik onarımı güvenli işlem sınırına ulaştığı için durduruldu.")
            break
        if bool(metrics.get("diversity_feasible", False)):
            break
    if max_iter >= max_repair_iterations and not bool(metrics.get("diversity_feasible", False)):
        repair_warnings.append("Çeşitlilik onarımı maksimum iterasyon sınırına ulaştığı için durduruldu.")

    final_metrics = compute_diversity_metrics(rows, 0.0, cfg)
    return {
        "plan_rows": rows,
        "metrics": final_metrics,
        "repair_applied": bool(applied),
        "repair_improved": bool(improved),
        "warnings": list(dict.fromkeys(repair_warnings)),
    }


def evaluate_plan_with_diversity(plan_rows: List[Dict[str, Any]], base_metrics: Dict[str, Any],
                                 diversity_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg = _diversity_config(diversity_config)
    total_area_da = safe_float((base_metrics or {}).get("total_area_da", 0.0), 0.0)
    diversity = compute_diversity_metrics(plan_rows, total_area_da, cfg)
    feasible = bool((base_metrics or {}).get("feasible", True))
    repair_applied = bool((base_metrics or {}).get("repair_applied", False))
    repair_improved = bool((base_metrics or {}).get("repair_improved", False))
    if not feasible:
        status = "not_feasible"
    elif bool(diversity.get("diversity_feasible", False)):
        status = "recommended"
    elif repair_applied or repair_improved:
        status = "recommended_with_diversity_warning"
    else:
        status = "not_recommended_due_to_diversity"
    if repair_applied:
        diversity.setdefault("warnings", [])
        diversity["warnings"] = list(dict.fromkeys(
            list(diversity.get("warnings") or [])
            + ["Ürün çeşitliliği kısıtı nedeniyle plan yeniden dengelenmiştir."]
        ))
    return {
        "diversity": diversity,
        "recommendation_status": status,
        "selectable": bool(feasible),
    }


def _standard_recommended_rows(parcel_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    result = parcel_result.get("result") if isinstance(parcel_result, dict) else {}
    if not isinstance(result, dict):
        return []
    rows = result.get("recommended")
    if isinstance(rows, list) and rows:
        return [r for r in rows if isinstance(r, dict)]
    primary = result.get("primaryRecommendation")
    if isinstance(primary, dict):
        return [primary]
    return []


def _standard_alternative_rows(parcel_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    result = parcel_result.get("result") if isinstance(parcel_result, dict) else {}
    if not isinstance(result, dict):
        return []
    rows = []
    for key in ("alternativeRecommendations", "alternatives", "all_options"):
        vals = result.get(key)
        if isinstance(vals, list):
            rows.extend([r for r in vals if isinstance(r, dict)])
    return rows


def _standard_s2_secondary_repair_row(parcel: Dict[str, Any], primary_name: str, year: int,
                                      objective_mode: str, season_source: str,
                                      avoid_names: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    try:
        crop_list, _, _, W2, R2, _, _ = build_candidate_matrix_two_season([parcel], year=int(year), season_source=season_source or "s2")
    except Exception:
        return None
    area = safe_float((parcel or {}).get("area_da", 0.0), 0.0)
    primary_key = normalize_crop_key(primary_name)
    avoid = [str(x or "") for x in ([primary_name] + (avoid_names or []))]
    family_map = load_crop_family_map()
    primary_family = family_map.get(normalize_crop_key(primary_name), "")
    candidates = []
    for j, crop in enumerate(crop_list):
        name = str(crop or "").strip()
        if _is_fallow_name(name) or normalize_crop_key(name) == primary_key:
            continue
        if any(_standard_crops_too_close(name, other) for other in avoid):
            continue
        wpd = safe_float(W2[0, j], 0.0)
        ppd = safe_float(R2[0, j], 0.0)
        if wpd <= 0:
            continue
        water = float(area * wpd)
        profit = float(area * ppd)
        eff = profit / water if water > 0 else 0.0
        if objective_mode == "water_saving":
            score = -water + 0.001 * max(profit, 0.0)
        elif objective_mode == "max_profit":
            score = profit - 0.001 * water
        else:
            score = eff + 0.000001 * profit - 0.000001 * water
        if primary_family and family_map.get(normalize_crop_key(name), "") == primary_family:
            score -= abs(score) * 0.08 + 1000.0
        candidates.append((score, name, wpd, ppd, water, profit))
    if not candidates:
        return None
    _, name, wpd, ppd, water, profit = max(candidates, key=lambda x: x[0])
    return {
        "name": name,
        "season": infer_crop_season_label(name, str((parcel or {}).get("parcel_type", "") or "")),
        "area": float(area),
        "waterPerDa": float(wpd),
        "waterTotal": float(water),
        "profitPerDa": float(ppd),
        "profitTotal": float(profit),
        "reason": "Senaryo-2 iki urun sarti icin gercek aday havuzundan eklenen ikinci bilesen; kota uygunlugu ayrica degerlendirilir.",
    }


def _calendar_warnings_for_plan(crops: List[Dict[str, Any]], scenario_type: str) -> Tuple[str, List[str]]:
    warnings = []
    if scenario_type != "double":
        return "Tek urunlu parsel plani", warnings
    if len(crops) < 2:
        warnings.append("Senaryo-2 icin iki urun/desen sarti saglanamadi.")
        return "Eksik iki urunlu desen", warnings
    same_season = normalize_crop_key(crops[0].get("season")) == normalize_crop_key(crops[1].get("season"))
    share_sum = sum(safe_float(c.get("area_share_pct", 0.0), 0.0) for c in crops[:2])
    if same_season:
        if share_sum > 150.0:
            warnings.append("Sezon etiketi ayni/eksik gorunuyor; iki bilesen tam parsel alaninda hesaplandigi icin ardisik desen olarak raporlandi.")
            return "Ardisik iki sezon deseni", warnings
        if abs(share_sum - 100.0) > 2.0:
            warnings.append("Ayni sezon alan paylasimli desende alan oranlari %100 toplamiyor.")
        return "Alan paylasimli desen", warnings
    dates = [(c.get("planting_date"), c.get("harvest_date")) for c in crops[:2]]
    if not all(a and b for a, b in dates):
        warnings.append("Ardisik desen icin ekim-hasat tarihleri eksik; yalniz sezon etiketiyle raporlandi.")
        return "Ardisik iki sezon deseni", warnings
    try:
        p1, h1 = pd.to_datetime(dates[0][0]), pd.to_datetime(dates[0][1])
        p2, h2 = pd.to_datetime(dates[1][0]), pd.to_datetime(dates[1][1])
        if not (h1 <= p2 or h2 <= p1):
            warnings.append("Ekim-hasat tarihleri cakisiyor; desen uygulanamaz.")
    except Exception:
        warnings.append("Takvim tarihleri okunamadi; cakisma kontrolu tamamlanamadi.")
    return "Ardisik iki sezon deseni", warnings


def _standard_data_sources() -> List[str]:
    try:
        names = []
        for p in sorted(DATA_DIR.glob("*")):
            if p.is_file() and p.suffix.lower() in (".csv", ".json", ".geojson"):
                names.append(f"data/{p.name}")
        return names
    except Exception:
        return []


RUN_COUNT_CALIBRATION_CANDIDATES = [10, 15, 30, 50, 100]
ACADEMIC_DEFAULT_REPEAT_COUNT = 30
RUN_COUNT_CALIBRATION_CACHE: Dict[str, Dict[str, Any]] = {}


def _calibration_cache_key(selected_ids: List[str], algorithm: str, scenario: str, scenario_type: str, year_val: Optional[int], water_budget_ratio: float) -> str:
    ids = ",".join(sorted(normalize_parcel_id(x) for x in (selected_ids or [])))
    return "|".join([
        ids,
        str(algorithm or "").upper(),
        _standard_objective_mode(scenario),
        str(scenario_type or ""),
        str(year_val or ""),
        f"{safe_float(water_budget_ratio, 1.0):.4f}",
    ])


def _completion_status_kind(completed: int, requested: int) -> str:
    return "completed" if int(completed) >= int(requested) and int(requested) > 0 else "partial"


def _completion_status_label(completed: int, requested: int) -> str:
    return f"Tamamlandı: {completed}/{requested} koşu" if _completion_status_kind(completed, requested) == "completed" else f"Kısmi sonuç: {completed}/{requested} koşu tamamlandı"


def _score_plan_for_calibration(plan: Dict[str, Any], objective_mode: str) -> float:
    water = safe_float(plan.get("total_water_m3", 0.0), 0.0)
    profit = safe_float(plan.get("total_profit_tl", 0.0), 0.0)
    eff = safe_float(plan.get("tl_per_m3", 0.0), 0.0)
    feasible_bonus = 5000.0 if bool(plan.get("feasible", True)) else -50000.0
    status = str(plan.get("recommendation_status") or plan.get("status") or "").lower()
    diversity = plan.get("diversity") if isinstance(plan.get("diversity"), dict) else {}
    diversity_penalty = safe_float(diversity.get("diversity_penalty", 0.0), 0.0) * 25000.0
    if status == "recommended_with_diversity_warning":
        diversity_penalty += 2500.0
    elif status == "not_recommended_due_to_diversity":
        diversity_penalty += 25000.0
    elif status == "not_feasible":
        diversity_penalty += 50000.0
    if objective_mode == "water_saving":
        return (-water * 0.8) + (profit * 0.0008) + (eff * 80.0) + feasible_bonus - diversity_penalty
    if objective_mode == "max_profit":
        return (profit * 0.001) - (water * 0.04) + (eff * 45.0) + feasible_bonus - diversity_penalty
    return (eff * 600.0) + (profit * 0.0005) - (water * 0.08) + feasible_bonus - diversity_penalty


def _selected_plan_signature(plan: Dict[str, Any]) -> str:
    try:
        crops = plan.get("crops") if isinstance(plan.get("crops"), list) else []
        parts = []
        for c in crops:
            if not isinstance(c, dict):
                continue
            pid = normalize_parcel_id(c.get("parcel_id", ""))
            crop = normalize_crop_key(c.get("crop_name") or c.get("name") or "")
            share = round(safe_float(c.get("area_share_pct", 0.0), 0.0), 1)
            parts.append(f"{pid}:{crop}:{share}")
        return "|".join(parts)
    except Exception:
        return ""


def _median(values: List[float]) -> float:
    if not values:
        return 0.0
    return float(statistics.median(values))


def _std(values: List[float]) -> float:
    if len(values) <= 1:
        return 0.0
    return float(statistics.stdev(values))


def _cv(values: List[float]) -> float:
    if len(values) <= 1:
        return 0.0
    mean_v = float(statistics.mean(values))
    return float(_std(values) / abs(mean_v)) if abs(mean_v) > 1e-9 else 0.0


def _select_recommended_repeat_count(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_count: Dict[int, List[Dict[str, Any]]] = {}
    for row in rows or []:
        by_count.setdefault(int(row.get("repeat_count", 0)), []).append(row)
    selected = None
    reasons = []
    for count in RUN_COUNT_CALIBRATION_CANDIDATES:
        group = by_count.get(count, [])
        if not group:
            continue
        feasible_ok = all(safe_float(r.get("feasible_rate", 0.0), 0.0) >= 0.95 for r in group)
        cv_ok = all(safe_float(r.get("cv_score", 999.0), 999.0) <= 0.05 for r in group)
        marginal_ok = all(
            r.get("marginal_gain_vs_previous") is None or safe_float(r.get("marginal_gain_vs_previous", 999.0), 999.0) < 0.01
            for r in group
        )
        dominance_ok = all(safe_float(r.get("dominant_plan_rate", 0.0), 0.0) <= 0.90 for r in group)
        completed_ok = all(int(r.get("completed_runs", 0)) >= int(r.get("requested_runs", 0)) for r in group)
        if feasible_ok and cv_ok and marginal_ok and dominance_ok and completed_ok:
            selected = count
            reasons.append(f"{count} tekrarda uygulanabilirlik, CV, marjinal iyileşme ve plan baskınlığı eşikleri sağlandı.")
            break
        reasons.append(
            f"{count} tekrar: uygulanabilirlik={feasible_ok}, CV={cv_ok}, marjinal={marginal_ok}, plan baskınlığı={dominance_ok}, tamamlanma={completed_ok}."
        )
    if selected is None:
        selected = ACADEMIC_DEFAULT_REPEAT_COUNT if ACADEMIC_DEFAULT_REPEAT_COUNT in by_count else (min(by_count.keys()) if by_count else ACADEMIC_DEFAULT_REPEAT_COUNT)
        reasons.append(f"Eşiklerin tamamı sağlanmadığı için akademik varsayılan {selected} tekrar seçildi.")
    return {
        "recommended_repeat_count": int(selected),
        "selection_rule": "feasible_rate>=95%, cv_score<=5%, marginal_gain_vs_previous<1%, dominant_plan_rate<=90%, süre/tamamlanma kabul edilebilir; bu eşiği sağlayan en küçük tekrar sayısı seçilir.",
        "reason": " ".join(reasons[-3:]),
    }


def _optimization_repeat_selection(selected_ids: List[str], algorithm: str, scenario: str, scenario_type: str, year_val: Optional[int], water_budget_ratio: float, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    opts = options if isinstance(options, dict) else {}
    fast_preview = bool(
        opts.get("fastPreview") is True
        or str(opts.get("optimizationMode", "")).lower() in ("fast", "fast_preview", "preview")
        or str(opts.get("benchmarkMode", "")).lower() == "fast"
    )
    if fast_preview:
        repeat_count = safe_int(opts.get("fastRepeatCount", opts.get("repeatCount", 5)), 5)
        repeat_count = max(3, min(10, repeat_count))
        return {
            "mode": "fast_preview",
            "algorithm": str(algorithm or "GA").upper(),
            "selected_repeat_count": repeat_count,
            "reason": "Hizli on izleme modu acik; akademik sonuc olarak yorumlanmaz.",
            "calibration_available": False,
        }
    key = _calibration_cache_key(selected_ids, algorithm, scenario, scenario_type, year_val, water_budget_ratio)
    cached = RUN_COUNT_CALIBRATION_CACHE.get(key)
    if cached:
        repeat_count = int(cached.get("recommended_repeat_count") or ACADEMIC_DEFAULT_REPEAT_COUNT)
        return {
            "mode": "calibrated",
            "algorithm": str(algorithm or "GA").upper(),
            "selected_repeat_count": repeat_count,
            "reason": cached.get("reason") or "Aynı parsel/hedef/senaryo koşulları için kalibrasyon sonucu kullanıldı.",
            "calibration_available": True,
            "warning": "Bu optimize endpoint'i mevcut sürümde ana planı tek standart backend çalıştırmasıyla üretir; akademik tekrar istatistikleri kalibrasyon/benchmark ekranında raporlanır.",
        }
    return {
        "mode": "default_30",
        "algorithm": str(algorithm or "GA").upper(),
        "selected_repeat_count": ACADEMIC_DEFAULT_REPEAT_COUNT,
        "reason": "Kalibrasyon sonucu yok; akademik varsayılan 30 tekrar kabul edilir, ancak bu endpoint mevcut sürümde tek karar paketi üretmektedir.",
        "calibration_available": False,
        "warning": "Bu endpoint mevcut sürümde tek koşu üretmektedir; akademik tekrar karşılaştırması benchmark/kalibrasyon ekranında yapılır.",
    }

def _optimization_run_policy(selected_ids: List[str], algorithm: str, scenario: str, scenario_type: str, year_val: Optional[int], water_budget_ratio: float) -> Dict[str, Any]:
    base = _optimization_repeat_selection(selected_ids, algorithm, scenario, scenario_type, year_val, water_budget_ratio, {})
    repeat_count = int(base.get("selected_repeat_count") or ACADEMIC_DEFAULT_REPEAT_COUNT)
    return {
        **base,
        "requested_runs": repeat_count,
        "completed_runs": 0,
        "completion_status_kind": "partial",
        "best_run_index": None,
        "feasible_run_count": 0,
        "feasible_rate": 0.0,
        "mean_score": None,
        "best_score": None,
        "cv_score": None,
        "mean_runtime_sec": None,
        "warning": "Bu politika alani route disi standartlastirma icin on bilgidir; /api/optimize gercek kosu istatistikleriyle doldurur.",
    }


def _optimization_policy_from_runs(base_policy: Dict[str, Any], run_stats: List[Dict[str, Any]], selected_run: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    requested = int(base_policy.get("selected_repeat_count") or ACADEMIC_DEFAULT_REPEAT_COUNT)
    completed = len(run_stats or [])
    scores = [safe_float(r.get("score", 0.0), 0.0) for r in (run_stats or []) if r.get("score") is not None]
    runtimes = [safe_float(r.get("runtime", 0.0), 0.0) for r in (run_stats or [])]
    feasible_count = sum(1 for r in (run_stats or []) if bool(r.get("feasible")) and bool(r.get("selectable", True)))
    best_score = max(scores) if scores else None
    return {
        **base_policy,
        "warning": None,
        "requested_runs": requested,
        "completed_runs": completed,
        "completion_status_kind": _completion_status_kind(completed, requested),
        "completion_status": _completion_status_label(completed, requested),
        "best_run_index": selected_run.get("run_index") if isinstance(selected_run, dict) else None,
        "feasible_run_count": int(feasible_count),
        "feasible_rate": float(feasible_count / max(1, completed)),
        "mean_score": float(statistics.mean(scores)) if scores else None,
        "best_score": float(best_score) if best_score is not None else None,
        "cv_score": _cv(scores),
        "mean_runtime_sec": float(statistics.mean(runtimes)) if runtimes else None,
    }


def _standardize_optimize_payload(result: Dict[str, Any], selected_ids: List[str], algorithm: str, scenario: str,
                                  water_budget_ratio: float, year_val: Optional[int], options: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(result, dict):
        return result

    opts = options if isinstance(options, dict) else {}
    meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
    scenario_type = _standard_scenario_type(opts, meta)
    objective_mode = _standard_objective_mode(result.get("objective") or scenario)
    y = int(result.get("year") or year_val or (available_years()[-1] if available_years() else 2024))

    base_parcels = load_parcels()
    custom_parcels = opts.get("customParcels") if isinstance(opts.get("customParcels"), list) else []
    parcels = merge_frontend_custom_parcels(base_parcels, custom_parcels)
    selected_norm = [normalize_parcel_id(x) for x in (selected_ids or [])]
    selected_parcels = [p for p in parcels if (not selected_norm) or normalize_parcel_id(p.get("id")) in selected_norm]
    parcel_meta = {normalize_parcel_id(p.get("id")): p for p in selected_parcels}

    baseline_rows = []
    baseline_warnings = []
    for p in selected_parcels:
        bw = safe_float(p.get("water_m3", 0.0), 0.0)
        bp = safe_float(p.get("profit_tl", 0.0), 0.0)
        if bw <= 0 or bp <= 0:
            baseline_warnings.append(f"{p.get('id')} parselinde baseline su/kar verisi eksik veya sifir.")
        baseline_rows.append({
            "parcel_id": _safe_text(p.get("id")),
            "crop_name": _safe_text(p.get("current_crop") or p.get("crop") or "Bilinmiyor"),
            "area_da": float(safe_float(p.get("area_da", 0.0), 0.0)),
            "water_m3": float(bw),
            "profit_tl": float(bp),
        })
    base_water = sum(r["water_m3"] for r in baseline_rows)
    base_profit = sum(r["profit_tl"] for r in baseline_rows)
    baseline = {
        "crop_pattern": baseline_rows,
        "total_water_m3": float(base_water),
        "total_profit_tl": float(base_profit),
        "tl_per_m3": float(base_profit / base_water) if base_water > 0 else 0.0,
    }

    plan_rows = []
    plan_warnings = list(baseline_warnings)
    for pr in result.get("parcels", []) or []:
        pid = normalize_parcel_id(pr.get("id") if isinstance(pr, dict) else "")
        parcel = parcel_meta.get(pid, {"id": pid, "area_da": pr.get("area_da", 0.0) if isinstance(pr, dict) else 0.0})
        rows = [r for r in _standard_recommended_rows(pr) if not _is_fallow_name(_row_name(r))]
        if scenario_type == "double" and len(rows) < 2:
            result_block = pr.get("result", {}) if isinstance(pr.get("result"), dict) else {}
            orchard_alt = result_block.get("orchardAlternative")
            if isinstance(orchard_alt, dict) and _row_name(orchard_alt):
                rows.append({
                    "name": _row_name(orchard_alt),
                    "season": "Sira arasi / uzman onayli",
                    "area": 0.0,
                    "waterTotal": 0.0,
                    "profitTotal": 0.0,
                    "reason": _safe_text(orchard_alt.get("decisionNote") or orchard_alt.get("note") or "Bahce parselinde uzman onayli ara yonetim alternatifi."),
                    "feasible": False,
                })
                plan_warnings.append(f"{pid} parselinde ikinci urun yalniz uzman onayli ara yonetim alternatifi olarak raporlandi.")
            else:
                primary_name = _row_name(rows[0]) if rows else _safe_text((parcel or {}).get("current_crop"))
                repair_row = _standard_s2_secondary_repair_row(
                    parcel=parcel,
                    primary_name=primary_name,
                    year=y,
                    objective_mode=objective_mode,
                    season_source=str(opts.get("seasonSource") or meta.get("seasonSource") or "s2"),
                )
                if repair_row is not None:
                    rows.append(repair_row)
                    plan_warnings.append(f"{pid} parselinde algoritma ikinci urunu bos/NADAS birakti; Senaryo-2 icin gercek aday havuzundan ikinci bilesen eklendi ve kota uygunlugu acikca raporlandi.")
        if scenario_type == "double" and len(rows) >= 2:
            first_name = _row_name(rows[0])
            second_name = _row_name(rows[1])
            if _standard_crops_too_close(first_name, second_name):
                replacement = _standard_s2_secondary_repair_row(
                    parcel=parcel,
                    primary_name=first_name,
                    year=y,
                    objective_mode=objective_mode,
                    season_source=str(opts.get("seasonSource") or meta.get("seasonSource") or "s2"),
                    avoid_names=[second_name],
                )
                if replacement is not None:
                    rows[1] = replacement
                    plan_warnings.append(f"{pid} parselinde {first_name} + {second_name} ayni/yakin urun varyanti sayildi; ikinci bilesen gercek aday havuzundan farkli urunle degistirildi.")
                else:
                    plan_warnings.append(f"{pid} parselinde {first_name} + {second_name} ayni/yakin urun varyanti oldugu icin iki urunlu desen guvenilir degil; uygun farkli ikinci urun bulunamadi.")
        for idx, row in enumerate(rows):
            role = "primary" if idx == 0 else ("secondary" if scenario_type == "double" else "alternative_component")
            plan_rows.append(_standard_crop_from_row(row, parcel, role, bool(result.get("feasible", True))))

    pattern_type, calendar_warnings = _calendar_warnings_for_plan(plan_rows, scenario_type)
    plan_warnings.extend(calendar_warnings)
    if scenario_type == "single" and len(plan_rows) != max(1, len(selected_parcels)):
        plan_warnings.append("Senaryo-1 tek urunlu plan bekler; parsel sayisi ile onerilen satir sayisi uyusmuyor.")
    if scenario_type == "double" and len(selected_parcels) == 1 and len(plan_rows) != 2:
        plan_warnings.append("Senaryo-2 ana plani tam iki urun/desen satiri uretmedi.")

    diversity_candidate_rows: List[Dict[str, Any]] = []
    if bool(_diversity_config(DIVERSITY_DEFAULTS).get("repair_enabled", True)):
        for pr in result.get("parcels", []) or []:
            if not isinstance(pr, dict):
                continue
            pid = normalize_parcel_id(pr.get("id"))
            parcel = parcel_meta.get(pid, {"id": pid, "area_da": pr.get("area_da", 0.0)})
            raw_candidates = []
            raw_candidates.extend(_standard_recommended_rows(pr))
            raw_candidates.extend(_standard_alternative_rows(pr))
            for row in raw_candidates:
                if not isinstance(row, dict):
                    continue
                crop = _standard_crop_from_row(row, parcel, "primary", True)
                if _is_fallow_name(crop.get("crop_name")):
                    continue
                if crop.get("area_da", 0.0) <= 0:
                    continue
                diversity_candidate_rows.append(crop)
        try:
            existing_candidate_keys = {
                (str(c.get("parcel_id") or ""), normalize_crop_key(c.get("crop_name") or c.get("name")))
                for c in diversity_candidate_rows
            }
            crop_list_fb, W_fb, R_fb = build_candidate_matrix(
                selected_parcels,
                year=y,
                season_source=str(opts.get("seasonSource") or meta.get("seasonSource") or "s1"),
            )
            for i, parcel in enumerate(selected_parcels):
                area = safe_float(parcel.get("area_da", 0.0), 0.0)
                pid_txt = _safe_text(parcel.get("id"))
                ranked = []
                for j, crop_name in enumerate(crop_list_fb):
                    if _is_fallow_name(crop_name):
                        continue
                    wpd = safe_float(W_fb[i, j], 0.0)
                    ppd = safe_float(R_fb[i, j], 0.0)
                    if (not np.isfinite(wpd)) or (not np.isfinite(ppd)) or wpd < 0 or wpd >= 1e8:
                        continue
                    water = float(area * wpd)
                    profit = float(area * ppd)
                    eff = profit / max(1.0, water)
                    if objective_mode == "water_saving":
                        score = -water + 0.001 * max(0.0, profit) + eff
                    elif objective_mode == "max_profit":
                        score = profit - 0.01 * water + eff
                    else:
                        score = eff * 1000.0 + 0.0001 * profit - 0.01 * water
                    ranked.append((score, crop_name, water, profit))
                ranked.sort(key=lambda x: x[0], reverse=True)
                for _score, crop_name, water, profit in ranked[:10]:
                    key = (pid_txt, normalize_crop_key(crop_name))
                    if key in existing_candidate_keys:
                        continue
                    existing_candidate_keys.add(key)
                    diversity_candidate_rows.append({
                        "parcel_id": pid_txt,
                        "crop_name": str(crop_name),
                        "name": str(crop_name),
                        "role": "primary",
                        "season": "Aday",
                        "area_da": float(area),
                        "area_share_pct": 100.0,
                        "water_m3": float(water),
                        "profit_tl": float(profit),
                        "tl_per_m3": float(profit / water) if water > 0 else 0.0,
                        "quota_m3": 0.0,
                        "quota_status": "Uygun",
                        "feasible": True,
                        "selectable": True,
                        "warnings": [],
                        "explanation": "Çeşitlilik onarımı için aynı parselin uygulanabilir aday havuzundan alınmıştır.",
                    })
        except Exception:
            pass

    row_total_water = sum(safe_float(c.get("water_m3", 0.0), 0.0) for c in plan_rows)
    row_total_profit = sum(safe_float(c.get("profit_tl", 0.0), 0.0) for c in plan_rows)
    total_water = row_total_water if plan_rows else safe_float(result.get("total_water_m3", 0.0), 0.0)
    total_profit = row_total_profit if plan_rows else safe_float(result.get("total_profit_tl", 0.0), 0.0)
    water_budget_m3 = safe_float(result.get("water_budget_m3", 0.0), 0.0)
    area_shared_repair_applied = False
    if scenario_type == "double" and len(selected_parcels) == 1 and len(plan_rows) == 2 and water_budget_m3 > 0 and total_water > water_budget_m3 + 1e-6:
        parcel_area = safe_float(selected_parcels[0].get("area_da", 0.0), 0.0)
        ratios = [(50, 50), (60, 40), (70, 30), (40, 60), (30, 70)]
        best_ratio_plan = None
        for r1_pct, r2_pct in ratios:
            r1 = float(r1_pct) / 100.0
            r2 = float(r2_pct) / 100.0
            c1 = dict(plan_rows[0])
            c2 = dict(plan_rows[1])
            a1_src = safe_float(c1.get("area_da", 0.0), 0.0)
            a2_src = safe_float(c2.get("area_da", 0.0), 0.0)
            wpd1 = safe_float(c1.get("water_m3", 0.0), 0.0) / max(1e-9, a1_src)
            wpd2 = safe_float(c2.get("water_m3", 0.0), 0.0) / max(1e-9, a2_src)
            ppd1 = safe_float(c1.get("profit_tl", 0.0), 0.0) / max(1e-9, a1_src)
            ppd2 = safe_float(c2.get("profit_tl", 0.0), 0.0) / max(1e-9, a2_src)
            c1_area = parcel_area * r1
            c2_area = parcel_area * r2
            c1.update({
                "area_da": float(c1_area),
                "area_share_pct": float(r1_pct),
                "water_m3": float(c1_area * wpd1),
                "profit_tl": float(c1_area * ppd1),
                "feasible": True,
                "selectable": True,
                "quota_status": "Uygun",
            })
            c1["tl_per_m3"] = float(c1["profit_tl"] / c1["water_m3"]) if c1["water_m3"] > 0 else 0.0
            c2.update({
                "area_da": float(c2_area),
                "area_share_pct": float(r2_pct),
                "water_m3": float(c2_area * wpd2),
                "profit_tl": float(c2_area * ppd2),
                "feasible": True,
                "selectable": True,
                "quota_status": "Uygun",
            })
            c2["tl_per_m3"] = float(c2["profit_tl"] / c2["water_m3"]) if c2["water_m3"] > 0 else 0.0
            cand_water = c1["water_m3"] + c2["water_m3"]
            cand_profit = c1["profit_tl"] + c2["profit_tl"]
            if cand_water <= water_budget_m3 + 1e-6:
                best_ratio_plan = (c1, c2, cand_water, cand_profit, r1_pct, r2_pct)
                break
        if best_ratio_plan is not None:
            c1, c2, total_water, total_profit, r1_pct, r2_pct = best_ratio_plan
            plan_rows = [c1, c2]
            pattern_type = "Alan paylasimli desen"
            area_shared_repair_applied = True
            plan_warnings.append(f"Ardisik iki sezon deseni kota disinda kaldigi icin ayni sezon alan paylasimli %{r1_pct}-%{r2_pct} desen uygulanabilir ana plan olarak secildi.")

    diversity_repair = repair_plan_for_diversity(
        plan_rows,
        diversity_candidate_rows,
        DIVERSITY_DEFAULTS,
        water_budget_m3=water_budget_m3,
    )
    plan_rows = diversity_repair.get("plan_rows", plan_rows)
    if diversity_repair.get("repair_applied"):
        plan_warnings.append("Ürün çeşitliliği kısıtı nedeniyle plan yeniden dengelenmiştir. Amaç, tek ürüne aşırı yığılmayı azaltarak daha uygulanabilir bir ürün deseni üretmektir.")
    plan_warnings.extend(diversity_repair.get("warnings") or [])
    total_water = sum(safe_float(c.get("water_m3", 0.0), 0.0) for c in plan_rows) if plan_rows else total_water
    total_profit = sum(safe_float(c.get("profit_tl", 0.0), 0.0) for c in plan_rows) if plan_rows else total_profit

    plan_feasible = (bool(result.get("feasible", True)) or area_shared_repair_applied) and all(bool(c.get("feasible")) for c in plan_rows)
    if scenario_type == "double" and len(selected_parcels) == 1 and len(plan_rows) != 2:
        plan_feasible = False
    if total_water > water_budget_m3 + 1e-6 and water_budget_m3 > 0:
        plan_feasible = False
        plan_warnings.append("Secili plan toplam su butcesini asiyor.")
    selected_status = "ok"
    if scenario_type == "double" and not plan_feasible:
        selected_status = "no_feasible_two_crop_plan"
        plan_warnings.append("Secili parsel ve su kotasi altinda uygulanabilir iki urunlu/desenli plan bulunamadi.")

    diversity_eval = evaluate_plan_with_diversity(
        plan_rows,
        {
            "feasible": bool(plan_feasible),
            "repair_applied": bool(diversity_repair.get("repair_applied")),
            "repair_improved": bool(diversity_repair.get("repair_improved")),
            "total_area_da": sum(safe_float(p.get("area_da", 0.0), 0.0) for p in selected_parcels),
        },
        DIVERSITY_DEFAULTS,
    )
    diversity_metrics = diversity_eval.get("diversity", {})
    recommendation_status = str(diversity_eval.get("recommendation_status") or "recommended")
    if recommendation_status == "not_feasible":
        plan_warnings.append("Bu seçenek su/uygunluk kısıtları altında uygulanabilir değildir.")
    elif recommendation_status == "not_recommended_due_to_diversity":
        plan_warnings.append("Bu seçenek su/uygunluk açısından uygulanabilir olabilir; ancak ürün yoğunlaşması nedeniyle tartışmalı alternatif olarak değerlendirilmelidir.")
    elif recommendation_status == "recommended_with_diversity_warning":
        plan_warnings.append("Bu seçenek su/uygunluk açısından uygulanabilir görünmektedir; ancak ürün yoğunlaşması nedeniyle dikkatli değerlendirilmelidir.")
    plan_warnings.extend(diversity_metrics.get("warnings") or [])

    plan_names = "-".join(normalize_crop_key(c.get("crop_name")) for c in plan_rows)[:80]
    selected_plan = {
        "plan_id": f"{str(result.get('algorithm') or algorithm).upper()}-{scenario_type}-{objective_mode}-{y}-{plan_names}",
        "status": selected_status,
        "recommendation_status": recommendation_status,
        "scenario_type": scenario_type,
        "pattern_type": pattern_type,
        "crops": plan_rows,
        "total_water_m3": float(total_water),
        "total_profit_tl": float(total_profit),
        "tl_per_m3": float(total_profit / total_water) if total_water > 0 else 0.0,
        "delta_water_m3": float(total_water - base_water),
        "delta_profit_tl": float(total_profit - base_profit),
        "feasible": bool(plan_feasible),
        "selectable": bool(plan_feasible),
        "diversity": diversity_metrics,
        "diversity_repair_applied": bool(diversity_repair.get("repair_applied")),
        "feasibility_reasons": ["Uygun"] if plan_feasible else plan_warnings,
        "warnings": plan_warnings,
        "explanation": (
            "Secili parsel ve su kotasi altinda uygulanabilir iki urunlu/desenli plan bulunamadi."
            if selected_status == "no_feasible_two_crop_plan"
            else (
                "Bu mod su tuketimi, net kar ve birim su basina getiriyi birlikte degerlendirir."
                if objective_mode == "balanced"
                else "Secili hedef modu ve su butcesi altinda backend karar motoru tarafindan uretilen nihai plandir."
            )
        ),
    }

    alternatives = []
    seen_alt = set(normalize_crop_key(c.get("crop_name")) for c in plan_rows)
    if scenario_type == "single":
        for pr in result.get("parcels", []) or []:
            pid = normalize_parcel_id(pr.get("id") if isinstance(pr, dict) else "")
            parcel = parcel_meta.get(pid, {"id": pid, "area_da": pr.get("area_da", 0.0) if isinstance(pr, dict) else 0.0})
            for row in _standard_alternative_rows(pr):
                name_key = normalize_crop_key(_row_name(row))
                if _is_fallow_name(name_key) or name_key in seen_alt:
                    continue
                seen_alt.add(name_key)
                crop = _standard_crop_from_row(row, parcel, "primary", True)
                alt_water = crop["water_m3"]
                alt_profit = crop["profit_tl"]
                alt_feasible = bool(crop.get("feasible"))
                alternatives.append({
                    "plan_id": f"ALT-single-{objective_mode}-{len(alternatives)+1}-{name_key}",
                    "scenario_type": "single",
                    "pattern_type": "Tek urunlu alternatif",
                    "crops": [crop],
                    "total_water_m3": float(alt_water),
                    "total_profit_tl": float(alt_profit),
                    "tl_per_m3": float(alt_profit / alt_water) if alt_water > 0 else 0.0,
                    "delta_water_m3": float(alt_water - base_water),
                    "delta_profit_tl": float(alt_profit - base_profit),
                    "feasible": alt_feasible,
                    "selectable": alt_feasible,
                    "feasibility_reasons": ["Uygun"] if alt_feasible else crop.get("warnings", []),
                    "warnings": crop.get("warnings", []),
                    "explanation": crop.get("explanation", ""),
                })
                if len(alternatives) >= 5:
                    break
            if len(alternatives) >= 5:
                break
    if scenario_type == "single" and len([a for a in alternatives if a.get("feasible")]) < 4:
        plan_warnings.append(f"Kisitlar nedeniyle {len([a for a in alternatives if a.get('feasible')])} uygulanabilir alternatif uretildi.")

    context = {
        "parcel_id": selected_norm[0] if len(selected_norm) == 1 else selected_norm,
        "area_da": float(sum(safe_float(p.get("area_da", 0.0), 0.0) for p in selected_parcels)),
        "total_area_da": float(sum(safe_float(p.get("area_da", 0.0), 0.0) for p in selected_parcels)),
        "water_year": int(y),
        "scenario_type": scenario_type,
        "objective_mode": objective_mode,
        "algorithm": str(result.get("algorithm") or algorithm).upper(),
        "seed": meta.get("seed", opts.get("seed")),
        "water_budget_m3": float(safe_float(result.get("water_budget_m3", 0.0), 0.0)),
        "budget_method": _safe_text(meta.get("allocation_model") or meta.get("budget_method") or "backend_water_budget"),
        "data_sources": _standard_data_sources(),
        "baseline_rows": baseline_rows,
    }
    agronomic_risk = compute_agronomic_risk_metrics(selected_plan, context)
    selected_plan["agronomic_risk"] = agronomic_risk

    plan_risk = "Dusuk" if selected_plan["feasible"] else "Yuksek"
    quota_status = "Uygun" if selected_plan["feasible"] else "Kota/uygunluk riski var"
    calendar_status = "Uygun" if not calendar_warnings else "Veri eksik / kontrol gerekli"
    charts = {
        "target_mode_water": {
            "title": "Hedef Modlarına Göre Toplam Su Kullanımı",
            "unit": "m3",
            "scope": "Secili parsel" if len(selected_parcels) == 1 else "Secili parseller",
            "scenario_type": scenario_type,
            "objective_mode": objective_mode,
            "description": "Bu grafik, secili senaryo tipi altinda mevcut desen ve secili hedef modu sonucunu karsilastirir.",
            "rows": [
                {"label": "Mevcut", "value": float(base_water)},
                {"label": _objective_mode_label_tr(objective_mode), "value": float(total_water)},
            ],
        },
        "target_mode_profit": {
            "title": "Hedef Modlarına Göre Toplam Net Kâr",
            "unit": "TL",
            "scope": "Secili parsel" if len(selected_parcels) == 1 else "Secili parseller",
            "scenario_type": scenario_type,
            "objective_mode": objective_mode,
            "description": "Bu grafik, secili senaryo tipi altinda mevcut desen ve secili hedef modu sonucunu karsilastirir.",
            "rows": [
                {"label": "Mevcut", "value": float(base_profit)},
                {"label": _objective_mode_label_tr(objective_mode), "value": float(total_profit)},
            ],
        },
        "selected_delta": {
            "title": "Seçili Planın Baseline'a Göre Su/Kâr Farkı",
            "unit": "m3 / TL",
            "scope": "Secili parsel" if len(selected_parcels) == 1 else "Secili parseller",
            "scenario_type": scenario_type,
            "objective_mode": objective_mode,
            "description": "Degerler backend plan ozeti ile ayni kaynaktan uretilir.",
            "rows": [
                {"label": "Su farki", "value": float(selected_plan["delta_water_m3"])},
                {"label": "Kar farki", "value": float(selected_plan["delta_profit_tl"])},
            ],
        },
    }
    tables = {
        "plan_summary": [
            {"label": "Mevcut", "water_m3": float(base_water), "profit_tl": float(base_profit), "tl_per_m3": baseline["tl_per_m3"]},
            {"label": "Secili plan", "water_m3": float(total_water), "profit_tl": float(total_profit), "tl_per_m3": selected_plan["tl_per_m3"]},
        ],
        "alternatives": [
            {"plan_id": a["plan_id"], "water_m3": a["total_water_m3"], "profit_tl": a["total_profit_tl"], "tl_per_m3": a["tl_per_m3"], "feasible": a["feasible"]}
            for a in alternatives
        ],
    }
    diagnostics = {
        "backend_single_source": True,
        "algorithm_choice_preserved": True,
        "scenario_type": scenario_type,
        "objective_mode": objective_mode,
        "alternative_count": len(alternatives),
        "feasible_alternative_count": len([a for a in alternatives if a.get("feasible")]),
        "risk_labels": {
            "dam_drought_risk": _safe_text(meta.get("dam_drought_risk") or "Veri yok"),
            "plan_feasibility_risk": plan_risk,
            "parcel_quota_status": quota_status,
            "calendar_rotation_status": calendar_status,
        },
        "warnings": list(dict.fromkeys(plan_warnings)),
        "legacy_meta": meta,
    }

    result.update({
        "context": context,
        "baseline": baseline,
        "selected_plan": selected_plan,
        "diversity": diversity_metrics,
        "agronomic_risk": agronomic_risk,
        "recommendation_status": recommendation_status,
        "alternatives": alternatives,
        "charts": charts,
        "tables": tables,
        "diagnostics": diagnostics,
        "optimization_run_policy": result.get("_optimization_run_policy") if isinstance(result.get("_optimization_run_policy"), dict) else _optimization_run_policy(
            selected_ids=selected_norm,
            algorithm=str(result.get("algorithm") or algorithm).upper(),
            scenario=scenario,
            scenario_type=scenario_type,
            year_val=y,
            water_budget_ratio=water_budget_ratio,
        ),
    })
    return result


@app.get("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")

@app.get("/<path:filename>")
def static_files(filename: str):
    # allow style.css, script.js, leaflet assets if any
    if (BASE_DIR / filename).exists():
        return send_from_directory(BASE_DIR, filename)
    return ("Not found", 404)

@app.get("/data/<path:filename>")
def data_files(filename: str):
    resp = send_from_directory(DATA_DIR, filename)
    lower = str(filename).lower()
    if lower.endswith(".csv") or lower.endswith(".tsv"):
        resp.headers["Content-Type"] = "text/csv; charset=utf-8"
        resp.headers["Content-Disposition"] = f'inline; filename="{Path(filename).name}"'
    elif lower.endswith(".json") or lower.endswith(".geojson"):
        resp.headers["Content-Type"] = "application/json; charset=utf-8"
        resp.headers["Content-Disposition"] = f'inline; filename="{Path(filename).name}"'
    return resp


@app.get("/api/data_table_preview")
def api_data_table_preview():
    rel = str(request.args.get("path", "")).strip().replace("\\", "/")
    if not rel:
        return jsonify({"status": "ERROR", "message": "Dosya yolu boş."}), 400
    if rel.startswith("/"):
        rel = rel[1:]
    if rel.startswith("data/"):
        rel = rel[5:]
    target = (DATA_DIR / rel).resolve()
    try:
        target.relative_to(DATA_DIR.resolve())
    except ValueError:
        return jsonify({"status": "ERROR", "message": "Geçersiz dosya yolu."}), 400
    if not target.exists() or not target.is_file():
        return jsonify({"status": "ERROR", "message": "Dosya bulunamadı."}), 404

    lower = target.name.lower()
    try:
        if lower.endswith((".json", ".geojson")):
            data = json.loads(target.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict) and isinstance(data.get("features"), list):
                rows = []
                for i, feat in enumerate(data["features"][:500]):
                    props = feat.get("properties") or {}
                    rows.append({"sira": i + 1, "geometry_type": (feat.get("geometry") or {}).get("type", ""), **props})
            elif isinstance(data, list):
                rows = data[:500]
            elif isinstance(data, dict):
                rows = [{"anahtar": k, "deger": json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v} for k, v in data.items()]
            else:
                rows = [{"deger": str(data)}]
        else:
            text = target.read_text(encoding="utf-8-sig", errors="replace")
            sample = text[:4096]
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except Exception:
                dialect = csv.excel
                dialect.delimiter = ";" if sample.count(";") >= sample.count(",") else ","
            raw_rows = [row for row in csv.reader(text.splitlines(), dialect) if any(str(c).strip() for c in row)]
            if not raw_rows:
                rows = []
            else:
                header_idx = 0
                for idx, row in enumerate(raw_rows[:12]):
                    filled = sum(1 for c in row if str(c).strip())
                    if filled >= 2:
                        header_idx = idx
                        break
                headers = [str(h).strip() or f"kolon_{i+1}" for i, h in enumerate(raw_rows[header_idx])]
                rows = []
                for row in raw_rows[header_idx + 1:501]:
                    rows.append({headers[i] if i < len(headers) else f"kolon_{i+1}": (row[i] if i < len(row) else "") for i in range(max(len(headers), len(row)))})
        flat_rows = []
        for row in rows:
            if isinstance(row, dict):
                flat_rows.append(row)
            else:
                flat_rows.append({"deger": row})
        headers = []
        seen = set()
        for row in flat_rows:
            for key in row.keys():
                if key not in seen:
                    seen.add(key)
                    headers.append(key)
        return jsonify({"status": "OK", "headers": headers, "rows": flat_rows, "totalRows": len(flat_rows), "path": "data/" + rel})
    except Exception as exc:
        return jsonify({"status": "ERROR", "message": str(exc)}), 500




@app.get("/api/meta")
def api_meta():
    """Return which built-in CSV files are being used by the backend (for transparency in the UI)."""
    p = enhanced_paths()
    # return relative paths for UI display
    rel = {k: str(v.relative_to(DATA_DIR)) if str(v).startswith(str(DATA_DIR)) else str(v) for k, v in p.items()}
    # Also expose what else exists in the packaged enhanced_dataset/csv folder.
    # (Some of these are optional or not yet fully wired into the optimizer, but users
    # frequently want to see the full data inventory for transparency.)
    enhanced_csv_dir = DATA_DIR / "enhanced_dataset" / "csv"
    available = []
    try:
        # v66: Sunumda veri izlenebilirliği için yalnızca enhanced CSV'leri değil,
        # paket içindeki tüm CSV/JSON veri dosyalarını UI'ye bildiriyoruz.
        # Gerçek parsel sınırları yüzlerce GeoJSON içerdiği için burada listelenmez;
        # onların kapsamı build meta rozetinde ayrıca gösterilir.
        exts = {".csv", ".json"}
        skip_names = {"_index.json"}  # klasör indekslerini tekrar tekrar şişirmesin
        for fp in sorted(DATA_DIR.rglob("*"), key=lambda x: str(x.relative_to(DATA_DIR)).lower()):
            if not fp.is_file() or fp.suffix.lower() not in exts:
                continue
            if fp.name in skip_names and "geojson" not in str(fp).lower() and "village_boundaries" not in str(fp).lower():
                continue
            try:
                rel_fp = str(fp.relative_to(DATA_DIR)).replace("\\", "/")
            except Exception:
                rel_fp = str(fp).replace("\\", "/")
            # Eski sync/log dosyalarını ve paket raporlarını listeyi kirletmemesi için dışarıda bırak.
            if rel_fp.startswith("ZIP_SYNC_LOG") or rel_fp.startswith("_unused_archive"):
                continue
            available.append(rel_fp)
        # Önce aktif enhanced dosyalar görünsün, sonra diğerleri alfabetik gelsin.
        def _prio(x):
            return (0 if x.startswith("enhanced_dataset/csv/") else 1, x.lower())
        available = sorted(set(available), key=_prio)
    except Exception:
        available = []
    years = available_years()
    # Data-driven Senaryo-1 rules and irrigation mapping
    try:
        s1_rules_out = load_s1_crop_calendar_rules() or {}
    except Exception as e:
        s1_rules_out = {"_derived": {"_rules_file_error": str(e)}}
    try:
        with open(os.path.join(DATA_DIR, "crop_irrigation_map.json"), "r", encoding="utf-8") as f:
            crop_irrigation_map = json.load(f)
    except Exception:
        crop_irrigation_map = {}
    
    return jsonify({
        "status": "OK",
        "build": APP_BUILD,
        "title": APP_TITLE,
        "generated_at": APP_GENERATED_AT,
        "data_quality": build_data_quality_report(),
        "water_allocation": build_water_allocation_logic(),
        "backend": {
            "data_source": "5 yerleşimli Excel türevli veri paketi (Sazlıca, Bahçeli, Kemerhisar, Bor İlçe Merkezi, Kaynarca)",
            "files": rel,
            "files_available": available,
            "years_min": int(min(years)) if years else None,
            "years_max": int(max(years)) if years else None,
            "s1_crop_rules_file": "data/s1_crop_calendar_rules.json",
            "s1_rules_loaded_count": int(len([k for k in (s1_rules_out or {}).keys() if k != '_derived'])),
            "s1_rules_file_exists": bool((DATA_DIR / 's1_crop_calendar_rules.json').exists()),
            "s1_rules_file_size": int((DATA_DIR / 's1_crop_calendar_rules.json').stat().st_size) if (DATA_DIR / 's1_crop_calendar_rules.json').exists() else 0,
            "s1_rules_error": (s1_rules_out.get("_error") if isinstance(s1_rules_out, dict) else None),
        },
        # Frontend expects these at top level (data-driven; no hardcoded lists)
        "scenario1_rules": {k:v for k,v in (s1_rules_out or {}).items() if k != "_derived"},
        "scenario1_rules_debug": (s1_rules_out or {}).get("_derived", {}),
        "crop_irrigation_map": crop_irrigation_map
    })

# Projection/timeseries route removed in equal-water planning mode
# @app.get("/api/timeseries")
def api_timeseries():
    """Return annual series for current, water_saving, max_profit (water/profit/budget)."""
    years = available_years()
    if not years:
        years = list(range(2000, 2026))
    selected_ids = request.args.get("selected", "")
    selected = [s for s in selected_ids.split(",") if s] if selected_ids else []
    parcels = load_parcels()
    sel_parcels = [p for p in parcels if (not selected) or (p["id"] in selected)]

    series = {"years": years, "budget_m3": [], "current_water_m3": [], "current_profit_tl": [],
              "water_saving_water_m3": [], "water_saving_profit_tl": [],
              "max_profit_water_m3": [], "max_profit_profit_tl": []}

    # baseline current totals (constant)
    base_water = sum(float(p.get("water_m3",0) or 0) for p in sel_parcels)
    base_profit = sum(float(p.get("profit_tl",0) or 0) for p in sel_parcels)
    if base_water <= 0:
        base_water = sum(float(p.get("area_da",0) or 0) for p in sel_parcels) * 500.0
    if base_profit <= 0:
        base_profit = sum(float(p.get("area_da",0) or 0) for p in sel_parcels) * 5000.0

    # precompute a single GA solution for objectives (fast), then scale to each year's budget ratio
    sol_ws = ga_optimize(sel_parcels, years[-1], "water_saving", pop_size=40, generations=80)
    sol_mp = ga_optimize(sel_parcels, years[-1], "max_profit", pop_size=40, generations=80)
    ws_w = sol_ws["total_water_m3"]; ws_p = sol_ws["total_profit_tl"]
    mp_w = sol_mp["total_water_m3"]; mp_p = sol_mp["total_profit_tl"]
    ws_budget_ref = sol_ws["water_budget_m3"] or base_water
    mp_budget_ref = sol_mp["water_budget_m3"] or base_water

    for y in years:
        b = water_budget_for_year(int(y), sel_parcels)
        series["budget_m3"].append(float(b))
        series["current_water_m3"].append(float(base_water))
        series["current_profit_tl"].append(float(base_profit))

        # scale GA solutions to match yearly budget if needed
        ws_scale = min(1.0, float(b)/float(ws_w)) if ws_w>0 else 0.0
        mp_scale = min(1.0, float(b)/float(mp_w)) if mp_w>0 else 0.0
        series["water_saving_water_m3"].append(float(ws_w*ws_scale))
        series["water_saving_profit_tl"].append(float(ws_p*ws_scale))
        series["max_profit_water_m3"].append(float(mp_w*mp_scale))
        series["max_profit_profit_tl"].append(float(mp_p*mp_scale))

    return jsonify({"status":"OK","series":series})

@app.get("/api/years")
def api_years():
    years = available_years()
    # also include last year even if not in reservoir, for UI fallback
    if years:
        default_year = 2024 if 2024 in years else years[-1]
        return jsonify({"status":"OK","years":years,"default":default_year})
    # Full fallback
    years = list(range(2000, 2051))
    return jsonify({"status":"OK","years":years,"default":2024})

@app.get("/api/parcels")
def api_parcels():
    try:
        return jsonify({"status": "OK", "parcels": load_parcels()})
    except Exception as e:
        # Return a JSON error so the frontend can show a useful message.
        return jsonify({"status": "ERROR", "message": str(e), "where": "api_parcels"}), 500


@app.get("/api/geojson_files")
def api_geojson_files():
    """Return the list of ALL GeoJSON parcel boundary files under /data (recursive).

    Why: In practice, parcels may be stored in multiple subfolders (e.g. geojson_yeni_klasor4,
    geojson_yeni_klasor5, etc.). This endpoint discovers *every* .geojson file under DATA_DIR,
    so the frontend can render ALL parcels without hard-coding filenames.

    Response:
      - base: "data" (frontend should load each file at `${base}/${relative_path}`)
      - files: paths relative to DATA_DIR, POSIX style (e.g. "geojson_yeni_klasor5/x.geojson")
    """
    if not DATA_DIR.exists():
        return jsonify({
            "status": "ERROR",
            "message": "DATA_DIR not found",
            "data_dir": str(DATA_DIR),
        }), 404

    ignore_dirs = {
        "__pycache__", ".git", ".idea", ".vscode", "node_modules",
        ".venv", "venv", "env", "dist", "build", "boundaries", "village_boundaries", "geojson_generated_multi_village"
    }

    files = []
    # v17: Varsayılan harita katmanı yalnızca kullanıcının yüklediği GERÇEK GeoJSON klasörüdür.
    # Excel alanından otomatik üretilen temsili dikdörtgen poligonlar haritadan kaldırıldı.
    preferred_dir = DATA_DIR / "geojson_yeni_klasor4"
    scan_roots = [preferred_dir] if preferred_dir.exists() else [DATA_DIR]
    for scan_root in scan_roots:
        pattern = scan_root.glob("*.geojson") if scan_root != DATA_DIR else DATA_DIR.rglob("*.geojson")
        for p in pattern:
            try:
                if any(part in ignore_dirs for part in p.parts):
                    continue
                rel = p.relative_to(DATA_DIR).as_posix()
                files.append(rel)
            except Exception:
                continue

    files = sorted(set(files), key=lambda s: s.lower())

    payload = {
        "status": "OK",
        "base": "data",
        "files": files,
        "count": len(files),
    }

    # Also write a static index file for offline/static fallback.
    try:
        (DATA_DIR / "_geojson_index.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception:
        pass

    return jsonify(payload)




@app.get("/api/geojson_bundle")
def api_geojson_bundle_v36():
    """Return persistent parcel GeoJSONs as one server-side FeatureCollection.

    v38: Tüm yüklenmiş parsel GeoJSON dosyaları tek paket halinde sunulur; köy sınırları ve baraj ayrı katmanda kalır.
    This prevents the screen from showing only a large village boundary when the user
    expects individual parcels. Real parcel files are read from data/geojson_yeni_klasor4;
    village boundaries remain under data/village_boundaries and are controlled separately.
    """
    preferred_dir = DATA_DIR / "geojson_yeni_klasor4"
    meta_path = DATA_DIR / "parcel_meta_map.json"
    registry_path = DATA_DIR / "parcel_drawing_registry_2024.json"
    meta_by_file = {}
    meta_by_id = {}
    registry = []
    try:
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta_by_file = meta.get("by_file", {}) or {}
            meta_by_id = meta.get("by_id", {}) or {}
    except Exception:
        meta_by_file = {}
        meta_by_id = {}
    try:
        if registry_path.exists():
            raw = json.loads(registry_path.read_text(encoding="utf-8"))
            registry = raw if isinstance(raw, list) else (raw.get("records", []) if isinstance(raw, dict) else [])
    except Exception:
        registry = []

    def _file_village(name: str) -> str:
        low = name.lower()
        if "bahceli" in low or "bahçeli" in low:
            return "Bahçeli"
        if "sazlica" in low or "sazlıca" in low:
            return "Sazlıca"
        if "kemerhisar" in low:
            return "Kemerhisar"
        if "kaynarca" in low:
            return "Kaynarca"
        if "borilce" in low or "bor_ilce" in low or "bor ilce" in low or "bor_ilçe" in low or "bor ilçe" in low or "borilcemerkezi" in low or "bor_ilce_merkezi" in low or "bor_ilçe_merkezi" in low or "bor_merkez" in low:
            return "Bor İlçe Merkezi"
        return ""

    def _is_boundary_or_reservoir(name: str, props=None) -> bool:
        low = name.lower()
        kind = str((props or {}).get("kind") or "").lower()
        title = str((props or {}).get("title") or "").lower()
        joined = " ".join([low, kind, title])
        if any(t in joined for t in ["sinir", "sınır", "boundary", "koy_siniri", "köy sınırı", "village_boundary"]):
            return True
        if any(t in joined for t in ["baraj", "akkaya", "reservoir", "göl", "gol"]):
            return True
        return False

    def _water_mode(name: str, props: dict, meta: dict) -> str:
        for k in ("water_mode", "irrigation_key", "irr_key"):
            v = str((props or {}).get(k) or (meta or {}).get(k) or "").strip().lower()
            if v in ("kuru", "rainfed", "dry"):
                return "kuru"
            if v in ("sulu", "irrigated", "drip", "sprinkler", "damla", "yağmurlama", "yagmurlama"):
                return "sulu"
        low = name.lower()
        if "_kuru_" in low or low.startswith("kuru_"):
            return "kuru"
        if "_sulu_" in low or low.startswith("sulu_"):
            return "sulu"
        return ""

    def _ensure_closed(feature: dict) -> dict:
        try:
            g = feature.get("geometry") or {}
            if g.get("type") == "LineString" and isinstance(g.get("coordinates"), list) and len(g["coordinates"]) >= 3:
                ring = list(g["coordinates"])
                if ring[0] != ring[-1]:
                    ring.append(ring[0])
                feature["geometry"] = {"type": "Polygon", "coordinates": [ring]}
            elif g.get("type") == "Polygon" and g.get("coordinates") and g["coordinates"][0]:
                ring = g["coordinates"][0]
                if ring[0] != ring[-1]:
                    ring.append(ring[0])
        except Exception:
            pass
        return feature

    parcels = {"type": "FeatureCollection", "features": []}
    reservoirs = {"type": "FeatureCollection", "features": []}
    files = []
    skipped = []
    errors = []

    if not preferred_dir.exists():
        return jsonify({"status": "ERROR", "message": "geojson_yeni_klasor4 not found"}), 404

    for path in sorted(preferred_dir.glob("*.geojson"), key=lambda x: x.name.lower()):
        name = path.name
        rel = path.relative_to(DATA_DIR).as_posix()
        try:
            gj = json.loads(path.read_text(encoding="utf-8"))
            feats = gj.get("features") if isinstance(gj, dict) and gj.get("type") == "FeatureCollection" else ([gj] if isinstance(gj, dict) and gj.get("type") == "Feature" else [])
            if not feats:
                continue
            feat = json.loads(json.dumps(feats[0], ensure_ascii=False))
            if not feat.get("geometry"):
                continue
            props = feat.get("properties") if isinstance(feat.get("properties"), dict) else {}
            feat["properties"] = props

            if _is_boundary_or_reservoir(name, props):
                if "baraj" in name.lower() or "akkaya" in name.lower() or "reservoir" in str(props).lower():
                    props["kind"] = "reservoir"
                    reservoirs["features"].append(_ensure_closed(feat))
                skipped.append({"file": rel, "reason": "boundary_or_reservoir_not_parcel"})
                continue

            raw_pid = props.get("id") or props.get("name") or props.get("parcel_id") or ""
            m_pid = re.search(r"(P\d+)", str(raw_pid), flags=re.I) or re.search(r"(P\d+)", name, flags=re.I)
            pid = m_pid.group(1).upper() if m_pid else ""
            mm = meta_by_file.get(name, {}) or (meta_by_id.get(pid, {}) if pid else {}) or {}
            if not pid:
                pid = str(mm.get("pid") or mm.get("parcel_id") or Path(name).stem)
            props["id"] = str(pid)
            props["name"] = str(pid)
            props["source_file"] = rel
            props["source_label"] = props.get("source_label") or name

            props["village"] = props.get("village") or mm.get("village") or _file_village(name)
            props["district"] = props.get("district") or mm.get("district") or "Merkez"
            props["current_crop"] = props.get("current_crop") or mm.get("crop") or props.get("crop") or ""
            props["farmer_name"] = props.get("farmer_name") or mm.get("farmer_name") or props.get("farmer") or ""
            props["farmer_id"] = props.get("farmer_id") or mm.get("farmer_id") or props.get("owner_username") or ""
            props["assigned_pattern"] = props.get("assigned_pattern") or mm.get("selected_pattern") or props.get("current_crop") or ""
            props["assigned_alternative_label"] = props.get("assigned_alternative_label") or mm.get("selected_alternative_label") or "Mevcut desen / Excel referansı"
            props["geometry_status"] = "Yüklü gerçek GeoJSON"
            props["assignment_status_label"] = "GeoJSON yüklü, seçilebilir"
            props["water_mode"] = _water_mode(name, props, mm)
            props["is_orchard"] = bool(props.get("is_orchard") if "is_orchard" in props else mm.get("orchard", False))
            props["parcel_type"] = props.get("parcel_type") or mm.get("parcel_type") or ("orchard" if props["is_orchard"] else "field")

            for key in ("area_da", "area_official_da", "water_m3_current", "profit_tl_current", "assigned_water_m3", "assigned_profit_tl"):
                if props.get(key) in (None, "") and mm.get(key) not in (None, ""):
                    props[key] = mm.get(key)
            if props.get("area_da") in (None, "") and mm.get("area_da") not in (None, ""):
                props["area_da"] = mm.get("area_da")

            _ensure_closed(feat)
            files.append(rel)
            parcels["features"].append(feat)
        except Exception as e:
            errors.append({"file": rel, "error": str(e)})

    counts_by_village = {}
    for f in parcels["features"]:
        v = str((f.get("properties") or {}).get("village") or "Bilinmiyor")
        counts_by_village[v] = counts_by_village.get(v, 0) + 1

    expected_by_village = {}
    try:
        for r in registry:
            if not isinstance(r, dict):
                continue
            v = str(r.get("village") or r.get("köy") or "").strip()
            pid = str(r.get("parcel_id") or r.get("id") or "").strip()
            if v and pid and not re.search(r"kızılca|kizilca", v, re.I):
                expected_by_village[v] = expected_by_village.get(v, 0) + 1
    except Exception:
        expected_by_village = {}
    missing_by_village = {v: max(0, int(expected_by_village.get(v, 0)) - int(counts_by_village.get(v, 0))) for v in expected_by_village}

    return jsonify({
        "status": "OK",
        "version": "v39",
        "base": "data/geojson_yeni_klasor4",
        "files": files,
        "skipped": skipped,
        "parcels": parcels,
        "reservoirs": reservoirs,
        "count": len(parcels["features"]),
        "reservoir_count": len(reservoirs["features"]),
        "counts_by_village": counts_by_village,
        "expected_by_village": expected_by_village,
        "missing_by_village": missing_by_village,
        "errors": errors,
    })

@app.post("/api/save_panel_geojson")
def api_save_panel_geojson_v36():
    """Save a panel-drawn parcel GeoJSON into data/geojson_yeni_klasor4.

    v36: Kaynarca/Kemerhisar/Bor İlçe Merkezi dahil tüm köylerde dosya adı köy + sulama tipi + ürün + alan + parsel ID
    düzeninde üretilir ve bundle endpointi tarafından otomatik okunur.

    This makes drawings persistent when the app is run through Flask. If the UI is opened
    as static files, the frontend still exports/downloads the GeoJSON, but the browser cannot
    write into the zip by itself.
    """
    try:
        payload = request.get_json(force=True, silent=False) or {}
        feature = payload.get("feature") or {}
        props = feature.get("properties") or {}
        if feature.get("type") != "Feature" or not feature.get("geometry"):
            return jsonify({"status":"ERROR", "message":"Feature geometry missing"}), 400
        parcel_id = str(props.get("id") or props.get("name") or payload.get("parcel_id") or "parsel").strip()
        village = str(props.get("village") or payload.get("village") or "parsel").strip()
        crop = str(props.get("current_crop") or props.get("assigned_pattern") or payload.get("crop") or "urun").strip()
        irr_key = str(props.get("irrigation_key") or "").strip().lower()
        irr = str(props.get("irrigation_current") or props.get("irrigation_label") or "").lower()
        water_word = "kuru" if ("kuru" in irr or "yağış" in irr or irr_key == "rainfed") else "sulu"
        try:
            area_da = float(str(props.get("area_official_da") or props.get("area_da") or payload.get("area_da") or 0).replace(",", "."))
        except Exception:
            area_da = 0.0
        def slugify(s):
            tr = str.maketrans({'ç':'c','Ç':'c','ğ':'g','Ğ':'g','ı':'i','İ':'i','ö':'o','Ö':'o','ş':'s','Ş':'s','ü':'u','Ü':'u'})
            s = str(s or '').translate(tr).lower()
            s = re.sub(r'\s+', '_', s)
            s = re.sub(r'[^a-z0-9_\-]+', '_', s)
            s = re.sub(r'_+', '_', s).strip('_')
            return s or 'parsel'
        area_part = (str(int(round(area_da))) if abs(area_da-round(area_da)) < 1e-9 else f"{area_da:.1f}".replace('.', ',')) + " da"
        filename = f"{slugify(village)}_{water_word}_{slugify(crop)}_{area_part}_{slugify(parcel_id).upper()}.geojson"
        out_dir = DATA_DIR / "geojson_yeni_klasor4"
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_name = filename.replace("/", "_").replace("\\", "_")
        feature["properties"] = props
        feature["properties"]["source_file"] = f"geojson_yeni_klasor4/{safe_name}"
        feature["properties"]["source_label"] = safe_name
        feature["properties"]["geometry_source"] = feature["properties"].get("geometry_source") or "panel_saved_geojson"
        feature["properties"]["geometry_status"] = feature["properties"].get("geometry_status") or "Yüklü gerçek GeoJSON"
        (out_dir / safe_name).write_text(json.dumps(feature, ensure_ascii=False, indent=2), encoding="utf-8")
        files = sorted([f"geojson_yeni_klasor4/{p.name}" for p in out_dir.glob("*.geojson") if p.is_file()], key=lambda x: x.lower())
        idx = {"status":"OK", "base":"data", "files":files, "count":len(files)}
        try:
            (DATA_DIR / "_geojson_index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
            (out_dir / "_index.json").write_text(json.dumps({"status":"OK", "files":[Path(f).name for f in files], "count":len(files)}, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

        # v36: Kalıcı kayıt sadece dosyayı yazmakla kalmaz; çizim kütüğü ve meta haritası da güncellenir.
        # Böylece Bor İlçe Merkezi dahil yeni çizimler yeniden açılışta Sazlıca/Bahçeli/Kaynarca ile aynı biçimde görünür.
        try:
            pid_key = str(parcel_id).strip()
            rel_path = f"geojson_yeni_klasor4/{safe_name}"
            status_updates = {
                "geometry_status": "Yüklü gerçek GeoJSON",
                "geometry_source": "panel_saved_geojson",
                "has_real_geojson": True,
                "drawing_required": False,
                "assignment_status": "geometry_ready",
                "assignment_status_label": "GeoJSON yüklü, seçilebilir",
                "geojson_file": rel_path,
                "source_file": rel_path,
            }
            # Registry JSON
            reg_path = DATA_DIR / "parcel_drawing_registry_2024.json"
            if reg_path.exists():
                raw = json.loads(reg_path.read_text(encoding="utf-8"))
                records = raw.get("records", []) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
                for rr in records:
                    if str(rr.get("parcel_id") or rr.get("id") or "").strip() == pid_key:
                        rr.update(status_updates)
                        rr["village"] = rr.get("village") or village
                        rr["current_crop"] = rr.get("current_crop") or crop
                        break
                if isinstance(raw, dict):
                    raw["records"] = records
                    raw["updated_at"] = datetime.now().isoformat(timespec="seconds")
                    raw["note"] = "v36 panel kayıt sonrası geometri durumları güncellendi"
                    reg_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
                else:
                    reg_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
            # Registry CSV
            reg_csv = DATA_DIR / "parcel_drawing_registry_2024.csv"
            if reg_csv.exists():
                import csv
                rows=[]
                with reg_csv.open("r", encoding="utf-8-sig", newline="") as fh:
                    reader=csv.DictReader(fh)
                    fields=list(reader.fieldnames or [])
                    extra=[k for k in status_updates.keys() if k not in fields]
                    fields += extra
                    for rr in reader:
                        if str(rr.get("parcel_id") or rr.get("id") or "").strip() == pid_key:
                            for k,v in status_updates.items(): rr[k] = str(v) if not isinstance(v, bool) else ("True" if v else "False")
                        rows.append(rr)
                with reg_csv.open("w", encoding="utf-8-sig", newline="") as fh:
                    writer=csv.DictWriter(fh, fieldnames=fields)
                    writer.writeheader(); writer.writerows(rows)
            # Meta map
            meta_path = DATA_DIR / "parcel_meta_map.json"
            meta = {"by_file": {}, "by_id": {}}
            if meta_path.exists():
                try: meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception: meta = {"by_file": {}, "by_id": {}}
            by_file = meta.setdefault("by_file", {})
            by_id = meta.setdefault("by_id", {})
            m = dict(by_id.get(pid_key, {}) or {})
            m.update({
                "pid": pid_key,
                "parcel_id": pid_key,
                "village": village,
                "district": props.get("district") or "Merkez",
                "crop": crop,
                "current_crop": crop,
                "farmer_id": props.get("farmer_id") or "",
                "farmer_name": props.get("farmer_name") or props.get("farmer") or "",
                "selected_pattern": props.get("selected_pattern") or props.get("assigned_pattern") or crop,
                "selected_alternative_label": props.get("selected_alternative_label") or props.get("assigned_alternative_label") or "Mevcut desen / Excel referansı",
                "area_da": area_da,
                "geojson_file": rel_path,
                "source_file": rel_path,
                "geometry_status": "Yüklü gerçek GeoJSON",
                "has_real_geojson": True,
                "drawing_required": False,
            })
            by_id[pid_key] = m
            by_file[safe_name] = m
            meta["updated_at"] = datetime.now().isoformat(timespec="seconds")
            meta["note"] = "v36 panel kayıt sonrası dosya/parsel meta eşleştirmesi güncellendi"
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as meta_err:
            app.logger.warning("v36 registry/meta update failed: %s", meta_err)

        return jsonify({"status":"OK", "filename": safe_name, "rel_path": f"geojson_yeni_klasor4/{safe_name}", "count": len(files)})
    except Exception as e:
        return jsonify({"status":"ERROR", "message": str(e)}), 500


@app.get("/api/boundary/nigde")
def api_boundary_nigde():
    """Return Niğde province boundary as GeoJSON (FeatureCollection).

    Priority:
      1) data/boundaries/nigde_il_siniri.geojson (if provided for offline use)
      2) Fetch from Simplemaps admin1 dataset and extract TR51 (Niğde) (requires internet)

    If internet is blocked, please place the boundary file in data/boundaries/.
    """
    local_path = DATA_DIR / "boundaries" / "nigde_il_siniri.geojson"
    if local_path.exists():
        try:
            gj = json.loads(local_path.read_text(encoding="utf-8"))
            if isinstance(gj, dict) and gj.get("type") == "Feature":
                gj = {"type": "FeatureCollection", "features": [gj]}
            return jsonify({"status": "OK", "source": "local", "geojson": gj})
        except Exception as e:
            return jsonify({"status": "ERROR", "message": f"Failed to read local boundary: {e}"}), 500

    key = "nigde_boundary_cached"
    if key in _cache:
        return jsonify({"status": "OK", "source": "cache", "geojson": _cache[key]})

    url = "https://simplemaps.com/static/svg/country/tr/admin1/tr.json"
    try:
        import urllib.request

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (SazlicaApp)",
                "Accept": "application/json,text/plain;q=0.9,*/*;q=0.8",
            },
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            raw = resp.read().decode("utf-8", "ignore")
        data = json.loads(raw)

        features = []
        if isinstance(data, dict) and isinstance(data.get("features"), list):
            features = data["features"]
        elif isinstance(data, dict) and isinstance(data.get("shapes"), list):
            for sh in data["shapes"]:
                if isinstance(sh, dict) and "geometry" in sh:
                    features.append({
                        "type": "Feature",
                        "properties": {k: v for k, v in sh.items() if k != "geometry"},
                        "geometry": sh.get("geometry"),
                    })

        target = None
        for f in features:
            props = (f or {}).get("properties") or {}
            fid = str(props.get("id") or props.get("code") or props.get("adm1_code") or "").strip()
            name = str(props.get("name") or props.get("NAME_1") or props.get("adm1_name") or "").strip()
            low = (name or "").lower()
            if fid.upper() == "TR51" or low in ("nigde", "niğde") or ("niğde" in low) or ("nigde" in low):
                target = f
                break

        if not target:
            return jsonify({"status": "ERROR", "message": "Niğde feature not found in admin1 dataset"}), 404

        fc = {"type": "FeatureCollection", "features": [target]}
        _cache[key] = fc
        return jsonify({"status": "OK", "source": "simplemaps", "geojson": fc})

    except Exception as e:
        return jsonify({
            "status": "ERROR",
            "message": f"Boundary not available (no local file, and online fetch failed): {e}",
            "hint": "Place data/boundaries/nigde_il_siniri.geojson for offline use.",
        }), 502





def _top_recommended_crops(details: List[Dict[str, Any]], top_n: int = 8) -> List[Dict[str, Any]]:
    rows = []
    for d in details or []:
        crop = str(d.get("chosenCrop") or d.get("crop") or "").strip()
        if not crop:
            continue
        area = safe_float(d.get("area_da", 0.0), 0.0)
        water = safe_float(d.get("water_m3", 0.0), 0.0)
        profit = safe_float(d.get("profit_tl", 0.0), 0.0)
        rows.append({"crop": crop, "area_da": area, "water_m3": water, "profit_tl": profit})
    if not rows:
        return []
    df = pd.DataFrame(rows)
    g = df.groupby("crop", dropna=False).agg(area_da=("area_da", "sum"), water_m3=("water_m3", "sum"), profit_tl=("profit_tl", "sum")).reset_index()
    g = g.sort_values(["area_da", "profit_tl"], ascending=[False, False]).head(top_n)
    out = []
    for _, r in g.iterrows():
        out.append({
            "crop": str(r.get("crop", "")),
            "area_da": float(r.get("area_da", 0.0)),
            "water_m3": float(r.get("water_m3", 0.0)),
            "profit_tl": float(r.get("profit_tl", 0.0)),
        })
    return out


def build_data_quality_report() -> Dict[str, Any]:
    frames = load_enhanced_frames()
    catalog = load_crop_catalog()
    parcels = load_parcels() or []
    out: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "build": APP_BUILD,
        "parcel_count": int(len(parcels)),
        "catalog_crop_count": int(len(catalog or {})),
    }

    manifest_path = DATA_DIR / "SAZLICA_DATA_MANIFEST.json"
    if manifest_path.exists():
        try:
            out["manifest"] = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            out["manifest"] = {"warning": "manifest okunamadı"}

    # GeoJSON coverage transparency
    try:
        legacy_geo_dir = DATA_DIR / "geojson_yeni_klasor4"
        active_geo_dir = legacy_geo_dir
        geo_files = sorted([fp for fp in active_geo_dir.glob("*.geojson") if fp.is_file()]) if active_geo_dir.exists() else []
        meta_map_path = DATA_DIR / "parcel_meta_map.json"
        covered_ids = set()
        geometry_source = "uploaded_real_geojson"
        if meta_map_path.exists():
            try:
                mm = json.loads(meta_map_path.read_text(encoding="utf-8"))
                by_id = (mm.get("by_id") if isinstance(mm, dict) else {}) or {}
                for k, v in by_id.items():
                    relp = str((v or {}).get("rel_path") or "").strip()
                    if relp and (DATA_DIR / relp).exists():
                        covered_ids.add(normalize_parcel_id(k))
            except Exception:
                covered_ids = set()
        total_ids = {normalize_parcel_id(p.get("id") or p.get("parcel_id") or p.get("parsel_id") or "") for p in parcels}
        total_ids.discard("")
        out["geojson_coverage"] = {
            "files": int(len(geo_files)),
            "mapped_parcels": int(len(covered_ids)),
            "total_parcels": int(len(total_ids)),
            "coverage_ratio": float(len(covered_ids) / max(1, len(total_ids))),
            "geometry_source": geometry_source,
            "note": "Haritada yalnızca yüklenmiş gerçek GeoJSON sınırları gösterilir. Excel'deki diğer köy/parsel kayıtları sayısal analizde kullanılır; gerçek GeoJSON sınırı yoksa haritada temsili dikdörtgen üretilmez."
        }
    except Exception as e:
        out["geojson_coverage"] = {"error": str(e)}

    suit_path = DATA_DIR / "enhanced_dataset" / "csv" / "crop_suitability_assumed.csv"
    if suit_path.exists():
        try:
            suit_df = pd.read_csv(suit_path)
            sc_col = next((c for c in ["suitability_score_assumed", "suitability_score", "score"] if c in suit_df.columns), None)
            status_col = next((c for c in ["suitability_status", "rule"] if c in suit_df.columns), None)
            out["suitability"] = {
                "rows": int(len(suit_df)),
                "filled_ratio": float((suit_df[sc_col].notna().mean()) if sc_col else 0.0),
                "status_counts": ({str(k): int(v) for k, v in suit_df[status_col].fillna("bos").value_counts().to_dict().items()} if status_col else {}),
            }
        except Exception as e:
            out["suitability"] = {"error": str(e)}

    market_path = DATA_DIR / "enhanced_dataset" / "csv" / "market_overrides_demo.csv"
    if market_path.exists():
        try:
            mdf = pd.read_csv(market_path)
            src_col = "ekonomi_kaynak_durumu" if "ekonomi_kaynak_durumu" in mdf.columns else None
            out["economy"] = {
                "rows": int(len(mdf)),
                "price_coverage": float(mdf["price_tl_kg"].notna().mean()) if "price_tl_kg" in mdf.columns else 0.0,
                "cost_coverage": float(mdf["cost_tl_da"].notna().mean()) if "cost_tl_da" in mdf.columns else 0.0,
                "source_status_counts": ({str(k): int(v) for k, v in mdf[src_col].fillna("bos").value_counts().to_dict().items()} if src_col else {}),
            }
        except Exception as e:
            out["economy"] = {"error": str(e)}

    try:
        s1 = normalize_parcel_id_series(frames.get("s1", pd.DataFrame()).copy(), ["parcel_id"])
        s2 = normalize_parcel_id_series(frames.get("s2", pd.DataFrame()).copy(), ["parcel_id"])
        if len(s1) and len(s2):
            keys = [c for c in ["parcel_id", "crop", "season"] if c in s1.columns and c in s2.columns]
            compare_cols = [c for c in ["area_da", "water_m3_calib_gross", "profit_tl"] if c in s1.columns and c in s2.columns]
            merged = s1[keys + compare_cols].merge(s2[keys + compare_cols], on=keys, how="outer", suffixes=("_s1", "_s2"), indicator=True)
            scenario_report = {
                "s1_rows": int(len(s1)),
                "s2_rows": int(len(s2)),
                "s1_seasons": sorted({str(x) for x in s1.get("season", pd.Series(dtype=str)).dropna().astype(str).unique().tolist()}),
                "s2_seasons": sorted({str(x) for x in s2.get("season", pd.Series(dtype=str)).dropna().astype(str).unique().tolist()}),
                "common_rows": int((merged["_merge"] == "both").sum()),
                "s2_has_secondary": bool((s2.get("season", pd.Series(dtype=str)).astype(str).str.lower() == "secondary").any()) if "season" in s2.columns else False,
            }
            identical_all = []
            for c in compare_cols:
                a = pd.to_numeric(merged[f"{c}_s1"], errors="coerce")
                b = pd.to_numeric(merged[f"{c}_s2"], errors="coerce")
                same = ((a.fillna(-999999) - b.fillna(-999999)).abs() < 1e-9)
                identical_ratio = float(same.mean()) if len(same) else 1.0
                scenario_report[c] = {
                    "identical_ratio": identical_ratio,
                    "mean_s1": float(a.dropna().mean()) if a.notna().any() else None,
                    "mean_s2": float(b.dropna().mean()) if b.notna().any() else None,
                }
                identical_all.append(identical_ratio)
            scenario_report["is_meaningfully_separated"] = bool((scenario_report.get("s2_has_secondary") is True) and (min(identical_all) < 0.98 if identical_all else False))
            out["scenario_separation"] = scenario_report
    except Exception as e:
        out["scenario_separation"] = {"error": str(e)}

    rr = load_rotation_rules()
    out["rotation_rules"] = {
        "rows": int(len(rr)),
        "rule_ids": [str(x) for x in rr.get("rule_id", pd.Series(dtype=str)).tolist()] if len(rr) else [],
    }

    # Matrix feasibility and current-crop coverage
    try:
        mx = load_matrix_candidates().copy()
        if len(mx):
            if "parcel_id" in mx.columns:
                mx["parcel_id"] = mx["parcel_id"].astype(str).map(normalize_parcel_id)
            zero_feasible = 0
            low_choice = 0
            parcel_ids = sorted({str(x) for x in mx["parcel_id"].astype(str).tolist()})
            feas = pd.DataFrame()
            if ("current_quota_m3" in mx.columns) and ("water_m3_da" in mx.columns) and ("area_da" in mx.columns):
                tmp = mx.copy()
                tmp["_quota"] = pd.to_numeric(tmp["current_quota_m3"], errors="coerce").fillna(0.0)
                tmp["_wda"] = pd.to_numeric(tmp["water_m3_da"], errors="coerce").fillna(0.0)
                tmp["_area"] = pd.to_numeric(tmp["area_da"], errors="coerce").fillna(0.0)
                tmp["_feasible_area"] = np.where(tmp["_wda"] > 0, np.minimum(tmp["_area"], tmp["_quota"] / np.maximum(tmp["_wda"], 1e-9)), 0.0)
                feas = tmp[tmp["_feasible_area"] > 1e-6].copy()
                cnt = feas.groupby("parcel_id").size() if len(feas) else pd.Series(dtype=int)
                zero_feasible = int(sum(1 for pid in parcel_ids if int(cnt.get(pid, 0)) == 0))
                low_choice = int(sum(1 for pid in parcel_ids if int(cnt.get(pid, 0)) <= 3))

            pa = normalize_parcel_id_series(_read_csv_safe(frames["files"].get("parcels") if isinstance(frames.get("files"), dict) else None), ["parcel_id", "parsel_id", "id"])
            missing_current = []
            if len(pa) and "current_crop" in pa.columns and "parcel_id" in pa.columns:
                cur_rows = mx[pd.to_numeric(mx.get("is_current_crop", 0), errors="coerce").fillna(0) > 0].copy() if "is_current_crop" in mx.columns else pd.DataFrame()
                cur_rows["crop_key"] = cur_rows.get("crop", pd.Series(dtype=str)).map(canonical_crop_key) if len(cur_rows) else pd.Series(dtype=str)
                cur_set = {(str(r["parcel_id"]), str(r["crop_key"])) for _, r in cur_rows.iterrows()} if len(cur_rows) else set()
                for _, r in pa.iterrows():
                    pid = str(r.get("parcel_id") or r.get("parsel_id") or r.get("id") or "")
                    ck = canonical_crop_key(r.get("current_crop") or "")
                    if pid and ck and (pid, ck) not in cur_set:
                        missing_current.append(pid)
            out["matrix_feasibility"] = {
                "rows": int(len(mx)),
                "parcels_zero_feasible": int(zero_feasible),
                "parcels_low_choice_3_or_less": int(low_choice),
                "feasibility_definition": "Parsel kotası altında en az kısmi ekim alanı üretilebilen aday sayısı",
                "missing_current_crop_in_candidates": sorted(missing_current)[:50],
                "missing_current_crop_count": int(len(missing_current)),
            }
    except Exception as e:
        out["matrix_feasibility"] = {"error": str(e)}
    return out



def build_validation_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = payload or {}
    selected = payload.get("selectedParcelIds") or payload.get("selected") or []
    if isinstance(selected, str):
        selected = [normalize_parcel_id(s) for s in selected.split(",") if str(s).strip()]
    elif not isinstance(selected, list):
        selected = list(selected) if selected else []
    algorithm = str(payload.get("algorithm", "GA") or "GA")
    scenario = str(payload.get("scenario", "su_tasarruf") or "su_tasarruf")
    year_raw = payload.get("year", None)
    year_val = None if year_raw in (None, "", "none", "null") else safe_int(year_raw, 0)
    if year_val == 0:
        year_val = None
    options = payload.get("options", {}) if isinstance(payload.get("options", {}), dict) else {}
    water_budget_ratio = safe_float(payload.get("waterBudgetRatio", 1.0), 1.0)

    baseline = optimize(selected, algorithm, "current", 1.0, year_val, options)
    candidate = optimize(selected, algorithm, scenario, water_budget_ratio, year_val, options)
    stress_budget = optimize(selected, algorithm, scenario, water_budget_ratio * 0.85, year_val, options)

    base_water = safe_float(baseline.get("total_water_m3", 0.0), 0.0)
    base_profit = safe_float(baseline.get("total_profit_tl", 0.0), 0.0)
    cand_water = safe_float(candidate.get("total_water_m3", 0.0), 0.0)
    cand_profit = safe_float(candidate.get("total_profit_tl", 0.0), 0.0)
    stress_water = safe_float(stress_budget.get("total_water_m3", 0.0), 0.0)
    stress_profit = safe_float(stress_budget.get("total_profit_tl", 0.0), 0.0)

    water_delta_pct = ((cand_water - base_water) / base_water * 100.0) if base_water > 0 else None
    profit_delta_pct = ((cand_profit - base_profit) / base_profit * 100.0) if base_profit > 0 else None
    price_shock_profit_tl = cand_profit * 0.90
    robustness = "orta"
    if (stress_budget.get("feasible") is True) and (price_shock_profit_tl >= 0.8 * cand_profit):
        robustness = "güçlü"
    elif (stress_budget.get("feasible") is False) or (price_shock_profit_tl < 0.7 * cand_profit):
        robustness = "kırılgan"

    score_components = candidate.get("score_components") or ((candidate.get("meta") or {}).get("score_components")) or {}
    dominant_constraint = None
    if isinstance(score_components, dict) and score_components:
        numeric_items = []
        for k, v in score_components.items():
            try:
                numeric_items.append((k, abs(float(v))))
            except Exception:
                pass
        if numeric_items:
            dominant_constraint = sorted(numeric_items, key=lambda x: x[1], reverse=True)[0][0]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "request": {
            "selected_count": len(selected),
            "algorithm": algorithm,
            "scenario": scenario,
            "year": year_val,
            "season_source": str(options.get("seasonSource", "s1")),
        },
        "baseline": {
            "total_water_m3": base_water,
            "total_profit_tl": base_profit,
            "efficiency_tl_per_m3": safe_float(baseline.get("efficiency_tl_per_m3", 0.0), 0.0),
        },
        "optimized": {
            "total_water_m3": cand_water,
            "total_profit_tl": cand_profit,
            "efficiency_tl_per_m3": safe_float(candidate.get("efficiency_tl_per_m3", 0.0), 0.0),
            "feasible": bool(candidate.get("feasible", False)),
            "water_delta_pct_vs_current": water_delta_pct,
            "profit_delta_pct_vs_current": profit_delta_pct,
            "top_recommended_crops": _top_recommended_crops(candidate.get("details", []), 10),
        },
        "stress_tests": {
            "budget_minus_15": {
                "feasible": bool(stress_budget.get("feasible", False)),
                "total_water_m3": stress_water,
                "total_profit_tl": stress_profit,
            },
            "price_minus_10_ex_post": {
                "optimized_profit_tl_after_shock": price_shock_profit_tl,
                "note": "Bu test yeniden optimizasyon değil; mevcut planın fiyat şokuna maruziyetini gösterir.",
            },
        },
        "decision_rationale": {
            "dominant_constraint": dominant_constraint,
            "robustness": robustness,
            "explainability_available": bool(candidate.get("meta")),
            "note": "Su ve kâr farkları mevcut desen referansına göre hesaplandı."
        }
    }


def build_water_allocation_logic() -> Dict[str, Any]:
    """Expose v42 water-allocation logic.

    v42 change:
      - The default planning quota is no longer "each village gets the same total water".
      - The default is area/dekar fairness: total observed current water / total area.
      - Equal-village allocation remains visible as a comparison model because it is administratively
        simple, but it can over-advantage small-area/low-demand villages and restrict larger areas.
    """
    out: Dict[str, Any] = {
        "version": "v47_area_fair_per_da_default_decision_model",
        "recommended_model": "area_fair_per_da",
        "allocation_model": "Ana karar modeli: observed_current_total_water -> total m3/da -> parcel area × m3/da; eşit köy modeli yalnızca karşılaştırmadır",
        "villages_expected": 5,
        "villages": [],
        "totals": {},
        "reservoir_context": {},
        "fairness": {},
        "allocation_models": [
            {
                "key": "area_fair_per_da",
                "label": "Dekar bazlı adil kota",
                "is_default": True,
                "description": "Toplam mevcut su toplam alana bölünür; her parsel alanı kadar su hakkı alır. Dekar başına eşitlik sağlar.",
            },
            {
                "key": "equal_village_equal_parcel",
                "label": "Eşit köy + eşit parsel kotası",
                "is_default": False,
                "description": "Her köye aynı toplam su verilir; köy içinde her parsele aynı kota düşer. Yalnızca karşılaştırma/idari eşitlik senaryosudur; dekar adaleti sağlamaz.",
            },
            {
                "key": "current_demand_reference",
                "label": "Mevcut talep referansı",
                "is_default": False,
                "description": "Her parselin mevcut ürün desenindeki su talebi korunur. Mevcut düzeni gösterir; tasarruf baskısı oluşturmaz.",
            },
            {
                "key": "hybrid_area70_current30",
                "label": "Karma adalet",
                "is_default": False,
                "description": "%70 dekar bazlı adil kota + %30 mevcut talep referansı. Geçiş dönemi senaryosu olarak kullanılabilir.",
            },
        ],
        "formula": {
            "observed_current_total_water_m3": "Σ(mevcut parsel ürün suyu)",
            "total_observed_m3_per_da": "Σ(mevcut su) / Σ(alan_da)",
            "area_fair_parcel_quota_m3": "parcel_area_da × total_observed_m3_per_da",
            "area_fair_village_share_m3": "Σ(area_fair_parcel_quota_m3)",
            "equal_village_share_m3": "Σ(mevcut su) / aktif köy sayısı",
            "equal_parcel_quota_m3": "equal_village_share_m3 / village_parcel_count",
            "current_demand_reference_m3": "mevcut ürün deseninin parsel su tüketimi",
            "hybrid_area70_current30_m3": "0.70×area_fair_parcel_quota_m3 + 0.30×current_demand_reference_m3",
            "candidate_effective_area_da": "min(parcel_area_da, selected_quota_m3 / crop_water_m3_da)",
            "candidate_water_m3": "candidate_effective_area_da × crop_water_m3_da",
            "candidate_profit_tl": "candidate_effective_area_da × crop_profit_tl_da",
        },
        "interpretation": (
            "Bu çalışma barajdan ölçülen kesin çekişi doğrudan dağıtmaz; 5 köyün mevcut ürün deseninden "
            "hesaplanan tarımsal su talebini planlama referansı alır. v42'de öneri üretiminde ana kota "
            "dekar bazlıdır: herkes aynı m³/da hakkına sahip olur. Eşit köy payı ise yalnızca karşılaştırma "
            "senaryosu olarak ekranda tutulur."
        ),
        "fairness_note": (
            "Dekar bazlı model, tarımsal planlama açısından daha savunulabilir kabul edilir; çünkü 10 da ve "
            "7000 da parsel aynı suyu almaz. Eşit köy modeli idari olarak basittir ancak köylerin alan ve "
            "parsel dağılımı farklı olduğunda Kaynarca gibi küçük/az parsel içeren yerleri aşırı avantajlı, "
            "Bor veya Kemerhisar gibi büyük tüketim alanlarını ise fazla kısıtlı gösterebilir."
        )
    }

    # Parcel-level current demand and quota columns from the candidate matrix.
    mx_path = DATA_DIR / "excel_derived" / "combined_parcel_candidate_matrix_2024.csv"
    rows = []
    if mx_path.exists():
        try:
            mx = pd.read_csv(mx_path)
            parcel_base = mx[["parcel_id", "village", "area_da"]].drop_duplicates(subset=["parcel_id"]).copy()
            for c in ("area_da",):
                parcel_base[c] = pd.to_numeric(parcel_base[c], errors="coerce").fillna(0.0)

            if "is_current_crop" in mx.columns:
                cur = mx[mx["is_current_crop"].astype(str).isin(["1", "1.0", "true", "True"])].copy()
            else:
                cur = pd.DataFrame()
            if cur.empty and "current_crop_norm" in mx.columns and "candidate_crop_norm" in mx.columns:
                cur = mx[mx["current_crop_norm"].astype(str) == mx["candidate_crop_norm"].astype(str)].copy()
            cur = cur[["parcel_id", "water_m3_total", "profit_tl_total"]].drop_duplicates(subset=["parcel_id"]) if not cur.empty else pd.DataFrame(columns=["parcel_id", "water_m3_total", "profit_tl_total"])
            cur["water_m3_total"] = pd.to_numeric(cur.get("water_m3_total", 0), errors="coerce").fillna(0.0)
            cur["profit_tl_total"] = pd.to_numeric(cur.get("profit_tl_total", 0), errors="coerce").fillna(0.0)

            p = parcel_base.merge(cur, on="parcel_id", how="left")
            p["water_m3_total"] = pd.to_numeric(p.get("water_m3_total", 0), errors="coerce").fillna(0.0)
            p["profit_tl_total"] = pd.to_numeric(p.get("profit_tl_total", 0), errors="coerce").fillna(0.0)

            total_observed = float(p["water_m3_total"].sum())
            total_area_da = float(p["area_da"].sum())
            total_parcels = int(len(p))
            global_m3_per_da = (total_observed / total_area_da) if total_area_da else 0.0
            active_village_count = max(1, int(p["village"].dropna().astype(str).nunique()))
            equal_village_share = total_observed / active_village_count if total_observed else 0.0

            p["area_fair_parcel_quota_m3"] = p["area_da"] * global_m3_per_da
            p["current_demand_reference_m3"] = p["water_m3_total"]
            p["hybrid_area70_current30_m3"] = 0.70 * p["area_fair_parcel_quota_m3"] + 0.30 * p["current_demand_reference_m3"]

            grouped = p.groupby("village", dropna=False).agg(
                parcel_count=("parcel_id", "count"),
                total_area_da=("area_da", "sum"),
                observed_current_total_water_m3=("water_m3_total", "sum"),
                current_profit_tl=("profit_tl_total", "sum"),
                area_fair_share_m3=("area_fair_parcel_quota_m3", "sum"),
                current_demand_reference_share_m3=("current_demand_reference_m3", "sum"),
                hybrid_area70_current30_share_m3=("hybrid_area70_current30_m3", "sum"),
            ).reset_index()

            for _, r in grouped.iterrows():
                village = str(r.get("village", "") or "").strip()
                parcel_count = int(safe_int(r.get("parcel_count", 0), 0))
                area_da = float(safe_float(r.get("total_area_da", 0), 0.0))
                current_water = float(safe_float(r.get("observed_current_total_water_m3", 0), 0.0))
                area_fair_share = float(safe_float(r.get("area_fair_share_m3", 0), 0.0))
                current_demand_share = float(safe_float(r.get("current_demand_reference_share_m3", 0), 0.0))
                hybrid_share = float(safe_float(r.get("hybrid_area70_current30_share_m3", 0), 0.0))
                current_m3_da = current_water / area_da if area_da else 0.0
                current_per_parcel = current_water / max(1, parcel_count)
                equal_share = equal_village_share
                equal_per_parcel = equal_share / max(1, parcel_count)
                equal_m3_da = equal_share / area_da if area_da else 0.0
                area_fair_per_parcel_avg = area_fair_share / max(1, parcel_count)
                hybrid_per_parcel_avg = hybrid_share / max(1, parcel_count)

                rows.append({
                    "village": village,
                    "parcel_count": parcel_count,
                    "total_area_da": area_da,
                    "current_profit_tl": float(safe_float(r.get("current_profit_tl", 0), 0.0)),

                    "observed_current_total_water_m3": current_water,
                    "observed_current_avg_per_parcel_m3": current_per_parcel,
                    "observed_current_m3_per_da": current_m3_da,

                    "equal_village_share_m3": equal_share,
                    "equal_parcel_quota_m3": equal_per_parcel,
                    "equal_village_m3_per_da": equal_m3_da,
                    "equal_vs_current_change_m3": equal_share - current_water,
                    "equal_vs_current_change_pct": ((equal_share - current_water) / current_water * 100.0) if current_water else 0.0,
                    "equal_m3_per_da_change": equal_m3_da - current_m3_da,
                    "equal_m3_per_da_change_pct": ((equal_m3_da - current_m3_da) / current_m3_da * 100.0) if current_m3_da else 0.0,

                    "area_fair_share_m3": area_fair_share,
                    "area_fair_parcel_quota_avg_m3": area_fair_per_parcel_avg,
                    "area_fair_m3_per_da": global_m3_per_da,
                    "area_fair_vs_current_change_m3": area_fair_share - current_water,
                    "area_fair_vs_current_change_pct": ((area_fair_share - current_water) / current_water * 100.0) if current_water else 0.0,
                    "area_fair_m3_per_da_change": global_m3_per_da - current_m3_da,
                    "area_fair_m3_per_da_change_pct": ((global_m3_per_da - current_m3_da) / current_m3_da * 100.0) if current_m3_da else 0.0,

                    "current_demand_reference_share_m3": current_demand_share,
                    "hybrid_area70_current30_share_m3": hybrid_share,
                    "hybrid_area70_current30_parcel_avg_m3": hybrid_per_parcel_avg,
                    "interpretation_label": (
                        "Alan bazlı kota mevcut talebi ÜSTÜNDE" if ((area_fair_share - current_water) / current_water * 100.0 if current_water else 0) > 5 else
                        "Alan bazlı kota mevcut talebi ALTINDA" if ((area_fair_share - current_water) / current_water * 100.0 if current_water else 0) < -5 else
                        "Alan bazlı kota mevcut talebe YAKIN"
                    )
                })

            total_equal_share = equal_village_share * active_village_count
            total_hybrid = float(p["hybrid_area70_current30_m3"].sum())
            out["villages"] = rows
            out["totals"] = {
                "village_count": int(len(rows)),
                "parcel_count": total_parcels,
                "total_area_da": total_area_da,
                "observed_current_total_water_m3": total_observed,
                "observed_current_total_water_hm3": total_observed / 1_000_000.0,
                "observed_current_avg_per_parcel_m3": (total_observed / max(1, total_parcels)) if total_parcels else 0.0,
                "observed_current_m3_per_da": global_m3_per_da,
                "current_profit_tl": float(p["profit_tl_total"].sum()),
                "equal_share_total_m3": total_equal_share,
                "equal_share_total_hm3": total_equal_share / 1_000_000.0,
                "average_equal_village_share_m3": equal_village_share,
                "average_equal_parcel_quota_m3": (total_equal_share / max(1, total_parcels)) if total_parcels else 0.0,
                "equal_total_m3_per_da": (total_equal_share / total_area_da) if total_area_da else 0.0,
                "area_fair_total_m3": total_observed,
                "area_fair_total_hm3": total_observed / 1_000_000.0,
                "area_fair_m3_per_da": global_m3_per_da,
                "average_area_fair_parcel_quota_m3": (total_observed / max(1, total_parcels)) if total_parcels else 0.0,
                "hybrid_area70_current30_total_m3": total_hybrid,
                "hybrid_area70_current30_hm3": total_hybrid / 1_000_000.0,
            }

            if rows:
                eq_inc = max(rows, key=lambda x: x.get("equal_vs_current_change_pct", 0.0))
                eq_dec = min(rows, key=lambda x: x.get("equal_vs_current_change_pct", 0.0))
                area_inc = max(rows, key=lambda x: x.get("area_fair_vs_current_change_pct", 0.0))
                area_dec = min(rows, key=lambda x: x.get("area_fair_vs_current_change_pct", 0.0))
                out["fairness"] = {
                    "primary_model": "area_fair_per_da",
                    "primary_model_type": "tarımsal/dekar bazlı adalet",
                    "recommended": True,
                    "why_more_fair": (
                        "Eşit köy payı, köylerin alanı ve parsel büyüklüğü farklı olduğunda gerçek tarımsal yükü "
                        "yansıtmayabilir. Dekar bazlı modelde her da aynı su hakkını aldığı için parsel ve köy "
                        "büyüklüğü doğal olarak hesaba katılır."
                    ),
                    "equal_village_model_kept_for_comparison": True,
                    "equal_village_warning": (
                        "Eşit köy modeli idari eşitliktir; dekar başına eşitlik değildir. Küçük/az parsel içeren köyleri "
                        "çok avantajlı, büyük alanlı köyleri kısıtlı gösterebilir."
                    ),
                    "most_increased_equal_village": {
                        "village": eq_inc.get("village"),
                        "change_pct": eq_inc.get("equal_vs_current_change_pct"),
                        "change_m3": eq_inc.get("equal_vs_current_change_m3"),
                    },
                    "most_decreased_equal_village": {
                        "village": eq_dec.get("village"),
                        "change_pct": eq_dec.get("equal_vs_current_change_pct"),
                        "change_m3": eq_dec.get("equal_vs_current_change_m3"),
                    },
                    "most_increased_area_fair": {
                        "village": area_inc.get("village"),
                        "change_pct": area_inc.get("area_fair_vs_current_change_pct"),
                        "change_m3": area_inc.get("area_fair_vs_current_change_m3"),
                    },
                    "most_decreased_area_fair": {
                        "village": area_dec.get("village"),
                        "change_pct": area_dec.get("area_fair_vs_current_change_pct"),
                        "change_m3": area_dec.get("area_fair_vs_current_change_m3"),
                    },
                }

        except Exception as e:
            out["error"] = str(e)

    # Reservoir context is descriptive, not the direct allocator.
    rpath = DATA_DIR / "akkaya_baraj_su_bilanco_2000_2025_clean.csv"
    if rpath.exists():
        try:
            rdf = pd.read_csv(rpath)
            dol = pd.to_numeric(rdf.get("ortalama_doluluk_pct"), errors="coerce").dropna()
            draw = pd.to_numeric(rdf.get("cekis_su_hacmi_hm3"), errors="coerce").dropna()
            inflow = pd.to_numeric(rdf.get("girisim_su_hacmi_hm3"), errors="coerce").dropna()
            out["reservoir_context"] = {
                "year_min": int(pd.to_numeric(rdf.get("yil"), errors="coerce").min()),
                "year_max": int(pd.to_numeric(rdf.get("yil"), errors="coerce").max()),
                "avg_fullness_pct": float(dol.mean()) if len(dol) else 0.0,
                "avg_observed_draw_m3": float(draw.mean()) if len(draw) else 0.0,
                "avg_observed_draw_hm3": float(draw.mean() / 1_000_000.0) if len(draw) else 0.0,
                "avg_inflow_m3": float(inflow.mean()) if len(inflow) else 0.0,
                "avg_inflow_hm3": float(inflow.mean() / 1_000_000.0) if len(inflow) else 0.0,
                "source_note": "Baraj serisi bağlam amaçlıdır; kota hesabının ana girdisi mevcut parsel×ürün su tüketimidir.",
            }
        except Exception:
            out["reservoir_context"] = {}
    return out

@app.get("/api/water_allocation_logic")
def api_water_allocation_logic():
    try:
        return jsonify({"status": "OK", "allocation": build_water_allocation_logic()})
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e), "where": "api_water_allocation_logic"}), 500


@app.get("/api/data_quality_report")
def api_data_quality_report():
    try:
        return jsonify({"status": "OK", "report": build_data_quality_report()})
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e), "where": "api_data_quality_report"}), 500


@app.get("/api/app_meta")
def api_app_meta():
    try:
        report = build_data_quality_report()
        return jsonify({
            "status": "OK",
            "build": APP_BUILD,
            "title": APP_TITLE,
            "generated_at": APP_GENERATED_AT,
            "data_quality": report,
            "water_allocation": build_water_allocation_logic(),
        })
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e), "where": "api_app_meta"}), 500


@app.post("/api/validation_report")
def api_validation_report():
    try:
        payload = request.get_json(silent=True) or {}
        return jsonify({"status": "OK", "report": build_validation_report(payload)})
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e), "where": "api_validation_report"}), 500


@app.post("/api/optimize")
def api_optimize():
    try:
        payload = request.get_json(silent=True) or {}
        selected = payload.get("selectedParcelIds") or payload.get("selected") or []
        if isinstance(selected, str):
            selected = [normalize_parcel_id(s) for s in selected.split(",") if str(s).strip()]
        elif not isinstance(selected, list):
            selected = list(selected) if selected else []

        algorithm = str(payload.get("algorithm", "GA") or "GA")
        scenario = str(payload.get("scenario", "recommended") or "recommended")
        water_budget_ratio = safe_float(payload.get("waterBudgetRatio", 1.0), 1.0)

        year_raw = payload.get("year", None)
        year_val = None if year_raw in (None, "", "none", "null") else safe_int(year_raw, 0)
        if year_val == 0:
            year_val = None

        options = payload.get("options", None)
        if not isinstance(options, dict):
            options = {} if options is None else dict(options)
        if payload.get("cropCategoryMode") is not None:
            options["cropCategoryMode"] = payload.get("cropCategoryMode")
        if isinstance(payload.get("customParcels"), list) and payload.get("customParcels"):
            options["customParcels"] = payload.get("customParcels")

        scenario_type = _standard_scenario_type(options, {})
        objective_mode = _standard_objective_mode(scenario)
        base_policy = _optimization_repeat_selection(
            selected_ids=selected,
            algorithm=algorithm,
            scenario=scenario,
            scenario_type=scenario_type,
            year_val=year_val,
            water_budget_ratio=water_budget_ratio,
            options=options,
        )
        requested_runs = int(base_policy.get("selected_repeat_count") or ACADEMIC_DEFAULT_REPEAT_COUNT)
        try:
            seed_root = int(options.get("seed", payload.get("seed", int(time.time() * 1000) % 1000000)))
        except Exception:
            seed_root = int(time.time() * 1000) % 1000000
        algo_key = str(algorithm or "GA").upper()
        algo_seed_offset = {"GA": 0, "ABC": 10000, "ACO": 20000}.get(algo_key, 0)

        run_records: List[Dict[str, Any]] = []
        standardized_runs: List[Dict[str, Any]] = []
        for run_idx in range(requested_runs):
            run_options = dict(options)
            if base_policy.get("mode") == "fast_preview":
                fast_defaults = {"generations": 5, "popSize": 8, "cycles": 6, "foodSources": 6, "ants": 5, "iterations": 6, "riskMode": "none"}
                for k, v in fast_defaults.items():
                    if k not in run_options or run_options.get(k) in (None, "", 0):
                        run_options[k] = v
            run_options["seed"] = int(seed_root) + int(algo_seed_offset) + run_idx
            t0 = time.perf_counter()
            try:
                out = optimize(
                    selected_ids=selected,
                    algorithm=algorithm,
                    scenario=scenario,
                    water_budget_ratio=water_budget_ratio,
                    year=year_val,
                    options=run_options
                )
                std = _standardize_optimize_payload(
                    out,
                    selected_ids=selected,
                    algorithm=algorithm,
                    scenario=scenario,
                    water_budget_ratio=water_budget_ratio,
                    year_val=year_val,
                    options=run_options,
                )
                if std.get("status") != "OK":
                    continue
                plan = std.get("selected_plan") if isinstance(std.get("selected_plan"), dict) else {}
                score = _score_plan_for_calibration(plan, objective_mode)
                record = {
                    "run_index": run_idx,
                    "score": float(score),
                    "feasible": bool(plan.get("feasible", False)),
                    "selectable": bool(plan.get("selectable", plan.get("feasible", False))),
                    "recommendation_status": str(plan.get("recommendation_status") or std.get("recommendation_status") or ""),
                    "diversity": plan.get("diversity") if isinstance(plan.get("diversity"), dict) else std.get("diversity"),
                    "total_water_m3": safe_float(plan.get("total_water_m3", 0.0), 0.0),
                    "total_profit_tl": safe_float(plan.get("total_profit_tl", 0.0), 0.0),
                    "tl_per_m3": safe_float(plan.get("tl_per_m3", 0.0), 0.0),
                    "runtime": float(time.perf_counter() - t0),
                }
                std["_optimize_run_record"] = record
                run_records.append(record)
                standardized_runs.append(std)
            except Exception:
                continue

        if not standardized_runs:
            final_policy = _optimization_policy_from_runs(base_policy, run_records, None)
            return jsonify({
                "status": "ERROR",
                "message": "Optimizasyon kosularindan standart karar paketi uretilemedi.",
                "where": "api_optimize",
                "optimization_run_policy": final_policy,
            }), 500

        feasible_runs = [r for r in standardized_runs if bool((r.get("_optimize_run_record") or {}).get("feasible")) and bool((r.get("_optimize_run_record") or {}).get("selectable"))]
        candidate_runs = feasible_runs if feasible_runs else standardized_runs
        chosen = max(candidate_runs, key=lambda r: safe_float((r.get("_optimize_run_record") or {}).get("score", -1e100), -1e100))
        selected_record = chosen.get("_optimize_run_record") if isinstance(chosen.get("_optimize_run_record"), dict) else None
        final_policy = _optimization_policy_from_runs(base_policy, run_records, selected_record)
        final_policy["selection_rule"] = "Ana onerı uygulanabilir ve secilebilir kosular arasindan hedef fonksiyon skoruna gore secilir; uygulanabilir kosu yoksa durum acikca partial/no_feasible olarak raporlanir."
        chosen["optimization_run_policy"] = final_policy
        chosen.pop("_optimize_run_record", None)
        return jsonify(chosen)
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e), "where": "api_optimize"}), 500


@app.post("/api/benchmark")
def api_benchmark():
    """Run GA/ABC/ACO multiple times under identical inputs and return comparable summary stats.

    Payload (JSON) – largely compatible with /api/optimize:
      {
        selectedParcelIds: ["P1", ...],
        scenario: "mevcut"|"su_tasarruf"|"maks_kar"|"balanced",
        year: 2024,
        waterBudgetRatio: 1.0,
        repeats: 15,
        baseSeed: 42,   // optional
        algorithms: ["GA","ABC","ACO"], // optional
        options: {...}  // passed through; seed will be overridden per-run if baseSeed given
      }
    """
    try:
        payload = request.get_json(silent=True) or {}

        selected = payload.get("selectedParcelIds") or payload.get("selected") or []
        if isinstance(selected, str):
            selected = [normalize_parcel_id(s) for s in selected.split(",") if str(s).strip()]
        elif not isinstance(selected, list):
            selected = list(selected) if selected else []

        scenario = str(payload.get("scenario", "recommended") or "recommended")
        water_budget_ratio = safe_float(payload.get("waterBudgetRatio", 1.0), 1.0)

        year_raw = payload.get("year", None)
        year_val = None if year_raw in (None, "", "none", "null") else safe_int(year_raw, 0)
        if year_val == 0:
            year_val = None

        benchmark_mode_raw = str(payload.get("benchmarkMode", payload.get("benchmark_mode", "academic")) or "academic").lower()
        benchmark_mode = "fast" if benchmark_mode_raw in ("fast", "quick", "hizli", "hızlı") else "detailed"
        repeats = int(payload.get("repeats", 8 if benchmark_mode == "fast" else 30) or (8 if benchmark_mode == "fast" else 30))
        if benchmark_mode == "detailed":
            repeats = max(10, min(120, repeats))
        else:
            repeats = max(3, min(12, repeats))

        include_baseline = bool(payload.get("includeBaseline", True))
        base_seed = payload.get("baseSeed", None)
        if base_seed in ("", "none", "null"):
            base_seed = None
        if base_seed is not None:
            try:
                base_seed = int(base_seed)
            except Exception:
                base_seed = None

        algos = payload.get("algorithms", None)
        if not algos:
            algos = ["GA", "ABC", "ACO"]
        algos = [str(a).upper() for a in algos]
        algos = [a for a in algos if a in ("GA", "ABC", "ACO")]
        if not algos:
            algos = ["GA", "ABC", "ACO"]

        base_opts = payload.get("options", None)
        if not isinstance(base_opts, dict):
            base_opts = {}

        seed_root = int(base_seed) if base_seed is not None else int(time.time() * 1000) % 1000000
        objective_mode = _standard_objective_mode(scenario)
        scenario_type = _standard_scenario_type(base_opts, {})
        results: Dict[str, Any] = {
            "status": "OK",
            "repeats": repeats,
            "requested_runs_per_algorithm": repeats,
            "benchmark_mode": benchmark_mode,
            "fast_mode": bool(benchmark_mode == "fast"),
            "algorithms": {},
            "backend": True,
            "scenario": scenario,
            "objective": scenario,
            "objective_mode": objective_mode,
            "scenario_type": scenario_type,
            "seed_policy": ("fixed+algo_offset" if base_seed is not None else "time_randomized+algo_offset"),
            "seed_root": seed_root,
            "selected_count": len(selected),
        }
        started_at = time.perf_counter()
        # Total time budget for the whole benchmark request.
        # Default is intentionally generous so each algorithm gets at least one run.
        max_seconds = payload.get("maxSeconds", 35 if benchmark_mode == "fast" else 180)
        try:
            max_seconds = float(max_seconds)
        except Exception:
            max_seconds = 35.0 if benchmark_mode == "fast" else 180.0
        if benchmark_mode == "detailed":
            max_seconds = max(60.0, min(900.0, max_seconds))
        else:
            max_seconds = max(20.0, min(90.0, max_seconds))
        enforce_time_budget = benchmark_mode == "fast"

        # Fast mode keeps the UI responsive; detailed mode is for expert/academic review.
        if benchmark_mode == "detailed":
            speed_defaults = {"generations": 24, "popSize": 30, "cycles": 28, "foodSources": 28, "ants": 24, "iterations": 28}
            min_depth = 8
            max_depth = 80
            max_population = 120
        else:
            speed_defaults = {"generations": 5, "popSize": 8, "cycles": 6, "foodSources": 6, "ants": 5, "iterations": 6}
            min_depth = 3
            max_depth = 18
            max_population = 36

        benchmark_matrix_problem = None
        benchmark_candidate_builds = 0
        selected_parcels_for_benchmark: List[Dict[str, Any]] = []
        try:
            base_parcels_for_benchmark = load_parcels()
            custom_parcels_for_benchmark = base_opts.get("customParcels") if isinstance(base_opts.get("customParcels"), list) else []
            all_parcels_for_benchmark = merge_frontend_custom_parcels(base_parcels_for_benchmark, custom_parcels_for_benchmark)
            selected_norm_for_benchmark = [normalize_parcel_id(x) for x in (selected or [])]
            selected_parcels_for_benchmark = [
                p for p in all_parcels_for_benchmark
                if (not selected_norm_for_benchmark) or normalize_parcel_id(p.get("id")) in selected_norm_for_benchmark
            ]
        except Exception:
            selected_parcels_for_benchmark = []

        can_use_matrix_benchmark = bool(
            scenario_type == "single"
            and str(base_opts.get("seasonSource") or "s1").strip().lower() != "s2"
            and selected_parcels_for_benchmark
        )
        if can_use_matrix_benchmark:
            try:
                benchmark_matrix_problem = _matrix_build_problem(
                    selected_parcels_for_benchmark,
                    scenario,
                    water_budget_ratio,
                    year=year_val,
                    options=base_opts,
                )
                if isinstance(benchmark_matrix_problem, dict):
                    benchmark_matrix_problem["benchmark_fast"] = bool(benchmark_mode == "fast")
                benchmark_candidate_builds = 1 if benchmark_matrix_problem is not None else 0
            except Exception:
                benchmark_matrix_problem = None
                benchmark_candidate_builds = 0
        results["benchmark_execution"] = {
            "run_level": "matrix_fast" if benchmark_matrix_problem is not None else "standard_payload_fallback",
            "candidate_matrix_build_count": int(benchmark_candidate_builds),
            "standard_payload_scope": "best_run_only" if benchmark_matrix_problem is not None else "each_run_fallback",
        }

        # Optional baseline (current) – useful when UI scenario was "mevcut".
        if include_baseline:
            try:
                base_out = optimize(
                    selected_ids=selected,
                    algorithm="BASELINE",
                    scenario="current",
                    water_budget_ratio=water_budget_ratio,
                    year=year_val,
                    options=base_opts,
                )
                results["baseline"] = {
                    "total_profit_tl": safe_float(base_out.get("total_profit_tl", 0.0), 0.0),
                    "total_water_m3": safe_float(base_out.get("total_water_m3", 0.0), 0.0),
                    "efficiency_tl_per_m3": safe_float(base_out.get("efficiency_tl_per_m3", 0.0), 0.0),
                }
            except Exception:
                results["baseline"] = None

        def _plan_signature(opt_out: Dict[str, Any], ignore_fallow: bool = False) -> str:
            """Create a stable string signature for a parcel-level 2-season plan.

            If ignore_fallow=True, NADAS is treated as empty so 'mostly the same plan' does not get
            counted as different just because one run used fallow for feasibility.
            """
            try:
                parts = []
                std_grouped: Dict[str, List[Dict[str, Any]]] = {}
                for crop in (((opt_out.get("selected_plan") or {}).get("crops") or [])):
                    if not isinstance(crop, dict):
                        continue
                    pid_std = str(crop.get("parcel_id") or "").strip()
                    if pid_std:
                        std_grouped.setdefault(pid_std, []).append(crop)
                if std_grouped:
                    for pid, crops in std_grouped.items():
                        c1 = str((crops[0] or {}).get("crop_name") or (crops[0] or {}).get("name") or "").strip() if len(crops) > 0 else ""
                        c2 = str((crops[1] or {}).get("crop_name") or (crops[1] or {}).get("name") or "").strip() if len(crops) > 1 else ""
                        if ignore_fallow:
                            if c1.strip().upper() == FALLOW:
                                c1 = ""
                            if c2.strip().upper() == FALLOW:
                                c2 = ""
                        parts.append(f"{pid}:{c1}|{c2}")
                    parts.sort()
                    return ";".join(parts)
                for pr in (opt_out.get("parcels") or []):
                    pid = str(pr.get("id"))
                    rec = (((pr.get("result") or {}).get("recommended")) or [])
                    c1 = str((rec[0] or {}).get("name")) if len(rec) > 0 else ""
                    c2 = str((rec[1] or {}).get("name")) if len(rec) > 1 else ""
                    if ignore_fallow:
                        if c1.strip().upper() == FALLOW:
                            c1 = ""
                        if c2.strip().upper() == FALLOW:
                            c2 = ""
                    parts.append(f"{pid}:{c1}|{c2}")
                parts.sort()
                return ";".join(parts)
            except Exception:
                return ""

        def _row_area_da(row: Dict[str, Any], default: float = 0.0) -> float:
            return safe_float((row or {}).get("area", (row or {}).get("area_da", default)), default)


        def _standard_plan_crops_by_pid(opt_out: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
            grouped: Dict[str, List[Dict[str, Any]]] = {}
            try:
                crops = ((opt_out.get("selected_plan") or {}).get("crops") or [])
                for crop in crops:
                    if not isinstance(crop, dict):
                        continue
                    pid = str(crop.get("parcel_id") or "").strip()
                    if not pid:
                        continue
                    grouped.setdefault(pid, []).append(crop)
            except Exception:
                return {}
            return grouped


        def _secondary_metrics(opt_out: Dict[str, Any]) -> Dict[str, float]:
            total_parcels = 0
            secondary_used = 0
            secondary_area = 0.0
            try:
                grouped = _standard_plan_crops_by_pid(opt_out)
                if grouped:
                    for _pid, crops in grouped.items():
                        total_parcels += 1
                        if len(crops) > 1:
                            sec = crops[1] or {}
                            sname = str(sec.get("crop_name") or sec.get("name") or "").strip()
                            sarea = safe_float(sec.get("area_da", 0.0), 0.0)
                            if sname and canonical_crop_key(sname) != FALLOW and sarea > 0:
                                secondary_used += 1
                                secondary_area += float(sarea)
                    return {
                        "parcel_rate": float(secondary_used / max(1, total_parcels)),
                        "secondary_area_da": float(secondary_area),
                    }
                for pr in (opt_out.get("parcels") or []):
                    total_parcels += 1
                    rec = (((pr.get("result") or {}).get("recommended")) or [])
                    if len(rec) > 1:
                        sec = rec[1] or {}
                        sname = str(sec.get("name") or "").strip()
                        sarea = _row_area_da(sec, 0.0)
                        if sname and canonical_crop_key(sname) != FALLOW and sarea > 0:
                            secondary_used += 1
                            secondary_area += float(sarea)
            except Exception:
                pass
            return {
                "parcel_rate": float(secondary_used / max(1, total_parcels)),
                "secondary_area_da": float(secondary_area),
            }

        def _nadas_metrics(opt_out: Dict[str, Any]) -> Dict[str, float]:
            """Compute fallow (NADAS) ratios using actual planned areas.

            UI payload rows may carry either `area` or `area_da`. Older benchmark packs
            were only reading `area`, which made many crop areas look like 0 da in the
            benchmark cards even when the plans were valid."""
            total_area = 0.0
            nadas_p = 0.0
            nadas_s = 0.0
            try:
                for pr in (opt_out.get("parcels") or []):
                    parcel_meta = (pr.get("result") or {}).get("parcel") or {}
                    a = safe_float(pr.get("area_da", parcel_meta.get("area_da", 0.0)), 0.0)
                    if a <= 0:
                        rec = (((pr.get("result") or {}).get("recommended")) or [])
                        a = max([_row_area_da(x, 0.0) for x in rec] + [0.0])
                    total_area += a
                    rec = (((pr.get("result") or {}).get("recommended")) or [])
                    if len(rec) > 0 and str((rec[0] or {}).get("name") or "").strip().upper() == FALLOW:
                        nadas_p += _row_area_da((rec[0] or {}), a)
                    if len(rec) > 1 and str((rec[1] or {}).get("name") or "").strip().upper() == FALLOW:
                        nadas_s += _row_area_da((rec[1] or {}), a)
            except Exception:
                pass
            if total_area <= 0:
                return {"nadas_ratio": 0.0, "nadas_primary_ratio": 0.0, "nadas_secondary_ratio": 0.0, "planted_ratio": 1.0}
            nadas_ratio = (nadas_p + nadas_s) / max(1e-9, (2.0 * total_area))
            return {
                "nadas_ratio": float(nadas_ratio),
                "nadas_primary_ratio": float(nadas_p / max(1e-9, total_area)),
                "nadas_secondary_ratio": float(nadas_s / max(1e-9, total_area)),
                "planted_ratio": float(1.0 - nadas_ratio),
            }

        def _crop_area_summary(opt_out: Dict[str, Any]) -> Dict[str, Any]:
            """Return top crop areas for primary/secondary seasons using real planned areas."""
            prim: Dict[str, float] = {}
            sec: Dict[str, float] = {}
            try:
                grouped = _standard_plan_crops_by_pid(opt_out)
                if grouped:
                    for crops in grouped.values():
                        if len(crops) > 0:
                            c = str((crops[0] or {}).get("crop_name") or (crops[0] or {}).get("name") or "").strip()
                            a = safe_float((crops[0] or {}).get("area_da", 0.0), 0.0)
                            if c and a > 0:
                                prim[c] = prim.get(c, 0.0) + a
                        if len(crops) > 1:
                            c = str((crops[1] or {}).get("crop_name") or (crops[1] or {}).get("name") or "").strip()
                            a = safe_float((crops[1] or {}).get("area_da", 0.0), 0.0)
                            if c and c.upper() != FALLOW and a > 0:
                                sec[c] = sec.get(c, 0.0) + a
                    raise StopIteration
                for pr in (opt_out.get("parcels") or []):
                    rec = (((pr.get("result") or {}).get("recommended")) or [])
                    if len(rec) > 0:
                        c = str((rec[0] or {}).get("name") or "").strip()
                        a = _row_area_da((rec[0] or {}), 0.0)
                        if c and a > 0:
                            prim[c] = prim.get(c, 0.0) + a
                    if len(rec) > 1:
                        c = str((rec[1] or {}).get("name") or "").strip()
                        a = _row_area_da((rec[1] or {}), 0.0)
                        if c and c.upper() != FALLOW and a > 0:
                            sec[c] = sec.get(c, 0.0) + a
            except StopIteration:
                pass
            except Exception:
                pass

            def _top(d: Dict[str, float], k: int = 8) -> List[Dict[str, Any]]:
                items = [(c, float(a)) for c, a in d.items() if c and float(a) > 0.0]
                items.sort(key=lambda x: x[1], reverse=True)
                return [{"crop": c, "area_da": a} for c, a in items[:k]]

            return {"primary": _top(prim, 10), "secondary": _top(sec, 10)}

        def _plan_map(opt_out: Dict[str, Any], ignore_fallow: bool = False) -> Dict[str, Tuple[str, str]]:
            out: Dict[str, Tuple[str, str]] = {}
            try:
                grouped = _standard_plan_crops_by_pid(opt_out)
                if grouped:
                    for pid, crops in grouped.items():
                        c1 = str((crops[0] or {}).get("crop_name") or (crops[0] or {}).get("name") or "").strip() if len(crops) > 0 else ""
                        c2 = str((crops[1] or {}).get("crop_name") or (crops[1] or {}).get("name") or "").strip() if len(crops) > 1 else ""
                        if ignore_fallow:
                            if c1.upper() == FALLOW:
                                c1 = ""
                            if c2.upper() == FALLOW:
                                c2 = ""
                        out[pid] = (c1, c2)
                    return out
                for pr in (opt_out.get("parcels") or []):
                    pid = str(pr.get("id"))
                    rec = (((pr.get("result") or {}).get("recommended")) or [])
                    c1 = str((rec[0] or {}).get("name") or "").strip() if len(rec) > 0 else ""
                    c2 = str((rec[1] or {}).get("name") or "").strip() if len(rec) > 1 else ""
                    if ignore_fallow:
                        if c1.upper() == FALLOW:
                            c1 = ""
                        if c2.upper() == FALLOW:
                            c2 = ""
                    out[pid] = (c1, c2)
            except Exception:
                pass
            return out

        def _plan_distance(a_map: Dict[str, Tuple[str, str]], b_map: Dict[str, Tuple[str, str]]) -> float:
            ids = sorted(set(a_map.keys()) | set(b_map.keys()))
            if not ids:
                return 0.0
            diff = 0
            for pid in ids:
                if tuple(a_map.get(pid, ("", ""))) != tuple(b_map.get(pid, ("", ""))):
                    diff += 1
            return float(diff / max(1, len(ids)))

        # Distribute remaining time across algorithms so GA cannot starve ABC/ACO.
        for algo_idx, algo in enumerate(algos):
            runs = []
            sigs = []
            sigs_core = []
            plan_maps = []
            nadas_ratios = []
            sec_parcel_rates = []
            sec_area_vals = []
            diversity_penalties = []
            diversity_feasible_vals = []
            times = []
            infeasible = 0
            errors = 0

            best_out: Optional[Dict[str, Any]] = None
            best_sol_for_payload: Optional[List[int]] = None
            best_score = -1e100

            s_low = str(scenario or "").lower()
            if s_low in ("water_saving", "su_tasarruf", "su tasarruf"):
                score_mode = "water_saving"
            elif s_low in ("max_profit", "maks_kar", "maks kar"):
                score_mode = "max_profit"
            else:
                score_mode = "water_efficiency"

            # Use the same base seed policy but offset per algorithm so repeated
            # runs are comparable without collapsing into identical pseudo-random streams.
            algo_seed_offset = {"GA": 0, "ABC": 10000, "ACO": 20000}.get(algo, 0)

            # In fast preview we keep a response-time budget. In detailed/academic mode
            # the benchmark must execute the requested repeat_count x algorithms count.
            elapsed_total = time.perf_counter() - started_at
            remaining_total = max(0.0, max_seconds - elapsed_total)
            algos_left = max(1, len(algos) - algo_idx)
            # Minimum 8s per algorithm slice; if the total is low, still allow at least 1 run.
            algo_budget = max(8.0, remaining_total / float(algos_left)) if enforce_time_budget and remaining_total > 0 else 0.0
            algo_started = time.perf_counter()

            for i in range(repeats):
                # Fast preview may return partial results; detailed/academic mode must not
                # silently stop at 1 run per algorithm and call 3/90 a benchmark.
                if enforce_time_budget and i > 0 and algo_budget > 0 and (time.perf_counter() - algo_started) > algo_budget:
                    break
                if enforce_time_budget and i > 0 and (time.perf_counter() - started_at) > max_seconds:
                    break
                opts = dict(base_opts)
                # ensure benchmark runs quickly and consistently
                for k, dv in speed_defaults.items():
                    if k not in opts or opts.get(k) in (None, "", 0):
                        opts[k] = dv
                # Clamp hyper-parameters per mode so the UI request stays responsive.
                opts["generations"] = int(max(min_depth, min(max_depth, int(opts.get("generations", speed_defaults["generations"])))))
                opts["popSize"] = int(max(min_depth, min(max_population, int(opts.get("popSize", speed_defaults["popSize"])))))
                opts["cycles"] = int(max(min_depth, min(max_population, int(opts.get("cycles", speed_defaults["cycles"])))))
                opts["foodSources"] = int(max(min_depth, min(max_population, int(opts.get("foodSources", speed_defaults["foodSources"])))))
                opts["iterations"] = int(max(min_depth, min(max_population, int(opts.get("iterations", speed_defaults["iterations"])))))
                opts["ants"] = int(max(min_depth, min(max_population, int(opts.get("ants", speed_defaults["ants"])))))
                # keep risk off in benchmark unless user explicitly enables (it is expensive)
                if "riskMode" not in opts:
                    opts["riskMode"] = "none"
                if opts.get("riskMode") == "none":
                    opts["riskSamples"] = int(max(20, min(120, int(opts.get("riskSamples", 40)))))
                opts["seed"] = int(seed_root) + int(algo_seed_offset) + int(i)
                t0 = time.perf_counter()
                try:
                    if benchmark_matrix_problem is not None:
                        if algo == "GA":
                            sol, run_meta = _matrix_ga_optimize(
                                benchmark_matrix_problem,
                                seed=opts.get("seed"),
                                pop_size=int(opts.get("popSize", speed_defaults["popSize"])),
                                generations=int(opts.get("generations", speed_defaults["generations"])),
                                cx_rate=float(opts.get("cxRate", 0.72) or 0.72),
                                mut_rate=float(opts.get("mutRate", 0.05) or 0.05),
                            )
                        elif algo == "ABC":
                            sol, run_meta = _matrix_abc_optimize(
                                benchmark_matrix_problem,
                                seed=opts.get("seed"),
                                food_sources=int(opts.get("foodSources", speed_defaults["foodSources"])),
                                cycles=int(opts.get("cycles", speed_defaults["cycles"])),
                                limit=int(opts.get("limit", 10) or 10),
                            )
                        else:
                            sol, run_meta = _matrix_aco_optimize(
                                benchmark_matrix_problem,
                                seed=opts.get("seed"),
                                ants=int(opts.get("ants", speed_defaults["ants"])),
                                iterations=int(opts.get("iterations", speed_defaults["iterations"])),
                                rho=float(opts.get("rho", 0.22) or 0.22),
                                q=float(opts.get("q", 1.0) or 1.0),
                            )
                        score, run_metrics = _matrix_eval_solution(benchmark_matrix_problem, sol)
                        dt = time.perf_counter() - t0
                        times.append(float(dt))

                        p_v = safe_float(run_metrics.get("total_profit", 0.0), 0.0)
                        w_v = safe_float(run_metrics.get("total_water", 0.0), 0.0)
                        e_v = safe_float(run_metrics.get("efficiency", 0.0), 0.0)
                        run_invalid = bool(w_v > safe_float(benchmark_matrix_problem.get("budget", 0.0), 0.0) + 1e-6)
                        if run_invalid:
                            infeasible += 1
                        if (not np.isfinite(w_v)) or (w_v >= 1e8) or (w_v < 0):
                            infeasible += 1
                            continue
                        if (not np.isfinite(p_v)) or (p_v < 0 and score_mode == "water_saving"):
                            p_v = 0.0
                        if (not np.isfinite(e_v)) or (e_v < 0) or (e_v > 1e9):
                            e_v = 0.0

                        parts = []
                        plan_map_fast: Dict[str, Tuple[str, str]] = {}
                        nadas_area = 0.0
                        total_area_fast = 0.0
                        for pi, parcel_problem in enumerate(benchmark_matrix_problem.get("parcels", [])):
                            opts_fast = parcel_problem.get("options") or []
                            if not opts_fast:
                                continue
                            choice_idx = int(sol[pi]) if pi < len(sol) else 0
                            choice_idx = max(0, min(choice_idx, len(opts_fast) - 1))
                            opt_fast = opts_fast[choice_idx]
                            pid_fast = str(parcel_problem.get("id") or "")
                            crop_fast = str(opt_fast.get("name") or "")
                            area_fast = safe_float(opt_fast.get("area_da", 0.0), 0.0)
                            total_area_fast += max(0.0, area_fast)
                            if canonical_crop_key(crop_fast) == FALLOW:
                                nadas_area += max(0.0, area_fast)
                            parts.append(f"{pid_fast}:{crop_fast}|")
                            plan_map_fast[pid_fast] = (crop_fast, "")
                        parts.sort()
                        sig = ";".join(parts)
                        sig_core = sig.replace(FALLOW, "")
                        sigs.append(sig)
                        sigs_core.append(sig_core)
                        plan_maps.append(plan_map_fast)
                        nadas_ratios.append(float(nadas_area / max(1e-9, total_area_fast)))
                        sec_parcel_rates.append(0.0)
                        sec_area_vals.append(0.0)

                        if float(score) > best_score:
                            best_score = float(score)
                            best_sol_for_payload = [int(x) for x in sol]

                        runs.append({
                            "total_profit_tl": float(p_v),
                            "total_water_m3": float(w_v),
                            "efficiency_tl_per_m3": float(e_v),
                            "signature": sig,
                            "diversity": None,
                            "recommendation_status": None,
                        })
                        continue

                    out = optimize(
                        selected_ids=selected,
                        algorithm=algo,
                        scenario=scenario,
                        water_budget_ratio=water_budget_ratio,
                        year=year_val,
                        options=opts,
                    )
                    out = _standardize_optimize_payload(
                        out,
                        selected_ids=selected,
                        algorithm=algo,
                        scenario=scenario,
                        water_budget_ratio=water_budget_ratio,
                        year_val=year_val,
                        options=opts,
                    )
                    dt = time.perf_counter() - t0
                    times.append(float(dt))

                    if out.get("status") != "OK":
                        errors += 1
                        continue
                    selected_plan = out.get("selected_plan") if isinstance(out.get("selected_plan"), dict) else {}
                    run_invalid = not bool(out.get("feasible", True))
                    if selected_plan and (not bool(selected_plan.get("feasible", True)) or not bool(selected_plan.get("selectable", True))):
                        run_invalid = True
                    if run_invalid:
                        infeasible += 1
                    p_v = safe_float(selected_plan.get("total_profit_tl", out.get("total_profit_tl", 0.0)), 0.0)
                    w_v = safe_float(selected_plan.get("total_water_m3", out.get("total_water_m3", 0.0)), 0.0)
                    e_v = safe_float(selected_plan.get("tl_per_m3", out.get("efficiency_tl_per_m3", 0.0)), 0.0)
                    div_v = selected_plan.get("diversity") if isinstance(selected_plan.get("diversity"), dict) else out.get("diversity")
                    if isinstance(div_v, dict):
                        diversity_penalties.append(safe_float(div_v.get("diversity_penalty", 0.0), 0.0))
                        diversity_feasible_vals.append(1.0 if bool(div_v.get("diversity_feasible", False)) else 0.0)
                    # Treat extreme or non-finite totals as infeasible (usually caused by selecting missing/unsupported cells filled with W=1e9).
                    if (not np.isfinite(w_v)) or (w_v >= 1e8) or (w_v < 0):
                        infeasible += 1
                        continue
                    if (not np.isfinite(p_v)) or (p_v < 0 and score_mode == "water_saving"):
                        # allow negative profit in some modes, but still guard NaNs
                        p_v = 0.0
                    if (not np.isfinite(e_v)) or (e_v < 0) or (e_v > 1e9):
                        e_v = 0.0

                    sig = _plan_signature(out, ignore_fallow=False)
                    sig_core = _plan_signature(out, ignore_fallow=True)
                    sigs.append(sig)
                    sigs_core.append(sig_core)
                    plan_maps.append(_plan_map(out, ignore_fallow=False))
                    nadas_ratios.append(_nadas_metrics(out).get('nadas_ratio', 0.0))
                    secm = _secondary_metrics(out)
                    sec_parcel_rates.append(secm.get("parcel_rate", 0.0))
                    sec_area_vals.append(secm.get("secondary_area_da", 0.0))

                    # choose the best run for showing the recommended pattern
                    if score_mode == "water_saving":
                        score = (-w_v) + (0.00005 * p_v)
                    elif score_mode == "max_profit":
                        score = p_v - (0.02 * w_v)
                    else:
                        score = (e_v * 1000.0) + (0.00008 * p_v) - (0.015 * w_v)
                    try:
                        score = _score_plan_for_calibration(selected_plan, score_mode)
                    except Exception:
                        pass
                    if score > best_score:
                        best_score = float(score)
                        best_out = out

                    runs.append({
                        "total_profit_tl": float(p_v),
                        "total_water_m3": float(w_v),
                        "efficiency_tl_per_m3": float(e_v),
                        "signature": sig,
                        "diversity": div_v if isinstance(div_v, dict) else None,
                        "recommendation_status": selected_plan.get("recommendation_status", out.get("recommendation_status")),
                    })
                except Exception:
                    dt = time.perf_counter() - t0
                    times.append(float(dt))
                    errors += 1

            def _stats(vals: List[float]) -> Dict[str, Any]:
                if not vals:
                    return {"n": 0, "mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0, "median": 0.0, "cv": 0.0}
                if len(vals) == 1:
                    vv = float(vals[0])
                    return {"n": 1, "mean": vv, "std": 0.0, "min": vv, "max": vv, "median": vv, "cv": 0.0}
                mean_v = float(statistics.mean(vals))
                std_v = float(statistics.stdev(vals))
                med_v = float(statistics.median(vals))
                cv_v = float(std_v / abs(mean_v)) if abs(mean_v) > 1e-9 else 0.0
                return {
                    "n": len(vals),
                    "mean": mean_v,
                    "std": std_v,
                    "min": float(min(vals)),
                    "max": float(max(vals)),
                    "median": med_v,
                    "cv": cv_v,
                    "range": float(max(vals) - min(vals)),
                }

            prof = [r["total_profit_tl"] for r in runs]
            wat = [r["total_water_m3"] for r in runs]
            eff = [r["efficiency_tl_per_m3"] for r in runs]

            unique_patterns = len({s for s in sigs if s}) if sigs else 0
            pairwise_plan_distances = []
            try:
                if len(plan_maps) >= 2:
                    for ii in range(len(plan_maps)):
                        for jj in range(ii + 1, len(plan_maps)):
                            pairwise_plan_distances.append(_plan_distance(plan_maps[ii], plan_maps[jj]) * 100.0)
            except Exception:
                pairwise_plan_distances = []

            if benchmark_matrix_problem is not None and best_sol_for_payload is not None:
                try:
                    best_raw = _matrix_solution_to_payload(benchmark_matrix_problem, best_sol_for_payload, algo)
                    best_out = _standardize_optimize_payload(
                        best_raw,
                        selected_ids=selected,
                        algorithm=algo,
                        scenario=scenario,
                        water_budget_ratio=water_budget_ratio,
                        year_val=year_val,
                        options=base_opts,
                    )
                    best_selected_for_div = best_out.get("selected_plan") if isinstance(best_out.get("selected_plan"), dict) else {}
                    div_best = best_selected_for_div.get("diversity") if isinstance(best_selected_for_div.get("diversity"), dict) else best_out.get("diversity")
                    if isinstance(div_best, dict):
                        diversity_penalties.append(safe_float(div_best.get("diversity_penalty", 0.0), 0.0))
                        diversity_feasible_vals.append(1.0 if bool(div_best.get("diversity_feasible", False)) else 0.0)
                except Exception:
                    best_out = None

            best_pack = None
            if isinstance(best_out, dict):
                try:
                    # compact parcel-level plan (for UI compare)
                    parcels_compact = []
                    std_grouped = _standard_plan_crops_by_pid(best_out)
                    if std_grouped:
                        for pid, crops in std_grouped.items():
                            c1 = (crops[0] or {}) if len(crops) > 0 else {}
                            c2 = (crops[1] or {}) if len(crops) > 1 else {}
                            parcels_compact.append({
                                "id": pid,
                                "primary": {"crop": str(c1.get("crop_name") or c1.get("name") or ""), "area_da": safe_float(c1.get("area_da", 0.0), 0.0)},
                                "secondary": {"crop": str(c2.get("crop_name") or c2.get("name") or ""), "area_da": safe_float(c2.get("area_da", 0.0), 0.0)},
                            })
                    else:
                        for pr in (best_out.get("parcels") or []):
                            pid = str(pr.get("id"))
                            rec = (((pr.get("result") or {}).get("recommended")) or [])
                            c1 = (rec[0] or {}) if len(rec) > 0 else {}
                            c2 = (rec[1] or {}) if len(rec) > 1 else {}
                            parcels_compact.append({
                                "id": pid,
                                "primary": {"crop": str(c1.get("name") or ""), "area_da": _row_area_da(c1, 0.0)},
                                "secondary": {"crop": str(c2.get("name") or ""), "area_da": _row_area_da(c2, 0.0)},
                            })
                    parcels_compact.sort(key=lambda x: x.get("id"))

                    best_selected = best_out.get("selected_plan") if isinstance(best_out.get("selected_plan"), dict) else {}
                    best_pack = {
                        "total_profit_tl": safe_float(best_selected.get("total_profit_tl", best_out.get("total_profit_tl", 0.0)), 0.0),
                        "total_water_m3": safe_float(best_selected.get("total_water_m3", best_out.get("total_water_m3", 0.0)), 0.0),
                        "efficiency_tl_per_m3": safe_float(best_selected.get("tl_per_m3", best_out.get("efficiency_tl_per_m3", 0.0)), 0.0),
                        "status": best_selected.get("status", "ok"),
                        "feasible": bool(best_selected.get("feasible", best_out.get("feasible", True))),
                        "selectable": bool(best_selected.get("selectable", best_selected.get("feasible", best_out.get("feasible", True)))),
                        "recommendation_status": best_selected.get("recommendation_status", best_out.get("recommendation_status")),
                        "diversity": best_selected.get("diversity") if isinstance(best_selected.get("diversity"), dict) else best_out.get("diversity"),
                        "agronomic_risk": best_selected.get("agronomic_risk") if isinstance(best_selected.get("agronomic_risk"), dict) else best_out.get("agronomic_risk"),
                        "diversity_repair_applied": bool(best_selected.get("diversity_repair_applied", False)),
                        "signature": _plan_signature(best_out),
                        "crop_area": _crop_area_summary(best_out),
                        "nadas": _nadas_metrics(best_out),
                        "parcels": parcels_compact,
                    }
                except Exception:
                    best_pack = None

            attempted_runs = int(len(runs) + errors)
            successful_runs = int(len(runs))
            feasible_runs = int(max(0, successful_runs - infeasible))
            success_rate = float(successful_runs / attempted_runs) if attempted_runs > 0 else 0.0
            feasible_rate = float(feasible_runs / successful_runs) if successful_runs > 0 else 0.0
            feasible_rate = max(0.0, min(1.0, feasible_rate))
            profit_stats = _stats(prof)
            water_stats = _stats(wat)
            efficiency_stats = _stats(eff)
            runtime_stats = _stats(times)
            plan_distance_stats = _stats(pairwise_plan_distances)
            diversity_stats = _stats(diversity_penalties)
            best_diversity = {}
            if isinstance(best_pack, dict) and isinstance(best_pack.get("diversity"), dict):
                best_diversity = best_pack.get("diversity") or {}
            best_agronomic_risk = {}
            if isinstance(best_pack, dict) and isinstance(best_pack.get("agronomic_risk"), dict):
                best_agronomic_risk = best_pack.get("agronomic_risk") or {}
            plan_diversity = float(unique_patterns / successful_runs) if successful_runs > 0 else None
            completion_kind = _completion_status_kind(successful_runs, repeats)
            completion_status = _completion_status_label(successful_runs, repeats)
            algo_partial = bool(successful_runs != repeats or errors > 0)
            metric_warnings = []
            if successful_runs <= 1:
                metric_warnings.append("CV ve standart sapma icin en az iki basarili kosu gerekir.")
            if successful_runs > 1 and not pairwise_plan_distances:
                metric_warnings.append("Plan farki hesaplanamadi; yeterli karsilastirilabilir plan imzasi yok.")
            if best_diversity.get("warnings"):
                metric_warnings.extend([str(x) for x in (best_diversity.get("warnings") or [])[:3]])
            results["algorithms"][algo] = {
                "run_count": successful_runs,
                "requested_runs": repeats,
                "completion_status": completion_status,
                "completion_status_kind": completion_kind,
                "partial": algo_partial,
                "partial_status": "partial" if algo_partial else "completed",
                "partial_reason": (
                    f"Fast mod sure butcesi nedeniyle {successful_runs}/{repeats} kosu tamamlandi."
                    if algo_partial and benchmark_mode == "fast" else
                    f"Detayli modda {successful_runs}/{repeats} kosu tamamlandi; hata veya sure siniri olabilir."
                    if algo_partial else None
                ),
                "best_profit": float(max(prof)) if prof else None,
                "mean_profit": profit_stats.get("mean") if prof else None,
                "std_profit": profit_stats.get("std") if prof else None,
                "cv": profit_stats.get("cv") if prof else None,
                "best_water": float(min(wat)) if wat else None,
                "mean_water": water_stats.get("mean") if wat else None,
                "tl_per_m3": efficiency_stats.get("mean") if eff else None,
                "mean_runtime": runtime_stats.get("mean") if times else None,
                "plan_diversity": plan_diversity,
                "plan_distance": plan_distance_stats.get("mean") if pairwise_plan_distances else None,
                "seed_policy": results["seed_policy"],
                "metric_warnings": metric_warnings,
                "runs": successful_runs,
                "attempted_runs": attempted_runs,
                "errors": errors,
                "infeasible": infeasible,
                "successful_runs": successful_runs,
                "feasible_runs": feasible_runs,
                "success_rate": success_rate,
                "feasible_rate": feasible_rate,
                "unique_patterns": unique_patterns,
                "identical_plan_warning": bool(successful_runs > 1 and unique_patterns <= 1),
                "profit": profit_stats,
                "water": water_stats,
                "efficiency": efficiency_stats,
                "runtime_s": runtime_stats,
                "nadas_ratio": _stats(nadas_ratios),
                "secondary_parcel_rate": _stats(sec_parcel_rates),
                "secondary_area_da": _stats(sec_area_vals),
                "diversity": best_diversity,
                "agronomic_risk": best_agronomic_risk,
                "top_crop": best_diversity.get("top_crop"),
                "top_crop_area_da": best_diversity.get("top_crop_area_da"),
                "top_crop_share": best_diversity.get("top_crop_share"),
                "top3_crop_share": best_diversity.get("top3_crop_share"),
                "hhi": best_diversity.get("hhi"),
                "diversity_penalty": best_diversity.get("diversity_penalty"),
                "diversity_penalty_stats": diversity_stats,
                "diversity_feasible": best_diversity.get("diversity_feasible"),
                "diversity_feasible_rate": float(statistics.mean(diversity_feasible_vals)) if diversity_feasible_vals else None,
                "recommendation_status": (best_pack or {}).get("recommendation_status") if isinstance(best_pack, dict) else None,
                "warnings": best_diversity.get("warnings", []),
                "plan_distance_pct": plan_distance_stats,
                "failed_runs": int(max(0, attempted_runs - successful_runs)),
                "best": best_pack,
            }

        results["elapsed_seconds"] = float(time.perf_counter() - started_at)
        completed_total = int(sum(safe_int(v.get("run_count", 0), 0) for v in results.get("algorithms", {}).values()))
        requested_total = int(repeats * max(1, len(algos)))
        partial_algorithms = [a for a, v in results.get("algorithms", {}).items() if bool(v.get("partial"))]
        partial_result = bool(partial_algorithms or completed_total != requested_total)
        results["completed_runs"] = completed_total
        results["requested_total_runs"] = requested_total
        results["completion_status_kind"] = _completion_status_kind(completed_total, requested_total)
        results["completion_status"] = _completion_status_label(completed_total, requested_total)
        results["partial"] = partial_result
        results["partial_status"] = "partial" if partial_result else "completed"
        results["partial_reason"] = (
            f"Fast mod sure butcesi nedeniyle {completed_total}/{requested_total} kosu tamamlandi."
            if partial_result and benchmark_mode == "fast" else
            f"Detayli modda {completed_total}/{requested_total} kosu tamamlandi; hata veya sure siniri olabilir."
            if partial_result else None
        )
        results["algorithm_count"] = len(algos)
        results["expected_total_runs"] = requested_total
        results["partial_algorithms"] = partial_algorithms
        valid_algos = {
            a: v for a, v in results.get("algorithms", {}).items()
            if v.get("mean_profit") is not None and v.get("mean_water") is not None and safe_int(v.get("run_count", 0), 0) > 0
        }
        interpretation = "Yeterli basarili kosu olmadigi icin algoritmalar arasinda akademik yorum uretilemedi."
        if valid_algos:
            mean_profits = [safe_float(v.get("mean_profit", 0.0), 0.0) for v in valid_algos.values()]
            mean_waters = [safe_float(v.get("mean_water", 0.0), 0.0) for v in valid_algos.values()]
            max_profit = max(mean_profits)
            min_profit = min(mean_profits)
            max_water = max(mean_waters)
            min_water = min(mean_waters)
            profit_band = abs(max_profit - min_profit) / max(1.0, abs(max_profit))
            water_band = abs(max_water - min_water) / max(1.0, abs(max_water))
            if len(valid_algos) == 1:
                only_algo = next(iter(valid_algos.keys()))
                interpretation = f"Yalniz {only_algo} algoritmasi calistirildi; bu sonuc algoritmalar arasi ustunluk yorumu icin kullanilmamalidir."
            elif profit_band <= 0.01 and water_band <= 0.01:
                interpretation = "Algoritmalar esdeger performans bandindadir; karar tek algoritmaya baglanmamalidir."
            else:
                def _algo_rank(item: Tuple[str, Dict[str, Any]]) -> Tuple[float, float, float]:
                    _, v = item
                    mean_profit = safe_float(v.get("mean_profit", 0.0), 0.0)
                    cv = safe_float(v.get("cv", 999.0), 999.0) if v.get("cv") is not None else 999.0
                    feasible = safe_float(v.get("feasible_rate", 0.0), 0.0)
                    return (mean_profit, feasible, -cv)
                best_algo, best_metrics = sorted(valid_algos.items(), key=_algo_rank, reverse=True)[0]
                interpretation = f"Secili kosullarda {best_algo} algoritmasi daha yuksek ortalama kar/uygulanabilirlik ve daha dusuk degiskenlik dengesinde one cikmistir."
        if results.get("completion_status_kind") == "partial":
            leader = None
            try:
                leader = sorted(
                    valid_algos.items(),
                    key=lambda item: (
                        safe_float(item[1].get("mean_profit", 0.0), 0.0),
                        safe_float(item[1].get("feasible_rate", 0.0), 0.0),
                        -safe_float(item[1].get("cv", 999.0), 999.0),
                    ),
                    reverse=True,
                )[0][0] if valid_algos else None
            except Exception:
                leader = None
            interpretation = (
                f"Tamamlanan kosulara gore {leader} one cikmaktadir; ancak tum kosular tamamlanmadigi icin bu sonuc on degerlendirme niteligindedir."
                if leader else
                "Tamamlanan kosular kisitli oldugu icin sonuc on degerlendirme niteligindedir; kesin en iyi algoritma dili kullanilmamalidir."
            )
        results["interpretation"] = interpretation
        results["diagnostics"] = {
            "benchmark_is_backend_computed": True,
            "fast_mode": bool(benchmark_mode == "fast"),
            "partial": partial_result,
            "partial_status": results["partial_status"],
            "partial_reason": results["partial_reason"],
            "completion_status": results["completion_status"],
            "completed_runs": completed_total,
            "requested_total_runs": requested_total,
            "objective_mode": objective_mode,
            "scenario_type": scenario_type,
            "warnings": (
                ["Fast mod aktif; akademik varsayilan 30 kosu yerine hizli kosu ayarlari kullanildi."] if benchmark_mode == "fast" else []
            ) + ([results["partial_reason"] or "Tum kosular tamamlanmadi; sonuc kismi olarak yorumlanmalidir."] if partial_result else []),
        }
        return jsonify(results)
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e), "where": "api_benchmark"}), 500


@app.post("/api/run_count_calibration")
def api_run_count_calibration():
    """Compare 10/15/30/50/100 repeat counts for GA/ABC/ACO under the same input.

    This endpoint is intentionally separate from /api/optimize: it justifies the repeat
    policy academically by comparing stability, feasibility, marginal gain and runtime.
    """
    try:
        payload = request.get_json(silent=True) or {}
        selected = payload.get("selectedParcelIds") or payload.get("selected") or []
        if isinstance(selected, str):
            selected = [normalize_parcel_id(s) for s in selected.split(",") if str(s).strip()]
        elif not isinstance(selected, list):
            selected = list(selected) if selected else []

        scenario = str(payload.get("scenario", "water_saving") or "water_saving")
        water_budget_ratio = safe_float(payload.get("waterBudgetRatio", 1.0), 1.0)
        year_raw = payload.get("year", None)
        year_val = None if year_raw in (None, "", "none", "null") else safe_int(year_raw, 0)
        if year_val == 0:
            year_val = None

        algos = payload.get("algorithms") or ["GA", "ABC", "ACO"]
        algos = [str(a).upper() for a in algos if str(a).upper() in ("GA", "ABC", "ACO")]
        if not algos:
            algos = ["GA", "ABC", "ACO"]
        candidates = payload.get("repeatCandidates") or RUN_COUNT_CALIBRATION_CANDIDATES
        candidates = [int(x) for x in candidates if int(x) in RUN_COUNT_CALIBRATION_CANDIDATES]
        if not candidates:
            candidates = RUN_COUNT_CALIBRATION_CANDIDATES[:]

        base_opts = payload.get("options") if isinstance(payload.get("options"), dict) else {}
        scenario_type = _standard_scenario_type(base_opts, {})
        objective_mode = _standard_objective_mode(scenario)
        seed_root = payload.get("baseSeed", None)
        try:
            seed_root = int(seed_root) if seed_root not in (None, "", "none", "null") else int(time.time() * 1000) % 1000000
        except Exception:
            seed_root = int(time.time() * 1000) % 1000000
        try:
            max_seconds = float(payload.get("maxSeconds", 420))
        except Exception:
            max_seconds = 420.0
        max_seconds = max(60.0, min(1800.0, max_seconds))

        speed_defaults = {"generations": 10, "popSize": 14, "cycles": 12, "foodSources": 12, "ants": 10, "iterations": 12}
        started = time.perf_counter()
        rows: List[Dict[str, Any]] = []
        previous_mean_by_algo: Dict[str, float] = {}
        requested_total = int(sum(candidates) * len(algos))
        completed_total = 0
        warnings: List[str] = []

        for repeat_count in candidates:
            for algo in algos:
                scores: List[float] = []
                profits: List[float] = []
                waters: List[float] = []
                effs: List[float] = []
                runtimes: List[float] = []
                signatures: List[str] = []
                feasible_count = 0
                best_score = -1e100
                best_profit = 0.0
                requested_runs = int(repeat_count)
                for i in range(requested_runs):
                    if completed_total > 0 and (time.perf_counter() - started) > max_seconds:
                        break
                    opts = dict(base_opts)
                    opts.update({k: opts.get(k, v) or v for k, v in speed_defaults.items()})
                    opts["riskMode"] = opts.get("riskMode", "none")
                    opts["seed"] = int(seed_root) + {"GA": 0, "ABC": 10000, "ACO": 20000}.get(algo, 0) + (repeat_count * 1000) + i
                    t0 = time.perf_counter()
                    try:
                        out = optimize(
                            selected_ids=selected,
                            algorithm=algo,
                            scenario=scenario,
                            water_budget_ratio=water_budget_ratio,
                            year=year_val,
                            options=opts,
                        )
                        out = _standardize_optimize_payload(
                            out,
                            selected_ids=selected,
                            algorithm=algo,
                            scenario=scenario,
                            water_budget_ratio=water_budget_ratio,
                            year_val=year_val,
                            options=opts,
                        )
                        plan = out.get("selected_plan") if isinstance(out.get("selected_plan"), dict) else {}
                        score = _score_plan_for_calibration(plan, objective_mode)
                        profit = safe_float(plan.get("total_profit_tl", 0.0), 0.0)
                        water = safe_float(plan.get("total_water_m3", 0.0), 0.0)
                        eff = safe_float(plan.get("tl_per_m3", 0.0), 0.0)
                        if bool(plan.get("feasible", False)):
                            feasible_count += 1
                        signatures.append(_selected_plan_signature(plan))
                        scores.append(float(score))
                        profits.append(float(profit))
                        waters.append(float(water))
                        effs.append(float(eff))
                        runtimes.append(float(time.perf_counter() - t0))
                        completed_total += 1
                        if score > best_score:
                            best_score = float(score)
                            best_profit = float(profit)
                    except Exception:
                        runtimes.append(float(time.perf_counter() - t0))

                completed_runs = len(scores)
                unique = len(set(s for s in signatures if s))
                dominant = 0.0
                if signatures:
                    counts: Dict[str, int] = {}
                    for sig in signatures:
                        counts[sig] = counts.get(sig, 0) + 1
                    dominant = max(counts.values()) / max(1, len(signatures))
                mean_score = float(statistics.mean(scores)) if scores else 0.0
                prev_mean = previous_mean_by_algo.get(algo)
                marginal = None
                if prev_mean is not None and abs(prev_mean) > 1e-9:
                    marginal = float((mean_score - prev_mean) / abs(prev_mean))
                previous_mean_by_algo[algo] = mean_score
                feasible_rate = max(0.0, min(1.0, feasible_count / max(1, completed_runs)))
                cv_score = _cv(scores)
                plan_diversity = float(unique / max(1, completed_runs)) if completed_runs else 0.0
                stability_label = "kararlı" if feasible_rate >= 0.95 and cv_score <= 0.05 else ("kısmi" if completed_runs < requested_runs else "oynak")
                note = "Kararlılık ve uygulanabilirlik kabul edilebilir." if stability_label == "kararlı" else "Bu tekrar düzeyi tek başına nihai akademik karar için yeterli değildir."
                row = {
                    "repeat_count": int(repeat_count),
                    "algorithm": algo,
                    "completed_runs": int(completed_runs),
                    "requested_runs": int(requested_runs),
                    "completion_status_kind": _completion_status_kind(completed_runs, requested_runs),
                    "best_score": float(max(scores)) if scores else None,
                    "mean_score": mean_score if scores else None,
                    "median_score": _median(scores),
                    "std_score": _std(scores),
                    "cv_score": cv_score,
                    "best_profit": best_profit,
                    "mean_profit": float(statistics.mean(profits)) if profits else 0.0,
                    "mean_water": float(statistics.mean(waters)) if waters else 0.0,
                    "mean_tl_per_m3": float(statistics.mean(effs)) if effs else 0.0,
                    "feasible_rate": feasible_rate,
                    "plan_diversity": plan_diversity,
                    "dominant_plan_rate": float(dominant),
                    "mean_runtime_sec": float(statistics.mean(runtimes)) if runtimes else 0.0,
                    "marginal_gain_vs_previous": marginal,
                    "stability_label": stability_label,
                    "recommendation_note": note,
                }
                rows.append(row)

        selection = _select_recommended_repeat_count(rows)
        for algo in algos:
            key = _calibration_cache_key(selected, algo, scenario, scenario_type, year_val, water_budget_ratio)
            RUN_COUNT_CALIBRATION_CACHE[key] = selection

        by_count = {int(c): [r for r in rows if int(r.get("repeat_count", 0)) == int(c)] for c in candidates}
        if 100 in by_count and 50 in by_count:
            for algo in algos:
                r50 = next((r for r in by_count[50] if r.get("algorithm") == algo), None)
                r100 = next((r for r in by_count[100] if r.get("algorithm") == algo), None)
                if r50 and r100:
                    mean_gain = safe_float(r100.get("marginal_gain_vs_previous", 0.0), 0.0)
                    if (
                        mean_gain < 0.01
                        or safe_float(r100.get("dominant_plan_rate", 0.0), 0.0) > 0.90
                        or safe_float(r100.get("cv_score", 0.0), 0.0) >= safe_float(r50.get("cv_score", 0.0), 0.0)
                    ):
                        warnings.append("Yüksek tekrar sayısı tekil en iyi sonucu artırsa da ortalama performans/kararlılık anlamlı biçimde iyileşmediği için bu tekrar düzeyi operasyonel varsayılan olarak seçilmemiştir.")
                        break

        response = {
            "status": "OK",
            "mode": "run_count_calibration",
            "calibration_candidates": RUN_COUNT_CALIBRATION_CANDIDATES,
            "rows": rows,
            "recommended_repeat_count": selection["recommended_repeat_count"],
            "selection_rule": selection["selection_rule"],
            "reason": selection["reason"],
            "warnings": list(dict.fromkeys(warnings)),
            "completed_runs": int(sum(int(r.get("completed_runs", 0)) for r in rows)),
            "requested_total_runs": int(requested_total),
            "completion_status_kind": _completion_status_kind(sum(int(r.get("completed_runs", 0)) for r in rows), requested_total),
            "completion_status": _completion_status_label(sum(int(r.get("completed_runs", 0)) for r in rows), requested_total),
            "elapsed_seconds": float(time.perf_counter() - started),
            "objective_mode": objective_mode,
            "scenario_type": scenario_type,
            "seed_policy": "fixed+repeat+algorithm_offset",
        }
        return jsonify(response)
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e), "where": "api_run_count_calibration"}), 500


if __name__ == "__main__":
    # Run: python app.py  -> http://127.0.0.1:5000
    # NOTE (Windows): Werkzeug's debug reloader (watchdog) may incorrectly detect
    # changes inside site-packages and restart the server continuously.
    # That breaks long-running optimization requests and causes the UI to show
    # "Hata: Önceki sonuçlar gösteriliyor".
    # Keep debug enabled (for tracebacks), but disable the auto-reloader.
    app.run(debug=True, host="127.0.0.1", port=5000, use_reloader=False)
