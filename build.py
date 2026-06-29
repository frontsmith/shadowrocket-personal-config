#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build Shadowrocket personal config by combining:
1) johnshall upstream lazy_group.conf
2) your personal proxy groups
3) your personal priority rules

Output:
  public/Front_Shadowrocket_personal.conf
"""

from __future__ import annotations

import datetime as _dt
import re
import sys
import urllib.request
from pathlib import Path

UPSTREAM_URL = "https://johnshall.github.io/Shadowrocket-ADBlock-Rules-Forever/lazy_group.conf"
ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public"
OUT = PUBLIC / "Front_Shadowrocket_personal.conf"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "front-shadowrocket-builder/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    return data.decode("utf-8", errors="replace")


def extract_section(text: str, name: str) -> str:
    m = re.search(rf"^\[{re.escape(name)}\]\s*$", text, flags=re.M)
    if not m:
        return ""
    start = m.end()
    m2 = re.search(r"^\[[^\]]+\]\s*$", text[start:], flags=re.M)
    end = start + m2.start() if m2 else len(text)
    return text[start:end].strip("\n")


def parse_overrides(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        result[k.strip()] = v.strip()
    return result


def patch_general(upstream_general: str, overrides: dict[str, str]) -> str:
    """Keep upstream General, but patch personal keys and remove update-url."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in upstream_general.splitlines():
        stripped = raw.strip()
        if not stripped:
            out.append(raw)
            continue
        if stripped.startswith("#"):
            # Drop the upstream update-url comment too if it is next to old update-url? keep comments generally.
            out.append(raw)
            continue
        if "=" not in raw:
            out.append(raw)
            continue
        key = raw.split("=", 1)[0].strip()
        if key == "update-url":
            out.append("# update-url disabled by personal build: do not overwrite this generated config with upstream original")
            seen.add(key)
            continue
        if key in overrides:
            out.append(f"{key} = {overrides[key]}")
            seen.add(key)
        else:
            out.append(raw)
    for key, value in overrides.items():
        if key not in seen:
            out.append(f"{key} = {value}")
    return "\n".join(out).strip() + "\n"


def normalize_rule_line(line: str) -> str | None:
    s = line.strip()
    if not s or s.startswith("#"):
        return None
    if s.upper().startswith("FINAL,"):
        return None

    # Most Shadowrocket rules put the policy at the last comma field.
    if "," not in s:
        return s
    head, policy = s.rsplit(",", 1)
    policy = policy.strip()

    exact_map = {
        "YOUTUBE": "YouTube",
        "TELEGRAM": "Telegram",
        "TWITTER": "Twitter",
        "谷歌服务": "Google",
        "微软服务": "Microsoft",
        "苹果服务": "Apple",
        "NETFLIX": "GlobalMedia",
        "DISNEY+": "GlobalMedia",
        "MAX": "GlobalMedia",
        "SPOTIFY": "GlobalMedia",
        "TIKTOK": "GlobalMedia",
        "FACEBOOK": "GlobalMedia",
        "PAYPAL": "GlobalMedia",
        "AMAZON": "GlobalMedia",
        "游戏平台": "GlobalMedia",
        "哔哩哔哩": "Domestic",
    }
    if policy in exact_map:
        policy = exact_map[policy]
    elif policy == "DIRECT":
        # Keep LAN separate; map mainland app/rules to Domestic so you can manually switch if needed.
        if "/Lan/" in s or "/Lan.list" in s:
            policy = "LAN"
        elif any(x in s for x in [
            "/China/", "/Baidu/", "/DouBan/", "/WeChat/", "/Sina/", "/Zhihu/",
            "/XiaoHongShu/", "/DouYin/", "/NetEaseMusic/", "/BiliBili/", "GEOIP,CN"
        ]):
            policy = "Domestic"
    elif policy == "PROXY":
        if "/GitHub/" in s:
            policy = "GitHub"
        elif "/Google/" in s:
            policy = "Google"
        else:
            policy = "PROXY"

    return f"{head},{policy}"


def build() -> None:
    PUBLIC.mkdir(exist_ok=True)
    upstream = fetch(UPSTREAM_URL)

    upstream_general = extract_section(upstream, "General")
    upstream_rule = extract_section(upstream, "Rule")
    upstream_host = extract_section(upstream, "Host")
    upstream_rewrite = extract_section(upstream, "URL Rewrite")

    proxy_group = read_text(ROOT / "personal" / "proxy_group.conf").strip() + "\n"
    rule_top = read_text(ROOT / "personal" / "rule_top.conf").strip() + "\n"
    overrides = parse_overrides(read_text(ROOT / "personal" / "general_overrides.ini"))
    general = patch_general(upstream_general, overrides)

    # Normalize upstream rule tail and remove exact duplicates already in rule_top.
    personal_rule_set = {x.strip() for x in rule_top.splitlines() if x.strip() and not x.strip().startswith("#")}
    normalized_tail: list[str] = []
    seen: set[str] = set()
    for raw in upstream_rule.splitlines():
        n = normalize_rule_line(raw)
        if not n:
            continue
        if n in personal_rule_set or n in seen:
            continue
        seen.add(n)
        normalized_tail.append(n)

    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    content = []
    content.append("# Shadowrocket Personal Config for Front")
    content.append(f"# Auto-built at: {now}")
    content.append(f"# Upstream: {UPSTREAM_URL}")
    content.append("# Personal rules: VPS-US first; long only 美国/日本; 198804.xyz direct; MITM disabled.")
    content.append("")

    content.append("[General]")
    content.append(general.strip())
    content.append("")

    content.append("[Proxy]")
    content.append("# 本配置不内置节点。请在 Shadowrocket 中添加两个订阅，并确保订阅名称完全为：VPS-US、long。")
    content.append("")

    content.append("[Proxy Group]")
    content.append(proxy_group.strip())
    content.append("")

    content.append("[Rule]")
    content.append(rule_top.strip())
    content.append("")
    content.append("# ==============================")
    content.append("# 上游规则尾部：来自 johnshall lazy_group.conf，经策略组名称自动映射")
    content.append("# ==============================")
    content.extend(normalized_tail)
    content.append("FINAL,Final")
    content.append("")

    if upstream_host:
        content.append("[Host]")
        content.append(upstream_host.strip())
        content.append("")

    if upstream_rewrite:
        content.append("[URL Rewrite]")
        content.append(upstream_rewrite.strip())
        content.append("")

    content.append("[MITM]")
    content.append("# 个人长期使用建议关闭 HTTPS 解密。")
    content.append("enable = false")
    content.append("hostname =")
    content.append("")

    OUT.write_text("\n".join(content), encoding="utf-8")
    (PUBLIC / "index.html").write_text(
        """<!doctype html><html><head><meta charset=\"utf-8\"><title>Shadowrocket Config</title></head><body><h1>Shadowrocket Personal Config</h1><p><a href=\"Front_Shadowrocket_personal.conf\">Front_Shadowrocket_personal.conf</a></p></body></html>""",
        encoding="utf-8",
    )
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    try:
        build()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise
