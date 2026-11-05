#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build Front's Shadowrocket config (v2.0, standard library only).

Upstream supplies General/Host/URL Rewrite defaults, NOT upstream routing rules.
Personal files define policies, deterministic routing order, and host overrides.
A failed fetch or validation aborts before writing the publishable file.
"""

from __future__ import annotations

import datetime as dt
import re
import sys
import time
import urllib.request
from pathlib import Path

UPSTREAM_URL = "https://johnshall.github.io/Shadowrocket-ADBlock-Rules-Forever/lazy_group.conf"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "public" / "Front_Shadowrocket_personal.conf"
BUILTIN_POLICIES = {
    "DIRECT", "PROXY", "REJECT", "REJECT-DROP", "REJECT-NO-DROP", "REJECT-200",
    "REJECT-IMG", "REJECT-ARRAY", "REJECT-DICT", "REJECT-TINYGIF",
    "REJECT-VIDEO", "TAILSCALE",
}
SUBSCRIPTIONS = {"VPS-US", "long"}
GROUP_TYPES = {"fallback", "select", "url-test", "load-balance", "random"}


def section(source: str, name: str) -> str:
    pattern = re.compile(r"^\[" + re.escape(name) + r"\]\s*$", re.MULTILINE)
    match = pattern.search(source)
    if not match:
        return ""
    following = re.search(r"^\[[^\]\r\n]+\]\s*$", source[match.end():], re.MULTILINE)
    ending = match.end() + following.start() if following else len(source)
    return source[match.end():ending].strip("\r\n")


def active_lines(source: str) -> list[str]:
    return [s.strip() for s in source.splitlines() if s.strip() and not s.lstrip().startswith(("#", ";"))]


def read_kv(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in active_lines(path.read_text(encoding="utf-8")):
        if "=" not in line:
            raise ValueError(f"Bad setting in {path}: {line}")
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in result:
            raise ValueError(f"Duplicate/empty setting in {path}: {key}")
        result[key] = value.strip()
    return result


def merge_general(upstream_general: str, overrides: dict[str, str]) -> str:
    if not upstream_general or "dns-server" not in upstream_general:
        raise ValueError("Upstream [General] missing or contains no dns-server")
    output: list[str] = []
    applied: set[str] = set()
    for line in upstream_general.splitlines():
        s = line.strip()
        if not s or s.startswith(("#", ";")) or "=" not in line:
            output.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key == "update-url":
            output.append("# Removed upstream update-url to keep using personal Pages config")
        elif key in overrides:
            if key not in applied:
                output.append(f"{key} = {overrides[key]}")
                applied.add(key)
            # Ignore any duplicate upstream instances of the same key.
        else:
            output.append(line)
    for key, value in overrides.items():
        if key not in applied:
            output.append(f"{key} = {value}")
    return "\n".join(output).strip()


def merge_hosts(upstream_hosts: str, personal_hosts: str) -> str:
    replacements: dict[str, str] = {}
    for line in active_lines(personal_hosts):
        if "=" not in line:
            raise ValueError("Invalid personal [Host] line: " + line)
        key, value = [s.strip() for s in line.split("=", 1)]
        if not key or not value or key in replacements:
            raise ValueError("Duplicate/invalid personal [Host] key: " + key)
        replacements[key] = value
    result = []
    for line in upstream_hosts.splitlines():
        if "=" in line and not line.lstrip().startswith(("#", ";")):
            key = line.split("=", 1)[0].strip()
            if key in replacements:
                continue
        result.append(line)
    result.extend(f"{k} = {v}" for k, v in replacements.items())
    return "\n".join(result).strip()


def parse_groups(proxy_groups: str) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for line in active_lines(proxy_groups):
        if "=" not in line:
            raise ValueError("Invalid [Proxy Group] line: " + line)
        name, definition = [v.strip() for v in line.split("=", 1)]
        if name in groups or name in BUILTIN_POLICIES or not name:
            raise ValueError("Duplicate or reserved proxy group: " + name)
        values = [v.strip() for v in definition.split(",")]
        if len(values) < 2 or values[0] not in GROUP_TYPES:
            raise ValueError("Invalid proxy group definition: " + name)
        groups[name] = values
    if "AutoProxy" not in groups or "NAS服务" not in groups or "Final" not in groups:
        raise ValueError("Missing required AutoProxy/NAS服务/Final group")
    for name, entries in groups.items():
        for entry in entries[1:]:
            if "=" in entry:  # group options (url=, use=, policy-regex-filter=, ...)
                continue
            if entry not in groups and entry not in SUBSCRIPTIONS and entry not in BUILTIN_POLICIES:
                raise ValueError(f"Unknown group member: {name} -> {entry}")
    if "DIRECT" not in groups["NAS服务"][1:3]:
        raise ValueError("NAS服务 must be DIRECT first")
    if groups["Final"][1] != "AutoProxy":
        raise ValueError("Final must select AutoProxy first")
    if groups["AutoProxy"][0] != "fallback":
        raise ValueError("AutoProxy must use fallback")
    return groups


def validate_rules(rules: str, groups: dict[str, list[str]]) -> None:
    entries = active_lines(rules)
    if any(line.upper().startswith("FINAL,") for line in entries):
        raise ValueError("Do not put FINAL in personal rules; builder appends it")
    if any("/QuantumultX/" in line or "/Global/Global.list" in line for line in entries):
        raise ValueError("Found a foreign-format or oversized Global ruleset")
    seen: dict[tuple[str, str], str] = {}
    for line in entries:
        fields = [x.strip() for x in line.split(",")]
        if len(fields) < 3:
            raise ValueError("Malformed routing rule: " + line)
        kind, target, policy = fields[:3]
        if kind not in {"DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "IP-CIDR", "IP-CIDR6", "RULE-SET", "DOMAIN-SET", "GEOIP"}:
            raise ValueError("Unsupported rule type: " + kind)
        if policy not in groups and policy not in BUILTIN_POLICIES:
            raise ValueError(f"Undefined policy {policy}: {line}")
        if kind == "RULE-SET" and not target.startswith("https://"):
            raise ValueError("Rule-set must use HTTPS: " + line)
        signature = kind, target.casefold()
        if signature in seen and seen[signature] != policy:
            raise ValueError(f"Conflicting routing rule: {signature} -> {seen[signature]}, {policy}")
        seen[signature] = policy
    if entries[0] != "DOMAIN-SUFFIX,198804.xyz,NAS服务":
        raise ValueError("Private domain must be the first routing rule")
    if "DOMAIN-SUFFIX,ts.net,TAILSCALE" not in entries:
        raise ValueError("Missing Tailscale MagicDNS routing")
    if "IP-CIDR,100.64.0.0/10,TAILSCALE,no-resolve" not in entries:
        raise ValueError("Missing Tailscale IP routing")
    if "GEOIP,CN,Domestic" not in entries:
        raise ValueError("Missing China geoip fallback")


def generate(upstream: str, root: Path = ROOT) -> str:
    upstream_general = section(upstream, "General")
    if not upstream_general or not section(upstream, "Rule"):
        raise ValueError("Upstream is missing [General] or [Rule] - reject incomplete downloads")
    overrides = read_kv(root / "personal" / "general_overrides.ini")
    if overrides.get("dns-direct-system") != "true" or overrides.get("dns-direct-fallback-proxy") != "false":
        raise ValueError("DIRECT DNS safeguards missing")
    excluded = overrides.get("tun-excluded-routes", "")
    if "100.64.0.0/10" in excluded:
        raise ValueError("Tailscale 100.64.0.0/10 must not be TUN excluded")
    groups_text = (root / "personal" / "proxy_group.conf").read_text(encoding="utf-8").strip()
    rules_text = (root / "personal" / "rule_top.conf").read_text(encoding="utf-8").strip()
    hosts_text = (root / "personal" / "host_overrides.conf").read_text(encoding="utf-8")
    groups = parse_groups(groups_text)
    validate_rules(rules_text, groups)
    general = merge_general(upstream_general, overrides)
    hosts = merge_hosts(section(upstream, "Host"), hosts_text)
    rewrite = section(upstream, "URL Rewrite")
    built = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    chunks = [
        "# Front Shadowrocket Personal v2.0",
        f"# Generated: {built}",
        f"# General, Host and URL Rewrite upstream: {UPSTREAM_URL}",
        "# All routing rules and policy groups are personal; built-in TAILSCALE is intentional.",
        "", "[General]", general,
        "", "[Proxy]", "# Nodes are provided by VPS-US and long subscriptions installed on the phone.",
        "", "[Proxy Group]", groups_text,
        "", "[Rule]", rules_text, "FINAL,Final",
        "", "[Host]", hosts,
    ]
    if rewrite:
        chunks.extend(["", "[URL Rewrite]", rewrite])
    chunks.extend(["", "[MITM]", "enable = false", "hostname =", ""])
    result = "\n".join(chunks)
    # Check the effective assembled configuration as well.
    if result.count("[Rule]") != 1 or active_lines(section(result, "Rule")).count("FINAL,Final") != 1:
        raise ValueError("Duplicated rule section or FINAL")
    if "198804.xyz = server:system" not in result or "*.198804.xyz = server:system" not in result:
        raise ValueError("Private host DNS overrides missing")
    return result


def fetch_upstream(url: str = UPSTREAM_URL) -> str:
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "front-shadowrocket-builder/2.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            return data.decode("utf-8")
        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
    raise AssertionError("unreachable")


def main() -> None:
    source = fetch_upstream()
    built = generate(source, ROOT)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # Do not touch published output before every validation has succeeded.
    OUT.write_text(built, encoding="utf-8")
    (OUT.parent / "index.html").write_text(
        '<!doctype html><html><meta charset="utf-8"><title>Front Shadowrocket</title>'
        '<h1>Front Shadowrocket</h1><p><a href="Front_Shadowrocket_personal.conf">'
        'Personal configuration</a></p></html>\n', encoding="utf-8"
    )
    print("[PASS] Generated and validated:", OUT)
    print("[PASS] Sections: General / Proxy / Proxy Group / Rule / Host / MITM")
    print("[PASS] 198804.xyz DIRECT-by-default; system DNS; Tailscale kept")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("[FAIL] No new configuration published: " + str(exc), file=sys.stderr)
        sys.exit(1)
