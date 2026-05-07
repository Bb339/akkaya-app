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
APP_BUILD = "v71-2026-04-26-baslik-ve-stabil-grid"
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

        # Fitness: maximize profit while minimizing water
        fitness = alpha * profit_n - beta * water_n - penalty
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

    core_score = _objective_score_value(total_profit, total_water, objective)
    fitness = core_score - penalty - monthly_pen - div_pen - share_pen - prev_pen
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
    fitness = core_score - budget_penalty - monthly_penalty - hard_penalty + soft_bonus + low_input_bonus - div_pen - share_pen - prev_pen - nadas_pen - primary_nadas_pen
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
    best_fit, best_w, best_p = _score_solution(best_sol, areas, W, R, budget, objective, month_weights, month_caps)

    for _ in range(cycles):
        # employed bees
        for k in range(food_sources):
            v = neighbor(foods[k])
            fit_v, _, _ = _score_solution(v, areas, W, R, budget, objective, month_weights, month_caps)
            fit_k, _, _ = _score_solution(foods[k], areas, W, R, budget, objective, month_weights, month_caps)
            if fit_v > fit_k:
                foods[k] = v
                trials[k] = 0
            else:
                trials[k] += 1

        # onlooker probabilities (normalize positive)
        fits = np.array([_score_solution(foods[k], areas, W, R, budget, objective, month_weights, month_caps)[0] for k in range(food_sources)], dtype=float)
        # shift to positive
        fmin = float(np.min(fits))
        probs = fits - fmin + 1e-9
        probs = probs / float(np.sum(probs))

        # onlookers count equals food_sources (common choice)
        for _o in range(food_sources):
            k = int(np.random.choice(np.arange(food_sources), p=probs))
            v = neighbor(foods[k])
            fit_v, _, _ = _score_solution(v, areas, W, R, budget, objective, month_weights, month_caps)
            fit_k, _, _ = _score_solution(foods[k], areas, W, R, budget, objective, month_weights, month_caps)
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
            fit_k, w_k, p_k = _score_solution(foods[k], areas, W, R, budget, objective, month_weights, month_caps)
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
                 env_flow_ratio: float = 0.10, irrigation_method: Optional[str] = None, enforce_delivery_caps: bool = True) -> Dict[str, Any]:
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
            fit, tw, tp = _score_solution(chosen, areas, W, R, budget, objective, month_weights, month_caps)
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

    sel_ids = [normalize_parcel_id(p.get("id")) for p in (selected_parcels or []) if str(p.get("id", "")).strip()]
    if sel_ids:
        df = df[df["parcel_id"].isin(sel_ids)].copy()
    if df.empty:
        return None

    objective = _matrix_objective_from_scenario(scenario)
    y = int(year) if year is not None else 2024
    ratio = max(0.0, float(water_budget_ratio or 1.0))
    opts = options or {}
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

    for pid, g in df.groupby("parcel_id", sort=True):
        g = g.copy()
        parcel_info = parcel_info_map.get(str(pid), {})
        parcel_type = str((parcel_info or {}).get("parcel_type", "") or "").strip().lower()
        quota = float(quota_map.get(pid, 0.0))

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

        # local utility guides all algorithms, while the final choice remains a global portfolio search
        cov_n = _norm_series(g["_coverage_pct"])
        prof_n = _norm_series(g["_effective_profit_tl"])
        eff_n = _norm_series(g["_tl_per_m3"])
        water_low_n = 1.0 - _norm_series(g["_effective_water_m3"])
        compat_n = _norm_series(g["_compat_score"])

        if objective == "water_saving":
            g["_local_utility"] = 0.54 * water_low_n + 0.16 * eff_n + 0.12 * compat_n + 0.10 * cov_n + 0.08 * prof_n
        elif objective == "water_efficiency":
            g["_local_utility"] = 0.34 * water_low_n + 0.22 * cov_n + 0.18 * eff_n + 0.12 * prof_n + 0.14 * compat_n
        elif objective == "max_profit":
            g["_local_utility"] = 0.48 * prof_n + 0.18 * cov_n + 0.08 * eff_n + 0.10 * water_low_n + 0.16 * compat_n
        else:
            g["_local_utility"] = 0.30 * prof_n + 0.22 * water_low_n + 0.18 * cov_n + 0.16 * eff_n + 0.14 * compat_n

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
                allow_mask = g["candidate_crop"].astype(str).apply(lambda c: candidate_allowed_for_parcel(parcel_type, current_crop, c)[0])
                if bool(allow_mask.any()):
                    dropped_count = int((~allow_mask).sum())
                    if dropped_count > 0:
                        g = g[allow_mask].copy()
                        g["_compat_cautions"] = g["_compat_cautions"].apply(lambda xs: list(xs or []) + [f"{dropped_count} uyumsuz bahçe/çok yıllık aday normal senaryodan elendi."])
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
        chosen = opts[idx]

        is_locked_orchard = bool(p.get("locked")) and str(p.get("lock_kind") or "") == "orchard"
        if problem["objective"] == "water_efficiency":
            alt_sorted = sorted(opts, key=lambda o: (-int(bool(o.get("fullFeasible"))), float(o.get("totalWater", 0.0)), -float(o.get("tlPerM3", 0.0)), -float(o.get("totalProfit", 0.0))))
        elif problem["objective"] == "max_profit":
            alt_sorted = sorted(opts, key=lambda o: (-float(o.get("totalProfit", 0.0)), -int(bool(o.get("fullFeasible"))), -float(o.get("coverage_pct", 0.0)), -float(o.get("tlPerM3", 0.0))))
        else:
            alt_sorted = sorted(opts, key=lambda o: (-float(o.get("localUtility", 0.0)), -float(o.get("coverage_pct", 0.0)), -float(o.get("totalProfit", 0.0))))

        if is_locked_orchard:
            alternatives = []
            for ar in _orchard_interrow_alternatives(str(chosen.get("name", "") or p.get("current_crop") or "Bahçe ürünü"))[:5]:
                alternatives.append({
                    "name": str(ar.get("name", "") or "").strip(),
                    "kind": str(ar.get("kind", "") or "").strip(),
                    "waterLevel": str(ar.get("waterLevel", "") or "").strip(),
                    "decisionNote": str(ar.get("note", "") or "").strip(),
                    "isInterrow": True
                })
        else:
            alternatives = []
            for ar in alt_sorted[:5]:
                alt_cat = load_crop_catalog().get(normalize_crop_key(str(ar.get("name", "") or "")), {})
                alt_irr_current = str(alt_cat.get("irrigationCurrentKey") or p.get("irrigation_key") or "").strip()
                alt_irr_suggested = str(alt_cat.get("irrigationRecommendedKey") or alt_irr_current).strip()
                alternatives.append({
                    "name": str(ar.get("name", "") or "").strip(),
                    "season": str(ar.get("season_label", "") or infer_crop_season_label(str(ar.get("name", "") or ""), str(p.get("parcel_type", "") or ""))).strip(),
                    "area_da": float(ar.get("area_da", 0.0) or 0.0),
                    "coverage_pct": float(ar.get("coverage_pct", 0.0) or 0.0),
                    "totalWater": float(ar.get("totalWater", 0.0) or 0.0),
                    "totalProfit": float(ar.get("totalProfit", 0.0) or 0.0),
                    "tlPerM3": float(ar.get("tlPerM3", 0.0) or 0.0),
                    "parcelQuotaM3": float(ar.get("parcelQuotaM3", 0.0) or 0.0),
                    "quotaAdjusted": bool(ar.get("quotaAdjusted")),
                    "candidateLandType": str(ar.get("candidateLandType", "") or candidate_crop_land_type(str(ar.get("name", "") or ""))),
                    "compatibilityRule": str(ar.get("compatibilityRule", "") or candidate_allowed_for_parcel(str(p.get("parcel_type", "") or ""), str(p.get("current_crop", "") or ""), str(ar.get("name", "") or ""))[1]),
                    "compatibilityScore": float(ar.get("compatibilityScore", 0.0) or 0.0),
                    "reasonDetails": list(ar.get("reasonDetails", []) or []),
                    "cautionDetails": list(ar.get("cautionDetails", []) or []),
                    "decisionNote": str(ar.get("compatibilitySummary", "") or "Eşit köy kotası ve eşit parsel kotası altında hesaplandı."),
                    "irrigationCurrentKey": alt_irr_current,
                    "irrigationSuggestedKey": alt_irr_suggested,
                    **_decision_metrics_for_crop(str(ar.get("name", "") or ""), float(ar.get("area_da", 0.0) or 0.0), float(ar.get("water_m3_da", 0.0) or 0.0), float(ar.get("profit_tl_da", 0.0) or 0.0)),
                })

        chosen_cat = load_crop_catalog().get(normalize_crop_key(str(chosen.get("name", "") or "")), {})
        irr_current_key = str(chosen_cat.get("irrigationCurrentKey") or p.get("irrigation_key") or "").strip()
        irr_suggested_key = str(chosen_cat.get("irrigationRecommendedKey") or irr_current_key).strip()
        rec = {
            "name": str(chosen.get("name", "") or "").strip(),
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
            "parcelQuotaM3": float(chosen.get("parcelQuotaM3", 0.0) or 0.0),
            "quotaAdjusted": bool(chosen.get("quotaAdjusted")),
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
            "decisionNote": ("Kurulu çok yıllık/bahçe parselinde ana ürün korunmuştur; yalnızca ara ürün ve yönetim alternatifleri gösterilir." if is_locked_orchard else str(chosen.get("compatibilitySummary", "") or "Toplam mevcut su 5 köye eşit, köy içindeki parseller de eşit kota alacak şekilde planlandı."))
        }

        total_water += rec["totalWater"]
        total_profit += rec["totalProfit"]
        parcels_out.append({
            "id": str(p.get("id")),
            "area_da": float(p.get("area_da", 0.0) or 0.0),
            "parcel_type": str(p.get("parcel_type", "") or "").strip(),
            "current_crop": str(p.get("current_crop", "") or "").strip(),
            "result": {
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
    pop_size = max(12, min(120, int(pop_size or 36)))
    generations = max(10, min(160, int(generations or 36)))
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
    food_sources = max(10, min(120, int(food_sources or 28)))
    cycles = max(10, min(180, int(cycles or 42)))
    limit = max(4, min(50, int(limit or 10)))

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
    ants = max(10, min(120, int(ants or 28)))
    iterations = max(10, min(180, int(iterations or 42)))
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
    prefer_matrix = (season_source != "s2") and (not two_season) and (scenario_type == "single")

    if prefer_matrix:
        try:
            matrix_out = optimize_from_excel_matrix(selected, algorithm, scenario, water_budget_ratio, year=year, options=options)
            if matrix_out is not None:
                matrix_out.setdefault("meta", {})["planner_mode"] = "matrix_single"
                matrix_out.setdefault("meta", {})["seasonSource"] = season_source
                matrix_out.setdefault("meta", {})["scenarioType"] = scenario_type
                matrix_out.setdefault("meta", {})["twoSeason"] = False
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
        if isinstance(payload.get("customParcels"), list) and payload.get("customParcels"):
            options["customParcels"] = payload.get("customParcels")

        return jsonify(optimize(
            selected_ids=selected,
            algorithm=algorithm,
            scenario=scenario,
            water_budget_ratio=water_budget_ratio,
            year=year_val,
            options=options
        ))
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

        benchmark_mode = str(payload.get("benchmarkMode", payload.get("benchmark_mode", "fast")) or "fast").lower()
        benchmark_mode = "detailed" if benchmark_mode in ("detailed", "detail", "tez", "academic") else "fast"
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
        results: Dict[str, Any] = {"status": "OK", "repeats": repeats, "benchmark_mode": benchmark_mode, "algorithms": {}, "backend": True, "scenario": scenario, "objective": scenario, "seed_policy": ("fixed+algo_offset" if base_seed is not None else "time_randomized+algo_offset"), "seed_root": seed_root, "selected_count": len(selected) }
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


        def _secondary_metrics(opt_out: Dict[str, Any]) -> Dict[str, float]:
            total_parcels = 0
            secondary_used = 0
            secondary_area = 0.0
            try:
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
            times = []
            infeasible = 0
            errors = 0

            best_out: Optional[Dict[str, Any]] = None
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

            # Allocate a fair slice of the remaining time budget to this algorithm.
            elapsed_total = time.perf_counter() - started_at
            remaining_total = max(0.0, max_seconds - elapsed_total)
            algos_left = max(1, len(algos) - algo_idx)
            # Minimum 8s per algorithm slice; if the total is low, still allow at least 1 run.
            algo_budget = max(8.0, remaining_total / float(algos_left)) if remaining_total > 0 else 0.0
            algo_started = time.perf_counter()

            for i in range(repeats):
                # Per-algorithm time budget guard. Ensure every algorithm gets at least 1 attempt.
                if i > 0 and algo_budget > 0 and (time.perf_counter() - algo_started) > algo_budget:
                    break
                # Also guard total budget, but allow the first run per algorithm.
                if i > 0 and (time.perf_counter() - started_at) > max_seconds:
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
                    out = optimize(
                        selected_ids=selected,
                        algorithm=algo,
                        scenario=scenario,
                        water_budget_ratio=water_budget_ratio,
                        year=year_val,
                        options=opts,
                    )
                    dt = time.perf_counter() - t0
                    times.append(float(dt))

                    if out.get("status") != "OK":
                        errors += 1
                        continue
                    if not bool(out.get("feasible", True)):
                        infeasible += 1

                    p_v = safe_float(out.get("total_profit_tl", 0.0), 0.0)
                    w_v = safe_float(out.get("total_water_m3", 0.0), 0.0)
                    e_v = safe_float(out.get("efficiency_tl_per_m3", 0.0), 0.0)
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
                    if score > best_score:
                        best_score = float(score)
                        best_out = out

                    runs.append({
                        "total_profit_tl": float(p_v),
                        "total_water_m3": float(w_v),
                        "efficiency_tl_per_m3": float(e_v),
                        "signature": sig,
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

            best_pack = None
            if isinstance(best_out, dict):
                try:
                    # compact parcel-level plan (for UI compare)
                    parcels_compact = []
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

                    best_pack = {
                        "total_profit_tl": safe_float(best_out.get("total_profit_tl", 0.0), 0.0),
                        "total_water_m3": safe_float(best_out.get("total_water_m3", 0.0), 0.0),
                        "efficiency_tl_per_m3": safe_float(best_out.get("efficiency_tl_per_m3", 0.0), 0.0),
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
            results["algorithms"][algo] = {
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
                "profit": _stats(prof),
                "water": _stats(wat),
                "efficiency": _stats(eff),
                "runtime_s": _stats(times),
                "nadas_ratio": _stats(nadas_ratios),
                "secondary_parcel_rate": _stats(sec_parcel_rates),
                "secondary_area_da": _stats(sec_area_vals),
                "plan_distance_pct": _stats(pairwise_plan_distances),
                "failed_runs": int(max(0, attempted_runs - successful_runs)),
                "best": best_pack,
            }

        results["elapsed_seconds"] = float(time.perf_counter() - started_at)
        return jsonify(results)
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e), "where": "api_benchmark"}), 500


# 15-year impact route removed in equal-water planning mode
# @app.post("/api/impact15y")
def api_impact15y():
    """
    Compute 15-year water savings per algorithm (GA/ABC/ACO) for the selected season dataset (seasonSource),
    and also return the average (mean) across algorithms.

    Payload:
      {
        selectedParcelIds: ["P1",...],
        scenario: "su_tasarruf"|"maks_kar"|...,
        year: 2024,
        waterBudgetRatio: 1.0,
        seasonSource: "s1"|"s2"|"both",
        horizonYears: 15,
        algorithms: ["GA","ABC","ACO"],
        repeats: 8,
        maxSeconds: 120
      }

    Returns:
      {
        status: "OK",
        horizonYears: 15,
        totals: { GA:{...}, ABC:{...}, ACO:{...}, AVG:{...} },
        geojson: FeatureCollection(points with per-algo & avg savings)
      }
    """
    try:
        payload = request.get_json(force=True, silent=True) or {}
        selected = payload.get("selectedParcelIds", []) or []
        if isinstance(selected, str):
            selected = [normalize_parcel_id(s) for s in selected.split(",") if str(s).strip()]
        elif not isinstance(selected, list):
            selected = list(selected) if selected else []

        scenario = str(payload.get("scenario", "recommended") or "recommended")
        season_source = str(payload.get("seasonSource", "both") or "both")
        water_budget_ratio = safe_float(payload.get("waterBudgetRatio", 1.0), 1.0)
        year_raw = payload.get("year", None)
        year_val = None if year_raw in (None, "", "none", "null") else safe_int(year_raw, 0)
        if year_val == 0:
            year_val = None

        horizon_years = int(payload.get("horizonYears", 15) or 15)
        horizon_years = max(1, min(30, horizon_years))

        repeats = int(payload.get("repeats", 8) or 8)
        repeats = max(1, min(30, repeats))

        algos = payload.get("algorithms", None) or ["GA", "ABC", "ACO"]
        algos = [str(a).upper() for a in algos if str(a).strip()]
        if not algos:
            algos = ["GA", "ABC", "ACO"]

        max_seconds = payload.get("maxSeconds", 120)
        try:
            max_seconds = float(max_seconds)
        except Exception:
            max_seconds = 120.0
        max_seconds = max(20.0, min(240.0, max_seconds))

        # Load parcel baseline (current) water per parcel
        parcels_df = load_parcels_csv()
        parcels_df = parcels_df.copy()
        parcels_df["parsel_id"] = parcels_df["parsel_id"].astype(str)

        if selected:
            parcels_df = parcels_df[parcels_df["parsel_id"].isin(selected)].copy()

        # Build crop water lookup (m3/da)
        crops_df = load_crops_csv()
        crops_df = crops_df.copy()
        crops_df["urun_adi"] = crops_df["urun_adi"].astype(str)
        water_per_da = {normalize_crop_key(r["urun_adi"]): safe_float(r["su_tuketimi_m3_da"], 0.0) for _, r in crops_df.iterrows()}
        # Non-zero water fallbacks so UI tables never show 0 m³ for rainfed/fallow.
        nonzero_water_fallback_m3_da = {
            normalize_crop_key("ARPA_KURU"): 220.0,
            normalize_crop_key("BUGDAY_KURU"): 250.0,
            normalize_crop_key("NOHUT_KURU"): 180.0,
            normalize_crop_key("MERCIMEK_KURU"): 160.0,
            normalize_crop_key("NADAS"): 50.0,
        }
        for ck, v in list(nonzero_water_fallback_m3_da.items()):
            if (ck not in water_per_da) or (not np.isfinite(water_per_da.get(ck, 0.0))) or (float(water_per_da.get(ck, 0.0)) <= 0.0):
                water_per_da[ck] = float(v)
        # Aliases for fallow => same non-zero proxy
        for k in ["FALLOW", "FALOW", "NAD"]:
            water_per_da[normalize_crop_key(k)] = float(nonzero_water_fallback_m3_da[normalize_crop_key("NADAS")])

        def _parcel_opt_water_from_bestpack(best_pack: Dict[str, Any]) -> Dict[str, float]:
            """Compute per-parcel annual water (m3) from best_pack parcels list using crop water_per_da and area."""
            out = {}
            for pr in (best_pack.get("parcels") or []):
                pid = str(pr.get("id"))
                p1 = (pr.get("primary") or {})
                p2 = (pr.get("secondary") or {})
                c1 = normalize_crop_key(str(p1.get("crop") or ""))
                c2 = normalize_crop_key(str(p2.get("crop") or ""))
                a1 = safe_float((p1.get("area_da") or 0.0), 0.0)
                a2 = safe_float((p2.get("area_da") or 0.0), 0.0)
                w1 = water_per_da.get(c1, 0.0) * a1
                w2 = water_per_da.get(c2, 0.0) * a2
                out[pid] = float(w1 + w2)
            return out

        def _run_algo_best(algo: str) -> Dict[str, Any]:
            """Run optimize 'repeats' times for a given algo and return the best output dict by objective (profit or efficiency depending on scenario)."""
            best_out = None
            best_score = None

            # per-run speed clamps
            # keep relatively small for UI responsiveness
            if algo == "GA":
                speed = {"generations": 18, "popSize": 28}
            elif algo == "ABC":
                speed = {"cycles": 25, "foodSources": 22}
            else:  # ACO
                speed = {"iterations": 25, "ants": 22}

            # Choose score: for su_tasarruf -> maximize efficiency (TL/m3) but also respect profit; for maks_kar -> maximize profit.
            def score_fn(out: Dict[str, Any]) -> float:
                prof = safe_float(out.get("total_profit_tl", 0.0), 0.0)
                wat = safe_float(out.get("total_water_m3", 0.0), 0.0)
                eff = prof / wat if wat > 0 else 0.0
                if scenario == "su_tasarruf":
                    return eff * 1e6 + prof  # prioritize efficiency, tie-break by profit
                if scenario == "maks_kar":
                    return prof
                # balanced/recommended: blend
                return prof + eff * 1e5

            # time budget per algo
            per_algo_budget = max_seconds / max(1, len(algos))
            t0 = time.perf_counter()

            for r in range(repeats):
                if (time.perf_counter() - t0) > per_algo_budget:
                    break
                seed = None
                try:
                    seed = int(payload.get("baseSeed")) + r if payload.get("baseSeed") not in (None, "", "none", "null") else None
                except Exception:
                    seed = None

                out = optimize(
                    selected,
                    scenario=scenario,
                    water_budget_ratio=water_budget_ratio,
                    year=year_val,
                    algorithm=algo,
                    options={
                        "twoSeason": True,
                        "seasonSource": season_source,
                "scenarioType": scenario_type,
                        **speed,
                        "seed": seed,
                    },
                )
                if not isinstance(out, dict) or out.get("status") != "OK":
                    continue

                sc = score_fn(out)
                if (best_score is None) or (sc > best_score):
                    best_score = sc
                    best_out = out

            # Fallback: one run if all failed
            if best_out is None:
                best_out = optimize(
                    selected,
                    scenario=scenario,
                    water_budget_ratio=water_budget_ratio,
                    year=year_val,
                    algorithm=algo,
                    options={"twoSeason": True, "seasonSource": season_source, **speed},
                )
            return best_out if isinstance(best_out, dict) else {"status": "ERROR", "message": "No output"}

        # Run each algorithm and compute per-parcel savings (annual and 15y)
        algo_results = {}
        for algo in algos:
            out = _run_algo_best(algo)
            if not isinstance(out, dict) or out.get("status") != "OK":
                algo_results[algo] = {"status": "ERROR", "message": str(out.get("message", "run failed"))}
                continue
            # Build best_pack-like parcels list from output (reuse same logic as benchmark)
            parcels_compact = []
            for pr in (out.get("parcels") or []):
                pid = str(pr.get("id"))
                rec = (((pr.get("result") or {}).get("recommended")) or [])
                c1 = (rec[0] or {}) if len(rec) > 0 else {}
                c2 = (rec[1] or {}) if len(rec) > 1 else {}
                parcels_compact.append({
                    "id": pid,
                    "primary": {"crop": str(c1.get("name") or ""), "area_da": safe_float(c1.get("area", 0.0), 0.0)},
                    "secondary": {"crop": str(c2.get("name") or ""), "area_da": safe_float(c2.get("area", 0.0), 0.0)},
                })
            parcels_compact.sort(key=lambda x: x.get("id"))

            best_pack = {"parcels": parcels_compact}
            opt_water_by_parcel = _parcel_opt_water_from_bestpack(best_pack)

            # Baseline per-parcel water (m3) from parcels_df
            base_by_parcel = {str(r["parsel_id"]): safe_float(r.get("mevcut_su_m3", 0.0), 0.0) for _, r in parcels_df.iterrows()}

            savings_annual = {}
            for pid, base_w in base_by_parcel.items():
                opt_w = safe_float(opt_water_by_parcel.get(pid, base_w), base_w)
                sav = max(0.0, float(base_w - opt_w))
                savings_annual[pid] = sav

            total_base = float(sum(base_by_parcel.values()))
            total_opt = float(sum(safe_float(opt_water_by_parcel.get(pid, base_by_parcel[pid]), base_by_parcel[pid]) for pid in base_by_parcel.keys()))
            total_save_annual = float(sum(savings_annual.values()))
            total_save_15y = total_save_annual * horizon_years

            algo_results[algo] = {
                "status": "OK",
                "total_base_m3": total_base,
                "total_opt_m3": total_opt,
                "annual_saving_m3": total_save_annual,
                "saving_15y_m3": total_save_15y,
                "saving_pct": (100.0 * total_save_annual / total_base) if total_base > 0 else 0.0,
                "parcel_saving_annual": savings_annual,
                "parcel_saving_15y": {pid: sav * horizon_years for pid, sav in savings_annual.items()},
            }

        # Compute AVG across successful algos
        ok_algos = [a for a in algos if algo_results.get(a, {}).get("status") == "OK"]
        avg = {"status": "ERROR", "message": "No successful algorithm runs"}
        if ok_algos:
            # per-parcel mean
            base_by_parcel = {str(r["parsel_id"]): safe_float(r.get("mevcut_su_m3", 0.0), 0.0) for _, r in parcels_df.iterrows()}
            parcel_avg_annual = {}
            for pid in base_by_parcel.keys():
                vals = [safe_float(algo_results[a]["parcel_saving_annual"].get(pid, 0.0), 0.0) for a in ok_algos]
                parcel_avg_annual[pid] = float(sum(vals) / len(vals)) if vals else 0.0
            total_base = float(sum(base_by_parcel.values()))
            total_save_annual = float(sum(parcel_avg_annual.values()))
            total_save_15y = total_save_annual * horizon_years
            avg = {
                "status": "OK",
                "total_base_m3": total_base,
                "annual_saving_m3": total_save_annual,
                "saving_15y_m3": total_save_15y,
                "saving_pct": (100.0 * total_save_annual / total_base) if total_base > 0 else 0.0,
                "parcel_saving_annual": parcel_avg_annual,
                "parcel_saving_15y": {pid: sav * horizon_years for pid, sav in parcel_avg_annual.items()},
            }

        # Build GeoJSON point layer from parcels_df (lat/lon)
        features = []
        for _, r in parcels_df.iterrows():
            pid = str(r["parsel_id"])
            lat = safe_float(r.get("lat", 0.0), 0.0)
            lon = safe_float(r.get("lon", 0.0), 0.0)
            if lat == 0.0 and lon == 0.0:
                continue
            props = {
                "parsel_id": pid,
                "koy": str(r.get("koy", "")),
                "ilce": str(r.get("ilce", "")),
                "alan_da": safe_float(r.get("alan_da", 0.0), 0.0),
                "base_m3": safe_float(r.get("mevcut_su_m3", 0.0), 0.0),
                "horizon_years": horizon_years,
            }
            # per algo parcel saving
            for algo in algos:
                if algo_results.get(algo, {}).get("status") == "OK":
                    props[f"save15_{algo}_m3"] = safe_float(algo_results[algo]["parcel_saving_15y"].get(pid, 0.0), 0.0)
                    props[f"save_{algo}_pct"] = safe_float(algo_results[algo]["saving_pct"], 0.0)
                else:
                    props[f"save15_{algo}_m3"] = 0.0
                    props[f"save_{algo}_pct"] = 0.0
            # average
            if avg.get("status") == "OK":
                props["save15_AVG_m3"] = safe_float(avg["parcel_saving_15y"].get(pid, 0.0), 0.0)
                props["save_AVG_pct"] = safe_float(avg["saving_pct"], 0.0)
            else:
                props["save15_AVG_m3"] = 0.0
                props["save_AVG_pct"] = 0.0

            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": props,
            })

        # --- Build simple year-by-year series for UI charts (cumulative savings) ---
        years = list(range(1, horizon_years + 1))
        series = {"years": years}
        for algo in algos:
            if algo_results.get(algo, {}).get("status") == "OK":
                annual = safe_float(algo_results[algo].get("annual_saving_m3", 0.0), 0.0)
                series[algo] = {
                    "annual_saving_m3": annual,
                    "cumulative_saving_m3": [annual * y for y in years],
                }
            else:
                series[algo] = {"annual_saving_m3": 0.0, "cumulative_saving_m3": [0.0 for _ in years]}
        if avg.get("status") == "OK":
            annual = safe_float(avg.get("annual_saving_m3", 0.0), 0.0)
            series["AVG"] = {"annual_saving_m3": annual, "cumulative_saving_m3": [annual * y for y in years]}
        else:
            series["AVG"] = {"annual_saving_m3": 0.0, "cumulative_saving_m3": [0.0 for _ in years]}

        return jsonify({
            "status": "OK",
            "horizonYears": horizon_years,
            "series": series,
            "seasonSource": season_source,
            "scenario": scenario,
            "algorithms": algos,
            "totals": {**{a: {k: algo_results[a].get(k) for k in ["total_base_m3","total_opt_m3","annual_saving_m3","saving_15y_m3","saving_pct"]} if algo_results.get(a, {}).get("status")=="OK" else {"status":"ERROR","message":algo_results.get(a,{}).get("message","")} for a in algos},
                       "AVG": {k: avg.get(k) for k in ["total_base_m3","annual_saving_m3","saving_15y_m3","saving_pct"]} if avg.get("status")=="OK" else {"status":"ERROR","message":avg.get("message","")}},
            "series": series,
            "geojson": {"type": "FeatureCollection", "features": features},
            "howCalculated": {
                "baseline": "Per-parcel baseline water uses data/parsel_su_kar_ozet.csv -> mevcut_su_m3 (annual).",
                "optimized": "Per-parcel optimized water = sum_seasons(area_da * crop_su_tuketimi_m3_da) using data/urun_parametreleri_demo.csv; NADAS treated as 0.",
                "annualSaving": "max(0, baseline - optimized)",
                "saving15y": f"annualSaving * {horizon_years}"
            }
        })
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e), "where": "api_impact15y"}), 500


# 15-year profit route removed in equal-water planning mode
# @app.post("/api/profit15y")
def api_profit15y():
    """Compute 15-year profit projection per algorithm (GA/ABC/ACO) and their mean (AVG).

    Baseline (current) per-parcel profit is taken from data/parsel_su_kar_ozet.csv -> mevcut_kar_tl (annual).
    Optimized profit is computed as sum_seasons(area_da * net_profit_tl_da) using data/urun_parametreleri_demo.csv,
    where net_profit_tl_da = beklenen_verim_kg_da * fiyat_tl_kg - maliyet_tl_da. NADAS treated as 0.

    Returns totals and a GeoJSON point layer with per-algo profit15 fields.
    """
    try:
        payload = request.get_json(force=True, silent=True) or {}
        selected = payload.get("selectedParcelIds", []) or []
        if isinstance(selected, str):
            selected = [normalize_parcel_id(s) for s in selected.split(",") if str(s).strip()]
        elif not isinstance(selected, list):
            selected = list(selected) if selected else []

        scenario = str(payload.get("scenario", "recommended") or "recommended")
        season_source = str(payload.get("seasonSource", "both") or "both")
        water_budget_ratio = safe_float(payload.get("waterBudgetRatio", 1.0), 1.0)

        year_raw = payload.get("year", None)
        year_val = None if year_raw in (None, "", "none", "null") else safe_int(year_raw, 0)
        if year_val == 0:
            year_val = None

        horizon_years = int(payload.get("horizonYears", 15) or 15)
        horizon_years = max(1, min(30, horizon_years))

        repeats = int(payload.get("repeats", 8) or 8)
        repeats = max(1, min(30, repeats))

        algos = payload.get("algorithms", None) or ["GA", "ABC", "ACO"]
        algos = [str(a).upper() for a in algos if str(a).strip()]
        if not algos:
            algos = ["GA", "ABC", "ACO"]

        max_seconds = payload.get("maxSeconds", 120)
        try:
            max_seconds = float(max_seconds)
        except Exception:
            max_seconds = 120.0
        max_seconds = max(20.0, min(240.0, max_seconds))

        parcels_df = load_parcels_csv().copy()
        parcels_df["parsel_id"] = parcels_df["parsel_id"].astype(str)
        if selected:
            parcels_df = parcels_df[parcels_df["parsel_id"].isin(selected)].copy()

        crops_df = load_crops_csv().copy()
        crops_df["urun_adi"] = crops_df["urun_adi"].astype(str)

        def _net_profit_da(row) -> float:
            y = safe_float(row.get("beklenen_verim_kg_da", 0.0), 0.0)
            p = safe_float(row.get("fiyat_tl_kg", 0.0), 0.0)
            c = safe_float(row.get("maliyet_tl_da", 0.0), 0.0)
            return float(y * p - c)

        profit_per_da = {normalize_crop_key(r["urun_adi"]): _net_profit_da(r) for _, r in crops_df.iterrows()}
        for k in ["NADAS", "FALLOW", "FALOW", "NAD"]:
            profit_per_da[normalize_crop_key(k)] = 0.0

        def _parcel_opt_profit_from_out(out: Dict[str, Any]) -> Dict[str, float]:
            outp = {}
            for pr in (out.get("parcels") or []):
                pid = str(pr.get("id"))
                rec = (((pr.get("result") or {}).get("recommended")) or [])
                c1 = (rec[0] or {}) if len(rec) > 0 else {}
                c2 = (rec[1] or {}) if len(rec) > 1 else {}
                n1 = normalize_crop_key(str(c1.get("name") or ""))
                n2 = normalize_crop_key(str(c2.get("name") or ""))
                a1 = safe_float(c1.get("area", 0.0), 0.0)
                a2 = safe_float(c2.get("area", 0.0), 0.0)
                prof = profit_per_da.get(n1, 0.0) * a1 + profit_per_da.get(n2, 0.0) * a2
                outp[pid] = float(prof)
            return outp

        def _run_algo_best(algo: str) -> Dict[str, Any]:
            best_out = None
            best_score = None
            if algo == "GA":
                speed = {"generations": 18, "popSize": 28}
            elif algo == "ABC":
                speed = {"cycles": 25, "foodSources": 22}
            else:
                speed = {"iterations": 25, "ants": 22}

            def score_fn(out: Dict[str, Any]) -> float:
                prof = safe_float(out.get("total_profit_tl", 0.0), 0.0)
                wat = safe_float(out.get("total_water_m3", 0.0), 0.0)
                eff = prof / wat if wat > 0 else 0.0
                if scenario == "su_tasarruf":
                    return eff * 1e6 + prof
                if scenario == "maks_kar":
                    return prof
                return prof + eff * 1e5

            per_algo_budget = max_seconds / max(1, len(algos))
            t0 = time.perf_counter()
            for r in range(repeats):
                if (time.perf_counter() - t0) > per_algo_budget:
                    break
                seed = None
                try:
                    seed = int(payload.get("baseSeed")) + r if payload.get("baseSeed") not in (None, "", "none", "null") else None
                except Exception:
                    seed = None

                out = optimize(
                    selected,
                    scenario=scenario,
                    water_budget_ratio=water_budget_ratio,
                    year=year_val,
                    algorithm=algo,
                    options={"twoSeason": True, "seasonSource": season_source, **speed, "seed": seed},
                )
                if not isinstance(out, dict) or out.get("status") != "OK":
                    continue
                sc = score_fn(out)
                if (best_score is None) or (sc > best_score):
                    best_score = sc
                    best_out = out

            if best_out is None:
                best_out = optimize(
                    selected,
                    scenario=scenario,
                    water_budget_ratio=water_budget_ratio,
                    year=year_val,
                    algorithm=algo,
                    options={"twoSeason": True, "seasonSource": season_source, **speed},
                )
            return best_out if isinstance(best_out, dict) else {"status": "ERROR", "message": "No output"}

        base_by_parcel = {str(r["parsel_id"]): safe_float(r.get("mevcut_kar_tl", 0.0), 0.0) for _, r in parcels_df.iterrows()}
        total_base = float(sum(base_by_parcel.values()))

        algo_results = {}
        for algo in algos:
            out = _run_algo_best(algo)
            if not isinstance(out, dict) or out.get("status") != "OK":
                algo_results[algo] = {"status": "ERROR", "message": str(out.get("message", "run failed"))}
                continue

            opt_profit_by_parcel = _parcel_opt_profit_from_out(out)
            delta_by_parcel = {}
            for pid, base_p in base_by_parcel.items():
                opt_p = safe_float(opt_profit_by_parcel.get(pid, base_p), base_p)
                delta_by_parcel[pid] = float(opt_p - base_p)

            total_opt = float(sum(safe_float(opt_profit_by_parcel.get(pid, base_by_parcel[pid]), base_by_parcel[pid]) for pid in base_by_parcel.keys()))
            total_delta = total_opt - total_base

            algo_results[algo] = {
                "status": "OK",
                "total_base_tl": total_base,
                "total_opt_tl": total_opt,
                "delta_annual_tl": total_delta,
                "delta_15y_tl": total_delta * horizon_years,
                "parcel_opt_annual": {pid: safe_float(opt_profit_by_parcel.get(pid, base_by_parcel[pid]), base_by_parcel[pid]) for pid in base_by_parcel.keys()},
                "parcel_delta_annual": delta_by_parcel,
                "parcel_delta_15y": {pid: d * horizon_years for pid, d in delta_by_parcel.items()},
            }

        ok_algos = [a for a in algos if algo_results.get(a, {}).get("status") == "OK"]
        avg = {"status": "ERROR", "message": "No successful algorithm runs"}
        if ok_algos:
            parcel_opt_avg = {}
            parcel_delta_avg = {}
            for pid, base_p in base_by_parcel.items():
                vals_opt = [safe_float(algo_results[a]["parcel_opt_annual"].get(pid, base_p), base_p) for a in ok_algos]
                opt_mean = float(sum(vals_opt) / len(vals_opt)) if vals_opt else float(base_p)
                parcel_opt_avg[pid] = opt_mean
                parcel_delta_avg[pid] = float(opt_mean - base_p)
            total_opt_avg = float(sum(parcel_opt_avg.values()))
            total_delta_avg = total_opt_avg - total_base
            avg = {
                "status": "OK",
                "total_base_tl": total_base,
                "total_opt_tl": total_opt_avg,
                "delta_annual_tl": total_delta_avg,
                "delta_15y_tl": total_delta_avg * horizon_years,
                "parcel_opt_annual": parcel_opt_avg,
                "parcel_delta_annual": parcel_delta_avg,
                "parcel_delta_15y": {pid: d * horizon_years for pid, d in parcel_delta_avg.items()},
            }

        features = []
        for _, r in parcels_df.iterrows():
            pid = str(r["parsel_id"])
            lat = safe_float(r.get("lat", 0.0), 0.0)
            lon = safe_float(r.get("lon", 0.0), 0.0)
            if lat == 0.0 and lon == 0.0:
                continue
            props = {
                "parsel_id": pid,
                "koy": str(r.get("koy", "")),
                "ilce": str(r.get("ilce", "")),
                "alan_da": safe_float(r.get("alan_da", 0.0), 0.0),
                "base_profit_tl": safe_float(r.get("mevcut_kar_tl", 0.0), 0.0),
                "horizon_years": horizon_years,
            }
            for algo in algos:
                if algo_results.get(algo, {}).get("status") == "OK":
                    props[f"profit15_{algo}_tl"] = safe_float(algo_results[algo]["parcel_delta_15y"].get(pid, 0.0), 0.0)
                    props[f"profit_{algo}_annual_tl"] = safe_float(algo_results[algo]["parcel_opt_annual"].get(pid, 0.0), 0.0)
                else:
                    props[f"profit15_{algo}_tl"] = 0.0
                    props[f"profit_{algo}_annual_tl"] = 0.0
            if avg.get("status") == "OK":
                props["profit15_AVG_tl"] = safe_float(avg["parcel_delta_15y"].get(pid, 0.0), 0.0)
                props["profit_AVG_annual_tl"] = safe_float(avg["parcel_opt_annual"].get(pid, 0.0), 0.0)
            else:
                props["profit15_AVG_tl"] = 0.0
                props["profit_AVG_annual_tl"] = 0.0

            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": props,
            })

        # --- Build simple year-by-year series for UI charts (cumulative profit delta) ---
        years = list(range(1, horizon_years + 1))
        series = {"years": years}
        for algo in algos:
            if algo_results.get(algo, {}).get("status") == "OK":
                annual = safe_float(algo_results[algo].get("delta_annual_tl", 0.0), 0.0)
                series[algo] = {
                    "delta_annual_tl": annual,
                    "cumulative_delta_tl": [annual * y for y in years],
                }
            else:
                series[algo] = {"delta_annual_tl": 0.0, "cumulative_delta_tl": [0.0 for _ in years]}
        if avg.get("status") == "OK":
            annual = safe_float(avg.get("delta_annual_tl", 0.0), 0.0)
            series["AVG"] = {"delta_annual_tl": annual, "cumulative_delta_tl": [annual * y for y in years]}
        else:
            series["AVG"] = {"delta_annual_tl": 0.0, "cumulative_delta_tl": [0.0 for _ in years]}

        return jsonify({
            "status": "OK",
            "horizonYears": horizon_years,
            "series": series,
            "seasonSource": season_source,
            "scenario": scenario,
            "algorithms": algos,
            "totals": {**{a: {k: algo_results[a].get(k) for k in ["total_base_tl", "total_opt_tl", "delta_annual_tl", "delta_15y_tl"]} if algo_results.get(a, {}).get("status") == "OK" else {"status": "ERROR", "message": algo_results.get(a, {}).get("message", "")} for a in algos},
                       "AVG": {k: avg.get(k) for k in ["total_base_tl", "total_opt_tl", "delta_annual_tl", "delta_15y_tl"]} if avg.get("status") == "OK" else {"status": "ERROR", "message": avg.get("message", "")}},
            "geojson": {"type": "FeatureCollection", "features": features},
            "howCalculated": {
                "baseline": "Per-parcel baseline profit uses data/parsel_su_kar_ozet.csv -> mevcut_kar_tl (annual).",
                "optimized": "Per-parcel optimized profit = sum_seasons(area_da * (beklenen_verim_kg_da*fiyat_tl_kg - maliyet_tl_da)) using data/urun_parametreleri_demo.csv; NADAS treated as 0.",
                "deltaAnnual": "optimized - baseline",
                "delta15y": f"deltaAnnual * {horizon_years}"
            }
        })
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e), "where": "api_profit15y"}), 500


if __name__ == "__main__":
    # Run: python app.py  -> http://127.0.0.1:5000
    # NOTE (Windows): Werkzeug's debug reloader (watchdog) may incorrectly detect
    # changes inside site-packages and restart the server continuously.
    # That breaks long-running optimization requests and causes the UI to show
    # "Hata: Önceki sonuçlar gösteriliyor".
    # Keep debug enabled (for tracebacks), but disable the auto-reloader.
    app.run(debug=True, host="127.0.0.1", port=5000, use_reloader=False)
