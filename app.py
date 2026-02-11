from __future__ import annotations

import json
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

import pandas as pd
import numpy as np
from flask import Flask, jsonify, request, send_from_directory
import time
import statistics

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

app = Flask(__name__, static_folder=None)

# Print the real file path so you can verify which project folder is running.
print(f"[Akkaya] Running app from: {__file__}")

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
        df["parsel_id"] = df["parsel_id"].astype(str).str.strip()
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
                    pid = str(r.get("parcel_id","")).strip()
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
    tr_map = str.maketrans({"Ç":"C","Ğ":"G","İ":"I","Ö":"O","Ş":"S","Ü":"U","Â":"A","Û":"U","Î":"I",
                            "ç":"C","ğ":"G","ı":"I","ö":"O","ş":"S","ü":"U"})
    s = s.translate(tr_map)
    for ch in ["-", ".", ",", "(", ")", "[", "]", "{", "}", "/"]:
        s = s.replace(ch, " ")
    s = "_".join([p for p in s.split() if p])
    return s



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
    """Map (land_capability_class, crop_key) -> suitability_score (0..1)."""
    key = "crop_suitability_map"
    if key in _cache:
        return _cache[key]
    path = DATA_DIR / "enhanced_dataset" / "csv" / "crop_suitability_assumed.csv"
    m: Dict[Tuple[str, str], float] = {}
    if path.exists():
        try:
            df = pd.read_csv(path)
            for _, r in df.iterrows():
                lcc = str(r.get("land_capability_class","") or "").strip().upper()
                ck = normalize_crop_key(str(r.get("crop","")))
                sc = safe_float(r.get("suitability_score_assumed", 0.85), 0.85)
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
        df_enh["parcel_id"] = df_enh["parcel_id"].astype(str).str.strip()
        # unify lat/lon
        if "lat_deg" in df_enh.columns and "lat" not in df_enh.columns:
            df_enh["lat"] = df_enh["lat_deg"]
        if "lon_deg" in df_enh.columns and "lon" not in df_enh.columns:
            df_enh["lon"] = df_enh["lon_deg"]

    df_leg = pd.read_csv(legacy_csv) if legacy_csv.exists() else pd.DataFrame()
    if not df_leg.empty:
        df_leg["parsel_id"] = df_leg["parsel_id"].astype(str).str.strip()
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
        seasons["parcel_id"] = seasons["parcel_id"].astype(str).str.strip()
        area_map = seasons.groupby("parcel_id")["area_da"].max().to_dict()
    except Exception:
        area_map = {}

    # GeoJSON-derived area overrides (computed externally)

    parcels: List[Dict[str, Any]] = []
    for _, r in df.iterrows():
        pid = str(r.get("parcel_id","") or "").strip()
        if not pid:
            continue

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

    parcels = sorted(parcels, key=lambda x: x["id"])
    _cache[key] = parcels
    return _cache[key]




def load_crop_catalog() -> Dict[str, Dict[str, Any]]:
    """Load per-crop agronomic & economic parameters from CSV.

    Data-driven requirement: values MUST come from file, not hardcoded.

    Expected columns (either ; or ,):
      urun_adi, su_tuketimi_m3_da, beklenen_verim_kg_da, fiyat_tl_kg,
      degisken_maliyet_tl_da, net_kar_tl_da, kategori

    Returns dict keyed by normalized crop name.
    """
    key = "crop_catalog"
    if key in _cache:
        return _cache[key]

    path = DATA_DIR / "urun_parametreleri_demo.csv"
    if not path.exists():
        _cache[key] = {}
        return _cache[key]

    # delimiter auto-detect (; or ,)
    first = path.read_text(encoding="utf-8", errors="replace").splitlines()[0]
    sep = ";" if (";" in first and "," not in first) else ","

    try:
        df = pd.read_csv(path, sep=sep)
    except Exception:
        df = pd.read_csv(path, sep=sep, engine="python")

    # If the CSV contains 0 water for rainfed ("*_KURU") crops or fallow, the UI shows 0 m³ which
    # users interpret as a bug. We therefore apply conservative non-zero fallbacks when water==0.
    # You can calibrate these later with ET0/Kc or local agronomy sources.
    nonzero_water_fallback_m3_da = {
        normalize_crop_name("ARPA_KURU"): 220.0,
        normalize_crop_name("BUGDAY_KURU"): 250.0,
        normalize_crop_name("NOHUT_KURU"): 180.0,
        normalize_crop_name("MERCIMEK_KURU"): 160.0,
        normalize_crop_name("NADAS"): 50.0,
    }

    cat: Dict[str, Dict[str, Any]] = {}
    for _, r in df.iterrows():
        name = str(r.get("urun_adi", "") or r.get("urun", "") or r.get("name", "")).strip()
        if not name:
            continue
        nk = normalize_crop_name(name)
        wpd = float(r.get("su_tuketimi_m3_da", 0) or 0)
        if (not np.isfinite(wpd)) or (wpd <= 0):
            wpd = float(nonzero_water_fallback_m3_da.get(nk, wpd) or 0)

        # Profit per da: prefer explicit net_kar_tl_da; otherwise derive from yield*price - cost.
        try:
            ppd = float(r.get("net_kar_tl_da", 0) or 0)
        except Exception:
            ppd = 0.0
        if (not np.isfinite(ppd)) or (ppd <= 0):
            try:
                yld = float(r.get("beklenen_verim_kg_da", 0) or 0)
                price = float(r.get("fiyat_tl_kg", 0) or 0)
                cost = float(r.get("degisken_maliyet_tl_da", 0) or 0)
                derived = yld * price - cost
                if np.isfinite(derived) and derived > 0:
                    ppd = float(derived)
            except Exception:
                pass

        # If still missing/zero, use conservative category/keyword defaults so the UI doesn't show 0 TL/da.
        # These are intentionally modest and should be replaced with calibrated local economics.
        if (not np.isfinite(ppd)) or (ppd <= 0):
            ck = normalize_crop_name(name)
            if ck == normalize_crop_name("NADAS"):
                ppd = 0.0
            elif _is_rainfed_crop(ck):
                ppd = 2500.0
            else:
                veg_markers = ('BIBER', 'DOMATES', 'MARUL', 'ISPANAK', 'SOGAN', 'KABAK', 'KARPUZ', 'KAVUN')
                if any(m in ck for m in veg_markers):
                    ppd = 4500.0
                elif any(m in ck for m in ("NOHUT","MERCIMEK","FASULYE")):
                    ppd = 3500.0
                else:
                    ppd = 3000.0

        # Apply the same realism caps/discounts used by the optimizer.
        try:
            if normalize_crop_key(nk) != FALLOW:
                ppd = _realistic_profit_per_da(nk, ppd)
        except Exception:
            pass

        cat[nk] = {
            "name": name,
            # canonical keys used across the app/UI
            "waterPerDa": wpd,
            "profitPerDa": float(ppd),

            # detailed economics (kept for transparency)
            "yieldKgPerDa": float(r.get("beklenen_verim_kg_da", 0) or 0),
            "priceTlPerKg": float(r.get("fiyat_tl_kg", 0) or 0),
            "varCostTlPerDa": float(r.get("degisken_maliyet_tl_da", 0) or 0),
            "netProfitTlPerDa": float(r.get("net_kar_tl_da", 0) or 0),

            "category": str(r.get("kategori", "") or "").strip(),
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

def merged_pattern_candidates(village: str, district: str, top_n: int = 12) -> List[Tuple[str, float]]:
    """
    Returns candidate crops with weights from village/district patterns (JSON).

    Supports two JSON shapes:
      A) {"CROP": share, ...}
      B) {"top_crops":[{"crop":"PATATES","share":0.12}, ...], ...}
    """
    village_path = DATA_DIR / "village_crop_patterns.json"
    district_path = DATA_DIR / "district_crop_patterns.json"
    village_obj = load_json(village_path) if village_path.exists() else {}
    district_obj = load_json(district_path) if district_path.exists() else {}

    def _norm_key(s: str) -> str:
        return normalize_crop_key(s)

    vkey = _norm_key(village)
    dkey = _norm_key(district)

    merged: Dict[str, float] = {}

    def _add_from(src: Any, weight: float) -> None:
        if not src:
            return
        # Shape B
        if isinstance(src, dict) and isinstance(src.get("top_crops", None), list):
            for item in src["top_crops"]:
                try:
                    ck = _norm_key(item.get("crop", ""))
                    sh = float(item.get("share", 0) or 0)
                except Exception:
                    continue
                if ck:
                    merged[ck] = merged.get(ck, 0.0) + weight * sh
            return
        # Shape A
        if isinstance(src, dict):
            # sometimes nested under "crops"
            crops = src.get("crops", src)
            if isinstance(crops, dict):
                for c, share in crops.items():
                    ck = _norm_key(c)
                    if not ck:
                        continue
                    try:
                        merged[ck] = merged.get(ck, 0.0) + weight * float(share)
                    except Exception:
                        pass

    _add_from(district_obj.get(dkey, {}), 0.6)
    _add_from(village_obj.get(vkey, {}), 0.4)

    if not merged:
        return []

    tot = sum(merged.values()) or 1.0
    items = [(c, s / tot) for c, s in merged.items()]
    items.sort(key=lambda x: x[1], reverse=True)
    return items[:top_n]

def recommend_crop_for_parcel(parcel: Dict[str, Any], algo: str = "GA") -> Optional[Dict[str, Any]]:
    """
    Picks ONE crop for the parcel (simple heuristic): among candidate crops,
    maximize profitPerDa / max(1, waterPerDa), with a slight preference for crops that are common locally.

    This is not a full scientific optimizer; it's a transparent baseline that uses your CSV+JSON data.
    """
    catalog = load_crop_catalog()
    if not catalog:
        return None

    candidates = merged_pattern_candidates(parcel.get("village",""), parcel.get("district",""))
    if not candidates:
        # fallback: all catalog crops
        candidates = [(k, 1.0/len(catalog)) for k in list(catalog.keys())[:50]]

    best = None
    best_score = -1e18
    for crop_name, share in candidates:
        ck = normalize_crop_key(crop_name)
        if ck not in catalog:
            continue
        c = catalog[ck]
        w = float(c.get("waterPerDa", 0) or 0)
        p = float(c.get("profitPerDa", 0) or 0)
        eff = p / max(1.0, w)

        # algorithm flavour: tweak scoring slightly (keeps deterministic + transparent)
        if algo.upper() == "ABC":
            score = 0.85*eff + 0.15*p/10000 + 0.10*share
        elif algo.upper() == "ACO":
            score = 0.80*eff + 0.20*share
        else:  # GA
            score = 0.90*eff + 0.10*share

        if score > best_score:
            best_score = score
            best = {
                "name": c["name"],
                "area": parcel.get("area_da", 0),
                "waterPerDa": w,
                "profitPerDa": p,
                "share": share
            }

    return best


# -----------------------------
# Enhanced dataset loaders
# -----------------------------

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
    out["parcels"] = _read_csv_safe(p.get("parcels"))
    out["s1"] = _read_csv_safe(p.get("seasons1"))
    out["s2"] = _read_csv_safe(p.get("seasons2"))
    out["reservoir"] = _read_csv_safe(p.get("reservoir"))
    out["irrigation_methods"] = _read_csv_safe(p.get("irrigation_methods"))
    out["delivery"] = _read_csv_safe(p.get("delivery"))

    # Optional / advanced frames
    out["crop_params"] = _read_csv_safe(p.get("crop_params"))
    out["crop_suitability"] = _read_csv_safe(p.get("crop_suitability"))
    out["crop_family"] = _read_csv_safe(p.get("crop_family"))
    out["monthly_climate"] = _read_csv_safe(p.get("monthly_climate"))
    out["objective_weights"] = _read_csv_safe(p.get("objective_weights"))

    _cache[key] = out
    return out



# -----------------------------
# FAO-56 style water requirement (ET0-Kc) + effective rainfall + monthly breakdown
# -----------------------------

def _effective_rain_scs_mm(p_mm: float) -> float:
    """USDA-SCS monthly effective rainfall approximation (mm)."""
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
    """Build a simple FAO-56 like daily Kc curve using stage proportions.
    Piecewise-linear: ini (flat kc_ini), dev (kc_ini->kc_mid), mid (flat kc_mid), late (kc_mid->kc_end).
    """
    total_days = int(max(1, total_days))
    # stage lengths
    def _len(p):
        return int(round(total_days * float(p)))
    L_ini, L_dev, L_mid, L_late = _len(p_ini), _len(p_dev), _len(p_mid), _len(p_late)
    # fix rounding drift
    drift = total_days - (L_ini + L_dev + L_mid + L_late)
    L_late = max(0, L_late + drift)

    kc = []
    kc += [float(kc_ini)] * max(0, L_ini)

    # dev: linear kc_ini -> kc_mid
    if L_dev > 0:
        for t in range(L_dev):
            frac = (t + 1) / max(1, L_dev)
            kc.append(float(kc_ini + (kc_mid - kc_ini) * frac))

    kc += [float(kc_mid)] * max(0, L_mid)

    # late: linear kc_mid -> kc_end
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
    for _, r in df.iterrows():
        ck = normalize_crop_key(str(r.get("crop","")))
        if not ck:
            continue
        out[ck] = {
            "kc_ini": float(r.get("kc_ini", 0.6) or 0.6),
            "kc_mid": float(r.get("kc_mid", 1.0) or 1.0),
            "kc_end": float(r.get("kc_end", 0.8) or 0.8),
            "p_ini": float(r.get("p_ini", 0.2) or 0.2),
            "p_dev": float(r.get("p_dev", 0.3) or 0.3),
            "p_mid": float(r.get("p_mid", 0.3) or 0.3),
            "p_late": float(r.get("p_late", 0.2) or 0.2),
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
        if row.empty:
            et0_d = 0.0
            p_d = 0.0
        else:
            r = row.iloc[0]
            et0_m = float(r.get("et0_mm", 0.0) or 0.0)
            p_m = float(r.get("precip_mm", r.get("rain_mm", 0.0)) or 0.0)
            days_in_month = int((mstart + pd.offsets.MonthEnd(0)).day)
            et0_d = et0_m / max(1, days_in_month)
            p_d = p_m / max(1, days_in_month)
        etc_d = et0_d * float(kc_daily[idx_day])
        peff_d = _effective_rain_scs_mm(p_d)  # daily approx
        nir_d = max(0.0, etc_d - peff_d)
        gross_d = nir_d / eff
        out_mm[int(day.month)] += gross_d

    return {m: float(max(0.0, v)) for m,v in out_mm.items() if v > 0.0}

def _load_monthly_climate_for_parcel_year(parcel_id: str, year: int) -> pd.DataFrame:
    frames = load_enhanced_frames()
    clim = frames.get("climate")
    if clim is None or clim.empty:
        return pd.DataFrame(columns=["month","et0_mm","precip_mm"])
    df = clim.copy()
    df["parcel_id"] = df["parcel_id"].astype(str)
    df["year"] = df["year"].astype(int)
    df = df[(df["parcel_id"] == str(parcel_id)) & (df["year"] == int(year))]
    # ensure month column exists as YYYY-MM-01
    if "month" not in df.columns:
        df["month"] = pd.to_datetime(dict(year=df["year"], month=df["month_num"], day=1), errors="coerce")
    else:
        df["month"] = pd.to_datetime(df["month"], errors="coerce")
    df = df.rename(columns={"precip_mm":"precip_mm","rain_mm":"precip_mm"})
    if "precip_mm" not in df.columns:
        df["precip_mm"] = df.get("rain_mm", 0.0)
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
    """Annual basin water budget (m3) for irrigation.

    Consistency note:
    - The reservoir table (akkaya_reservoir_monthly_backend.csv) represents a **basin-wide**
      irrigation baseline (monthly), not a per-parcel budget.
    - The UI, however, compares this budget against totals computed from the **selected parcels**.

    To keep the comparison meaningful, we scale the basin-wide budget by the share of
    baseline demand of the selected parcels:

        budget_selected = budget_basin * (selected_baseline_water / all_baseline_water)

    If the reservoir series is missing, we fall back to the selected parcels' baseline water.
    """
    frames = load_enhanced_frames()
    res = frames["reservoir"].copy()
    if "month" in res.columns:
        res["year"] = res["month"].astype(str).str.slice(0,4).astype(int)
        y = int(year)
        sub = res[res["year"] == y]
        if len(sub) and "irrigation_m3_baseline" in sub.columns:
            basin_budget = float(sub["irrigation_m3_baseline"].sum())
            if basin_budget > 0:
                # scale basin budget to the selected parcel group
                try:
                    all_parcels = load_parcels()
                    all_water = sum(float(p.get("water_m3", 0) or 0) for p in all_parcels)
                    sel_water = sum(float(p.get("water_m3", 0) or 0) for p in selected_parcels)
                    if all_water <= 0:
                        all_water = sum(float(p.get("area_da", 0) or 0) for p in all_parcels) * 500.0
                    if sel_water <= 0:
                        sel_water = sum(float(p.get("area_da", 0) or 0) for p in selected_parcels) * 500.0
                    if all_water > 0:
                        share = max(0.0, min(1.0, sel_water / all_water))
                        return basin_budget * share
                except Exception:
                    pass
                return basin_budget
    # fallback: current total water from parcel summary
    return sum(float(p.get("water_m3",0) or 0) for p in selected_parcels)


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
    # Normalise parcel ids aggressively to prevent "Senaryo-2 sonuç yok" issues
    # caused by whitespace / casing inconsistencies between parcel meta and season CSVs.
    seasons["parcel_id"] = seasons["parcel_id"].astype(str).str.strip()
    seasons["crop_key"] = seasons["crop"].astype(str).map(normalize_crop_key)

    # Join district/LCC for group-level fallbacks and suitability checks
    parcels_df = frames.get("parcels")
    if parcels_df is not None and len(parcels_df):
        meta = parcels_df.copy()
        meta["parcel_id"] = meta["parcel_id"].astype(str)
        meta["district"] = meta["district"].astype(str) if "district" in meta.columns else ""
        meta["lcc"] = meta["land_capability_class"].astype(str).str.strip().str.upper() if "land_capability_class" in meta.columns else ""
        seasons = seasons.merge(meta[["parcel_id","district","lcc"]], on="parcel_id", how="left")
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
        return crop_list, W, R, W.copy(), R.copy()

    seasons = seasons.copy()
    # Normalize parcel_id keys to avoid hidden whitespace mismatches ("P1" vs "P1 ").
    seasons["parcel_id"] = seasons["parcel_id"].astype(str).str.strip()
    seasons["crop_key"] = seasons["crop"].astype(str).map(normalize_crop_key)
    seasons["season_key"] = seasons["season"].astype(str).str.lower().str.strip()
    seasons.loc[seasons["season_key"].str.contains("primary", na=False), "season_key"] = "primary"
    seasons.loc[seasons["season_key"].str.contains("secondary", na=False), "season_key"] = "secondary"

    parcels_df = frames.get("parcels")
    if parcels_df is not None and len(parcels_df):
        meta = parcels_df.copy()
        meta["parcel_id"] = meta["parcel_id"].astype(str)
        meta["district"] = meta["district"].astype(str) if "district" in meta.columns else ""
        meta["lcc"] = meta["land_capability_class"].astype(str).str.strip().str.upper() if "land_capability_class" in meta.columns else ""
        seasons = seasons.merge(meta[["parcel_id","district","lcc"]], on="parcel_id", how="left")
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
# Senaryo-2 (bahçe/perennial) kısıtı ve sulama ayarı
# -----------------------------

PERENNIAL_CROPS = {
    normalize_crop_key(x) for x in [
        "CEVIZ","BADEM","UZUM","UZUM_SOFRALIK","UZUM_SARAPLIK","ELMA","ARMUT","KAYISI",
        "SEFTALI","NAR","KIRAZ","ZEYTIN","FISTIK","FINDIK","INCIR","AYVA",
    ]
}

def _compute_perennial_locks(selected_parcels: List[Dict[str,Any]], year: int, crop_list: List[str], season_source: str) -> np.ndarray:
    """For Senaryo-2, if a parcel is a fruit-orchard/perennial in that year, lock crop choice to that crop.

    This prevents unrealistic switching of an established orchard to a different product.
    """
    P = len(selected_parcels)
    locks = np.full(P, -1, dtype=int)
    src = str(season_source or "both").lower()
    if src != "s2" or P == 0:
        return locks

    frames = load_enhanced_frames()
    seasons = frames["s2"].copy()
    if "year" in seasons.columns:
        seasons = seasons[seasons["year"].astype(int) == int(year)]

    if seasons.empty:
        return locks

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
        if ck and (ck in PERENNIAL_CROPS) and (ck in idx_crop):
            locks[i] = int(idx_crop[ck])
    return locks


def _apply_s2_irrigation_adjustments(objective: str) -> Tuple[float, float, str]:
    """Return (water_mult, profit_mult, label) for Senaryo-2 orchard parcels."""
    obj = (objective or "balanced").lower()
    if obj == "water_saving":
        return 0.80, 0.90, "Damla + kontrollü kısıntı (%20)"
    if obj == "max_profit":
        return 1.00, 1.00, "Standart sulama (verim odaklı)"
    return 0.90, 0.95, "Damla + hafif kısıntı (%10)"


# -----------------------------
# UI çıktı formatı (en az 2 ürün + 2 sezon etiketleri)
# -----------------------------


def _objective_alpha_beta(objective: str) -> Tuple[float, float]:
    """Return (profit_weight, water_weight).

    Naming kept for backward compatibility, but semantics are:
      - higher profit_weight => profit contributes more to fitness
      - higher water_weight  => water use is penalized more

    NOTE: Fitness uses *normalized* profit/water, so these weights are meaningful.
    """
    obj = str(objective or "balanced").lower()
    if obj == "water_saving":
        return 0.80, 1.60
    if obj == "max_profit":
        return 1.40, 0.40
    return 1.00, 1.00
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
    # Default: only add a second crop if it improves water efficiency and/or soil health
    # without sacrificing too much profitability.
    use_second = np.ones(P, dtype=bool)
    # WATER-SAVING POLICY:
    # In "water_saving" objective we do NOT recommend a second crop (double-cropping) for annual parcels,
    # because farmers explicitly want lower total water use; a second crop often increases seasonal water demand.
    # Scenario-2 orchard/perennial parcels (lock_mask) can still keep a cover crop if locked by rules.
    if str(objective).lower() in ("water_saving","su_tasarruf","su tasarruf","tasarruf"):
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
                "reason": "Ana ürün: 15 ürün havuzundan (su-kâr dengesi + parsel uygunluğu)"
            },
            {
                "name": c2,
                "season": season2,
                "area": float(a2[i]),
                "waterPerDa": w2,
                "waterTotal": wt2,
                "profitPerDa": p2,
                "profitTotal": pt2,
                **_irrig_block(c2, float(a2[i]), w2),
                "reason": "İkinci ürün: Niğde'de yaygın + düşük su + rotasyon/toprak faydası"
            },
        ]
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
        W1 = apply_irrigation_method_to_W(W1, selected_parcels, irrigation_method)
        W2 = apply_irrigation_method_to_W(W2, selected_parcels, irrigation_method)

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
    if np.any(lock_mask):
        ch1[lock_mask] = locks[lock_mask]
        # secondary: keep as provided (usually cover crop), but avoid same crop when possible
        for i in np.where(lock_mask)[0].tolist():
            if ch2[i] == ch1[i]:
                ch2[i] = int(np.argmin(W2[i, :]))

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
                "recommended": [
                    {
                        "name": c1,
                        "season": _season_label(c1, 'primary'),
                        "area": float(areas[i]),
                        "waterPerDa": float(W1[i, int(ch1[i])]),
                        "waterTotal": float(areas[i]) * float(W1[i, int(ch1[i])]),
                        "profitPerDa": float(R1[i, int(ch1[i])]),
                        "profitTotal": float(areas[i]) * float(R1[i, int(ch1[i])]),
                        **_irrig_block(c1, float(areas[i]), float(W1[i, int(ch1[i])])),
                        "reason": "Ana ürün: iki-sezon çözümü (su bütçesi + parsel uygunluğu)"
                    },
                    {
                        "name": c2,
                        "season": _season_label(c2, 'secondary'),
                        "area": float(areas[i]),
                        "waterPerDa": float(W2[i, int(ch2[i])]),
                        "waterTotal": float(areas[i]) * float(W2[i, int(ch2[i])]),
                        "profitPerDa": float(R2[i, int(ch2[i])]),
                        "profitTotal": float(areas[i]) * float(R2[i, int(ch2[i])]),
                        **_irrig_block(c2, float(areas[i]), float(W2[i, int(ch2[i])])),
                        "reason": "İkinci ürün: rotasyon + düşük su + kârlılık dengesi"
                    }
                ],
                "irrigationLabel": irrigation_label,
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
        "baselineTotals": baseline_totals,
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

    fitness = (profit_w * total_profit) - (water_w * total_water * 500.0) - penalty - monthly_pen - div_pen - share_pen - prev_pen
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

    # R1: hard - no same family back-to-back
    for i in range(P):
        if fam_p[i] and fam_s[i] and fam_p[i] == fam_s[i]:
            hard_penalty += 1e10

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
                w = float(r.get("penalty_weight", 1.0) or 1.0)
                if rid == "R1" and rtype == "hard":
                    hard_penalty *= w
                if rid == "R2" and rtype == "soft":
                    soft_bonus *= w
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
    if str(objective) in ("water_saving", "min_water"):
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

    fitness = (profit_w * total_profit) - (water_w * total_water * 500.0) - budget_penalty - monthly_penalty - hard_penalty + soft_bonus + low_input_bonus - div_pen - share_pen - prev_pen - nadas_pen - primary_nadas_pen
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
        W1 = apply_irrigation_method_to_W(W1, selected_parcels, irrigation_method)
        W2 = apply_irrigation_method_to_W(W2, selected_parcels, irrigation_method)
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
        W1 = apply_irrigation_method_to_W(W1, selected_parcels, irrigation_method)
        W2 = apply_irrigation_method_to_W(W2, selected_parcels, irrigation_method)
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
        W1 = apply_irrigation_method_to_W(W1, selected_parcels, irrigation_method)
        W2 = apply_irrigation_method_to_W(W2, selected_parcels, irrigation_method)
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
        eta1 = np.power(np.maximum(1e-9, eff1), 1.2)
        eta2 = np.power(np.maximum(1e-9, eff2), 1.2)
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
                 env_flow_ratio: float = 0.10, irrigation_method: Optional[str] = None, enforce_delivery_caps: bool = True) -> Dict[str, Any]:
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
        W1 = apply_irrigation_method_to_W(W1, selected_parcels, irrigation_method)
        W2 = apply_irrigation_method_to_W(W2, selected_parcels, irrigation_method)
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
        W1 = apply_irrigation_method_to_W(W1, selected_parcels, irrigation_method)
        W2 = apply_irrigation_method_to_W(W2, selected_parcels, irrigation_method)
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
        eta = np.power(np.maximum(1e-9, eff), 1.2)
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




def optimize(selected_ids: List[str], algorithm: str, scenario: str, water_budget_ratio: float, year: Optional[int]=None, options: Optional[Dict[str,Any]]=None) -> Dict[str, Any]:
    parcels = load_parcels()
    selected = [p for p in parcels if (not selected_ids) or (p["id"] in selected_ids)]

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

    # NOTE (v74): Project goal is always water saving.
    # We still allow "mevcut" for baseline display, but every optimization run
    # is solved with a water-saving objective plus a profit floor so farmers
    # still earn (even if modestly).
    objective = "water_saving"


    # --- v51 CLEAN: Simple 2-crop optimizer (always on unless options.simpleMode==False) ---
    simple_mode = bool(options.get('simpleMode', False))
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
        if season_source == 's2':
            # Conservative placeholder params for crops that may not exist in demo catalog.
            for k in SC2_PERENNIAL_N:
                _ensure_catalog_key(k, default_water=320.0, default_profit=9000.0)
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
            # This keeps recommendations realistic for farmers.
            loss_penalty = 0.0
            if p < 0:
                loss_penalty = 2000.0 + abs(p) * 0.25
            bonus = _parcel_suitability_bonus(crop, parcel)

            # Profit floor (per-da) to avoid "too low" income suggestions.
            # Floor is derived from the parcel's baseline profit per-da if available.
            # This keeps the objective water-saving while ensuring farmers still earn.
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

            # Water-saving always: prioritize low water, but reward profit and punish falling
            # below the profit floor.
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

            # Scenario-2 perennial rule: if the parcel's current crop is a perennial, KEEP IT (do not change crop).
            if season_source == 's2':
                curr_raw = current_crop_map.get(pid) or current_crop_map.get(str(pid))
                curr_key = _sc2_norm(curr_raw) if curr_raw else ''
                if curr_key in SC2_PERENNIAL_N:
                    rec = catalog.get(curr_key, {})
                    w1 = float(rec.get('waterPerDa', rec.get('water_per_da', 320.0)) or 0.0)
                    p1 = float(rec.get('profitPerDa', rec.get('profit_per_da', 9000.0)) or 0.0)
                    return [{
                        'name': curr_key,
                        'area_da': area_da,
                        'water_m3_da': w1, 'waterPerDa': w1,
                        'profit_tl_da': p1, 'profitPerDa': p1
                    }]
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
                rec_list.append({
                    "name": c["name"],
                    "area": area,
                    "waterPerDa": w_per,
                    "profitPerDa": prof_per,
                    "totalWater": tot,
                    "totalProfit": tprof,
                    "irrigation": irr_map.get(c["name"], {})
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
            "meta":{"mode":"simple_v51","note":"Max 2 crops; irrigation-adjusted water; fixed Senaryo-1 pool"}
        }

    algo = str(algorithm or "GA").upper()
    opts = options or {}
    season_source = str((opts.get("seasonSource") if isinstance(opts, dict) else None) or "both")
    two_season = bool(opts.get("twoSeason", True)) if isinstance(opts, dict) else True

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
            "generated_at": datetime.utcnow().isoformat() + "Z",
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
    return send_from_directory(DATA_DIR, filename)




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
        if enhanced_csv_dir.exists():
            for fp in sorted(enhanced_csv_dir.glob("*.csv"), key=lambda x: x.name.lower()):
                try:
                    available.append(str(fp.relative_to(DATA_DIR)))
                except Exception:
                    available.append(str(fp))
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
        "backend": {
            "data_source": "data/enhanced_dataset (CSV)",
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

@app.get("/api/timeseries")
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
        return jsonify({"status":"OK","years":years,"default":years[-1]})
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

@app.post("/api/optimize")
def api_optimize():
    try:
        payload = request.get_json(silent=True) or {}
        selected = payload.get("selectedParcelIds") or payload.get("selected") or []
        if isinstance(selected, str):
            selected = [s.strip() for s in selected.split(",") if s.strip()]
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
            selected = [s.strip() for s in selected.split(",") if s.strip()]
        elif not isinstance(selected, list):
            selected = list(selected) if selected else []

        scenario = str(payload.get("scenario", "recommended") or "recommended")
        water_budget_ratio = safe_float(payload.get("waterBudgetRatio", 1.0), 1.0)

        year_raw = payload.get("year", None)
        year_val = None if year_raw in (None, "", "none", "null") else safe_int(year_raw, 0)
        if year_val == 0:
            year_val = None

        repeats = int(payload.get("repeats", 10) or 10)
        repeats = max(1, min(30, repeats))  # keep API responsive

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

        results: Dict[str, Any] = {"status": "OK", "repeats": repeats, "algorithms": {}}
        # Baseline (Mevcut): observed parcel totals, used as reference column in charts
        if include_baseline:
            try:
                results["baseline"] = optimize(selected, "CURRENT", "mevcut", year=year_val, water_budget_ratio=water_budget_ratio, options=base_opts)
            except Exception as _e:
                results["baseline"] = {"status":"ERROR","message": str(_e)}
        started_at = time.perf_counter()
        # Total time budget for the whole benchmark request.
        # Default is intentionally generous so each algorithm gets at least one run.
        max_seconds = payload.get("maxSeconds", 90)
        try:
            max_seconds = float(max_seconds)
        except Exception:
            max_seconds = 90.0
        max_seconds = max(15.0, min(180.0, max_seconds))

        # lightweight defaults for benchmarking; kept small to avoid starving later algorithms.
        # user may override but we will clamp later per-run.
        speed_defaults = {"generations": 18, "popSize": 28, "cycles": 25, "foodSources": 22, "ants": 22, "iterations": 25}

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

        def _nadas_metrics(opt_out: Dict[str, Any]) -> Dict[str, float]:
            """Compute fallow (NADAS) ratios using area_da for primary/secondary seasons."""
            total_area = 0.0
            nadas_p = 0.0
            nadas_s = 0.0
            try:
                for pr in (opt_out.get("parcels") or []):
                    a = safe_float(pr.get("area_da", 0.0), 0.0)
                    total_area += a
                    rec = (((pr.get("result") or {}).get("recommended")) or [])
                    if len(rec) > 0 and str((rec[0] or {}).get("name") or "").strip().upper() == FALLOW:
                        nadas_p += safe_float((rec[0] or {}).get("area", a), a)
                    if len(rec) > 1 and str((rec[1] or {}).get("name") or "").strip().upper() == FALLOW:
                        nadas_s += safe_float((rec[1] or {}).get("area", a), a)
            except Exception:
                pass
            if total_area <= 0:
                return {"nadas_ratio": 0.0, "nadas_primary_ratio": 0.0, "nadas_secondary_ratio": 0.0, "planted_ratio": 1.0}
            # average across two seasons
            nadas_ratio = (nadas_p + nadas_s) / max(1e-9, (2.0 * total_area))
            return {
                "nadas_ratio": float(nadas_ratio),
                "nadas_primary_ratio": float(nadas_p / max(1e-9, total_area)),
                "nadas_secondary_ratio": float(nadas_s / max(1e-9, total_area)),
                "planted_ratio": float(1.0 - nadas_ratio),
            }

        def _crop_area_summary(opt_out: Dict[str, Any]) -> Dict[str, Any]:
            """Return top crop areas for primary/secondary seasons."""
            prim: Dict[str, float] = {}
            sec: Dict[str, float] = {}
            try:
                for pr in (opt_out.get("parcels") or []):
                    rec = (((pr.get("result") or {}).get("recommended")) or [])
                    if len(rec) > 0:
                        c = str((rec[0] or {}).get("name") or "")
                        a = safe_float((rec[0] or {}).get("area", 0.0), 0.0)
                        prim[c] = prim.get(c, 0.0) + a
                    if len(rec) > 1:
                        c = str((rec[1] or {}).get("name") or "")
                        a = safe_float((rec[1] or {}).get("area", 0.0), 0.0)
                        sec[c] = sec.get(c, 0.0) + a
            except Exception:
                pass

            def _top(d: Dict[str, float], k: int = 8) -> List[Dict[str, Any]]:
                items = [(c, float(a)) for c, a in d.items() if c]
                items.sort(key=lambda x: x[1], reverse=True)
                return [{"crop": c, "area_da": a} for c, a in items[:k]]

            return {"primary": _top(prim, 10), "secondary": _top(sec, 10)}

        # Distribute remaining time across algorithms so GA cannot starve ABC/ACO.
        for algo_idx, algo in enumerate(algos):
            runs = []
            sigs = []
            sigs_core = []
            nadas_ratios = []
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
                score_mode = "balanced"

            # Use the same seed stream across algorithms for a fair benchmark.
            algo_seed_offset = 0

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
                # clamp overly large hyper-parameters (keeps API responsive)
                opts["generations"] = int(max(10, min(80, int(opts.get("generations", speed_defaults["generations"])))))
                opts["popSize"] = int(max(10, min(120, int(opts.get("popSize", speed_defaults["popSize"])))))
                opts["cycles"] = int(max(10, min(120, int(opts.get("cycles", speed_defaults["cycles"])))))
                opts["foodSources"] = int(max(10, min(120, int(opts.get("foodSources", speed_defaults["foodSources"])))))
                opts["iterations"] = int(max(10, min(120, int(opts.get("iterations", speed_defaults["iterations"])))))
                opts["ants"] = int(max(10, min(120, int(opts.get("ants", speed_defaults["ants"])))))
                # keep risk off in benchmark unless user explicitly enables (it is expensive)
                if "riskMode" not in opts:
                    opts["riskMode"] = "none"
                if opts.get("riskMode") == "none":
                    opts["riskSamples"] = int(max(20, min(120, int(opts.get("riskSamples", 40)))))
                if base_seed is not None:
                    opts["seed"] = int(base_seed) + int(i)
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
                    nadas_ratios.append(_nadas_metrics(out).get('nadas_ratio', 0.0))

                    # choose the best run for showing the recommended pattern
                    if score_mode == "water_saving":
                        score = (-w_v) + (0.00005 * p_v)
                    elif score_mode == "max_profit":
                        score = p_v - (0.02 * w_v)
                    else:
                        score = e_v
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
                    return {"n": 0, "mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}
                if len(vals) == 1:
                    return {"n": 1, "mean": float(vals[0]), "std": 0.0, "min": float(vals[0]), "max": float(vals[0])}
                return {
                    "n": len(vals),
                    "mean": float(statistics.mean(vals)),
                    "std": float(statistics.pstdev(vals)),
                    "min": float(min(vals)),
                    "max": float(max(vals)),
                }

            prof = [r["total_profit_tl"] for r in runs]
            wat = [r["total_water_m3"] for r in runs]
            eff = [r["efficiency_tl_per_m3"] for r in runs]

            unique_patterns = len({s for s in sigs if s}) if sigs else 0

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
                            "primary": {"crop": str(c1.get("name") or ""), "area_da": safe_float(c1.get("area", 0.0), 0.0)},
                            "secondary": {"crop": str(c2.get("name") or ""), "area_da": safe_float(c2.get("area", 0.0), 0.0)},
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

            results["algorithms"][algo] = {
                "runs": len(runs),
                "errors": errors,
                "infeasible": infeasible,
                "unique_patterns": unique_patterns,
                "profit": _stats(prof),
                "water": _stats(wat),
                "efficiency": _stats(eff),
                "runtime_s": _stats(times),
                "nadas_ratio": _stats(nadas_ratios),
                "best": best_pack,
            }

        return jsonify(results)
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e), "where": "api_benchmark"}), 500


@app.post("/api/impact15y")
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
            selected = [s.strip() for s in selected.split(",") if s.strip()]
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


@app.post("/api/profit15y")
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
            selected = [s.strip() for s in selected.split(",") if s.strip()]
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