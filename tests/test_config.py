"""Tests for template safety and key routing intentions; not a phone runtime test."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build

SAMPLE_UPSTREAM = """# upstream sample
[General]
skip-proxy = localhost
dns-server = https://dns.alidns.com/dns-query
dns-direct-system = false
dns-direct-fallback-proxy = true
update-url = https://example.com/obsolete.conf
[Proxy Group]
OldGroup = select,PROXY
[Rule]
RULE-SET,https://example.com/old.list,PROXY
FINAL,PROXY
[Host]
*.apple.com = server:system
localhost = 127.0.0.1
[URL Rewrite]
^https?://www.g.cn https://www.google.com 302
[MITM]
hostname = *.example.org
"""


class TestBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = build.generate(SAMPLE_UPSTREAM, ROOT)

    def test_private_domain_rule_first(self):
        self.assertEqual(build.active_lines(build.section(self.config, "Rule"))[0],
                         "DOMAIN-SUFFIX,198804.xyz,NAS服务")

    def test_private_dns(self):
        gen = build.section(self.config, "General")
        self.assertIn("dns-direct-system = true", gen)
        self.assertIn("dns-direct-fallback-proxy = false", gen)
        hosts = build.section(self.config, "Host")
        self.assertIn("198804.xyz = server:system", hosts)
        self.assertIn("*.198804.xyz = server:system", hosts)

    def test_tailscale(self):
        rules = build.section(self.config, "Rule")
        self.assertIn("DOMAIN-SUFFIX,ts.net,TAILSCALE", rules)
        self.assertIn("IP-CIDR,100.64.0.0/10,TAILSCALE,no-resolve", rules)
        general = build.section(self.config, "General")
        tun_route = next(x for x in build.active_lines(general) if x.startswith("tun-excluded-routes ="))
        self.assertNotIn("100.64.0.0/10", tun_route)

    def test_proxy_group_defaults(self):
        groups = build.parse_groups(build.section(self.config, "Proxy Group"))
        self.assertNotIn("PROXY", groups)
        self.assertEqual(groups["AutoProxy"][0:2], ["fallback", "A-主用-vl-reality"])
        self.assertEqual(groups["NAS服务"][1], "DIRECT")
        self.assertEqual(groups["Final"][1], "AutoProxy")
        for name in ("AI", "YouTube", "Twitter", "GitHub", "Google"):
            self.assertEqual(groups[name][1], "AutoProxy")

    def test_personal_routing_set(self):
        rules = build.section(self.config, "Rule")
        self.assertIn("DOMAIN-SUFFIX,x.com,Twitter", rules)
        self.assertIn("DOMAIN-SUFFIX,chatgpt.com,AI", rules)
        self.assertIn("DOMAIN-SUFFIX,weixin.com,Domestic", rules)
        self.assertIn("GEOIP,CN,Domestic", rules)
        self.assertIn("FINAL,Final", rules)
        self.assertNotIn("QuantumultX", rules)
        self.assertNotIn("/Global/Global.list", rules)
        self.assertNotIn("iab0x00", rules)

    def test_mitm_off_and_upstream_update_url_removed(self):
        self.assertIn("enable = false", build.section(self.config, "MITM"))
        self.assertNotIn("hostname = *.example.org", self.config)
        self.assertNotIn("update-url =", self.config)

    def test_missing_upstream_fails(self):
        with self.assertRaises(ValueError):
            build.generate("[General]\ndns-server=system\n", ROOT)

    def test_undefined_policy_fails(self):
        groups = build.parse_groups((ROOT / "personal" / "proxy_group.conf").read_text(encoding="utf-8"))
        with self.assertRaises(ValueError):
            build.validate_rules("DOMAIN-SUFFIX,198804.xyz,NAS服务\nDOMAIN,x.com,NotAGroup", groups)


if __name__ == "__main__":
    unittest.main()
