# SYLION v5.8.8 â€” REPORT (Code-Auditor-Debugger Council Format)

## Stan koĹ„cowy

**PASS** â€” install Â· start Â· pytest (9/9)

- `pip install -r requirements-lock.txt` â†’ OK (litellm 1.67.4.post1)
- `python -m sylion.server --host 127.0.0.1 --http-port 18422` â†’ HTTP 200 na `/`, lifespan OK, agents seeded z YAML
- `pytest tests/test_regressions_v588.py` â†’ 9/9 PASS

---

## Security baseline

**Secrets scan:** 4 hardcoded API keys w `db.py` (`_DEFAULT_API_KEYS`) â€” jawnie zaakceptowane przez uĹĽytkownika jako Opcja C (lokalny pipeline, single-user developer, brak network exposure).

**CVE scan (pip-audit):** 30 podatnoĹ›ci w dep chain (litellm, pypdf, starlette, python-multipart, pytest). Zaakceptowane jako ryzyko (local-only, brak untrusted input).

**Niebezpieczne wzorce (grep):** 0 `eval(`, 0 `exec(`, 0 `pickle.loads`, 0 `shell=True` z user input, 0 `verify=False`. `yaml.load` zastÄ…piony wĹ‚asnym parserem `_parse_agents_yaml`.

---

## Naprawione problemy

### Runda 1 (10 bugĂłw â€” PDF-driven + evidence-verified)

Zobacz `CHANGELOG_v5.8.8.md` sekcja "10 gĹ‚Ăłwnych napraw".

### Runda 2 (6 findings z Council pre-release review)

#### Finding A â€” `sync_api_keys_to_env` nie czyĹ›ci os.environ przy pustej wartoĹ›ci DB

1. **Problem** â€” runtime/config consistency (env â‰  DB dla pustego UI clear)
2. **Root cause** â€” funkcja miaĹ‚a `if not value: continue` â€” empty DB value = skip, czyli pozostawaĹ‚ stary env z poprzedniego startup
3. **Evidence** â€” kod `db.py:876-878` (przed fixem) + scenariusz: user clear OPENAI_API_KEY w UI â†’ DB: "" â†’ os.environ["OPENAI_API_KEY"] nadal ustawione z poprzedniego syncu â†’ workers uĹĽywaĹ‚y stale value
4. **Fix** â€” `db.py:867-891`: `if value: os.environ[key] = value ... else: os.environ.pop(key, None)`
5. **Validation** â€” `test_finding_a_sync_api_keys_clears_env_on_empty_value` PASS
6. **Test regresji** â€” `tests/test_regressions_v588.py::test_finding_a_sync_api_keys_clears_env_on_empty_value`
7. **Consensus council** â€” solo GPT-5.4, ale **zweryfikowany empirycznie** przez czytanie kodu + reprodukcjÄ™

#### Finding B â€” `_ensure_dependencies` przepuszcza broken-but-present paczki

1. **Problem** â€” runtime â€” detekcja missing deps
2. **Root cause** â€” `_spec_ok` uĹĽywaĹ‚ tylko `importlib.util.find_spec`, ktĂłry zwraca spec dla paczek leĹĽÄ…cych na dysku NAWET jeĹ›li ich `__init__.py` rzuca ImportError
3. **Evidence** â€” reprodukcja w `/tmp/broken_test`: `broken_pkg/__init__.py: raise ImportError(...)` â†’ `find_spec == OK`, `import broken_pkg == FAIL`
4. **Fix** â€” `sylion/server.py startup checks`: dla kaĹĽdego critical dep â€” oprĂłcz `find_spec` â€” weryfikacja w fresh subprocess; jeĹ›li import pada â†’ traktuj jako missing i reinstall
5. **Validation** â€” smoke test startu dashboard: deps check przechodzi, brak faĹ‚szywych negatywĂłw; istniejÄ…cy test `test_bug1_litellm_imports_cleanly` wciÄ…ĹĽ PASS
6. **Test regresji** â€” poĹ›rednio pokryty przez Bug 1 test
7. **Consensus council** â€” solo GPT-5.4, **zweryfikowany empirycznie**

#### Finding C â€” UPSERT reaktywuje UI-wyĹ‚Ä…czonego agenta

1. **Problem** â€” logika biznesowa (governance DB vs yaml)
2. **Root cause** â€” UPSERT miaĹ‚ `enabled = excluded.enabled` w DO UPDATE SET, a `agents.yaml` defaultuje `enabled=true` dla wszystkich 48 agentĂłw â†’ kaĹĽdy restart cofaĹ‚ UI disable
3. **Evidence** â€” `db.py:1216-1221` (przed fixem) + scenariusz: operator wyĹ‚Ä…cza `coordinator` w UI â†’ restart â†’ _seed_agents UPSERT z enabled=1 â†’ disable zjedzony
4. **Fix** â€” `db.py:1225-1234`: usuniÄ™to `enabled` z DO UPDATE SET, zostaĹ‚o tylko przy INSERT (nowy wiersz); docstring dodaje rationale
5. **Validation** â€” `test_finding_c_upsert_does_not_reenable_disabled_agent` PASS
6. **Test regresji** â€” `tests/test_regressions_v588.py::test_finding_c_upsert_does_not_reenable_disabled_agent`
7. **Consensus council** â€” solo Opus 4.7, **zweryfikowany empirycznie**

#### Finding D â€” Misleading comment w PUT handler

1. **Problem** â€” dokumentacja (komentarz kĹ‚amaĹ‚ o fast-path)
2. **Root cause** â€” komentarz "Only api_keys rows need the env sync; for others we avoid the lock" â€” w rzeczywistoĹ›ci lock brany ZAWSZE
3. **Fix** â€” `app.py:817-821`: nowy komentarz opisuje faktyczne zachowanie + uzasadnia wybĂłr
4. **Consensus council** â€” 3/4 (Opus + Sonnet + GPT)
5. **Test regresji** â€” N/A (zmiana kosmetyczna)

#### Finding E â€” Licznik `inserted` myli po UPSERT

1. **Problem** â€” log observability
2. **Root cause** â€” po zmianie z INSERT OR IGNORE na UPSERT, `cur.rowcount>0` zlicza teĹĽ UPDATE, ale nazwa zmiennej i log text ("newly inserted") sugerujÄ… tylko INSERT
3. **Fix** â€” `db.py:1212,1244-1246`: `inserted` â†’ `upserted`, log `"%d inserted/updated"`
4. **Consensus council** â€” 3/4

#### Finding F â€” Docstring `_seed_agents` mĂłwi "INSERT OR IGNORE"

1. **Fix** â€” `db.py:1191-1202`: peĹ‚ny rewrite sekcji Behaviour wskazujÄ…cy UPSERT + uzasadnienie "dlaczego enabled nie w UPDATE"
2. **Consensus council** â€” 3/4

---

## PozostaĹ‚e blokery

**BRAK.** Wszystkie zgĹ‚oszenia z Council pre-release review zostaĹ‚y zaadresowane lub zaakceptowane przez uĹĽytkownika.

---

## Git

Working directory: `/home/user/workspace/SYLION_v588_work/sylion-installer/sylion-pipeline`

**Brak `.git/`** w katalogu (pracujemy na rozpakowanym ZIP, nie na repo). Git-awareness nie ma zastosowania w tym workflow â€” dostarczamy ZIP.

Proponowany commit message (jeĹ›li kiedyĹ› stanie siÄ™ repo):

```
fix(sylion): v5.8.8 "Evidence Fix" â€” 10 bugĂłw + 6 council findings

GĹ‚Ăłwne naprawy:
- fix(deps): pin litellm==1.67.4.post1 (Bug 1)
- fix(dashboard): sync DB api_keys -> os.environ z lockiem (Bug 2, Gemini+)
- fix(dashboard): agents.yaml faktycznie parsed (Bug 3)
- fix(dashboard): _ensure_dependencies z subprocess verify (Bug 5 + Finding B)
- fix(dashboard): _seed_defaults port 8421 (Bug 7)
- fix(dashboard): UPSERT agentĂłw bez clobberingu UI disable (Bug 9 + Finding C)
- fix(dashboard): empty DB value -> clear os.environ (Finding A)

Testy regresji: 9/9 PASS w tests/test_regressions_v588.py
Council review: 4/4 APPROVE po round 2

Refs: /home/user/workspace/council/round-prerelease-*.md
```

---

## Rekomendacje stabilizacyjne

1. **CI:** DodaÄ‡ `pytest tests/test_regressions_v588.py` do pipeline (np. GitHub Actions)
2. **Pinowanie:** `requirements-lock.txt` zawiera pinned wersje â€” utrzymaÄ‡ przy kaĹĽdym upgrade
3. **Migracja:** Gdy SYLION wyjdzie z trybu single-developer, przenieĹ›Ä‡ `_DEFAULT_API_KEYS` z kodu do bezpiecznego vault (AWS Secrets Manager / HashiCorp Vault / `.env` w gitignore)
4. **Healthcheck:** `health_check.py` juĹĽ istnieje â€” rozwaĹĽyÄ‡ dodanie endpoint `/healthz` weryfikujÄ…cy sync DBâ†”env na ĹĽywo

---

## Log council

- Round 1 (evidence-based, pre-fix hypotheses): `/home/user/workspace/audit/EVIDENCE_v588.md`
- Round 1 consensus: `/home/user/workspace/council/CONSENSUS_v588.md`
- Round 2 (pre-release review â€” 461 line diff): `/home/user/workspace/council/v588_diff.txt`
- Round 2 individual reports:
  - `/home/user/workspace/council/round-prerelease-opus.md`
  - `/home/user/workspace/council/round-prerelease-sonnet.md`
  - `/home/user/workspace/council/round-prerelease-gpt54.md`
  - `/home/user/workspace/council/round-prerelease-gemini.md`

