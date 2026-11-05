# Front Shadowrocket Personal Config v2.0

A minimal, reproducible Shadowrocket configuration for `VPS-US`, `long`, and private NAS services.

## Inputs and output

| Path | Role |
|---|---|
| `personal/general_overrides.ini` | Overrides for upstream `[General]` |
| `personal/host_overrides.conf` | System DNS for `198804.xyz` and its subdomains |
| `personal/proxy_group.conf` | AutoProxy priority / selectable strategy groups |
| `personal/rule_top.conf` | All personal routing rules, with no broad upstream rule tail |
| `build.py` | Pulls upstream General/Host/URL Rewrite, then validates/assembles |
| `tests/test_config.py` | Offline routing-intention and safety tests |
| `.github/workflows/build.yml` | Daily 08:20 Beijing build, validation, Pages deploy, artifact backup |
| `public/Front_Shadowrocket_personal.conf` | Generated output, published using GitHub Pages (not committed) |

## Requirements on iPhone

Two subscriptions must be added in Shadowrocket and named exactly:

- `VPS-US` — node names: `vl-reality-Front-VPS.US`, `vm-argo-Front-VPS.US`, `vm-ws-Front-VPS.US`, `anytls-Front-VPS.US`
- `long` — fallback nodes have `美国` or `日本` in their names

Strategy: `AutoProxy`: four `VPS-US` entries (in that order), then `long` USA / Japan.

**Private domain:** `198804.xyz` and subdomains are routed to `NAS服务`, which defaults to `DIRECT`. System DNS is requested via `[Host]` entries. You can manually change `NAS服务` if needed. DNS resolution/connection behavior still needs device testing; it cannot be guaranteed by static tests alone.

**Tailscale:** `.ts.net` and `100.64.0.0/10` use built-in `TAILSCALE`. Do not put `100.64.0.0/10` into `tun-excluded-routes`. Ensure the Shadowrocket Tailscale module is configured and active if using these rules.

**Privacy:** MITM is disabled; no scripts. `block-quic = all-proxy` does not affect direct-domain QUIC.

## Building and checking

```bash
python -m unittest discover -s tests -v
python build.py
```

When validation fails, `build.py` exits nonzero and GitHub Actions does not deploy a new Pages configuration. The previous successful Pages deployment remains the last published version.

The build preserves upstream `[General]`, `[Host]` and `[URL Rewrite]`, subject to personal overrides; it deliberately **does not append upstream `[Rule]`** to avoid third-party strategy-name drift and oversized mixed-format Global rules.

### Upgrade and rollback

Make changes on a temporary branch first. Confirm workflow success, merge into main, wait for Pages deployment, then refresh the configuration on iPhone. If behavior changes unexpectedly, use GitHub's commit history to revert the upgrade and redeploy; no subscription names or URLs need to change.

### Acceptance check on iPhone

Use "配置" routing mode. Verify rule tests and logs for:

- `198804.xyz` / `sub.198804.xyz`: `NAS服务` -> `DIRECT` with system DNS
- `x.com`: `Twitter` -> `AutoProxy`
- `chatgpt.com`: `AI` -> `AutoProxy`
- `weixin.com`: `Domestic` -> `DIRECT`
- `.ts.net` and Tailscale IPs: `TAILSCALE` (if enabled)
- MITM: disabled

If `198804.xyz` is still unstable with correct DIRECT logging, compare Wi-Fi vs mobile data, A/AAAA resolution, and Cloudflare Tunnel/server logs; configuration is not necessarily the root cause.
