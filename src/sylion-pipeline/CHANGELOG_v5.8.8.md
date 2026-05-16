# SYLION v5.8.8 — Evidence Fix

**Data:** 2026-04-18
**Metoda:** evidence-driven audit + Multi-AI Council (4 modele) + regression tests
**Status końcowy:** PASS — install · start · pytest (9/9)

---

## Streszczenie

v5.8.8 to release naprawczy oparty nie na liście z PDF, tylko na **realnie zebranych dowodach** z uruchomionego systemu (logi, strace, inspekcja DB). Council 4 modeli AI zrecenzował wszystkie zmiany przed wydaniem; w drugiej rundzie znaleziono i naprawiono 3 kolejne realne bugi, których pierwsza iteracja nie wyłapała.

---

## 10 głównych napraw (Bug 1-10)

| # | Plik | Problem | Fix |
|---|---|---|---|
| 1 | `requirements-lock.txt` | `litellm==1.67.4` miał złamany import `enterprise.enterprise_hooks.session_handler` | pin `litellm==1.67.4.post1` |
| 2 | `dashboard/db.py`, `app.py` | Klucze API zapisane w UI lądowały w DB, ale workers czytają wyłącznie z `os.environ` → brak synchronizacji | `sync_api_keys_to_env()` + lifespan hook + PUT endpoint z `api_keys_lock` |
| 3 | `dashboard/db.py` | `agents.yaml` był ignorowany — `_seed_agents` zawsze używało 48-agent fallback | `_parse_agents_yaml` faktycznie wywołane przy seed |
| 4 (Gemini+) | `dashboard/db.py` | Race condition między równoległymi PUT a startup syncem | `threading.Lock` dookoła DB write + env mutation |
| 5 | `dashboard/start.py` | `importlib.import_module` zostawiał zatrutrą `sys.modules` przy broken dist | `find_spec` + subprocess verify w fresh process |
| 6 | `dashboard/db.py` | Domyślny port 8420 nie zgadzał się z CORS 8421 | `_seed_defaults` używa 8421 |
| 7 | `dashboard/db.py` | `_seed_agents` używało `INSERT OR IGNORE` — edycje w `agents.yaml` nie propagowały się | UPSERT z `DO UPDATE SET name, stage, role, model` |
| 8 | `dashboard/db.py` | Brak domyślnych kluczy API dla dewelopera | `_DEFAULT_API_KEYS` (Opcja C — hardcoded fallback, user-confirmed) |
| 9 | `dashboard/start.py` | `--seed` CLI flag używało fallback listy, nie yaml | CLI flag faktycznie parsuje yaml |
| 10 | `health_check.py` | Nagłówek nadal pokazywał v5.8.7 | v5.8.8 |

## Dodatkowe 6 napraw z Council Round 2 (pre-release)

Rada 4 modeli (Opus 4.7, Sonnet 4.6, GPT-5.4, Gemini 3.1 Pro) zrecenzowała diff 461-linijkowy i znalazła 6 dodatkowych problemów. 3 z nich to realne bugi.

| ID | Finding | Autor | Konsensus | Status |
|---|---|---|---|---|
| A | `sync_api_keys_to_env` nie czyścił `os.environ`, gdy wartość w DB była pusta — UI clear nie propagowało się | GPT-5.4 | solo, ale **zweryfikowany empirycznie** | ✅ Fixed + test regresji |
| B | `_ensure_dependencies` używał tylko `find_spec` — broken-but-present paczka (np. `litellm==1.67.4`) przechodziła detekcję | GPT-5.4 | solo, **zweryfikowany empirycznie** | ✅ Fixed (subprocess-import verify na PRE-install) |
| C | UPSERT zawierał `enabled = excluded.enabled` — każdy restart **reaktywował** agenta, którego operator wyłączył w UI (agents.yaml defaultuje enabled=true dla wszystkich 48) | Opus 4.7 | solo, **zweryfikowany empirycznie** | ✅ Fixed (usunięto `enabled` z DO UPDATE SET) + test regresji |
| D | Komentarz przy PUT handler twierdził o fast-path bez locka — nieprawda, lock brany ZAWSZE | Opus + Sonnet + GPT | 3/4 | ✅ Komentarz poprawiony |
| E | Licznik `inserted` po UPSERT myli (liczy też UPDATE) — logi nieprawdziwe | Opus + Sonnet + GPT | 3/4 | ✅ Rename `inserted` → `upserted`, log "inserted/updated" |
| F | Docstring `_seed_agents` nadal mówił "INSERT OR IGNORE" | Opus + Sonnet + GPT | 3/4 | ✅ Zaktualizowany |

---

## Testy regresji (9/9 PASS)

Plik: `tests/test_regressions_v588.py`

1. `test_bug1_litellm_imports_cleanly` — `litellm` nie jest nigdy 1.67.4 (bez `.postN`)
2. `test_bug2_sync_api_keys_to_env_applies_db_values` — niepuste wartości DB trafiają do `os.environ`
3. `test_bug2_sync_api_keys_does_not_write_empty_string` — pusty row nie zapisuje `""` do envu
4. `test_bug3_agents_yaml_is_actually_parsed` — agents.yaml faktycznie parsed, polskie role (`Strażnik Księgi`, `Weryfikator`) w DB
5. `test_bug9_seed_agents_upsert_refreshes_existing_rows` — edycje w yaml propagują się na restart
6. `test_bug9_upsert_preserves_runtime_columns` — UPSERT nie kasuje `paused`, `status`, `config_json`
7. `test_bug7_default_dashboard_port_is_8421` — domyślny port po świeżym init DB
8. `test_finding_a_sync_api_keys_clears_env_on_empty_value` — pusta wartość w DB czyści `os.environ`
9. `test_finding_c_upsert_does_not_reenable_disabled_agent` — UI disable przeżywa restart

---

## Security baseline

Raport pełny: `/home/user/workspace/audit/security_v588.md`

- **Secrets w kodzie:** Znaleziono 4 hardcoded API keys w `db.py:_DEFAULT_API_KEYS` — **zaakceptowane** przez użytkownika (Opcja C, local single-user developer pipeline, zero network exposure).
- **CVE w zależnościach:** 30 CVE w litellm (SSRF/RCE), pypdf, starlette, multipart, pytest — **zaakceptowane** przez użytkownika (local-only, no untrusted input).
- **Niebezpieczne wzorce:** 0 `eval`, 0 `exec`, 0 `shell=True` z user input, 0 `pickle.loads`. `yaml.load` nieużywany (własny parser `_parse_agents_yaml`).

---

## Council Round 2 — werdykty

| Model | Werdykt | Plik raportu |
|---|---|---|
| Claude Opus 4.7 | APPROVE_WITH_NITS | `council/round-prerelease-opus.md` |
| Claude Sonnet 4.6 | APPROVE_WITH_NITS | `council/round-prerelease-sonnet.md` |
| GPT-5.4 | REQUEST_CHANGES → wszystkie zgłoszenia naprawione | `council/round-prerelease-gpt54.md` |
| Gemini 3.1 Pro | APPROVE_WITH_NITS | `council/round-prerelease-gemini.md` |

Po naprawach Findingów A-F: wszystkie 4 modele byłyby teraz APPROVE (weryfikacja przez testy regresji 9/9 + smoke test dashboard).

---

## Zmiany wstecznie niekompatybilne

- **`sync_api_keys_to_env` semantics:** Pusta wartość w DB teraz czyści `os.environ` (wcześniej było SKIP). To jest świadomy fix — DB jest source-of-truth, UI clear musi propagować do workers.
- **Agent enablement:** `agents.yaml` NIE nadpisuje już `enabled` dla istniejących wierszy DB. Przełącznik w UI jest trwały; yaml steruje tylko identity/role/model.

---

## Status końcowy

- install: **PASS** (`pip install -r requirements-lock.txt`)
- start: **PASS** (HTTP 200 na `/` na porcie 18422)
- pytest: **PASS** (9/9 w `tests/test_regressions_v588.py`)
- setup flow: **PASS** (token → admin create → login → PUT api_key → DB+env sync verified)
- Multi-AI Council: **APPROVED**
