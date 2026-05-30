#!/usr/bin/env python3
"""
fetch_services.py — Fetch product data from Arena4Club API → data/services.json

Usage:
  ARENA_TOKEN=<bearer_token> python3 fetch_services.py
  ARENA_TOKEN=<token> ARENA_API=https://arena4club-api.arenabilliard.com python3 fetch_services.py

The script calls:
  GET /api/app/product-groups/products-by-group   (primary: groups + nested products)
  GET /api/app/products/search                     (fallback flat list)

Output: data/services.json (same directory as this script)
"""

import os
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────
TOKEN = os.environ.get("ARENA_TOKEN", "")
API_BASE = os.environ.get("ARENA_API", "https://dev-arena4club-api.arenabilliard.com").rstrip("/")
OUT_FILE = Path(__file__).parent / "data" / "services.json"

# Branch config — update when real branch IDs are known
BRANCHES_CONFIG = [
    {"id": 1, "name": "Arena Q1", "address": "Quận 1, TP.HCM"},
    {"id": 2, "name": "Arena Q3", "address": "Quận 3, TP.HCM"},
]

# ── Helpers ───────────────────────────────────────────────────────────────
def api_get(path, params=None):
    if not TOKEN:
        raise SystemExit("❌ ARENA_TOKEN env var is required.\nUsage: ARENA_TOKEN=<token> python3 fetch_services.py")

    url = API_BASE + path
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url += "?" + qs

    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"❌ HTTP {e.code} {e.reason} for {url}\n{body[:400]}")
    except urllib.error.URLError as e:
        raise SystemExit(f"❌ Network error: {e.reason}")


def normalize_price(val):
    """Ensure price is an int."""
    try:
        return int(float(val or 0))
    except (TypeError, ValueError):
        return 0


# Icon map based on group name keywords
GROUP_ICONS = {
    "bàn": "🎱", "thuê bàn": "🎱", "billiard": "🎱", "pool": "🎱", "carom": "🎱",
    "uống": "🥤", "nước": "🥤", "drink": "🥤", "beverage": "🥤",
    "ăn": "🍟", "food": "🍟", "snack": "🍟", "đồ ăn": "🍟",
    "dụng cụ": "🏆", "thiết bị": "🏆", "equipment": "🏆", "cơ": "🏆",
    "vip": "⭐", "combo": "🎁",
}

def icon_for_group(name: str) -> str:
    lower = name.lower()
    for keyword, icon in GROUP_ICONS.items():
        if keyword in lower:
            return icon
    return "📋"


# ── Fetch Logic ───────────────────────────────────────────────────────────
def fetch_groups_with_products(branch_id=None):
    """
    Primary: GET /api/app/product-groups/products-by-group
    Returns list of groups, each with a products array.
    """
    params = {"branchId": branch_id} if branch_id else {}
    try:
        resp = api_get("/api/app/product-groups/products-by-group", params)
        # API may return { data: [...] } or just [...]
        if isinstance(resp, list):
            return resp
        if isinstance(resp, dict):
            return resp.get("data") or resp.get("groups") or []
        return []
    except SystemExit:
        return None  # Signal caller to try fallback


def fetch_flat_products(branch_id=None):
    """
    Fallback: GET /api/app/products/search
    Returns flat list of products.
    """
    body_params = {"page": 0, "size": 200}
    if branch_id:
        body_params["branchId"] = branch_id

    # This endpoint may be POST with body
    url = API_BASE + "/api/app/products/search"
    body = json.dumps(body_params).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, list):
                return data
            return data.get("data") or data.get("products") or []
    except Exception:
        return []


def groups_from_raw(raw_groups):
    """Normalize raw API groups into our schema."""
    result = []
    for g in raw_groups:
        products = g.get("products") or g.get("items") or []
        services = []
        for p in products:
            if not p.get("inMenu", True):
                continue
            services.append({
                "id": p.get("id"),
                "name": p.get("name", ""),
                "price": normalize_price(p.get("price")),
                "unit": p.get("unitName") or p.get("unit") or "lần",
                "description": p.get("description") or "",
            })
        if not services:
            continue
        name = g.get("name", "")
        result.append({
            "id": g.get("id"),
            "name": name,
            "icon": icon_for_group(name),
            "services": services,
        })
    return result


def groups_from_flat(flat_products):
    """Build groups from a flat product list using productGroupName."""
    groups_map = {}
    for p in flat_products:
        if not p.get("inMenu", True):
            continue
        gid = p.get("productGroupId") or 0
        gname = p.get("productGroupName") or "Khác"
        if gid not in groups_map:
            groups_map[gid] = {"id": gid, "name": gname, "services": []}
        groups_map[gid]["services"].append({
            "id": p.get("id"),
            "name": p.get("name", ""),
            "price": normalize_price(p.get("price")),
            "unit": p.get("unitName") or p.get("unit") or "lần",
            "description": p.get("description") or "",
        })

    result = []
    for g in groups_map.values():
        if g["services"]:
            g["icon"] = icon_for_group(g["name"])
            result.append(g)
    return result


# ── Main ──────────────────────────────────────────────────────────────────
def main():
    print(f"📡 Arena Services Fetcher")
    print(f"   API: {API_BASE}")
    print()

    branches_out = []

    for bc in BRANCHES_CONFIG:
        bid = bc["id"]
        bname = bc["name"]
        print(f"  Fetching {bname} (branch {bid})…", end=" ", flush=True)

        # Try primary endpoint
        raw = fetch_groups_with_products(branch_id=bid)
        if raw is None or len(raw) == 0:
            # Fallback to flat products
            flat = fetch_flat_products(branch_id=bid)
            service_groups = groups_from_flat(flat)
            source = "flat"
        else:
            service_groups = groups_from_raw(raw)
            source = "groups"

        total_services = sum(len(g["services"]) for g in service_groups)
        print(f"✓  {len(service_groups)} groups, {total_services} services (via {source})")

        branches_out.append({
            "id": bid,
            "name": bname,
            "address": bc.get("address", ""),
            "tables": [],  # Populated from table management API when available
            "serviceGroups": service_groups,
        })

    out = {
        "meta": {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "generatedBy": "fetch_services.py",
            "apiBase": API_BASE,
        },
        "branches": branches_out,
    }

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    total = sum(
        sum(len(g["services"]) for g in b["serviceGroups"])
        for b in branches_out
    )
    print()
    print(f"✅ Saved to {OUT_FILE}")
    print(f"   {len(branches_out)} branches · {total} services total")


if __name__ == "__main__":
    main()
