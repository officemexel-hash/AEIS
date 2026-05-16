# SYLION AEIS - clean export

Ten folder jest czystym eksportem programu AEIS z `C:\Users\razor\Desktop\pipeline_glm`.

Zawiera:

- backend FastAPI: `src/sylion-pipeline`
- frontend Next.js: `src/sylion-frontend`
- operator mobile: `operator-mobile`
- infrastrukture, manifesty i skills developerskie
- aktualna dokumentacje systemowa, operatorska, audytowa i deweloperska
- lokalne skrypty startowe: `start_backend.ps1`, `start_frontend.ps1`, `start_aeis.ps1`

Celowo nie zawiera:

- `.git`, worktree, cache i wirtualnych srodowisk
- `node_modules`, `.next`, buildow i test-results
- lokalnych baz danych `*.db`, WAL/SHM, logow i PID
- katalogow `output`, `results`, `evidence`, screenshotow testowych i runtime artefaktow
- sekretow runtime

Start lokalny:

```powershell
.\start_backend.ps1
.\start_frontend.ps1
```

Albo jednym poleceniem:

```powershell
.\start_aeis.ps1
```

Domyslne adresy:

- dashboard: `http://127.0.0.1:3001/overview`
- backend health: `http://127.0.0.1:8010/health`

Przed pierwszym startem zainstaluj zaleznosci:

```powershell
cd .\src\sylion-pipeline
pip install -r requirements.txt

cd ..\sylion-frontend
npm install
```

Ten eksport nie przenosi danych roboczych. Bazy SQLite zostana utworzone lokalnie dopiero po uruchomieniu systemu.
