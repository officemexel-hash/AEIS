# FAZA 3 — Environment Configuration (Część 1 z 2)

> **Status**: 🟢 Active draft — Część 1 z 2 (przed soft-freeze)
> **Grupa**: A — Przygotowanie Operatora (3 z 11)
> **Typ**: iteracyjna, operator wraca w cyklu projektów
> **Czas wykonania**: 5 min (sam laptop) / 30 min (1-2 cloud providers) / godziny (multi-cloud + edge + sovereign)
> **D-level**: D2 — środowiska deploy mają znaczenie kosztowe i operacyjne
> **Zależności**: Faza 1 zakończona; Faza 2 zalecana (providers LLM dla auto-deploy testów)
> **Następnik**: Faza 4 (Workspace Defaults)
>
> **Część 1 covers**: sekcje 3.1-3.6
> **Część 2 covers**: sekcje 3.7-3.12

---

## 3.1. Sens fazy i jej miejsce w cyklu

### 3.1.1. Czym są "środowiska" w AEIS

W AEIS **środowisko** to **logiczna jednostka deploy** (P3.2=c) — miejsce
gdzie kod operatora może być uruchomiony, testowany lub wdrożony. Może to
być:

- **Pojedyncza maszyna** (laptop, 1 VPS)
- **Cluster maszyn** (3 VPS z load balancer, K8s cluster)
- **Cloud environment** (AWS account + region + VPC)
- **Edge device** (Raspberry Pi w fabryce)
- **Customer's infrastructure** (sovereign on-prem)

**Operator widzi środowisko jako 1 jednostkę** mimo że może mieć dowolnie
złożoną strukturę pod spodem. Faza 3 abstraktuje complexity.

### 3.1.2. Czemu ta faza jest osobna od fazy 2

**Faza 2** (Provider Catalog) — gdzie inteligencja AI biegnie (LLM
providers).
**Faza 3** (Environment Configuration) — gdzie kod operatora biegnie
(deploy targets).

To są **różne wymiary**:

```
              FAZA 2                      FAZA 3
              ──────                      ──────
Co:           LLM providers               Compute targets
Przykłady:    Anthropic, Ollama,          AWS, Hetzner, RPi,
              OpenRouter                  laptop, customer's server
Cel:          Council deliberation,       Build artifacts, run apps,
              code generation,            host services, test
              text/image/audio gen
Trwałość:     Per-call (krótkie)          Per-deploy (długie)
Cost model:   Per token / per image       Per hour / per resource
Ryzyko:       Privacy (gdzie idą          Vendor lock-in,
              prompts)                    network attacks
```

Operator może mieć **multi-environment + multi-LLM** combinations:

```
Project Sylion Tailor:
  LLM (faza 2):           Anthropic + Bielik (lokalny)
  Build environment:       Lokalny Docker (faza 3)
  Test environment:        Hetzner CX21 dev (faza 3)
  Production environment:  Hetzner CX31 warsaw + Cloudflare CDN (faza 3)
  Edge:                    -
```

### 3.1.3. Wynik fazy (DoD adaptive per goals)

**Minimum (po pierwszym przejściu)**:
- ✓ Min 1 środowisko skonfigurowane (typowo "local-dev" auto-created)
- ✓ Operator wie różnicę między dev / staging / prod
- ✓ Cleanup policy zdefiniowana

**Rekomendowane (operator z goal "public_products")**:
- ✓ 2-3 środowiska (local-dev + staging-cloud + prod-cloud)
- ✓ Min 1 cloud provider integrated z testowanym credential
- ✓ Network policy zdefiniowana
- ✓ Cost limits per environment
- ✓ Healthcheck monitoring włączone

**Zaawansowane (multi-deploy, federation, edge)**:
- ✓ 5-15+ środowisk różnych typów
- ✓ Multi-cloud + edge + sovereign mix
- ✓ Mesh network między środowiskami
- ✓ Data residency rules (GDPR enforcement)
- ✓ Cleanup automatyzacja
- ✓ Cross-environment cost optimization

### 3.1.4. Co NIE jest w tej fazie

| Element | Dlaczego nie | Gdzie |
|---|---|---|
| LLM providers | Faza 2 | Faza 2 |
| Workspace defaults (autonomy, budgets) | Faza 4 | Faza 4 |
| Per-project deploy decisions | Project-level | Faza 17 / 33 |
| Konkretny deployment plan | Per project | Faza 39 (Deployment Configuration) |
| Code repositories / git config | Outside scope | Settings → Integrations |

---

## 3.2. Architektura środowisk (P3.1=d hybrid 3 widoki)

### 3.2.1. Trzy poziomy hierarchii

AEIS organizuje środowiska analogicznie do providerów (faza 2):

```
ENVIRONMENT TYPE   (np. AWS, Hetzner, Local, Edge)
   │
   ├── LOCATION/ACCOUNT  (np. AWS account 123, Hetzner project, lokalny)
   │       │
   │       └── REGION/ZONE  (np. eu-west-1, fra1, on-prem rack-A)
   │              │
   │              └── ENVIRONMENT  (logiczna jednostka deploy)
   │                  np. "sylion-prod" — może być 1 VPS lub K8s cluster
```

**Environment type** — kategoria providera (cloud / VPS / local / edge /
sovereign).

**Location/Account** — konkretne konto operatora (każdy operator może mieć
multiple accounts).

**Region/Zone** — geografia (matters dla data residency, latency,
compliance).

**Environment** — logiczna jednostka. Operator może mieć w jednym AWS
account `eu-west-1` 3 środowiska: "dev", "staging", "prod" — każde ma
swoje resources.

### 3.2.2. Trzy widoki (toggle)

#### Widok 1 — Type-first (default)

Hierarchiczny widok z drilldown:

```
┌──────────────────────────────────────────────────────────────┐
│  Environment Catalog                       [+ Add Environment]│
│  Widok: [● Type]  [○ Purpose]  [○ Flat]                      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ▼ Local                            1 environment           │
│      ▼ This machine (Robert's laptop)                        │
│           Endpoint: http://localhost                         │
│           Status: ✓ Running    Resources: 32 GB RAM, RTX 4090│
│           Environments:                                      │
│             • local-dev          (dev purpose)               │
│                                                              │
│  ▼ Hetzner                          2 environments           │
│      ▼ Account: robert@sylion.dev                            │
│           ▼ Region: warsaw-1                                 │
│              • sylion-prod-1   CX31  €8.40/mo  ✓ Running     │
│              • sylion-staging  CX21  €4.20/mo  ✓ Running     │
│                                                              │
│  ▼ AWS                              0 environments           │
│      ▼ Account: 123456789012                                 │
│           ◌ No environments yet  [+ Add]                     │
│                                                              │
│  ▼ Edge                             1 environment            │
│      ▼ Mesh: home-lab                                        │
│           • rpi-fabryka-1     RPi 4   ARM 4 GB  ✓ Online     │
│                                                              │
│  Empty slots:                                                │
│  ◌ GCP            [+ Add]                                    │
│  ◌ Azure          [+ Add]                                    │
│  ◌ DigitalOcean   [+ Add]                                    │
│  ◌ Linode         [+ Add]                                    │
│  ◌ OVH            [+ Add]                                    │
│  ◌ Vultr          [+ Add]                                    │
│  ◌ Scaleway       [+ Add]                                    │
│  ◌ IONOS          [+ Add]                                    │
│  ◌ Polcom         [+ Add]                                    │
│  ◌ Custom         [+ Configure]                              │
│                                                              │
│  Total: 4 active environments across 3 providers             │
│  Monthly cost: $12.60 (Hetzner only — no cloud yet)          │
└──────────────────────────────────────────────────────────────┘
```

#### Widok 2 — Purpose-first

Grupowanie według celu (dev/staging/prod/edge):

```
┌──────────────────────────────────────────────────────────────┐
│  Environment Catalog — by Purpose                            │
│  Widok: [○ Type]  [● Purpose]  [○ Flat]                      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ▼ DEVELOPMENT (1 environment)                               │
│      • local-dev (Local · This machine)                      │
│        For: rapid iteration, low risk                        │
│                                                              │
│  ▼ STAGING (1 environment)                                   │
│      • sylion-staging (Hetzner · CX21 warsaw-1)              │
│        For: integration testing, pre-prod                    │
│        Cost: €4.20/mo                                        │
│                                                              │
│  ▼ PRODUCTION (1 environment)                                │
│      • sylion-prod-1 (Hetzner · CX31 warsaw-1)               │
│        For: live customer traffic                            │
│        Cost: €8.40/mo                                        │
│        SLA target: 99.5%                                     │
│        Last deployment: 2026-04-28 14:32                     │
│                                                              │
│  ▼ EDGE (1 environment)                                      │
│      • rpi-fabryka-1 (Edge · RPi 4)                          │
│        For: customer-side (atelier production tracking)      │
│        Status: ✓ Online (last ping 30s ago)                  │
│                                                              │
│  ▼ TESTING (0 environments)                                  │
│      ◌ No testing environments yet                           │
│      [+ Add testing environment]                             │
│                                                              │
│  ▼ DEMO/SANDBOX (0)                                          │
│      ◌ Recommended dla showcase do klientów                  │
│      [+ Add demo environment]                                │
│                                                              │
│  Total: 4 environments, 5 purposes (1 empty)                 │
└──────────────────────────────────────────────────────────────┘
```

#### Widok 3 — Flat list

Płaska lista wszystkich środowisk (sortable, filterable):

```
┌──────────────────────────────────────────────────────────────┐
│  Environment Catalog — Flat List                             │
│  Widok: [○ Type]  [○ Purpose]  [● Flat]                      │
│  Filter: [All types ▼]  Sort: [Cost ↑]                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Name              Type     Purpose   Region    Cost  Status │
│  ─────────────── ─────── ────────── ─────────── ───── ────── │
│  local-dev        Local    Dev       n/a         $0    ✓     │
│  rpi-fabryka-1    Edge     Edge      home-lab    $0    ✓     │
│  sylion-staging   Hetzner  Staging   warsaw-1    €4.2  ✓     │
│  sylion-prod-1    Hetzner  Prod      warsaw-1    €8.4  ✓     │
│                                                              │
│  Total: 4 environments · €12.60/mo (~$13.50)                 │
└──────────────────────────────────────────────────────────────┘
```

### 3.2.3. Toggle preferences

Operator wybiera default widok per kontekst:

| Kontekst | Default | Powód |
|---|---|---|
| Pierwsza wizyta po fazie 1/2 | Type | Hierarchiczny, łatwo orientować się |
| Project planning (faza 33) | Purpose | "Where does each module deploy?" |
| Cost analysis | Flat (sort by cost) | Quick budget view |
| Health debugging | Type | Drilldown do source problemu |
| Deploy management | Purpose | Logical grouping per env stage |

### 3.2.4. Environment metadata

Per environment, AEIS śledzi:

```yaml
environment:
  id: env_sylion_prod_1
  name: sylion-prod-1
  display_name: "Sylion Production (Warsaw)"
  
  classification:
    type: hetzner
    purpose: production
    tier: standard  # dev / staging / prod / critical / sandbox
    sovereign: true  # EU-hosted
    air_gapped: false
  
  location:
    provider: hetzner
    account: robert@sylion.dev
    region: warsaw-1
    datacenter: nbg1-dc3  # specific datacenter
    coordinates: { lat: 52.2297, lon: 21.0122 }
  
  resources:
    instance_type: cx31
    cpu: 4
    ram_gb: 16
    disk_gb: 80
    gpu: null
    network_speed_gbps: 1
  
  configuration:
    os: ubuntu-22.04
    docker: true
    kubernetes: false
    healthcheck_url: https://sylion.dev/healthz
    monitoring: prometheus
  
  cost:
    monthly_estimate_eur: 8.40
    monthly_estimate_usd: 8.95
    billing_cycle: monthly
    last_invoice_date: 2026-04-01
  
  status:
    state: running  # creating / running / paused / decommissioning / failed
    health: healthy  # healthy / degraded / down
    last_seen: 2026-04-29T14:32:18Z
    uptime_days: 87
  
  metadata:
    created_at: 2026-02-01
    created_by_phase: 3
    tags: [production, sylion-tailor, customer-facing]
    deployments_count: 47
    last_deployment: 2026-04-28T22:04:31Z
  
  policies:
    auto_cleanup: false
    cleanup_after_days: null
    backup_strategy: daily
    snapshot_retention: 30
    
  network:
    public_ip: 78.46.x.x
    private_ip: 10.0.0.5
    vpn_attached: true
    firewall_rules: [...]
    accessible_from: [office_network, vpn_users]
```

---

## 3.3. Auto-detection środowisk (P3.4=b szerokie + P3.5=d hybrid CLI)

### 3.3.1. Co AEIS skanuje przy pierwszej wizycie w fazie 3

**Lokalna maszyna operatora** (P3.4=b szerokie):

```python
# Sequence przy entering faza 3 (~5-15 sek)

1. OS info:
   - Platform (Linux/macOS/Windows)
   - Kernel version
   - Distribution (jeśli Linux)
   - Architecture (x86_64, arm64)

2. Hardware resources:
   - CPU cores + model
   - RAM total + available
   - Disk space (per mount)
   - GPU (CUDA / Metal / ROCm presence + VRAM)
   - Network interfaces (count + speeds)

3. Containerization:
   - Docker installed? Version?
   - Docker daemon running?
   - Docker Compose v2 available?
   - Podman alternative?

4. Kubernetes:
   - kubectl in PATH?
   - ~/.kube/config istnieje?
   - Active context (jeśli jest)?
   - Local cluster (k3s, k3d, minikube, kind)?

5. Local ports:
   - Common dev ports busy: 80, 443, 3000, 5000, 5432, 8000, 8080
   - LLM ports: 11434 (Ollama), 1234 (LM Studio), 8188 (ComfyUI)
   - Pokazuje co używa portu

6. SSH/network:
   - ~/.ssh/config — known hosts (possible deploy targets)
   - Active VPN connections (Tailscale, WireGuard)
   - DNS configuration

7. Cloud CLI tools (P3.5=d — wykrywa, nie listuje):
   - aws-cli (`which aws`)
   - gcloud (`which gcloud`)
   - az (Azure CLI)
   - hcloud (Hetzner)
   - doctl (DigitalOcean)
   - linode-cli
   - terraform (`which terraform`)
   - pulumi
```

### 3.3.2. Auto-create local-dev (P3.3=a)

Po pierwszym scanowaniu, system automatycznie tworzy `local-dev`:

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Auto-detected: Your local machine                        │
│                                                              │
│  AEIS skonfigurował twoje pierwsze środowisko:               │
│                                                              │
│  ┌── ENVIRONMENT: local-dev ──────────────────────────────┐  │
│  │                                                        │  │
│  │  Type:         Local (this machine)                    │  │
│  │  Purpose:      Development                             │  │
│  │                                                        │  │
│  │  Resources:                                            │  │
│  │   • CPU:       AMD Ryzen 9 7950X (32 threads)         │  │
│  │   • RAM:       32 GB (12 GB available right now)       │  │
│  │   • GPU:       NVIDIA RTX 4090 (24 GB VRAM, CUDA 12.1) │  │
│  │   • Disk:      850 GB free / 2 TB                     │  │
│  │                                                        │  │
│  │  Software:                                             │  │
│  │   ✓ Docker 24.0.7                                      │  │
│  │   ✓ Docker Compose v2                                  │  │
│  │   ✗ Kubernetes (not installed locally)                 │  │
│  │   ✓ Git, Python 3.13, Node 20                          │  │
│  │                                                        │  │
│  │  Network:                                              │  │
│  │   • Local IP: 192.168.1.42                             │  │
│  │   • Public IP: detected (78.142.x.x)                   │  │
│  │   • Accessible from: localhost only                    │  │
│  │                                                        │  │
│  │  Detected cloud CLI tools (faza 3.5):                  │  │
│  │   ✓ aws-cli installed (suggest add AWS provider)       │  │
│  │   ✓ hcloud installed (suggest add Hetzner)             │  │
│  │   ✗ gcloud not installed                               │  │
│  │   ✗ az (Azure) not installed                           │  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  [Accept defaults]  [Customize]  [Skip auto-create]          │
│                                                              │
│  💡 Po akceptacji, zobaczysz suggestions dla kolejnych       │
│     środowisk (cloud, edge, sovereign).                      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Po klick "Accept defaults"**:
- `local-dev` saved jako pierwsze środowisko
- Auto-tagged: `local`, `dev`, `single-machine`
- Cleanup policy: never (lokalne, nie wymaga cleanup)
- Cost: $0
- Available immediately dla projektów

**Po klick "Customize"**:
- Operator może edytować name, purpose, resources description, network rules
- Może dodać metadata (np. notes, tags)
- Może wykluczyć GPU jeśli nie chce go używać dla AEIS workloads

### 3.3.3. Cloud CLI detection workflow (P3.5=d)

System wykrywa CLI tools ale nie auto-listuje resources. Pokazuje sugestię:

```
┌──────────────────────────────────────────────────────────────┐
│  💡  Wykryto cloud CLI tools                                 │
│                                                              │
│  AEIS znalazł skonfigurowane CLI tools dla:                  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  ☑ AWS CLI                                             │  │
│  │     Config: ~/.aws/credentials                         │  │
│  │     Profile: default                                   │  │
│  │     Region: eu-west-1                                  │  │
│  │     [Add AWS as provider]                              │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  ☑ Hetzner CLI (hcloud)                                │  │
│  │     Config: ~/.config/hcloud/cli.toml                  │  │
│  │     Active context: sylion-main                        │  │
│  │     [Add Hetzner as provider]                          │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ⚠ AEIS NIE listuje twoich istniejących resources w cloud.   │
│    Aby zobaczyć co masz w AWS:                               │
│      [Run `aws ec2 describe-instances` for me]               │
│      ↑ wymaga twoja explicit zgoda (P3.5=d)                  │
│                                                              │
│  Co AEIS zrobi po dodaniu providera:                         │
│   1. Zweryfikuje credentials (test API call)                 │
│   2. Zapamięta provider w katalogu                           │
│   3. Pozwoli ci tworzyć nowe environments w tym providerze   │
│   4. NIE auto-listuje istniejących resources                 │
│                                                              │
│  [Add detected providers]  [Skip — add manually later]       │
└──────────────────────────────────────────────────────────────┘
```

**Decision points**:
- Add detected (skips wizards, dodaje providers wszystkie)
- Skip (operator doda manually w fazie 3.4)
- Run resource listing (per provider explicit consent)

### 3.3.4. Periodic detection (background)

Po wstępnej konfiguracji, AEIS robi periodic scan:

```
Settings → Environment Detection → Periodic Scan

  ☑ On launch: szybki scan lokalnych zmian (5 sek)
     Wykrywa: zmiany w Docker, K8s contexts, network interfaces
  
  ☑ On-demand: full deep scan (operator klika "Re-scan")
     Wykrywa: nowo zainstalowane CLI tools, new disks, etc.
  
  ☑ File system events: continuous w tle
     Watch: ~/.kube/config, ~/.aws/credentials, ~/.config/hcloud/
     Trigger: gdy operator instaluje nowy CLI / dodaje credentials
  
  ☐ Cloud resource auto-listing (default OFF — privacy)
     Frequency: [Manual only ▼]
     Notify gdy: nowe resources pojawiają się (mogą być cost generators)

  ☑ Network change detection
     Wykrywa: nowe VPN, mesh networks, hosts w SSH config
     Trigger: nowe LAN connection, VPN auto-connect
```

---

## 3.4. Cloud providers (P3.6=c — Tier 1+2+5, 10 providers)

### 3.4.1. Wspierane cloud providers

Operator wybrał **Tier 1+2+5** = **10 providers** + custom workflow.

**Tier 1 — Enterprise**:
- AWS (Amazon Web Services)
- GCP (Google Cloud Platform)
- Azure (Microsoft)

**Tier 2 — VPS-focused**:
- Hetzner Cloud (DE/FI)
- DigitalOcean (US-based)
- Linode / Akamai
- OVH (FR)

**Tier 5 — Sovereign EU**:
- Scaleway (FR)
- IONOS (DE)
- (+ Hetzner z Tier 2 jako EU sovereign)

Plus **Custom HTTP** dla każdego innego (np. lokalne providers, self-hosted
PaaS).

### 3.4.2. Cloud provider templates

Każdy cloud provider ma template (analogiczny do faz 2):

```yaml
provider_template_aws:
  id: aws
  display_name: Amazon Web Services
  category: cloud_enterprise
  website: https://aws.amazon.com
  
  authentication_methods:
    - type: access_key_secret  # most common
      config:
        - aws_access_key_id (string)
        - aws_secret_access_key (string, encrypted)
        - aws_region (string, default: eu-west-1)
    - type: iam_role  # for EC2-hosted AEIS
      config:
        - role_arn (string)
    - type: sso  # AWS IAM Identity Center
      config:
        - sso_start_url (URL)
        - sso_region (string)
  
  regions:
    - id: eu-west-1
      display: Ireland (Dublin)
      sovereignty: EU
      gdpr_friendly: true
    - id: eu-central-1
      display: Germany (Frankfurt)
      sovereignty: EU
      gdpr_friendly: true
    - id: eu-central-2
      display: Switzerland (Zurich)
      sovereignty: EU+CH
    - id: us-east-1
      display: USA (Virginia)
      sovereignty: US
      gdpr_friendly: false  # requires DPA
    # ... 30+ more regions
  
  instance_types:
    - id: t3.micro
      display: T3 Micro (2 vCPU, 1 GB RAM)
      cost_per_hour: 0.0104
      cost_per_month_estimated: 7.59
      good_for: [dev, light_workloads]
    - id: t3.medium
      display: T3 Medium (2 vCPU, 4 GB RAM)
      cost_per_hour: 0.0416
      cost_per_month_estimated: 30.37
      good_for: [staging, small_prod]
    # ... hundreds more
  
  services_supported:
    - ec2 (compute)
    - rds (databases)
    - s3 (storage)
    - lambda (serverless)
    - eks (kubernetes)
    - cloudfront (CDN)
    # ...
  
  cost_estimation:
    method: pricing_api  # AWS Pricing API
    free_tier_credit: $300 / 12 months (new accounts)
    typical_dev_cost: $20-50/month
    typical_prod_cost: $100-1000/month
  
  signup:
    url: https://aws.amazon.com/free
    requires_credit_card: true
    typical_time_to_first_resource: 30 min
```

### 3.4.3. Comparison między providers

```
┌──────────────────────────────────────────────────────────────┐
│  Cloud Providers — Quick Comparison                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Provider     Sovereign  Min cost      Setup    SLA          │
│  ────────── ─────────── ──────────── ──────── ───────────── │
│  AWS         EU regions  $7.59/mo    30 min   99.99%        │
│              available   (t3.micro)                          │
│  GCP         EU regions  $6.13/mo    25 min   99.95%        │
│              available   (e2-small)                          │
│  Azure       EU regions  $7.59/mo    30 min   99.95%        │
│              available   (B1s)                               │
│  Hetzner     EU only     €4.20/mo    10 min   99.5%         │
│              (DE/FI/PL)  (CX21)                              │
│  DO          EU regions  $6/mo       10 min   99.99%        │
│              (Frankfurt) (Basic)                             │
│  Linode      EU regions  $5/mo       10 min   99.99%        │
│              (Frankfurt) (Nanode)                            │
│  OVH         FR/DE/PL    €3.50/mo    20 min   99.99%        │
│              EU sovereign                                    │
│  Scaleway    FR sovereign €1.99/mo   15 min   99.95%        │
│  IONOS       DE sovereign €4.50/mo   20 min   99.95%        │
│  Hetzner     →           →           →        →             │
│                                                              │
│  Best for SYLION (Polish operator):                          │
│   • Local dev:           local-dev (free)                    │
│   • Cheap staging:       Scaleway / Hetzner                  │
│   • EU sovereign prod:   Hetzner (Warsaw) / IONOS (DE)       │
│   • Global scale:        AWS / GCP                           │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 3.4.4. Add cloud provider workflow (P3.7=d multi-method)

Operator klika "+ Add Cloud Provider — AWS":

#### Step 1: Authentication method choice

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Add AWS — Step 1/4: Authentication                       │
│                                                              │
│  Wybierz metodę autoryzacji:                                 │
│                                                              │
│  [● Access Key + Secret] (most common)                       │
│      Operator wkleja AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS   │
│      _KEY. AEIS storage encrypted (jak faza 2 sekrety).      │
│      Setup: 5 min. Recommended dla individual operators.     │
│                                                              │
│  [○ Use existing aws-cli configuration]                      │
│      AEIS używa twojego ~/.aws/credentials i profile.        │
│      Setup: 1 min. Wymaga skonfigurowanego aws-cli.          │
│                                                              │
│  [○ AWS IAM Identity Center (SSO)]                           │
│      Operator loguje się przez AWS SSO portal.               │
│      Setup: 10 min. Better dla teams z corporate AWS.        │
│                                                              │
│  [○ IAM Role (jeśli AEIS biegnie na EC2)]                    │
│      Brak credentials — używa instance role.                 │
│      Setup: assumes EC2 deployment (rzadki dla operator).    │
│                                                              │
│  [○ OAuth flow] (browser-based)                              │
│      Otwiera AWS console signin, AEIS dostaje temporary creds│
│      Setup: 5 min, ale temporary creds (re-auth periodically)│
│                                                              │
│                                          [Cancel]  [Next →]  │
└──────────────────────────────────────────────────────────────┘
```

#### Step 2: Credentials input (zależnie od method)

**Dla "Access Key + Secret"**:

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Add AWS — Step 2/4: Credentials                          │
│                                                              │
│  Wpisz AWS credentials:                                      │
│                                                              │
│  ┌── ACCESS KEY ID ─────────────────────────────────────┐    │
│  │  [ AKIAIOSFODNN7EXAMPLE                              ] │   │
│  │  ↑ format: AKIA... 20 chars                          │   │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌── SECRET ACCESS KEY ────────────────────────────────┐     │
│  │  [ ●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●● 👁 ]         │     │
│  │  ↑ format: 40 chars random                          │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                              │
│  ┌── DEFAULT REGION ───────────────────────────────────┐     │
│  │  [eu-west-1 ▼]                                      │     │
│  │  ↓ EU sovereign options:                            │     │
│  │   • eu-west-1 (Ireland) — recommended dla PL        │     │
│  │   • eu-central-1 (Frankfurt)                        │     │
│  │   • eu-central-2 (Zurich)                           │     │
│  │   • eu-north-1 (Stockholm)                          │     │
│  │   • eu-south-1 (Milan)                              │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                              │
│  ┌── ACCOUNT NICKNAME ────────────────────────────────┐      │
│  │  [ aws-sylion-main                              ]   │      │
│  │  ↑ display name dla tego account                    │      │
│  └────────────────────────────────────────────────────┘      │
│                                                              │
│  ⚠ Sugerowane uprawnienia minimum:                           │
│     • EC2: Run/Stop/Terminate instances                      │
│     • IAM: Read own permissions                              │
│     • S3: Read/Write specific buckets                        │
│     • Pricing API: Read                                      │
│                                                              │
│  AEIS NIE wymaga full admin access. Możesz utworzyć IAM      │
│  user z minimum permissions specific dla AEIS.               │
│                                                              │
│  [View suggested IAM policy JSON]                            │
│                                          [← Back]  [Test →]  │
└──────────────────────────────────────────────────────────────┘
```

#### Step 3: Test & validate

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Add AWS — Step 3/4: Validation                           │
│                                                              │
│  Testing credentials...                                      │
│                                                              │
│  ✓ Credentials valid                                         │
│  ✓ Account ID retrieved: 123456789012                        │
│  ✓ IAM user identified: aeis-operator                        │
│  ✓ Region accessible: eu-west-1                              │
│                                                              │
│  ⚠ Permission checks:                                        │
│   ✓ EC2 RunInstances permission                              │
│   ✓ EC2 DescribeInstances permission                         │
│   ✓ EC2 TerminateInstances permission                        │
│   ✓ S3 read/write permission                                 │
│   ✗ IAM ListUsers permission (not granted, OK dla AEIS)     │
│   ✓ Pricing API access                                       │
│                                                              │
│  Account info:                                               │
│   • Account name: sylion-main                                │
│   • Free tier: 8 months remaining                            │
│   • Current spend (this month): $12.40                       │
│   • Spending limit: not set                                  │
│                                                              │
│  ⚠ Warning: brak budgeting alert w AWS account               │
│     Recommendation: ustaw AWS Budgets dla cost control       │
│     [Open AWS Budgets console]                               │
│                                                              │
│                                       [← Back]  [Save →]    │
└──────────────────────────────────────────────────────────────┘
```

#### Step 4: Save & next steps

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Add AWS — Step 4/4: Saved                                │
│                                                              │
│  ✓ AWS provider added successfully                           │
│                                                              │
│  Provider: aws-sylion-main                                   │
│  Account: 123456789012                                       │
│  Default region: eu-west-1                                   │
│  Credentials: encrypted in workspace                         │
│                                                              │
│  Capabilities unlocked:                                      │
│   ✓ Create EC2 instances                                     │
│   ✓ Use S3 for storage                                       │
│   ✓ Deploy Docker containers (via ECS or EC2)                │
│   ✓ Lambda functions                                         │
│   ✓ Multi-region deployments                                 │
│                                                              │
│  Suggested next steps:                                       │
│                                                              │
│  [● Create first AWS environment]                            │
│      Wizard: choose instance type, region, purpose           │
│                                                              │
│  [○ Configure cost limits dla AWS]                           │
│      Set monthly cap, alerts                                 │
│                                                              │
│  [○ Add more cloud providers]                                │
│      Operator może chcieć multi-cloud setup                  │
│                                                              │
│  [○ Skip — done with AWS for now]                            │
│                                                              │
│                                                              │
│                                                  [Continue]  │
└──────────────────────────────────────────────────────────────┘
```

### 3.4.5. Multi-region / multi-account (P3.8=a — jeden provider z drilldown)

Operator wybrał **jeden "AWS provider" z multiple regions/accounts wewnątrz**.

UI hierarchy:

```
AWS (provider entry)
  ├── Account: aws-sylion-main (123456789012)
  │     ├── Region: eu-west-1
  │     │     ├── Environment: prod-web
  │     │     ├── Environment: prod-db
  │     │     └── Environment: staging
  │     └── Region: us-east-1
  │           └── Environment: backup-region
  ├── Account: aws-customer-acme (987654321098)
  │     └── Region: eu-central-1
  │           └── Environment: customer-acme-prod
  └── Account: aws-personal (456789012345)
        └── Region: eu-west-1
              └── Environment: personal-experiments
```

**Add account workflow**:

```
AWS provider page → "+ Add another account"

┌────────────────────────────────────────────────────────┐
│  Add additional AWS account                            │
│                                                        │
│  Existing accounts:                                    │
│   • aws-sylion-main (default)                          │
│   • aws-customer-acme                                  │
│                                                        │
│  Add new:                                              │
│   Account nickname: [ _____________ ]                  │
│   Auth method: [Access Key ▼]                          │
│   Credentials: ___                                     │
│   Default region: ___                                  │
│                                                        │
│  Tags (optional):                                      │
│   [ ☐ Customer ☐ Personal ☐ Backup ☐ Production ]      │
│                                                        │
│  [Cancel]  [Test & Save]                               │
└────────────────────────────────────────────────────────┘
```

**Account switching** w deploy decisions: gdy operator deploy'uje, wybiera
provider → account → region → environment z drilldown.

### 3.4.6. Provider-specific quirks

Każdy provider ma własne specyfiki które AEIS handle'uje:

```
HETZNER:
  - SSH key required przed first instance
  - Floating IPs separate billing
  - Storage volumes separate od instance
  - Network model: simple (single network per project)

AWS:
  - VPC mandatory (auto-creates default jeśli nie ma)
  - Security groups (firewall rules)
  - Pricing very granular (data transfer charges visible)
  - Multi-AZ recommendations dla prod

GCP:
  - Service accounts dla auth (preferred over user keys)
  - Project ID required
  - Billing account separation

Azure:
  - Resource groups required
  - Subscription model
  - Tenant ID + subscription ID complexity

Scaleway:
  - Project ID required
  - Multi-zone w each region
  - Polish IPv6 support good

OVH:
  - Public Cloud vs Bare Metal differences
  - GRA/SBG/WAW datacenters
  - Private network configuration
```

AEIS pokazuje provider-specific tips w UI gdy operator dodaje:

```
ℹ Hetzner-specific tips:

  Przed first instance:
   1. Add SSH public key do account
   2. AEIS może zrobić to za ciebie:
      [Auto-add my ~/.ssh/id_ed25519.pub]
   
  Cost notes:
   • Floating IPs: €1/month + €0.0011/h
   • Volumes: €0.04/GB/month
   • Snapshots: €0.013/GB/month
   • Backups: 20% z instance cost
   • Network traffic: 20 TB included w larger plans
   
  Recommendations dla SYLION operator:
   • CX21 dla staging (€4.20/mo)
   • CX31 dla prod (€8.40/mo)
   • Region warsaw-1 dla EU sovereignty
```

---

## 3.5. Sovereign environments (P3.9=d wszystkie 3 typy)

### 3.5.1. Trzy typy sovereign

#### Typ 1: Cloud z dedykowaną EU/PL lokalizacją

**Definicja**: cloud provider który gwarantuje że dane operatora pozostają
w określonej jurysdykcji (najczęściej EU, czasem PL).

**Przykłady**:
- Hetzner Warsaw (Polska sovereignty)
- Hetzner Falkenstein/Nuremberg (DE)
- IONOS (DE)
- Scaleway Paris (FR)
- AWS eu-central-1/eu-west-1 z DPA

**Workflow w AEIS**:

```
┌──────────────────────────────────────────────────────────────┐
│  Configure EU Sovereign Environment                          │
│                                                              │
│  Provider: Hetzner                                           │
│  Region: warsaw-1 (Polska)                                   │
│                                                              │
│  Sovereignty details:                                        │
│   ✓ Servers fizycznie w Polsce                               │
│   ✓ Operator: Hetzner Online GmbH (DE-based, EU sovereign)   │
│   ✓ Data processing: EU + DPA available                      │
│   ✓ GDPR compliant                                           │
│   ⚠ Hetzner DE entity → German law applies dla company-level │
│                                                              │
│  Compliance attestations:                                    │
│   ✓ ISO 27001                                                │
│   ✓ SOC 2 Type II                                            │
│   ⚠ Polish-specific: nie ma Polish gov certification         │
│                                                              │
│  Recommended dla:                                            │
│   • PL business apps (commercial)                            │
│   • EU customer data                                         │
│   • Standard GDPR compliance                                 │
│                                                              │
│  NOT recommended dla:                                        │
│   • Polish government workloads (require Polish operator)    │
│   • Classified material (TLP:RED)                            │
│   • Critical national infrastructure                         │
│                                                              │
│  [Confirm sovereignty profile]                               │
└──────────────────────────────────────────────────────────────┘
```

#### Typ 2: On-premise hardware

**Definicja**: fizyczny serwer u klienta (lub w biurze operatora). Pełna
kontrola operatora nad fizycznym hardware.

**Use cases**:
- Atelier krawieckie ma serwer w warsztacie (production tracking)
- Kancelaria prawna ma server-room w biurze (private case data)
- Government agency ma sovereign on-prem (security clearance required)

**Setup workflow**:

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Add On-Premise Environment                               │
│                                                              │
│  Step 1: Identify on-prem server                             │
│                                                              │
│  Connection method:                                          │
│  [● SSH (most common)]                                       │
│      Connect via SSH z local network (VPN required dla      │
│      remote access).                                         │
│                                                              │
│  [○ Direct API (jeśli on-prem ma orchestrator)]              │
│      Proxmox, Nutanix, OpenStack etc.                        │
│                                                              │
│  [○ Manual deploy (operator runs scripts)]                   │
│      AEIS generuje scripts, operator uruchamia ręcznie       │
│      Bez direct connection (best dla air-gapped przygotowania)│
│                                                              │
│                                                              │
│  Server details:                                             │
│   IP / hostname:    [ 192.168.10.50          ]               │
│   SSH port:         [ 22 ]                                   │
│   SSH username:     [ aeis                    ]              │
│   SSH key:          [Use ~/.ssh/id_ed25519 ▼]                │
│                                                              │
│   Server location:  [Office basement, Warsaw ▼]              │
│   Owner:            [Operator's company       ]              │
│   Compliance tier:  [PL Gov classified ▼]                    │
│                                                              │
│  Network access:                                             │
│   ☑ Accessible from local LAN                                │
│   ☐ VPN required dla external access                         │
│   ☐ Air-gapped (no internet)                                 │
│                                                              │
│                                                              │
│  [Cancel]  [Test SSH connection]                             │
└──────────────────────────────────────────────────────────────┘
```

**Validation flow**:

```
Testing SSH connection to 192.168.10.50:22...

  ✓ Network reachable (ping OK, latency 1.2ms)
  ✓ SSH port open
  ✓ Key-based auth successful (aeis@server)
  ✓ Sudo access (passwordless): yes
  ✓ Disk space: 480 GB free / 2 TB total
  ✓ RAM: 32 GB total
  ✓ CPU: Intel Xeon E5-2680 v4 (28 threads)
  ✓ OS: Ubuntu 22.04 LTS
  ✓ Docker: installed (24.0.5)
  ⚠ Updates available: 12 packages (security patches)
  
  Suggested next:
   [Auto-update packages] (5 min)
   [Skip — operator manages updates separately]
```

#### Typ 3: Air-gapped environment

**Definicja**: środowisko bez internetu. Deploy przez offline package
delivery (USB stick, secure courier, internal network only).

**Use cases**:
- Polish government TLP:RED workloads
- Defense systems
- Critical infrastructure (energy grid, telecom)
- Customer's secure facility

**Setup workflow**:

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Add Air-Gapped Environment                               │
│                                                              │
│  ⚠  Air-gapped setup wymaga special handling                 │
│                                                              │
│  AEIS NIE może bezpośrednio zarządzać tym environment.       │
│  Operator pełni rolę bridge między AEIS a air-gapped infra.  │
│                                                              │
│  Workflow pattern:                                           │
│                                                              │
│  ┌────────────┐         ┌────────────┐         ┌──────────┐ │
│  │   AEIS     │  ───→   │  Operator  │  ───→   │ Air-gap  │ │
│  │ (online)   │         │   (USB)    │         │ (secure) │ │
│  └────────────┘         └────────────┘         └──────────┘ │
│                                                              │
│  1. AEIS generuje deploy package (artifacts + manifests)     │
│  2. Operator transfer-uje package przez physical media       │
│  3. Air-gapped system installs package                       │
│  4. Operator brings back logs/status (manual sync)           │
│                                                              │
│  Configuration:                                              │
│                                                              │
│   Environment name: [ _____________ ]                        │
│   Owner organization: [ _____________ ]                      │
│   Security classification: [ TLP:RED ▼ ]                     │
│   Sync frequency:           [ Manual ▼ ]                     │
│   Package format:           [ tar.gz + signed manifest ▼ ]   │
│                                                              │
│  Capabilities expected (operator declares):                  │
│   ☑ Linux server                                             │
│   ☑ Docker                                                   │
│   ☐ Kubernetes                                               │
│   ☐ Custom orchestration (specify)                           │
│                                                              │
│  Restrictions enforced przez AEIS:                           │
│   ✓ NIE wysyła telemetrii o tym environment                  │
│   ✓ NIE wysyła deploy artifacts do external services         │
│   ✓ Generates packages w isolated workspace                  │
│   ✓ Audit chain entries marked as "air_gapped"               │
│                                                              │
│  [Cancel]  [Configure air-gap environment]                   │
└──────────────────────────────────────────────────────────────┘
```

**Air-gap deploy workflow** (used in faza 39 Deployment Configuration):

```
1. Operator selects target: air-gap-customer-x

2. AEIS builds deploy package:
   • Container images (saved as .tar)
   • Configuration files
   • Migration scripts
   • Signed manifest (cryptographic provenance)
   • Installation instructions
   
3. Package output:
   /workspace/deployments/2026-04-29-air-gap-customer-x/
     ├── images/
     │   ├── frontend.tar
     │   ├── backend.tar
     │   └── postgres.tar
     ├── config/
     │   └── env.yaml
     ├── scripts/
     │   ├── install.sh
     │   ├── verify.sh
     │   └── rollback.sh
     ├── manifest.json (signed)
     └── README.md (operator instructions)

4. Operator transfers via USB / secure courier

5. Air-gapped system: operator runs install.sh, then verify.sh

6. Operator brings back status report (logs, healthcheck output)

7. AEIS imports status: marks deployment as confirmed
```

### 3.5.2. Sovereignty enforcement w AEIS

System może auto-route projekty per classification:

```
Settings → Sovereignty Rules

  Auto-routing rules:
   ☑ TLP:RED projects → air-gapped or sovereign on-prem only
   ☑ Polish gov classified → Polish data centers only
   ☑ EU GDPR PII → EU regions only
   ☐ Customer-specific isolation (per project flag)
  
  Default sovereignty preference (no project rule):
   [● Allow any region (operator decides per project)]
   [○ Prefer EU sovereign by default]
   [○ Strict EU only (block non-EU regions)]
  
  Conflict resolution:
   When project rule conflicts with environment:
    [● Block deploy, require operator override]
    [○ Warn operator but allow]
    [○ Auto-redirect do compliant environment]
```

---

## 3.6. Edge devices (P3.10=c Linux-based + P3.11=d multi-method)

### 3.6.1. Wspierane edge platforms

Operator wybrał **wszystko Linux-based**: Pi + ARM + Intel NUC + małe x86.

**Kategorie edge devices**:

```
RASPBERRY PI family:
  • Pi 4 (4GB / 8GB) — najpopularniejsze
  • Pi 5 (4GB / 8GB) — newer, faster
  • Pi Zero 2 W — bardzo małe, ARM
  • Compute Module 4 — embedded form factor

OTHER ARM SBC:
  • Orange Pi (5, 5 Plus) — alternatywa Pi
  • Banana Pi
  • Rock Pi (Radxa)
  • NVIDIA Jetson (Nano, Orin) — z GPU dla edge AI

INTEL NUC / MINI PC:
  • NUC 11/12/13 — bardziej powerful
  • Beelink mini PCs
  • Generic Intel-based mini systems

INDUSTRIAL / IoT:
  • Industrial PC (Advantech, Siemens)
  • Edge gateways (Cisco, Dell)
  • Custom hardware z Linux

KORZYSTNE WSPÓLNE CECHY (wszystkie):
  • Linux OS (Ubuntu, Debian, Raspberry Pi OS, Yocto)
  • SSH access
  • Docker support (most)
  • Persistent storage
  • Network capability
  • Min 1 GB RAM (rekomendowane 2+ GB)
```

### 3.6.2. Edge use cases dla SYLION

```
ATELIER KRAWIECKIE (sylion-tailor production):
  Hardware: Raspberry Pi 4
  Purpose: production tracking dashboard
  Apps: web frontend + local SQLite + sync
  Connection: WiFi z biura
  
KANCELARIA PRAWNA (sovereign endpoint):
  Hardware: Intel NUC 13
  Purpose: confidential document processing
  Apps: local CRM + GDPR-compliant storage
  Connection: VPN do central infra
  
FACTORY MONITORING:
  Hardware: Industrial PC (Advantech)
  Purpose: machine monitoring + predictive maintenance
  Apps: data collector + edge ML inference
  Connection: GSM + satellite backup
  
RETAIL POS:
  Hardware: Pi 5 + touchscreen
  Purpose: kiosk POS w sklepie
  Apps: catalog + payment + inventory sync
  Connection: WiFi store
```

### 3.6.3. Edge add workflow (P3.11=d multi-method)

Operator wybrał **multi-method** — może wybrać per device:

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Add Edge Device                                          │
│                                                              │
│  Wybierz metodę pairing:                                     │
│                                                              │
│  [● SSH connection (most common)]                            │
│      Operator wpisuje IP + SSH key                           │
│      AEIS connect i zarządza                                 │
│      Wymaga: device już skonfigurowane (Linux + SSH)         │
│      Setup: 5 min                                            │
│                                                              │
│  [○ Provisioning script]                                     │
│      AEIS generuje bash script                               │
│      Operator uruchamia na device (manually albo via curl)  │
│      Device łączy się back do AEIS                           │
│      Setup: 10 min, ale zero pre-config wymagane            │
│                                                              │
│  [○ QR code pairing]                                         │
│      Device wyświetla QR code (wymaga preinstalled agent)    │
│      Operator skanuje w AEIS UI                              │
│      Auto-pairing                                            │
│      Setup: 2 min, ale wymaga AEIS agent preinstalled        │
│                                                              │
│  [○ Bulk import (CSV)]                                       │
│      Operator ma 50 devices, importuje listę z CSV           │
│      Każde device musi być pre-configured                    │
│      Setup: 30 min dla 50 devices                            │
│                                                              │
│  [○ Auto-discovery (mDNS/SSDP)]                              │
│      AEIS skanuje LAN dla devices ogłaszających siebie       │
│      Wymaga: device runs AEIS edge agent                     │
│      Setup: 1 min                                            │
│                                                              │
│                                          [Cancel]  [Next →]  │
└──────────────────────────────────────────────────────────────┘
```

### 3.6.4. SSH connection method (most common)

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Add Edge Device — SSH Method                             │
│                                                              │
│  Device details:                                             │
│                                                              │
│   Display name:        [ rpi-fabryka-1            ]          │
│   Hostname/IP:         [ 192.168.50.10            ]          │
│   SSH port:            [ 22 ]                                │
│   SSH username:        [ pi                        ]         │
│   Authentication:      [● Key file] [○ Password]             │
│   SSH key path:        [ ~/.ssh/id_ed25519        ] [Browse] │
│                                                              │
│  Device classification:                                      │
│   Type:                [ Raspberry Pi 4 ▼ ]                  │
│   Architecture:        [ ARM 64 (auto-detected) ]            │
│   Purpose:             [ Atelier production tracking ▼ ]     │
│   Location:            [ Klient: Tailor Master, Warsaw ▼ ]   │
│   Owner:               [ Customer (atelier) ]                │
│                                                              │
│  Network configuration:                                      │
│   ☑ Accessible from operator's VPN                           │
│   ☐ Public IP (operator manages firewall)                    │
│   ☐ Behind NAT (requires reverse-tunnel from device)         │
│                                                              │
│  Capabilities:                                               │
│   ☑ Docker                                                   │
│   ☐ Kubernetes (k3s)                                         │
│   ☐ GPU (Jetson family)                                      │
│                                                              │
│  Resource expectations:                                      │
│   RAM:     [ 4 GB ▼ ]                                        │
│   Storage: [ 32 GB SD ▼ ]                                    │
│                                                              │
│  Auto-update policy:                                         │
│   [● OS updates: weekly automatically]                       │
│   [○ Manual updates only]                                    │
│   [○ Per-package approval]                                   │
│                                                              │
│  Sync strategy:                                              │
│   [● Periodic sync (every 5 min)]                            │
│   [○ Real-time (WebSocket persistent)]                       │
│   [○ On-demand only (manual sync)]                           │
│                                                              │
│  [Cancel]  [Test SSH & Save]                                 │
└──────────────────────────────────────────────────────────────┘
```

**Test result**:

```
Testing SSH connection to 192.168.50.10:22 jako pi...

  ✓ Network reachable (latency 8.2ms via VPN)
  ✓ SSH port open
  ✓ Key auth successful
  ✓ Sudo access: yes (passwordless)
  ✓ OS: Raspberry Pi OS 12 (Bookworm)
  ✓ Architecture: ARM 64
  ✓ RAM: 3.7 GB available (4 GB total)
  ✓ Storage: 24 GB free / 32 GB
  ✓ Docker: 24.0.5
  ✗ Kubernetes: not installed
  ✓ Network: WiFi connected (SSID: TailorMasterWiFi)
  ✓ Internet: yes
  ⚠ System updates available: 8 packages
  
  Recommendations:
   ☑ Install AEIS agent (lightweight, 50 MB) — enables features:
      • Real-time monitoring
      • Auto-rollback on healthcheck failure
      • Encrypted log shipping
      • Hardware anomaly detection
   
   [Install agent now]  [Install later]  [Skip — basic SSH only]

```

### 3.6.5. Edge device dashboard

Po dodaniu, operator widzi edge devices w dashboard:

```
┌──────────────────────────────────────────────────────────────┐
│  Edge Devices                                  [+ Add Device]│
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Name              Type        Purpose             Status   │
│  ──────────────── ─────────── ──────────────────── ──────── │
│  rpi-fabryka-1    Pi 4 4GB    Atelier production   ✓ Online │
│  rpi-fabryka-2    Pi 5 8GB    Backup display       ✓ Online │
│  nuc-kancelaria   NUC 13      Confidential storage ⚠ Slow   │
│  jetson-monitor   Jetson Orin Edge ML inference    ✓ Online │
│  pos-store-warsa  Pi 5 8GB    Retail POS           ✗ Offline│
│                                                              │
│  Total: 5 devices · 4 online · 1 offline                     │
│  Average uptime (30d): 98.2%                                 │
│                                                              │
│  ✗ pos-store-warsa offline since 14 hours                    │
│     [Diagnose]  [Notify customer]  [Disable temporarily]    │
│                                                              │
│  ⚠ nuc-kancelaria network slow (latency 850ms vs 45ms norm)  │
│     [Investigate]  [Mark as known issue]                     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## Status Część 1

🟢 **Sekcje 3.1-3.6 complete** — architektura środowisk, auto-detection,
cloud providers, sovereign types, edge devices.

**Część 1 zawiera**:
- ✓ Sense fazy + miejsce w cyklu (3.1)
- ✓ Architektura środowisk — 3-poziom hierarchia + 3 widoki toggle (3.2)
- ✓ Auto-detection — szerokie scan + cloud CLI tools detection (3.3)
- ✓ Cloud providers — 10 providers w 3 tiers + multi-method auth (3.4)
- ✓ Sovereign environments — 3 typy (cloud-EU, on-prem, air-gapped) (3.5)
- ✓ Edge devices — Linux-based + 5 paring methods (3.6)

**Część 2 będzie zawierała**:
- Sekcja 3.7: Network topology + federation (mesh vs hub-and-spoke vs isolated)
- Sekcja 3.8: VPN / network policy (per-environment configuration)
- Sekcja 3.9: Data residency enforcement (per-project, GDPR, classification)
- Sekcja 3.10: Cost tracking per environment (3 levels granularity)
- Sekcja 3.11: Cleanup policy (per-environment, auto, conditional)
- Sekcja 3.12: Edge cases (30 cases w 6 hybrid kategoriach)
- Sekcja 3.13: Inheritance + acceptance criteria + DoD

⏳ **Po Twojej akceptacji części 1** → piszę część 2.

**Daj feedback**:
- "OK kontynuuj" → idę pisać część 2
- "Zmień X w części 1" → modyfikacja przed częścią 2
- "Dorzuć Y" → ekspansja konkretnej sekcji
