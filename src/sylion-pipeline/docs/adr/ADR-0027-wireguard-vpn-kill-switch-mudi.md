# ADR-0027: WireGuard VPN z kill switch i DNS tunnel na Mudi

**Status:** PROPOSED  
**Data:** 2026-04-20  
**Wersja:** 5.9.2  
**Autor:** SYLION AI Council / mega_audit/wireguard_impl  

---

## Kontekst

SYLION działa w środowiskach o podwyższonych wymaganiach prywatności (kancelarie prawne DE/PL, biura rachunkowe). Urządzenie Mudi (GL.iNet GL-E750) jest używane jako mobilny router/hotspot dla agentów terenowych. Audyt mega_audit/wireguard_impl wykazał:

1. **Brak kill switch**: gdy tunel WireGuard zostaje zerwany, ruch sieciowy przechodzi przez nieszyfrowane łącze (DNS leak, IP leak). Testy z `mega_audit/kill_switch_dns_leak` potwierdziły wyciek DNS na Mudi firmware OpenWrt 21.02.
2. **DNS tunnel podatność**: urządzenie Mudi domyślnie odpytuje publiczny resolver (8.8.8.8) zamiast routować DNS przez tunel WireGuard — umożliwia fingerprinting ruchu DNS przez dostawcę internetu.
3. **Brak automatycznej rekonfiguracji**: po restarcie Mudi WireGuard nie wznawiał połączenia bez ręcznej interwencji — problem z `wg-quick` i `hotplug.d`.

Środowisko docelowe: Mudi z OpenWrt ≥ 22.03, peer endpoint: VPS z WireGuard server (Ubuntu 22.04), interfejs `wg0`.

Rozważane warianty:
- **W1** — OpenVPN z kill switch przez `tun-mtu-extra` i `route-nopull` (historyczne podejście)
- **W2** — WireGuard + iptables kill switch + DNS przez tunel (wybrana)
- **W3** — WireGuard + nftables (nowszy kernel, lepsza wydajność)
- **W4** — Tailscale (zarządzany WireGuard) — wymaga zewnętrznego serwera koordynacyjnego (naruszenie data sovereignty)

## Decyzja

Wdrożenie **W2**: WireGuard (`wg-quick`) na Mudi z:

1. **Kill switch** via iptables: reguły `FORWARD DROP` i `OUTPUT DROP` dla pakietów poza interfejsem `wg0`, aktywowane przez `PostUp`/`PreDown` w `/etc/wireguard/wg0.conf`.
2. **DNS przez tunel**: `DNS = 10.8.0.1` w konfiguracji WireGuard (resolver na VPS peer), `AllowedIPs = 0.0.0.0/0, ::/0`. Systemowy resolver na Mudi skonfigurowany przez `dnsmasq` z upstream `127.0.0.1#5353` (local loop do `wg0`).
3. **Auto-reconnect**: skrypt `wg-watchdog.sh` wywoływany przez `cron` co 60s, wznawia `wg-quick up wg0` jeśli peer handshake > 180s temu.
4. **Generator konfiguracji**: `scripts/wg_config_generator.py` (mega_audit/wg_config_generator) generuje konfigurację peer/server na podstawie `config.yaml`.

## Konsekwencje

### Pozytywne
- Pełna ochrona przed DNS leak i IP leak — każdy ruch routowany przez tunel
- Kill switch zapobiega wyciekowi danych przy zerwaniu VPN (compliance DE: BDSG §64, PL: UODO)
- Auto-reconnect eliminuje konieczność ręcznej obsługi przy przełączaniu sieci (WiFi ↔ LTE)
- WireGuard: ~40% niższe opóźnienie vs OpenVPN przy zachowaniu pełnego szyfrowania (ChaCha20-Poly1305)

### Negatywne
- iptables kill switch nie jest persistent — wymaga `iptables-save` i `iptables-restore` w `/etc/rc.local` (OpenWrt specyfika)
- `DNS = 10.8.0.1` wymaga działającego resolwera na peer VPS — single point of failure dla DNS
- `wg-watchdog.sh` może generować fałszywe alarmy przy chwilowych przerwach (< 180s grace period)

### Neutralne
- Migracja z OpenVPN nie wymaga zmian w klientach SYLION — tylko rekonfiguracja routera Mudi
- Konfiguracja WireGuard przechowywana w `/etc/wireguard/wg0.conf` — wymaga ochrony hasłem (chmod 600)

## Alternatywy odrzucone

- **Tailscale (W4)**: dane koordynacyjne przez serwer Tailscale (US) — naruszenie data residency DE/PL — odrzucone
- **nftables (W3)**: Mudi OpenWrt 21.02 używa kernel 5.4 bez pełnego wsparcia nftables — odrzucone dla kompatybilności; planowane w v5.10 po upgrade firmware

## Referencje

- `mega_audit/wireguard_impl/` — implementacja WireGuard dla Mudi
- `mega_audit/kill_switch_dns_leak/` — wyniki testów DNS leak przed i po fixie
- `mega_audit/mudi/`, `mega_audit/mudi_deep/` — konfiguracja urządzenia Mudi
- `scripts/wg_config_generator.py` — generator konfiguracji peer/server
- WireGuard whitepaper: https://www.wireguard.com/papers/wireguard.pdf
- OpenWrt WireGuard dokumentacja: https://openwrt.org/docs/guide-user/services/vpn/wireguard/basics
