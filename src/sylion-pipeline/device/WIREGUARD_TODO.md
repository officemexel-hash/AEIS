# WireGuard + Kill Switch — Implementation Status v5.9.1

STATUS: NOT IMPLEMENTED (documented gap).

Existing stack references VPN conceptually (orchestrator.py:2154 comment) but:
- No `kmod-wireguard` in OPKG_REQUIRED
- No wg0.conf generator
- No kill-switch iptables rules
- No DNS leak protection

Planned for v5.10 — see ADR-0020 (TBD). Current deployment relies on user-managed VPN external to SYLION.
