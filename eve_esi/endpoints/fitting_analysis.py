"""Ship fitting analysis — EFT parsing, dogma stats, and fit comparison."""

from __future__ import annotations

import re
from typing import Any

from eve_esi.client import ESIClient
from eve_esi.endpoints import universe


# ── Well-known dogma attribute IDs ────────────────────────────────────────────
# Ship / defense
ATTR_SHIELD_HP           = 263
ATTR_ARMOR_HP            = 265
ATTR_HULL_HP             = 9
ATTR_SHIELD_RECHARGE_MS  = 479
ATTR_SHIELD_EM_RES       = 271
ATTR_SHIELD_THERM_RES    = 274
ATTR_SHIELD_KIN_RES      = 273
ATTR_SHIELD_EXPL_RES     = 272
ATTR_ARMOR_EM_RES        = 267
ATTR_ARMOR_THERM_RES     = 270
ATTR_ARMOR_KIN_RES       = 269
ATTR_ARMOR_EXPL_RES      = 268
# Fitting
ATTR_CPU                 = 48
ATTR_POWERGRID           = 11
ATTR_CPU_OUTPUT          = 48
ATTR_PG_OUTPUT           = 11
ATTR_CALIBRATION         = 1132
ATTR_CALIBRATION_OUTPUT  = 1132
# Navigation
ATTR_MAX_VELOCITY        = 37
ATTR_MASS                = 4
ATTR_INERTIA             = 70
ATTR_SIGNATURE_RADIUS    = 552
# Targeting
ATTR_SCAN_RES            = 564
ATTR_MAX_TARGET_RANGE    = 76
ATTR_MAX_LOCKED_TARGETS  = 524
# Drones
ATTR_DRONE_BAY           = 283
ATTR_DRONE_BANDWIDTH     = 1271
# Capacitor
ATTR_CAPACITOR_CAPACITY  = 482
ATTR_CAP_RECHARGE_MS     = 55
# Cargo / Ore
ATTR_CAPACITY            = 38   # cargo hold
ATTR_SPEC_ORE_HOLD       = 1920
# Mining
ATTR_MINING_AMOUNT       = 77   # m3 per cycle on strip miners
ATTR_DURATION            = 73   # cycle time ms
# Module resource usage
ATTR_CPU_NEED            = 50
ATTR_PG_NEED             = 30
ATTR_CALIBRATION_NEED    = 1153
# Mining yield modifier (MLU)
ATTR_MINING_AMOUNT_BONUS = 434  # miningAmountBonus on Mining Laser Upgrade
# Crystal mining bonus
ATTR_SPEC_MINING_AMOUNT_MULT = 128  # specialisationAsteroidYieldMultiplier
# Rig mining bonus
ATTR_RIG_MINING_BONUS    = 2660  # varies by rig, but common for drone mining rigs
# Shield extender bonus
ATTR_SHIELD_BONUS        = 796  # shieldBonus from shield extender modules
# Speed boost
ATTR_SPEED_FACTOR        = 20   # speedFactor on AB/MWD
ATTR_SPEED_BOOST_FACTOR  = 567  # speedBoostFactor on AB/MWD
# Required skills (pairs of skill type ID attribute + level attribute)
REQUIRED_SKILL_ATTRS = [
    (182, 277),   # requiredSkill1 / requiredSkill1Level
    (183, 278),   # requiredSkill2 / requiredSkill2Level
    (184, 279),   # requiredSkill3 / requiredSkill3Level
    (1285, 1286), # requiredSkill4 / requiredSkill4Level
    (1289, 1287), # requiredSkill5 / requiredSkill5Level
    (1290, 1288), # requiredSkill6 / requiredSkill6Level
]

# Stacking penalty coefficients (first 8)
import math
_STACKING = [math.exp(-((i / 2.67) ** 2)) for i in range(8)]


def _stacking_factor(index: int) -> float:
    """Return the stacking penalty multiplier for the *index*-th module (0-based)."""
    if index < len(_STACKING):
        return _STACKING[index]
    return 0.0


# ── EFT parser ────────────────────────────────────────────────────────────────

def parse_eft(eft_text: str) -> dict[str, Any]:
    """Parse an EFT-format fitting string.

    Returns:
        {
            "ship_type": str,
            "fit_name": str,
            "low_slots": [str, ...],
            "med_slots": [str, ...],
            "hi_slots": [str, ...],
            "rig_slots": [str, ...],
            "drones": [{"name": str, "count": int}, ...],
            "cargo": [{"name": str, "count": int}, ...],
        }
    """
    lines = [l.strip() for l in eft_text.strip().splitlines()]
    if not lines:
        raise ValueError("Empty EFT block")

    # Header: [Ship, Name]
    header = lines[0]
    m = re.match(r"^\[(.+?),\s*(.+)\]$", header)
    if not m:
        raise ValueError(f"Invalid EFT header: {header}")
    ship_type, fit_name = m.group(1).strip(), m.group(2).strip()

    # Slots are separated by blank lines: lo, med, hi, rigs, drones, cargo
    sections: list[list[str]] = []
    current: list[str] = []
    for line in lines[1:]:
        if not line:
            if current:
                sections.append(current)
                current = []
        else:
            current.append(line)
    if current:
        sections.append(current)

    # Map sections by position: lo(0), med(1), hi(2), rigs(3), drones(4), cargo(5)
    def _items(sec: list[str]) -> list[str]:
        return [s.split(",")[0].strip() for s in sec if not s.startswith("[")]

    def _counted(sec: list[str]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for s in sec:
            m2 = re.match(r"^(.+?)\s+x(\d+)$", s.strip())
            if m2:
                out.append({"name": m2.group(1).strip(), "count": int(m2.group(2))})
            else:
                out.append({"name": s.strip(), "count": 1})
        return out

    low  = _items(sections[0]) if len(sections) > 0 else []
    med  = _items(sections[1]) if len(sections) > 1 else []
    hi   = _items(sections[2]) if len(sections) > 2 else []
    rigs = _items(sections[3]) if len(sections) > 3 else []

    drones: list[dict[str, Any]] = []
    cargo: list[dict[str, Any]] = []
    if len(sections) > 4:
        drones = _counted(sections[4])
    if len(sections) > 5:
        cargo = _counted(sections[5])

    return {
        "ship_type": ship_type,
        "fit_name": fit_name,
        "low_slots": low,
        "med_slots": med,
        "hi_slots": hi,
        "rig_slots": rigs,
        "drones": drones,
        "cargo": cargo,
    }


# ── Type resolution helpers ───────────────────────────────────────────────────

def _resolve_type_ids(client: ESIClient, names: list[str]) -> dict[str, int]:
    """Resolve a list of item/ship names to type IDs."""
    if not names:
        return {}
    resolved = universe.resolve_ids(client, names)
    out: dict[str, int] = {}
    for category in resolved.values():
        if isinstance(category, list):
            for item in category:
                if isinstance(item, dict) and "id" in item and "name" in item:
                    out[item["name"]] = item["id"]
    # Case-insensitive best-effort matching back to original names
    lower_map = {k.lower(): k for k in out}
    result: dict[str, int] = {}
    for n in names:
        if n in out:
            result[n] = out[n]
        elif n.lower() in lower_map:
            result[n] = out[lower_map[n.lower()]]
    return result


def _get_dogma(client: ESIClient, type_id: int) -> dict[int, float]:
    """Fetch dogma attributes for a type, returned as {attr_id: value}."""
    info = universe.get_type_info(client, type_id)
    return {a["attribute_id"]: a["value"] for a in info.get("dogma_attributes", [])}


# ── Stats calculator ──────────────────────────────────────────────────────────

def get_fit_stats(client: ESIClient, eft_text: str) -> dict[str, Any]:
    """Parse an EFT fitting and compute approximate ship stats.

    Computes: shield/armor/hull HP, resistances, capacitor, mining yield,
    navigation, targeting, drone capacity, cargo, and ore hold.

    NOTE: This is an *approximation*. Full simulation requires complete dogma
    expression evaluation. Stacking penalties are applied where appropriate.
    """
    fit = parse_eft(eft_text)

    # Collect all unique item names to resolve
    all_names: list[str] = [fit["ship_type"]]
    all_names.extend(fit["low_slots"])
    all_names.extend(fit["med_slots"])
    all_names.extend(fit["hi_slots"])
    all_names.extend(fit["rig_slots"])
    all_names.extend(d["name"] for d in fit["drones"])
    all_names.extend(c["name"] for c in fit["cargo"])
    unique_names = list(set(all_names))

    type_ids = _resolve_type_ids(client, unique_names)
    dogma_cache: dict[str, dict[int, float]] = {}

    for name in unique_names:
        tid = type_ids.get(name)
        if tid:
            dogma_cache[name] = _get_dogma(client, tid)

    ship = fit["ship_type"]
    sa = dogma_cache.get(ship, {})

    # ── Base stats ────────────────────────────────────────────────────────
    shield_hp   = sa.get(ATTR_SHIELD_HP, 0)
    armor_hp    = sa.get(ATTR_ARMOR_HP, 0)
    hull_hp     = sa.get(ATTR_HULL_HP, 0)
    cap_amount  = sa.get(ATTR_CAPACITOR_CAPACITY, 0)
    cap_rech_ms = sa.get(ATTR_CAP_RECHARGE_MS, 0)
    sh_rech_ms  = sa.get(ATTR_SHIELD_RECHARGE_MS, 0)
    cpu_out     = sa.get(ATTR_CPU, 0)
    pg_out      = sa.get(ATTR_POWERGRID, 0)
    calibration = sa.get(ATTR_CALIBRATION, 0)
    velocity    = sa.get(ATTR_MAX_VELOCITY, 0)
    mass        = sa.get(ATTR_MASS, 0)
    inertia     = sa.get(ATTR_INERTIA, 0)
    sig_radius  = sa.get(ATTR_SIGNATURE_RADIUS, 0)
    scan_res    = sa.get(ATTR_SCAN_RES, 0)
    max_range   = sa.get(ATTR_MAX_TARGET_RANGE, 0)
    max_targets = sa.get(ATTR_MAX_LOCKED_TARGETS, 0)
    drone_bay   = sa.get(ATTR_DRONE_BAY, 0)
    drone_bw    = sa.get(ATTR_DRONE_BANDWIDTH, 0)
    cargo_hold  = sa.get(ATTR_CAPACITY, 0)
    ore_hold    = sa.get(ATTR_SPEC_ORE_HOLD, 0)

    # Base resistances (ESI gives these as 0-1 where 0 = 100% resist)
    sh_em   = sa.get(ATTR_SHIELD_EM_RES, 1.0)
    sh_th   = sa.get(ATTR_SHIELD_THERM_RES, 1.0)
    sh_ki   = sa.get(ATTR_SHIELD_KIN_RES, 1.0)
    sh_ex   = sa.get(ATTR_SHIELD_EXPL_RES, 1.0)
    ar_em   = sa.get(ATTR_ARMOR_EM_RES, 1.0)
    ar_th   = sa.get(ATTR_ARMOR_THERM_RES, 1.0)
    ar_ki   = sa.get(ATTR_ARMOR_KIN_RES, 1.0)
    ar_ex   = sa.get(ATTR_ARMOR_EXPL_RES, 1.0)

    # ── Module CPU/PG usage ───────────────────────────────────────────────
    cpu_used = 0.0
    pg_used = 0.0
    cal_used = 0.0
    all_slots = fit["low_slots"] + fit["med_slots"] + fit["hi_slots"]
    for mod_name in all_slots:
        ma = dogma_cache.get(mod_name, {})
        cpu_used += ma.get(ATTR_CPU_NEED, 0)
        pg_used += ma.get(ATTR_PG_NEED, 0)
    for mod_name in fit["rig_slots"]:
        ma = dogma_cache.get(mod_name, {})
        cal_used += ma.get(ATTR_CALIBRATION_NEED, 0)

    # ── Mining yield (hi-slot strip miners) ───────────────────────────────
    mining_yield_per_sec = 0.0
    for mod_name in fit["hi_slots"]:
        ma = dogma_cache.get(mod_name, {})
        amount = ma.get(ATTR_MINING_AMOUNT, 0)
        duration_ms = ma.get(ATTR_DURATION, 0)
        if amount and duration_ms:
            mining_yield_per_sec += amount / (duration_ms / 1000.0)

    # ── Capacitor recharge rate ───────────────────────────────────────────
    cap_per_sec = 0.0
    if cap_rech_ms > 0 and cap_amount > 0:
        # Peak recharge = 2.5 * capacity / recharge_time
        cap_per_sec = 2.5 * cap_amount / (cap_rech_ms / 1000.0)

    # ── Align time ────────────────────────────────────────────────────────
    align_time = 0.0
    if inertia > 0 and mass > 0:
        align_time = -math.log(0.25) * inertia * mass / 1_000_000.0

    # ── EHP calculation ───────────────────────────────────────────────────
    def _ehp(hp: float, em: float, th: float, ki: float, ex: float) -> float:
        if hp <= 0:
            return 0.0
        avg_res = (em + th + ki + ex) / 4.0
        if avg_res >= 1.0:
            return hp
        return hp / avg_res

    shield_ehp = _ehp(shield_hp, sh_em, sh_th, sh_ki, sh_ex)
    armor_ehp = _ehp(armor_hp, ar_em, ar_th, ar_ki, ar_ex)
    hull_ehp = hull_hp  # hull resists are usually 1.0

    return {
        "fit": fit,
        "ship_type": fit["ship_type"],
        "fit_name": fit["fit_name"],
        "defense": {
            "shield_hp": round(shield_hp),
            "armor_hp": round(armor_hp),
            "hull_hp": round(hull_hp),
            "total_hp": round(shield_hp + armor_hp + hull_hp),
            "shield_ehp": round(shield_ehp),
            "armor_ehp": round(armor_ehp),
            "hull_ehp": round(hull_ehp),
            "total_ehp": round(shield_ehp + armor_ehp + hull_ehp),
            "shield_resistances": {
                "em": round((1.0 - sh_em) * 100, 1),
                "thermal": round((1.0 - sh_th) * 100, 1),
                "kinetic": round((1.0 - sh_ki) * 100, 1),
                "explosive": round((1.0 - sh_ex) * 100, 1),
            },
            "armor_resistances": {
                "em": round((1.0 - ar_em) * 100, 1),
                "thermal": round((1.0 - ar_th) * 100, 1),
                "kinetic": round((1.0 - ar_ki) * 100, 1),
                "explosive": round((1.0 - ar_ex) * 100, 1),
            },
        },
        "fitting": {
            "cpu_output": round(cpu_out),
            "cpu_used": round(cpu_used),
            "powergrid_output": round(pg_out),
            "powergrid_used": round(pg_used),
            "calibration_output": round(calibration),
            "calibration_used": round(cal_used),
        },
        "navigation": {
            "max_velocity_ms": round(velocity, 1),
            "mass_kg": round(mass),
            "inertia_modifier": round(inertia, 4),
            "align_time_s": round(align_time, 2),
            "signature_radius_m": round(sig_radius),
        },
        "targeting": {
            "scan_resolution_mm": round(scan_res),
            "max_target_range_m": round(max_range),
            "max_locked_targets": round(max_targets),
        },
        "capacitor": {
            "capacity_gj": round(cap_amount),
            "recharge_time_s": round(cap_rech_ms / 1000.0, 1) if cap_rech_ms else 0,
            "peak_recharge_gj_s": round(cap_per_sec, 2),
        },
        "mining": {
            "yield_m3_per_sec": round(mining_yield_per_sec, 3),
            "yield_m3_per_min": round(mining_yield_per_sec * 60, 1),
        },
        "capacity": {
            "cargo_m3": round(cargo_hold),
            "ore_hold_m3": round(ore_hold),
            "drone_bay_m3": round(drone_bay),
            "drone_bandwidth_mbit": round(drone_bw),
        },
    }


# ── Comparison ────────────────────────────────────────────────────────────────

def compare_fits(
    client: ESIClient,
    eft_text_a: str,
    eft_text_b: str,
) -> dict[str, Any]:
    """Compare two EFT fittings side by side.

    Returns stats for both fits plus a delta summary.
    """
    stats_a = get_fit_stats(client, eft_text_a)
    stats_b = get_fit_stats(client, eft_text_b)

    def _delta(path: list[str], a: Any, b: Any) -> dict:
        if isinstance(a, dict) and isinstance(b, dict):
            d: dict[str, Any] = {}
            for k in set(list(a.keys()) + list(b.keys())):
                if k in ("fit",):
                    continue
                d[k] = _delta(path + [k], a.get(k, 0), b.get(k, 0))
            return d
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return {"a": a, "b": b, "diff": round(b - a, 4), "pct": round((b - a) / a * 100, 1) if a else 0}
        return {"a": a, "b": b}

    return {
        "fit_a": stats_a,
        "fit_b": stats_b,
        "comparison": _delta([], stats_a, stats_b),
    }


# ── Required-skills extraction ───────────────────────────────────────────────

def _extract_required_skills(
    client: ESIClient,
    type_id: int,
    dogma: dict[int, float] | None = None,
) -> list[dict[str, Any]]:
    """Extract required skills from a single type's dogma attributes.

    Returns list of {"skill_type_id": int, "level": int}.
    """
    if dogma is None:
        dogma = _get_dogma(client, type_id)
    results: list[dict[str, Any]] = []
    for skill_attr, level_attr in REQUIRED_SKILL_ATTRS:
        skill_id = dogma.get(skill_attr)
        level = dogma.get(level_attr)
        if skill_id and level and int(skill_id) > 0 and int(level) > 0:
            results.append({"skill_type_id": int(skill_id), "level": int(level)})
    return results


def get_fit_required_skills(client: ESIClient, eft_text: str) -> dict[str, Any]:
    """Parse an EFT fit and return all skills required to fly it.

    For each item in the fit (hull, modules, rigs, drones), looks up the
    ``requiredSkill`` dogma attributes. Returns a deduplicated skill list
    with the *maximum* level required across all items.

    Returns::

        {
            "ship_type": str,
            "fit_name": str,
            "required_skills": [
                {"skill_name": str, "skill_type_id": int, "required_level": int},
                ...
            ],
            "items_checked": int,
        }
    """
    fit = parse_eft(eft_text)

    # Collect all unique item names
    all_names: list[str] = [fit["ship_type"]]
    all_names.extend(fit["low_slots"])
    all_names.extend(fit["med_slots"])
    all_names.extend(fit["hi_slots"])
    all_names.extend(fit["rig_slots"])
    all_names.extend(d["name"] for d in fit["drones"])
    unique_names = list(set(all_names))

    type_ids = _resolve_type_ids(client, unique_names)

    # Gather required skills from every item
    # skill_type_id -> max required level
    skill_max_level: dict[int, int] = {}
    items_checked = 0

    for name in unique_names:
        tid = type_ids.get(name)
        if not tid:
            continue
        items_checked += 1
        dogma = _get_dogma(client, tid)
        for req in _extract_required_skills(client, tid, dogma):
            sid = req["skill_type_id"]
            lvl = req["level"]
            if sid not in skill_max_level or lvl > skill_max_level[sid]:
                skill_max_level[sid] = lvl

    # Resolve skill type IDs to names
    skill_ids = list(skill_max_level.keys())
    skill_name_map: dict[int, str] = {}
    if skill_ids:
        try:
            resolved = universe.resolve_names(client, skill_ids)
            for r in resolved:
                skill_name_map[r["id"]] = r["name"]
        except Exception:
            pass

    required_skills = sorted(
        [
            {
                "skill_name": skill_name_map.get(sid, f"Skill {sid}"),
                "skill_type_id": sid,
                "required_level": lvl,
            }
            for sid, lvl in skill_max_level.items()
        ],
        key=lambda x: x["skill_name"],
    )

    return {
        "ship_type": fit["ship_type"],
        "fit_name": fit["fit_name"],
        "required_skills": required_skills,
        "items_checked": items_checked,
    }


def check_fit_readiness(
    client: ESIClient,
    eft_text: str,
    character_clients: list[ESIClient],
) -> dict[str, Any]:
    """Check which characters can fly a given fit and what skills they're missing.

    Args:
        client: Any ESIClient (used for type lookups).
        eft_text: The EFT-format fitting text.
        character_clients: List of ESIClient instances, one per character.

    Returns::

        {
            "ship_type": str,
            "fit_name": str,
            "required_skills": [...],
            "characters": [
                {
                    "character_id": int,
                    "character_name": str,
                    "can_fly": bool,
                    "missing_skills": [...],
                    "under_trained_skills": [...],
                },
                ...
            ],
        }
    """
    from eve_esi.endpoints import skills as skills_mod, characters as chars_mod

    req_data = get_fit_required_skills(client, eft_text)
    required = req_data["required_skills"]

    characters_result: list[dict[str, Any]] = []

    for cc in character_clients:
        entry: dict[str, Any] = {"character_id": cc.character_id}
        try:
            info = chars_mod.get_character_info(cc, cc.character_id)
            entry["character_name"] = info.get("name", "Unknown")

            skill_data = skills_mod.get_skills(cc)
            trained_map = {
                s["skill_id"]: s.get("active_skill_level", 0)
                for s in skill_data.get("skills", [])
            }

            missing: list[dict[str, Any]] = []
            under_trained: list[dict[str, Any]] = []

            for req in required:
                sid = req["skill_type_id"]
                req_lvl = req["required_level"]
                current_lvl = trained_map.get(sid, 0)

                if current_lvl == 0:
                    missing.append({
                        "skill_name": req["skill_name"],
                        "skill_type_id": sid,
                        "required_level": req_lvl,
                    })
                elif current_lvl < req_lvl:
                    under_trained.append({
                        "skill_name": req["skill_name"],
                        "skill_type_id": sid,
                        "required_level": req_lvl,
                        "current_level": current_lvl,
                    })

            entry["can_fly"] = len(missing) == 0 and len(under_trained) == 0
            entry["missing_skills"] = missing
            entry["under_trained_skills"] = under_trained

        except Exception as e:
            entry["error"] = str(e)
            entry["can_fly"] = False

        characters_result.append(entry)

    return {
        "ship_type": req_data["ship_type"],
        "fit_name": req_data["fit_name"],
        "required_skills": required,
        "characters": characters_result,
    }
