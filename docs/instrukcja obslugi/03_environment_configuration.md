# FAZA 3 — Environment Configuration

> **Status**: 🟢 Active draft (przed soft-freeze)
> **Grupa**: A — Przygotowanie Operatora (3 z 11)
> **Typ**: iteracyjna, operator wraca w cyklu projektów
> **Czas wykonania**: 5 min (sam laptop) / 30 min (1-2 cloud providers) / godziny (multi-cloud + edge + sovereign)
> **D-level**: D2 — środowiska deploy mają znaczenie kosztowe i operacyjne
> **Zależności**: Faza 1 zakończona; Faza 2 zalecana (providers LLM dla auto-deploy testów)
> **Następnik**: Faza 4 (Workspace Defaults)
>
> **Spis sekcji**:
> - 3.1 — Sense fazy i jej miejsce w cyklu
> - 3.2 — Architektura środowisk (3 widoki z toggle)
> - 3.3 — Auto-detection środowisk (szerokie scan + cloud CLI detection)
> - 3.4 — Cloud providers (10 providers w 3 tiers, multi-region/account)
> - 3.5 — Sovereign environments (3 typy: cloud-EU, on-prem, air-gapped)
> - 3.6 — Edge devices (Linux-based: Pi/ARM/NUC/industrial, 5 paring methods)
> - 3.7 — Network topology + federation (4 modele: isolated/mesh/hub-spoke/custom)
> - 3.8 — VPN / Network policy (per-environment WireGuard + firewall rules)
> - 3.9 — Data residency enforcement (per-project rules + audit trail)
> - 3.10 — Cost tracking per environment (3 levels: provider/env/resource)
> - 3.11 — Cleanup policy (4 strategies: manual/auto-N-hours/conditional/schedule)
> - 3.12 — Edge cases (30 cases w 6 hybrid kategoriach)
> - 3.13 — Inheritance + DoD + acceptance criteria

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

---

## 3.7. Network topology + federation (P3.12=d konfigurowalne)

### 3.7.1. Cztery modele topologii

Operator wybrał **konfigurowalne** — system oferuje 4 modele, operator wybiera.

#### Model A — Isolated (default)

**Każde środowisko jest niezależne**. AEIS koordynuje przez API calls do
każdego oddzielnie. Brak bezpośredniej komunikacji między środowiskami.

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  AEIS    │     │ local-dev│     │ Hetzner  │     │ Edge RPi │
│ (laptop) │ ──→ │          │     │ prod     │     │          │
│          │ ──→ │          │     │          │     │          │
│          │ ──→ │          │     │          │     │          │
│          │ ──→ │          │     │          │     │          │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
     ↓                                                       
   API calls każdy z osobna, środowiska nie wiedzą o sobie
```

**Pros**:
- Najprostszy setup (zero network config)
- Najbezpieczniejszy (brak ataków cross-environment)
- Każde środowisko niezależne (nie ma single point of failure)

**Cons**:
- AEIS musi proxy data między środowiskami (wolniej)
- Brak natural multi-environment workflows
- Multi-cloud orchestration manual

**Best for**: początkujący operator, single-environment projekty, security-first.

#### Model B — Mesh network

**Wszystkie środowiska gadają ze sobą bezpośrednio**. AEIS instaluje
WireGuard albo Tailscale, środowiska tworzą mesh.

```
              ┌──────────┐
              │  AEIS    │
              │ (laptop) │
              └────┬─────┘
                   │ mesh
                   │
        ┌──────────┼──────────┐
        │          │          │
        ↓          ↓          ↓
  ┌─────────┐ ┌─────────┐ ┌─────────┐
  │ local-  │ │ Hetzner │ │ Edge    │
  │ dev     │←→│ prod    │←→│ RPi     │
  │         │ │         │ │         │
  └─────────┘ └─────────┘ └─────────┘
        ↑          ↑          ↑
        └──────────┴──────────┘
            mesh network
```

**Pros**:
- Bezpośrednia komunikacja (low latency)
- Multi-environment workflows natural
- Edge devices accessible nawet zza NAT (mesh handles)
- Single VPN auth dla wszystkiego

**Cons**:
- Każdy node musi być reachable (firewall config)
- Wymaga management plane (Tailscale account, lub self-hosted Headscale)
- Nieco większy attack surface

**Best for**: multi-environment projekty, edge orchestration, dev teams.

#### Model C — Hub-and-spoke

**Laptop operatora to hub**, wszystkie środowiska podłączają się do niego
jako spokes.

```
                ┌──────────┐
                │  AEIS    │
        ┌──────→│ (laptop) │←──────┐
        │       │   HUB    │       │
        │       └────┬─────┘       │
        │            │             │
   ┌────────┐  ┌────────────┐  ┌────────┐
   │ local- │  │  Hetzner   │  │ Edge   │
   │ dev    │  │  prod      │  │ RPi    │
   │        │  │  (spoke)   │  │ (spoke)│
   └────────┘  └────────────┘  └────────┘
        Spokes nie gadają między sobą
```

**Pros**:
- Centralny control point (laptop)
- Łatwa audytowalność (wszystko przez hub)
- Operator zawsze "w środku"

**Cons**:
- Single point of failure (gdy laptop down → wszystko down)
- Latencja: dwa hops (spoke → hub → spoke)
- Hub musi być always-on (problematyczne dla mobile operator)

**Best for**: małe teams, security audits requiring central choke point.

#### Model D — Custom/hybrid

**Operator definiuje per-environment policy**. Niektóre w mesh, inne
isolated, edge przez hub-and-spoke.

```
        Hetzner prod ←→ AWS prod          (mesh)
                          ↓
                        AEIS                
                          ↓
                     local-dev             (hub)
                          ↓
                       Edge RPi           (hub)
        
        Customer X on-prem      (isolated, manual SSH)
```

**Pros**:
- Maximum flexibility
- Każdy environment dobrane podejście

**Cons**:
- Complex to manage
- Wymaga zrozumienia networking

**Best for**: zaawansowani operatorzy, multi-customer setups.

### 3.7.2. Konfiguracja per środowisko

W settings każdego środowiska:

```
Edit environment: hetzner-prod
─────────────────────────────────────

Network mode:
  [● Isolated]  
      Connect via direct API calls (z laptop AEIS)
      No persistent network connection

  [○ Mesh member]
      Join mesh network (Tailscale / WireGuard)
      Tailscale account: [robert@sylion.dev ▼]
      Auto-connect on boot: ☑
      ACLs: [Default — restrictive ▼]

  [○ Hub-and-spoke (spoke)]
      Hub: [aeis-laptop ▼]
      Connect via: WireGuard
      Auto-connect: ☑

  [○ Custom]
      [Edit network policy JSON]

Connectivity test:
  [Run network diagnostic]
```

### 3.7.3. Federation use cases

**Use case 1: Multi-cloud HA**

Sylion Tailor production deploy na 2 cloud providers (Hetzner + Scaleway)
dla redundancy. Mesh enables direct sync między nimi.

```
Hetzner prod (warsaw-1) ←─── mesh ───→ Scaleway prod (paris)
        ↓                                       ↓
  Active traffic 80%                  Active traffic 20%
                  + DB replication via mesh
```

**Use case 2: Edge fleet management**

50 atelier krawieckich, każdy ma RPi. Mesh pozwala AEIS-owi managować
wszystkimi z jednego miejsca, bez wymagania że atelier ma static IP /
public access.

```
                    AEIS hub
                       ↑
                    mesh
              ┌────────┼────────┐
              ↓        ↓        ↓
            RPi-1    RPi-2    RPi-3 ... RPi-50
        (atelier1)(atelier2)(atelier3)
```

Nawet jeśli atelier 23 jest za NAT routera bez public IP — mesh
(Tailscale-style) handles routing.

**Use case 3: Customer's on-prem + sovereign cloud**

Klient ma serwer on-prem (zaufany sovereign), ale AEIS zarządza nim z
sovereign cloud środowiska. Mesh tylko między tymi dwoma środowiskami,
isolated od reszty operator's infra.

### 3.7.4. Mesh providers comparison

```
┌──────────────────────────────────────────────────────────────┐
│  Mesh Network Providers                                      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Provider        Type        Cost       Setup    Sovereign  │
│  ─────────────── ─────────── ────────── ─────── ─────────── │
│  Tailscale       SaaS        Free <100  Easy    US-based ⚠  │
│                              dev, $5+/u                      │
│  Headscale       Self-host   Free       Medium  Operator-r. │
│                              (own VPS)                       │
│  Netbird         SaaS+OSS    Free <50,  Easy    EU sov. ✓   │
│                              €5+/user                        │
│  ZeroTier        SaaS        Free <25,  Easy    US-based ⚠  │
│                              $4+/u                           │
│  WireGuard raw   Self-host   Free       Hard    Operator-r. │
│                              (manual)                        │
│  Nebula          Self-host   Free       Medium  Operator-r. │
│                                                              │
│  Recommended dla SYLION operator:                            │
│   • Tailscale dla quick setup, EN-side acceptable             │
│   • Headscale dla EU sovereignty (self-hosted)                │
│   • Netbird dla EU sovereign + managed                        │
│   • Raw WireGuard dla zaawansowanych power-users             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 3.8. VPN / Network policy (P3.13=c VPN opcjonalne)

### 3.8.1. VPN per środowisko

Operator wybrał **VPN opcjonalne — operator może enable per środowisko**.

UI per environment:

```
Edit environment: hetzner-prod → Network → VPN

  VPN status:    [○ Disabled (direct internet)]
                 [● WireGuard tunnel]
                 [○ OpenVPN]
                 [○ Tailscale (uses mesh)]
                 [○ Custom]

  WireGuard config:
   Interface name: [wg-aeis        ]
   Listen port:    [51820 ]
   Private key:    [generated, encrypted ✓]
   Public key:     [Q3xKdf...           ] [Copy]
   Allowed IPs:    [10.0.0.0/24 ]
   
   Peers:
    [+ Add peer]
    
    Peer 1: aeis-laptop
       Public key: nm8H...
       Allowed IPs: 10.0.0.1/32
       Endpoint: dynamic (laptop NAT)
       
    Peer 2: rpi-fabryka-1
       Public key: 4j5K...
       Allowed IPs: 10.0.0.10/32
       Endpoint: 192.168.50.10:51820
       
  Auto-connect on boot:  ☑
  Restart on disconnect:  ☑
  Health check:
    Interval: [30s ▼]
    Failure action: [Notify operator ▼]
```

### 3.8.2. Firewall rules per environment

```
Edit environment: hetzner-prod → Network → Firewall

  Inbound rules:
  ┌──────────────────────────────────────────────────────────┐
  │  Port    Protocol  Source                  Action        │
  │  ─────── ───────── ───────────────────────  ──────────── │
  │  22      TCP       VPN-only (10.0.0.0/24)   ✓ Allow      │
  │  80      TCP       Anywhere                 ✓ Allow      │
  │  443     TCP       Anywhere                 ✓ Allow      │
  │  5432    TCP       VPN-only                 ✓ Allow      │
  │  6379    TCP       VPN-only                 ✓ Allow      │
  │  *       Any       Anywhere                 ✗ Deny       │
  └──────────────────────────────────────────────────────────┘
  
  Outbound rules:
  ┌──────────────────────────────────────────────────────────┐
  │  Port    Protocol  Destination              Action       │
  │  ─────── ───────── ───────────────────────  ──────────── │
  │  53      UDP       Anywhere                 ✓ Allow (DNS)│
  │  443     TCP       *.anthropic.com          ✓ Allow      │
  │  443     TCP       *.openai.com             ✓ Allow      │
  │  443     TCP       *.amazonaws.com          ✓ Allow      │
  │  443     TCP       Anywhere                 ✓ Allow      │
  │  *       Any       Anywhere                 ✗ Deny       │
  └──────────────────────────────────────────────────────────┘
  
  Templates:
   [Apply: Web server (80/443 public)]
   [Apply: Database (VPN-only)]
   [Apply: Strict (deny all + manual whitelist)]
   [Apply: Edge device (outbound-only)]
   
  [Save firewall rules]  [Validate]
```

### 3.8.3. Network monitoring

```
┌──────────────────────────────────────────────────────────────┐
│  Network Health — All environments                           │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Environment         VPN      Latency     Packet loss  Usage│
│  ──────────────────  ───────  ───────────  ─────────── ────  │
│  local-dev           none     n/a          n/a         n/a   │
│  hetzner-prod        ✓ WG     12ms         0.0%        3 GB  │
│  scaleway-prod       ✓ WG     45ms         0.1%        1 GB  │
│  rpi-fabryka-1       ✓ Tail   180ms ⚠      2.3% ⚠      0.1G  │
│  customer-acme-prod  ✓ WG     8ms          0.0%        50 GB │
│                                                              │
│  ⚠ rpi-fabryka-1 ma elevated packet loss (2.3%)              │
│     Możliwe: WiFi interference w atelier                     │
│     [Investigate]  [Suggest customer use cable]              │
│                                                              │
│  Bandwidth this month:                                       │
│   Total inbound: 47 GB                                       │
│   Total outbound: 12 GB                                      │
│   Costs (Hetzner): €0 (within 20 TB included)                │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 3.9. Data residency enforcement (P3.14=d per project)

### 3.9.1. Residency rules per project

Operator wybrał **per-project enforcement** — każdy projekt może mieć
własne residency rules.

W fazie 17 (Project Configuration), operator definiuje:

```
Project: Sylion Tailor → Data Residency

  Compliance profile:    [GDPR + Polish data law ▼]
  
  Allowed regions:
   ☑ EU (general)
   ☑ Polska (preferred)
   ☐ USA  
   ☐ UK (post-Brexit)
   ☐ Switzerland
   ☐ Anywhere (no restrictions)
  
  Hard requirements:
   ✗ NIE allow USA regions dla customer PII
   ✗ NIE allow non-EU storage dla payment data
   ✓ Allow USA for marketing assets (no PII)
   
  Per-data-class rules:
   PII (customer data):    EU only (Hetzner / Scaleway / IONOS / OVH)
   Payment tokens:         EU + DPA only
   Marketing assets:       Anywhere
   Server logs:            EU only
   ML training data:       EU + sovereign only
   
  Sub-processor disclosure:
   ☑ Inform customers o which providers process their data
   ☑ Update Privacy Policy gdy nowy provider added
  
  [Save residency profile]
```

### 3.9.2. Enforcement scenarios

**Scenario 1: Operator próbuje deploy do AWS us-east-1**

Projekt ma rule "PII to EU only", operator wybiera AWS us-east-1 dla
deployment:

```
┌──────────────────────────────────────────────────────────────┐
│  ⚠  Data Residency Violation Blocked                         │
│                                                              │
│  Project: Sylion Tailor                                      │
│  Project rule: PII data → EU regions only                    │
│  Selected target: AWS us-east-1 (USA)                        │
│                                                              │
│  Conflict:                                                   │
│   • Project ma data klasyfikowane jako PII                   │
│   • US region nie spełnia EU residency requirement           │
│                                                              │
│  Akcje:                                                      │
│                                                              │
│  [● Switch do EU region (auto-suggest)]                      │
│      AWS eu-west-1 (Ireland) — closest match                 │
│      AWS eu-central-1 (Frankfurt) — sovereign DE             │
│      Hetzner warsaw-1 — fully Polish sovereign               │
│                                                              │
│  [○ Override project rule (requires explicit)]               │
│      Operator deklaruje: "Ten deploy nie zawiera PII"        │
│      Wymaga: type "OVERRIDE_RESIDENCY_NO_PII" w confirm box  │
│      Audit chain entry: residency_override z reason          │
│                                                              │
│  [○ Modify project rule]                                     │
│      Open faza 17 → Data Residency → edit                    │
│                                                              │
│  [○ Cancel deployment]                                       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Scenario 2: Customer demands sovereign processing**

Klient atelier krawieckiego wymaga że ich dane nie wychodzą poza Polskę:

```
Project: Tailor Master Atelier (custom build dla klienta)
─────────────────────────────────────────────────────────

  Sovereignty: Polska only
  
  Rules:
   ✗ No EU regions outside PL
   ✗ No US regions
   ✗ No vendor with US parent company holding data
   ✓ Hetzner warsaw (DE company, but PL data center) — borderline
   ✓ Polcom (full Polish sovereign) — preferred
   ✓ Local atelier RPi (most sovereign)
   ✓ Operator's own VPS na PL territory
  
  Customer-facing certificate:
   Generate compliance attestation [Generate]
   Attests: data processed exclusively in Poland
   Signed by: AEIS workspace + operator
   Versioned: monthly snapshot dla audit purposes
```

### 3.9.3. Residency audit trail

Każda decyzja deploy generuje audit chain entry:

```jsonl
{"ts":"2026-04-29T14:32:01Z","event":"deploy.target_selected",
 "project":"sylion-tailor","target":"hetzner-warsaw-1",
 "residency_check":"passed","data_classes":["PII","payment"],
 "allowed_regions":["EU"],"selected_region":"warsaw-1","prev_hash":"..."}

{"ts":"2026-04-29T14:32:18Z","event":"deploy.completed",
 "project":"sylion-tailor","target":"hetzner-warsaw-1",
 "deploy_id":"dep_abc123","residency_compliant":true,
 "compliance_attestation_id":"att_xyz789","prev_hash":"..."}
```

Operator może w każdej chwili wygenerować residency report:

```
$ aeis-cli residency-report --project sylion-tailor --period last-12-months

Residency Report — Sylion Tailor
Generated: 2026-04-29

Total deployments: 47
Compliance: 47/47 (100%)
Violations: 0
Overrides: 0

By region:
  warsaw-1 (Hetzner, PL):  43 deployments (91%)
  fra1 (Hetzner, DE):       4 deployments (9%, internal staging)
  
Sub-processors used:
  • Hetzner Online GmbH (DE) — primary
  • Anthropic (US) — LLM processing only, no PII per audit
  • Stripe (US/EU) — payment tokens only, EU-residency confirmed

Customer-facing attestation: ✓ Available
Audit-ready: ✓ Yes
```

---

## 3.10. Cost tracking per environment (P3.15=d 3 levels z toggle)

### 3.10.1. Trzy levels granularity

Operator wybrał **wszystkie 3 levels z toggleable views**.

#### Level 1 — Provider total

```
┌──────────────────────────────────────────────────────────────┐
│  Cost Dashboard — by Provider                                │
│  Period: [This month ▼]   View: [● Provider] [○ Env] [○ Res] │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Provider          Spend       Budget    Status      Trend  │
│  ───────────────── ────────── ─────────  ──────────  ────── │
│  Hetzner           €34.20     €100      ✓ 34%       -8%    │
│  AWS               $48.50     $200      ✓ 24%       +15%   │
│  Scaleway          €4.20      €50       ✓ 8%        +0%    │
│  Local             $0         $0        n/a         n/a    │
│  Edge devices      $0         $0        n/a         n/a    │
│                                                              │
│  Total this month: $87.50 / $350 budget (25%)                │
│  Predicted: $115 (z current rate)                            │
│  vs last month: -12% (good — below trend)                    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### Level 2 — Per environment

```
┌──────────────────────────────────────────────────────────────┐
│  Cost Dashboard — by Environment                             │
│  Period: [This month ▼]   View: [○ Provider] [● Env] [○ Res] │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Environment             Provider    Spend     Notes         │
│  ───────────────────── ──────────  ──────── ─────────────── │
│  sylion-prod-1         Hetzner     €8.40    CX31, 24/7      │
│  sylion-prod-2 (HA)    Hetzner     €8.40    CX31, 24/7      │
│  sylion-staging        Hetzner     €4.20    CX21, 24/7      │
│  sylion-dev            Hetzner     €4.20    CX21, 24/7      │
│  sylion-backup-region  Scaleway    €4.20    cold standby    │
│  aws-prod-failover     AWS         $12.40   light usage     │
│  aws-data-lake         AWS         $36.10   S3 + ETL        │
│  local-dev             Local       $0       Always on       │
│  rpi-fabryka-1...5     Edge        $0       At customers    │
│                                                              │
│  Most expensive: aws-data-lake ($36.10/mo, 41%)              │
│  Recently active: sylion-prod-1 (1247 deploys this month)   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### Level 3 — Per resource

```
┌──────────────────────────────────────────────────────────────┐
│  Cost Dashboard — by Resource                                │
│  Period: [This month ▼]   View: [○ Provider] [○ Env] [● Res] │
│  Filter: [All resources ▼]   Sort: [Cost ↓]                  │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Resource             Type          Env             Cost     │
│  ────────────────── ──────────── ─────────────── ────────── │
│  data-lake-bucket   S3            aws-data-lake   $24.10    │
│  cx31-01            Instance      sylion-prod-1   €8.40     │
│  cx31-02            Instance      sylion-prod-2   €8.40     │
│  ec2-failover-1     Instance      aws-prod-failo  $12.40    │
│  data-etl-lambda    Lambda        aws-data-lake   $7.20     │
│  cx21-staging       Instance      sylion-staging  €4.20     │
│  cx21-dev           Instance      sylion-dev      €4.20     │
│  scaleway-standby   Instance      sylion-backup   €4.20     │
│  rds-postgres-prod  RDS           aws-data-lake   $4.80     │
│  cloudfront-cdn     CDN           aws-data-lake   $0.20     │
│  hetzner-snapshots  Snapshots     (multiple)      €1.40     │
│  hetzner-backups    Backups       (multiple)      €0.80     │
│  hetzner-volumes    Volumes       (multiple)      €1.60     │
│                                                              │
│  Hidden: 8 resources < $0.50/mo                              │
│  [Show all]                                                  │
│                                                              │
│  Top 3 to optimize:                                          │
│   1. data-lake-bucket — consider lifecycle policy            │
│      (move old data to Glacier → save ~$15/mo)               │
│   2. ec2-failover-1 — running 24/7 mimo failover-only         │
│      (switch to standby AMI → save $10/mo)                   │
│   3. data-etl-lambda — frequent invocations                  │
│      (batch processing → save ~$3/mo)                        │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 3.10.2. Cost forecasting

```
┌──────────────────────────────────────────────────────────────┐
│  Cost Forecasting                                            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Current month projection: $115 / $350 budget                │
│                                                              │
│  ┌─ NEXT 3 MONTHS PROJECTION ──────────────────────────┐     │
│  │                                                     │     │
│  │  May:    $120 (steady state)                        │     │
│  │  June:   $145 (planned: +Sylion Tailor v2 launch)   │     │
│  │  July:   $180 (planned: +new customer atelier)      │     │
│  │                                                     │     │
│  │  Cumulative Q2: $445 (over $350 budget)             │     │
│  │  Recommendation: increase budget do $500/month      │     │
│  │  OR: defer customer atelier launch                  │     │
│  │                                                     │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                              │
│  ┌─ SEASONAL PATTERNS ─────────────────────────────────┐     │
│  │  Holiday spikes: traffic 3x average w grudzień       │     │
│  │  Customer onboarding: +€50/mo per new atelier       │     │
│  │  Summer slowdown: -20% traffic czerwiec/sierpień    │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                              │
│  ┌─ COST OPTIMIZATION OPPORTUNITIES ────────────────────┐    │
│  │  Auto-shutdown dev/staging po godzinach:            │    │
│  │   ☐ Enable (save €4.20/mo na każde)                 │    │
│  │                                                     │    │
│  │  Reserved instances (1-year prepay):                │    │
│  │   AWS: save 30%, lock in current prices             │    │
│  │   Hetzner: nie applicable (already cheap)           │    │
│  │                                                     │    │
│  │  S3 lifecycle policy (move to Glacier po 90d):      │    │
│  │   Save: $15/mo                                      │    │
│  │   [Apply lifecycle policy]                          │    │
│  └─────────────────────────────────────────────────────┘     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 3.10.3. Cost alerts per environment

Per environment operator może ustawić alerts:

```
Edit environment: aws-data-lake → Cost Alerts

  Monthly budget cap: $50
  
  Alert thresholds:
   ☑ At 50% spend ($25)     [Notify in-app]
   ☑ At 80% spend ($40)     [Email + notify]
   ☑ At 95% spend ($47.50)  [Pause non-critical workloads]
   ☑ At 100% (over budget)  [Hard stop + Slack alert]
  
  Anomaly detection:
   ☑ Sudden spike >2x baseline (24h)
   ☑ New resource type appearing (could be misconfig)
   ☐ Cost trending up >10% week-over-week
  
  Notification channels:
   ☑ In-app (default)
   ☑ Email (operator + team@sylion.dev)
   ☐ Slack #alerts
   ☐ SMS (only critical)
  
  Auto-actions:
   At 95%: pause non-essential cron jobs
   At 100%: stop accepting new deploys do tego env
```

---

## 3.11. Cleanup policy (P3.16=d per environment)

### 3.11.1. Cleanup strategies

Operator wybrał **per environment policy**. Każde środowisko może mieć
inną strategię cleanup.

#### Strategy A — Manual decommission

Domyślne dla production. Operator klika "Decommission" gdy chce.

```
sylion-prod-1 → Settings → Cleanup

  Cleanup policy: [● Manual decommission]
  
  Warnings:
   ☑ Confirm decommission z password
   ☑ Backup data przed decommission
   ☑ Notify team 7 dni przed (jeśli scheduled)
   
  When manually decommissioned:
   1. Snapshot final state (encrypted backup)
   2. Backup w workspace dla N dni: [90 ▼]
   3. Stop instance / delete cluster
   4. Audit chain entry: env_decommissioned
   5. DNS records cleanup (jeśli auto-managed)
   6. Cost monitoring stops billing
   7. Operator może restore w ciągu retention window
```

#### Strategy B — Auto-cleanup po N hours

Dla ephemeral/test environments. Po czasie auto-decommission.

```
test-feature-x → Settings → Cleanup

  Cleanup policy: [● Auto-cleanup po N hours]
  
  Cleanup after: [24 hours ▼]
  
  Reset countdown na:
   ☑ Manual deploy (operator zaktualizował)
   ☑ Health check pass (still in use)
   ☐ Any HTTP request (zbyt sensitive — DDoS może utrzymywać alive)
  
  Pre-cleanup actions:
   ☑ Notify operator 1h przed cleanup
   ☑ Archive logs do S3 cold storage
   ☐ Email final report
  
  Cleanup actions:
   1. Stop services
   2. Snapshot ephemeral data (7d retention)
   3. Decommission instance
   4. DNS cleanup
   5. Audit chain entry
   
  Status: created 14:32 today, auto-cleanup in 22h 18m
  [Extend by 24h]  [Convert to permanent]  [Decommission now]
```

#### Strategy C — Conditional cleanup

"Delete if not used for X dni". Smart auto-cleanup.

```
demo-customer-acme → Settings → Cleanup

  Cleanup policy: [● Conditional cleanup]
  
  Cleanup if not used for: [7 days ▼]
  
  "Used" definition:
   ☑ Any deployment activity
   ☑ HTTP traffic > threshold (10 req/day)
   ☐ Manual operator visit (Settings page open)
   ☑ Cron jobs running
  
  Inactive period detection:
   Last activity: 3 dni temu
   Will cleanup w: 4 dni
   
  Pre-cleanup notifications:
   At 5 dni inactive: notify
   At 6 dni: email + reminder
   At 7 dni: cleanup proceeds
   
  Override:
   [Mark as critical — never cleanup]
   [Extend grace period]
   [Decommission now]
```

#### Strategy D — Schedule-based

Cleanup w określonych terminach (np. każdej niedzieli o 3:00 cleanup
wszystkich -dev environments).

```
sylion-dev → Settings → Cleanup

  Cleanup policy: [● Schedule-based]
  
  Schedule:
   ☑ Daily at:        [03:00 local ▼]
   ☐ Weekly:          [Sunday ▼] [03:00 ▼]
   ☐ Monthly:         [Last day of month] [03:00]
   ☐ Custom cron:     [_______________]
  
  Action at schedule:
   [● Hibernate (stop, keep state — €1.20/mo)]
   [○ Decommission completely (€0/mo, restore from snapshot)]
   [○ Notify only (operator decides)]
  
  Resume:
   [● Auto-resume on first deploy/access]
   [○ Manual resume only]
   [○ Resume on schedule: [09:00 ▼]]
   
  Cost savings:
   Current: €4.20/mo (24/7)
   Hibernate during nights+weekends: €1.40/mo (-67%)
   Decommission nightly: €0.80/mo (-81%, slower restart)
```

### 3.11.2. Cleanup decision matrix

System może rekomendować cleanup strategy per environment based on
purpose:

```
┌──────────────────────────────────────────────────────────────┐
│  Recommended Cleanup Policies                                │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Purpose            Recommended           Why                │
│  ─────────────────  ────────────────────  ───────────────── │
│  Production         Manual                Critical, no auto  │
│  Staging            Manual or schedule    Often used         │
│  Development        Schedule (nights)     Save cost          │
│  Testing            Auto N hours          Ephemeral          │
│  Demo               Conditional 7d        Show, then cleanup │
│  CI/CD              Auto N hours          Build artifacts    │
│  PR previews        Conditional 3d        Per-PR ephemeral   │
│  Edge devices       Manual                Customer property  │
│  Sovereign          Manual                Compliance audits  │
│  Air-gapped         Manual                External control   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 3.11.3. Bulk cleanup operations

```
┌──────────────────────────────────────────────────────────────┐
│  Bulk Cleanup                                                │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Find environments matching:                                 │
│   Purpose:        [test, demo ▼]                             │
│   Last activity:  [> 14 days ▼]                              │
│   Tags:           [☐ keep-permanent ☐ customer-prod]         │
│                                                              │
│  Found: 8 environments                                       │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  ☑ test-feature-auth     (3 dni inactive, dev tag)    │  │
│  │  ☑ test-payment-flow     (5 dni inactive)             │  │
│  │  ☑ demo-acme-old         (21 dni, demo tag)           │  │
│  │  ☑ pr-preview-127        (14 dni, PR closed)          │  │
│  │  ☑ pr-preview-128        (14 dni)                     │  │
│  │  ☑ pr-preview-129        (14 dni)                     │  │
│  │  ☑ test-i18n-de          (16 dni, abandoned)          │  │
│  │  ☑ test-mobile-views     (18 dni)                     │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  Estimated savings: €33.60/month                             │
│  Total decomission cost: €0 (free)                           │
│                                                              │
│  Safety:                                                     │
│   ☑ Backup snapshot (90d retention)                          │
│   ☑ Audit chain logs                                         │
│   ☐ Email summary report                                     │
│                                                              │
│  [Cancel]  [Decommission selected]                           │
└──────────────────────────────────────────────────────────────┘
```

---

## 3.12. Edge Cases (P3.18=b — 30 cases)

Faza 3 ma kompleksowość similar to fazy 2, więc 30 cases w 6 hybrid
kategoriach (jak faza 2).

### Kategoria A — Cloud provider issues (5 cases)

#### EC-A1: Cloud account suspended

**Trigger**: AWS suspends account (np. unpaid bill, ToS violation, fraud
detection). AEIS dostaje 401/403 podczas deploy.

```
┌──────────────────────────────────────────────────────────────┐
│  ✗  Cloud account suspended: AWS                             │
│                                                              │
│  Account: 123456789012                                        │
│  Last successful operation: 2h ago                           │
│  Error: Account is suspended                                 │
│                                                              │
│  Możliwe przyczyny:                                          │
│   • Unpaid invoice (AWS Billing)                             │
│   • ToS violation (suspicious activity)                      │
│   • Fraud detection trigger                                  │
│   • Credit card expired                                      │
│                                                              │
│  Wpływ:                                                      │
│   • 4 production environments unreachable                    │
│   • 12 staging deployments blocked                           │
│   • S3 buckets accessible (read-only po krótkim okresie)     │
│   • EC2 instances continue running (24-48h grace period)     │
│                                                              │
│  Akcje:                                                      │
│  [● Open AWS Support — resolve suspension]                   │
│      Otwiera AWS Support Center                              │
│      Operator handles vendor-side                            │
│                                                              │
│  [○ Failover do backup region/cloud]                         │
│      Automatycznie deploy do aws-prod-failover (us-east-1)   │
│      Or: Hetzner backup environment (jeśli skonfigurowane)   │
│                                                              │
│  [○ Pause AWS-hosted services]                               │
│      Zatrzymaj nowe deploys do AWS                           │
│      Existing services run as long as possible               │
│                                                              │
│  [○ Backup all data NOW]                                     │
│      Run urgent backup przed dane staną się inaccessible     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### EC-A2: Region-wide outage

**Trigger**: AWS eu-west-1 ma region-wide outage (rare but happens).
Wszystko w tym regionie down.

```
🚨 AWS Region Outage Detected: eu-west-1

  Affected:
   • sylion-prod-1 (Hetzner)         not affected
   • aws-data-lake (eu-west-1)       ✗ DOWN
   • aws-failover (us-east-1)        ✓ available
  
  AWS Status Page: status.aws.amazon.com
  Estimated recovery: 2-4 hours (vendor announcement)
  
  Auto-actions taken:
   ✓ DNS failover to us-east-1 (DR setup activated)
   ✓ Customer-facing notification posted
   ✓ Operator team notified via Slack
  
  Manual actions recommended:
   • Monitor AWS status page
   • Review impact on dependent services
   • Notify affected customers
   
  [View incident timeline]  [Trigger DR runbook]
```

#### EC-A3: Quota exhausted (cloud-side limits)

**Trigger**: AWS account hits service quota (np. 20 EC2 instances max).
Próba launch 21-szej fail-uje.

```
⚠  AWS Service Quota Exceeded

  Quota: EC2 instances per region (eu-west-1)
  Current: 20
  Requested: 21
  Limit: 20
  
  Options:
   [Request quota increase from AWS]
       Form pre-filled, takes 1-3 business days
       
   [Use different region (eu-central-1)]
       Same quota, fresh capacity
       
   [Decommission unused instances]
       AEIS shows: 5 candidates (idle >7 days)
       
   [Switch to different cloud (Hetzner)]
       Hetzner has higher default quotas
```

#### EC-A4: Cloud provider deprecates instance type

**Trigger**: AWS announces t2 family deprecation. Operator's environments
używają t2.micro.

```
ℹ  Deprecation Notice: AWS t2 family

  Affected environments:
   • aws-prod-failover (t2.medium)
   • aws-test-1 (t2.micro)
  
  Deprecation timeline:
   • New launches blocked: 2026-09-01
   • EOL existing instances: 2027-03-01
   
  Recommended migration:
   t2.micro → t3.micro (similar specs, +5% performance, -10% cost)
   t2.medium → t3.medium (similar)
   
  Actions:
   [● Schedule migration (operator picks date)]
       Auto-migration script generated
   [○ Plan manual migration]
       Operator does it themselves
   [○ Defer (will force-migrate at EOL)]
       AEIS warns periodically
```

#### EC-A5: Vendor pricing change

**Trigger**: Hetzner ogłasza price increase 10% dla CX31 plans.

```
ℹ Hetzner Pricing Change

  Effective: 2026-06-01
  
  Affected environments:
   • sylion-prod-1: €8.40 → €9.24 (+10%)
   • sylion-prod-2: €8.40 → €9.24 (+10%)
   • sylion-staging: €4.20 → €4.62 (+10%)
   
  Total monthly impact: +€2.10/mo
  
  Options:
   [Accept new pricing]
   [Downsize to CX21 (-€4.20/mo)]
   [Migrate to alternative provider]
       Compare: Scaleway PRO2-XS (€4.99) vs current
   [Stay on annual contract (lock current price 1 year)]
       Hetzner offers 1-year prepay locks
```

### Kategoria B — Networking issues (5 cases)

#### EC-B1: VPN tunnel breaks mid-deploy

**Trigger**: WireGuard tunnel between AEIS and target environment drops
podczas active deployment.

```
✗  VPN Disconnected Mid-Deploy

  Environment: sylion-prod-1
  Tunnel: wg-aeis (WireGuard)
  Lost connection: 14:32:08 (3 min ago)
  
  Deployment status: PARTIAL (3/8 steps complete)
   ✓ Pre-flight checks
   ✓ Backup current version
   ✓ Upload new artifacts
   ✗ Apply DB migrations (started)
   ✗ Restart services (pending)
   ✗ Healthcheck (pending)
   ✗ Switch traffic (pending)
   ✗ Cleanup old version (pending)
  
  ⚠ DB migration was started but not completed
     State: unknown (could be partial)
  
  Akcje:
   [● Wait for VPN auto-reconnect (60s)]
       Then resume deployment from step 4
       
   [○ Manual reconnect VPN]
       Diagnose connection issue
       
   [○ Rollback deployment]
       Use direct IP fallback (if available)
       Restore previous version
       
   [○ Mark partial deploy w audit]
       Continue manually via SSH (operator)
```

#### EC-B2: DNS propagation issue

**Trigger**: operator zmienił DNS records, ale propagation jest slow.
Część users widzi old version, część new.

```
⚠ DNS Propagation Inconsistent

  Domain: sylion.dev
  Change: A record updated 25 min ago
  Expected propagation: 5-60 min globally
  
  Current state:
   • Anthropic edge nodes: ✓ updated (2 min latency)
   • Google DNS (8.8.8.8): ✓ updated
   • Cloudflare DNS (1.1.1.1): ⠋ still old (TTL 1h)
   • ISP DNS w Polsce: mixed (some updated, some not)
  
  Impact:
   • ~30% users still hitting old IP
   • Old environment still receiving traffic
   • Cannot decomission old environment yet
  
  Options:
   [Wait for full propagation (estimate 35 min more)]
   [Force DNS cache refresh w operator's tools]
   [Reduce TTL preemptively dla future changes]
       Recommendation: TTL 300s dla dynamic resources
```

#### EC-B3: Firewall rule blocks legitimate traffic

**Trigger**: operator zaktualizował firewall rule, blokując PostgreSQL na
porcie 5432 dla legitymnego access.

```
✗ Application Cannot Connect To Database

  Project: Sylion Tailor
  Environment: sylion-prod-1
  Error: connection refused on 10.0.0.5:5432
  
  Diagnostic:
   ✓ Database server running
   ✓ Application server running
   ✗ Firewall blocks 5432 from app server's IP
  
  Recent firewall changes:
   2026-04-29 13:15: Rule modified
     Old: Allow 5432 from VPN-only (10.0.0.0/24)
     New: Allow 5432 from 10.0.0.5/32 (DB server only — bug)
   
  Application server IP: 10.0.0.7 (not allowed)
  
  Akcje:
   [● Auto-fix: revert to VPN-wide allow]
   [○ Add specific 10.0.0.7 to allowlist]
   [○ Manual review firewall rules]
```

#### EC-B4: Mesh network split-brain

**Trigger**: 2 environments thinking they're "primary" because mesh
network partitioned (rare but happens).

```
⚠ Mesh Network Partition Detected

  Mesh: sylion-mesh
  Partition detected: 2 islands
  
  Island 1 (5 nodes):
   • aeis-laptop
   • hetzner-prod-1
   • hetzner-prod-2
   • scaleway-prod
   • Other: ✓ communicating
   
  Island 2 (3 nodes):
   • rpi-fabryka-1
   • rpi-fabryka-2
   • customer-acme-prod
   • Cannot reach Island 1
  
  Implications:
   • Database replication may be stale
   • Customer atelier can't reach central API
   • Possible data divergence
  
  Akcje:
   [Diagnose root cause (network/firewall change?)]
   [Manual reconnect (operator action)]
   [Check Tailscale/Headscale control plane]
   [Initiate DR procedure if extended outage]
```

#### EC-B5: NAT traversal failure dla edge device

**Trigger**: edge RPi za router NAT (np. customer's home network). Mesh
nie może established direct connection.

```
ℹ NAT Traversal Failed

  Device: rpi-fabryka-1
  Customer network: residential ISP, double NAT detected
  
  Mesh setup:
   ✗ Direct UDP NAT traversal: failed (CGNAT)
   ✗ STUN-assisted: failed
   ✓ DERP relay (Tailscale): working (slower)
  
  Performance impact:
   • Latency: 250ms (vs 30ms direct)
   • Throughput: 30 Mbps (vs 100 Mbps direct)
   
  Recommendations:
   ☑ Use DERP relay (current — works but slow)
   ☐ Ask customer for port forwarding (UDP 41641)
   ☐ Move device to better connectivity
   ☐ Switch to OpenVPN/WireGuard (less NAT-friendly)
```

### Kategoria C — Edge devices (5 cases)

#### EC-C1: Edge device offline (customer-side issue)

**Trigger**: RPi w atelier offline od 6h. Customer's WiFi może być down.

```
✗ Edge Device Offline: rpi-fabryka-1

  Customer: Tailor Master
  Last seen: 6h ago
  Heartbeat missed: 720 consecutive (5min interval)
  
  Possible causes:
   • Customer's WiFi/internet down
   • Device powered off
   • Hardware failure
   • SD card corruption
  
  Customer impact:
   • Production tracking offline
   • Local cache fallback (atelier może continue with stale data)
   • Sync delayed (will catch up when online)
  
  Akcje:
   [Notify customer]
       Send SMS / call: "Czy AEIS działa w atelier?"
   [Check customer history]
       Recent issues? Pattern?
   [Wait passively]
       80% przypadków: customer notice and reboot
   [Schedule on-site visit]
       Jeśli >24h offline
```

#### EC-C2: SD card failure dla RPi

**Trigger**: RPi corrupted SD card (common w RPi field deployments).
Device boots but file system errors.

```
⚠ Edge Device Hardware Issue: rpi-fabryka-2

  Symptoms:
   • Periodic disconnects (every 30-60 min)
   • Slow disk operations
   • Application crashes z I/O errors
   • dmesg shows EXT4-fs errors
  
  Probable cause: SD card degradation
  SD card age: 18 months (typical lifespan 12-24 mo)
  
  Akcje:
   [● Schedule SD card replacement]
       AEIS generuje SD card image dla operator
       Operator wysyła nowe SD card customer'owi
       Customer swaps, AEIS detect new device
       
   [○ Migrate to USB SSD]
       Bardziej reliable, $20-50 hardware cost
       Operator coordinates z customer
       
   [○ Move to industrial-grade SD]
       SanDisk Industrial XI3, MLC chips
       Lifespan 5+ years
       
   [○ Flag for hardware refresh]
       Operator's customer support pipeline
```

#### EC-C3: Edge device hijacked (security)

**Trigger**: AEIS detect anomalous behavior on edge device — high CPU
when should be idle, network egress to unknown IPs, processes nie
recognized.

```
🚨 SECURITY ALERT: Suspicious Activity on Edge

  Device: rpi-pos-store-warsaw-1
  Customer: Retail Store (chain)
  Severity: HIGH
  
  Anomalies detected:
   • CPU 95% przez 2h (normalnie 5-15%)
   • Network egress 850 GB w 48h (normalnie 50 MB)
   • New process: cryptominer-style behavior (cpuminer-multi)
   • Outbound connections do mining pools (.eu)
   • SSH login attempts from unknown IP
   
  Possible causes:
   • Device compromised (cryptojacking)
   • Customer installed unauthorized software
   • Supply chain compromise (rare)
  
  Immediate actions:
   [● Isolate device from network NOW]
       Cut all outbound connections except AEIS control
   [● Snapshot current state for forensic analysis]
   [● Notify customer + provide incident report]
   [● Initiate device wipe + redeployment]
       Replace SD card, wipe device
   [○ Continue monitoring (NOT recommended)]
```

#### EC-C4: Edge device update fails (bricked)

**Trigger**: AEIS pushes OS update do RPi, update fails halfway, device
won't boot.

```
✗ Edge Device Update Failed: rpi-fabryka-3

  Update: kernel 5.15 → 6.1 (security patches)
  Failure point: 60% complete (during initramfs rebuild)
  Device state: not responding to ping (likely bricked)
  
  Possible causes:
   • Power loss during update
   • Insufficient disk space dla rollback partition
   • Hardware compatibility issue
  
  Recovery options:
   [Wait 30 min — device may auto-recover]
       RPi sometimes recovers itself z initramfs failures
       
   [Customer reboot device]
       Power cycle może trigger fallback boot
       Customer instructions: unplug, wait 30s, replug
       
   [Send replacement SD card]
       AEIS generuje image z latest config
       Customer swap, device immediately functional
       Cost: ~$15 SD card + shipping
       
   [On-site technical visit]
       Operator dispatches technician
       Cost: $50-200 zależnie od distance
```

#### EC-C5: Edge fleet — bulk update with mixed results

**Trigger**: operator pushes update do 50 edge devices. 47 succeed, 3
fail.

```
⚠ Bulk Edge Update — Mixed Results

  Update: AEIS agent v2.3 → v2.4
  Total devices: 50
  
  Results:
   ✓ Success: 47 (94%)
   ✗ Failed: 3 (6%)
   
  Failed devices:
   • rpi-customer-acme-2  (timeout, retry recommended)
   • rpi-customer-beta-7  (low disk space, expand needed)
   • nuc-customer-gamma-1 (ARM/x86 mismatch — wrong package)
  
  Akcje:
   [Retry failed (auto)]
   [Per-device manual diagnosis]
   [Rollback all to v2.3]
   [Force-update z fallback strategy]
   
  [View detailed logs per failure]
```

### Kategoria D — Sovereign / on-prem (5 cases)

#### EC-D1: Customer changes server hardware (on-prem)

**Trigger**: customer's IT team replaces on-prem server with new hardware
without AEIS knowledge. AEIS connection breaks.

```
⚠ On-Prem Server Hardware Changed

  Environment: customer-acme-prod
  Customer: Acme Corp
  Detected: SSH host key changed
  
  Old fingerprint: SHA256:abcd...
  New fingerprint: SHA256:wxyz...
  
  Possible scenarios:
   • Hardware replacement (legitimate)
   • Server compromised (man-in-the-middle attack)
   • OS reinstall
  
  Actions required:
   [Contact customer to verify]
       Confirm hardware change is legitimate
   [If verified: accept new host key]
       Update AEIS config, reconnect
   [If not verified: block connection]
       Treat as security incident
       Audit chain entry
   [Re-deploy from scratch]
       Full re-provisioning of services
```

#### EC-D2: Customer's compliance audit requires data export

**Trigger**: customer's auditor requires complete data export dla
compliance verification (GDPR Art. 15, ISO 27001 audit).

```
ℹ Data Export Request: customer-bank-prod

  Customer: Polish Bank (financial sector)
  Request type: Full compliance audit export
  Requester: KNF (Polish Financial Supervision)
  Deadline: 14 dni
  
  Required:
   • All data stored: ✓ (database export)
   • All access logs (last 12 months): ✓
   • All deployment manifests: ✓
   • Sub-processor list: ✓
   • Data flow diagram: ✓
   • Encryption attestations: ✓
   • Backup retention proof: ✓
   • Audit chain integrity proof: ✓
  
  AEIS can auto-generate:
   [● Generate full export package]
       ~5 GB encrypted ZIP
       Signed manifest
       Audit-ready format
       
  Manual additions needed:
   ☑ Customer's signed agreements (operator provides)
   ☑ Sub-processor DPAs (operator provides)
   ☐ Penetration test reports (if applicable)
```

#### EC-D3: Air-gapped environment sync conflict

**Trigger**: operator has 2 USB drives both with state from air-gapped
environment, but they're from different sync points.

```
⚠ Air-Gap Sync Conflict

  Air-gap environment: gov-classified-prod
  USB drive A: synced 2026-04-25 (4 dni temu)
  USB drive B: synced 2026-04-29 (today)
  
  Conflict detected:
   • Both drives contain post-deploy state
   • Different commit hashes
   • Different audit chains
  
  Possible scenarios:
   • Operator forgot which is newer (check timestamps)
   • Two operators visited different times
   • System time wrong on air-gap (drift over months)
  
  Resolution:
   [● Use newer drive (B, 2026-04-29)]
       Apply state from B
       Archive A as backup
       
   [○ Manual merge]
       Operator reviews differences
       Decides which changes to keep
       
   [○ Treat as hostile (audit)]
       Don't apply either
       Investigate provenance
```

#### EC-D4: On-prem server out of disk space

**Trigger**: customer's on-prem server fills up, AEIS deploy fails.

```
✗ On-Prem Server: Disk Full

  Environment: customer-acme-prod
  Server: 192.168.10.50 (SSH access)
  
  Disk usage:
   /     85% used (15 GB free of 100 GB)
   /data 98% used (4 GB free of 200 GB) ⚠
   
  Cannot deploy:
   • Container images need 8 GB
   • Database backups need 12 GB
  
  Customer-side fix needed:
   [Contact customer's IT]
   [Provide cleanup script]
       Old logs > 90 days
       Unused Docker images
       Backup files older than retention
   [Recommend disk expansion]
       Customer adds storage hardware
   [Migrate to bigger server]
       Customer provisions new hardware
```

#### EC-D5: Sovereign provider compliance certification expired

**Trigger**: Polcom (Polish sovereign provider) ISO 27001 certification
expires. Customer audit may flag this.

```
⚠ Sovereign Provider Certification Status

  Provider: Polcom
  Certification: ISO 27001
  Status: ⚠ EXPIRED 2026-04-15 (recertification w toku)
  
  Affected customers (4):
   • Customer Bank (financial)
   • Customer Atelier (retail)
   • Customer Gov-X (government)
   • Customer Healthcare-Y (medical)
  
  Risk levels:
   • Bank: HIGH (financial regulation requires current cert)
   • Gov-X: HIGH (gov audit may flag)
   • Atelier: LOW (informational)
   • Healthcare: HIGH (HIPAA-equivalent rules)
  
  Akcje:
   [Notify high-risk customers]
   [Provide alternative providers temporarily]
   [Track recertification timeline]
       Polcom estimates: 6-8 weeks
   [Migrate critical workloads]
       Move HIGH-risk customers do certified providers
```

### Kategoria E — Cost / quota (5 cases)

#### EC-E1: Sudden cost spike (crypto-mining attack)

**Trigger**: AEIS detect spending spike — $500 w 6h zamiast $5/dzień
normally. Possibly compromised credentials.

```
🚨 CRITICAL: Cost Anomaly Detected

  Environment: aws-data-lake
  Normal daily spend: $1.20
  Last 6h spend: $487
  Spike: 8000x normal
  
  Resource breakdown:
   • EC2 instances: 47 NEW (normalnie 3) — c5.24xlarge
   • Region: us-east-1, us-west-2, eu-west-1 (multiple)
   • Tagged: nothing (auto-detected as suspicious)
  
  Hipotezy:
   • Compromised AWS credentials
   • IAM key leaked (Github commit?)
   • Malicious insider
   • Crypto-mining attack
  
  Immediate actions taken (auto):
   ✓ All NEW instances stopped
   ✓ IAM key rotated
   ✓ MFA required dla all logins
   ✓ Operator notified (SMS + email + Slack)
  
  Manual investigation:
   [Open AWS CloudTrail logs]
   [Check Git history for leaked credentials]
   [Initiate incident response]
   [Contact AWS Support — fraud claim]
```

#### EC-E2: Reserved instance overbought

**Trigger**: operator zaplanował 1-year reserved instance dla traffic
spike który nie nastąpił. Płaci za nieużywaną capacity.

```
ℹ Reserved Instance Underutilization

  AWS account: aws-sylion-main
  Reserved: 4x t3.large (3-year prepay)
  Cost: $1,200/year prepaid
  
  Actual usage (6 months):
   • Average utilization: 35%
   • Peak utilization: 78%
   • Idle hours: ~1500 (12% of time)
   
  Loss vs on-demand:
   Prepaid: $1,200
   On-demand equivalent: $480
   Loss: $720/year
  
  Options:
   [Sell unused RIs on AWS Marketplace]
       Recover ~50-70% of remaining value
   [Keep RIs, expand workload to use them]
       Add more services to consume capacity
   [Plan future purchases more conservatively]
       Default: 1-year, 60% utilization threshold
```

#### EC-E3: Budget alert noise (too many false positives)

**Trigger**: operator gets 30 budget alerts/day. Most are false positives
(temporary spikes due to deploys).

```
ℹ Budget Alert Optimization

  Alert frequency last 30 days:
   • Total alerts sent: 247
   • Operator dismissed without action: 198 (80%)
   • Required action: 14 (6%)
   • Operator missed/late response: 35 (14%)
  
  Pattern: Most alerts during deployments (false positives)
  
  Recommendations:
   ☑ Increase deploy-time budget threshold (+25% during deploy)
   ☑ Batch alerts (max 1 per hour)
   ☑ Smart filtering: spike < 30 min ignored
   ☐ Reduce notification channels (currently 4)
   ☐ Auto-dismiss alerts that resolve within 5 min
  
  Apply optimizations?  [Yes]  [No]  [Customize per env]
```

#### EC-E4: Free tier expiration (cloud)

**Trigger**: AWS Free Tier expires po 12 miesiącach. Operator's "free"
test environment suddenly costs $50/mo.

```
ℹ AWS Free Tier Expired

  Account: aws-sylion-main
  Free Tier active: 2025-04-30 - 2026-04-30 (expired today)
  
  Resources używane "free":
   • t2.micro EC2 (750h/mo free) — now $7.59/mo
   • S3 5 GB — now $0.12/mo
   • CloudFront 50 GB — now $4.25/mo
   • Lambda 1M req/mo — now ~$2/mo
   • RDS db.t2.micro 750h — now $13/mo
   
  New monthly cost: ~$27/mo (vs $0 prior)
  
  Akcje:
   [Review and decommission unused resources]
   [Migrate dev/test to cheaper Hetzner]
   [Accept costs, continue z AWS]
   [Apply for AWS Activate credits (startup)]
```

#### EC-E5: Egress costs surprise (data transfer)

**Trigger**: operator deploy'ował AI app na AWS. Inferencje generują dużo
egress traffic. AWS bill = $200 z czego $150 to data transfer.

```
⚠ Data Egress Cost Spike

  Environment: aws-ml-inference
  Last month bill: $238
  Breakdown:
   • EC2 instances: $42
   • Storage (S3): $5
   • Data transfer (egress): $191 ⚠ 
  
  Egress destinations:
   • Customer-facing API responses: 42 TB
   • Backup syncs: 12 TB
   • Cross-region replication: 8 TB
  
  AWS data transfer pricing:
   First 10 TB/month: $0.09/GB
   Next 40 TB: $0.085/GB
   Next 100 TB: $0.07/GB
  
  Cost optimizations:
   [Add CloudFront CDN (reduce origin egress)]
       Estimated savings: $80-120/mo
   [Compress API responses (gzip/brotli)]
       Estimated savings: $30-50/mo
   [Move backups to Glacier (within-region)]
       Estimated savings: $40/mo
   [Deploy multi-region (reduce cross-region traffic)]
       Estimated savings: $20-40/mo
```

### Kategoria F — Recovery / migration (5 cases)

#### EC-F1: Cloud-to-cloud migration

**Trigger**: operator migruje wszystko z AWS na Hetzner (cost reduction).

```
┌──────────────────────────────────────────────────────────────┐
│  Migration Wizard — AWS → Hetzner                            │
│                                                              │
│  Affected:                                                   │
│   • 3 production environments                                │
│   • 8 databases (RDS → Hetzner managed PostgreSQL)           │
│   • 47 S3 buckets → Hetzner Object Storage                   │
│   • 12 Lambda functions → containerize + deploy              │
│   • DNS records (Route53 → Cloudflare)                       │
│   • CDN (CloudFront → Cloudflare)                            │
│   • Monitoring (CloudWatch → Prometheus + Grafana)           │
│                                                              │
│  Estimated effort:                                           │
│   • Auto-migration: 60% of components                        │
│   • Manual: 30% (Lambda → containers, IAM → keys)            │
│   • Cannot migrate: 10% (specific AWS services)              │
│                                                              │
│  Estimated timeline:                                         │
│   • Setup: 1 week                                            │
│   • Migration: 2-3 weeks (gradual)                           │
│   • Validation: 1 week                                       │
│   • Cutover: 1 day                                           │
│   • AWS cleanup: 1 month after cutover                       │
│                                                              │
│  Cost analysis:                                              │
│   • Current AWS spend: $487/mo                               │
│   • Estimated Hetzner: $89/mo (-82%)                         │
│   • One-time migration costs: $200 (data transfer)           │
│   • Payback period: 2 weeks                                  │
│                                                              │
│  [Start migration plan]  [Detailed component breakdown]      │
│  [Cancel]                                                    │
└──────────────────────────────────────────────────────────────┘
```

#### EC-F2: Disaster recovery — entire region down

**Trigger**: AWS eu-west-1 catastrophic failure (rare but happens).
Operator must execute DR runbook.

```
🚨 DISASTER RECOVERY ACTIVATED

  Trigger: AWS eu-west-1 region outage (4h+)
  Affected: aws-data-lake, aws-prod-failover (in same region)
  
  DR Runbook execution:
   1. ✓ Verify backup region available (us-east-1)
   2. ✓ Update DNS records (failover routing)
   3. ⠋ Restore latest backup to us-east-1
       Progress: 65% (3 GB / 4.6 GB DB restore)
       ETA: 12 min
   4. ⏸ Restart application stack in us-east-1
   5. ⏸ Update integrations (webhooks, DNS, monitoring)
   6. ⏸ Notify customers (email + status page)
   7. ⏸ Operator validation (smoke tests)
   8. ⏸ Resume traffic
  
  Estimated total time: 25 min
  
  Last successful backup: 14h ago (auto-daily)
  Data loss window: ~14h (acceptable for D2 services)
  
  ⚠ Critical D5 services (banking customer): synced realtime
     (no data loss expected)
```

#### EC-F3: Workspace import (operator switches machines)

**Trigger**: operator buys new laptop, imports workspace z backup.
Environments references mogą być stale.

```
ℹ Workspace Import Complete

  Imported environments: 12
  
  Validation:
   ✓ Hetzner credentials still valid (8 environments)
   ✓ AWS credentials still valid (3 environments)
   ⚠ Edge device connections: 4 still reachable, 1 offline
   ⚠ VPN configurations: 2 require re-auth (token expired)
   ✓ Cost monitoring: continuous z previous machine
  
  Required actions:
   [Re-authenticate VPN (Tailscale)]
   [Reconnect to offline edge device (rpi-fabryka-2)]
   [Update SSH keys jeśli operator zmienił klucz]
       Generate new key, distribute to environments
       
  Status:
   ✓ 11/12 environments fully operational
   ⚠ 1/12 needs operator attention (rpi-fabryka-2)
```

#### EC-F4: Backup restore — environment metadata corruption

**Trigger**: SQLite corruption in environments table. Some environments
references broken.

```
⚠ Environment Metadata Corruption

  Detected: 3 of 12 environments have corrupted metadata
  
  Corrupted:
   ✗ aws-data-lake — region field unreadable
   ✗ rpi-fabryka-2 — SSH key reference invalid
   ✗ customer-acme-prod — encryption mismatch
  
  Recovery options:
   [● Restore z backup (2026-04-28)]
       Loss: 24h of changes
       All 3 environments recovered
       
   [○ Manual re-entry]
       Operator wpisuje na nowo:
        - aws-data-lake region (eu-west-1)
        - rpi-fabryka-2 SSH key path
        - customer-acme-prod credentials
       
   [○ Disable corrupted, continue z working 9]
       Operator naprawia później
       
   [○ Try repair (best effort)]
       SQLite recover utility
       Może utracić ostatnie wpisy
```

#### EC-F5: Environment migration to new hardware

**Trigger**: customer upgrades hardware (np. RPi 4 → RPi 5 albo NUC →
serwer Dell). Need to migrate environment configuration.

```
┌──────────────────────────────────────────────────────────────┐
│  Edge Hardware Migration                                     │
│                                                              │
│  Old device: rpi-fabryka-1 (Pi 4, 4 GB RAM)                  │
│  New device: rpi-fabryka-1-v2 (Pi 5, 8 GB RAM)               │
│  Customer: Tailor Master                                     │
│                                                              │
│  Migration plan:                                             │
│   1. Snapshot rpi-fabryka-1 state                            │
│   2. Provision new device w customer's location              │
│   3. Install AEIS agent on new device                        │
│   4. Restore state from snapshot                             │
│   5. Validate functionality                                  │
│   6. Switch DNS / network references                         │
│   7. Decommission old device (return to operator)            │
│                                                              │
│  Estimated downtime: 30-60 min (during cutover)              │
│  Customer presence required: yes (physical hardware swap)    │
│                                                              │
│  Schedule:                                                   │
│   [● Coordinate w customer (operator picks date)]            │
│       Suggested: weekend 2026-05-10                          │
│   [○ Cancel migration]                                       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 3.13. Inheritance + Acceptance Criteria + DoD

### 3.13.1. Inheritance pattern (P3.17=b granular per moduł)

Operator wybrał **bardziej granular** — środowiska propagują nawet do
poziomu modułu w fazie 33.

**Przykład 1 — Frontend i backend na różnych środowiskach**:

```
Faza 3 sets:
  Default production: Hetzner warsaw-1 (CX31)
  Default staging: Hetzner warsaw-1 (CX21)
  Default dev: local-dev
   
   ↓
Faza 4 (Workspace Defaults):
  Default per goals "public_products":
   prod: 2 environments (Hetzner warsaw + Scaleway paris dla HA)
   
   ↓
Faza 17 (Per-project Sylion Tailor):
  Override prod: dodaj Cloudflare CDN przed Hetzner
  Override staging: tylko 1 (Hetzner warsaw-1)
  
   ↓
Faza 33 (Per moduł — granular):
  Frontend module → environment: cloudflare + hetzner-prod
  Backend API module → environment: hetzner-prod (only)
  Database module → environment: hetzner-prod-managed-postgres
  Worker queue module → environment: hetzner-prod
  Static assets module → environment: cloudflare-r2
  Admin panel module → environment: hetzner-prod (separate domain)
  
  Different modules → different environments (granular!)
```

**Przykład 2 — Cost allocation cascade**:

```
Faza 3: Global cost cap: $500/mo
   ↓
Faza 17 (per-project): Sylion Tailor — $250/mo (uses 50%)
   ↓
Faza 33 (per moduł):
  Frontend: $50/mo (Cloudflare)
  Backend: $80/mo (Hetzner CX31)
  Database: $40/mo (Hetzner managed)
  Workers: $30/mo (Hetzner CX21 x 2)
  CDN: $50/mo (Cloudflare premium tier)
  Total: $250 (within project cap)
```

### 3.13.2. Acceptance Criteria — DoD (adaptive per goals)

#### Wspólne (zawsze wymagane)

```
✓ Min 1 środowisko skonfigurowane (typowo local-dev auto-created)
✓ Network policy zdefiniowana per środowisko
✓ Cleanup policy default ustanowiona
✓ Cost monitoring włączony
✓ Audit chain entry: phase_3.complete
```

#### Goal-specific dodatkowe

**Jeśli goal = "public_products"**:
```
✓ Min 1 cloud provider integrated z testowanym credential
✓ Min 1 production environment (cloud, nie local)
✓ Backup strategy per production environment
✓ Cost limits per production environment
✓ Network policy z firewall rules dla prod
```

**Jeśli goal = "cybersecurity"**:
```
✓ Sovereign environment available (lokalny, on-prem, lub EU sovereign)
✓ Air-gapped capability dla TLP:RED workloads
✓ VPN obligatoryjnie dla sensitive environments
✓ Audit chain immutable (signed)
✓ Compliance attestations available (jeśli external audits)
```

**Jeśli goal = "research"**:
```
✓ Diverse environments (lokalny + cloud min)
✓ Cost limits relaxed (research może wymagać experimentation)
✓ Cleanup policy aggressive (test envs auto-cleanup)
```

**Jeśli goal = "apps_internal"**:
```
✓ Min 1 środowisko (lokalny może wystarczyć)
✓ Cost limits low
✓ Backup minimal (internal tools)
```

### 3.13.3. Soft warnings vs hard blocks

**Hard blocks** (operator nie może iść dalej):
- 0 środowisk skonfigurowane
- Brak network policy dla cloud production env
- Brak backup strategy dla critical production
- Cost monitoring disabled dla production env

**Soft warnings** (operator może continue z risk):
- Brak cloud provider gdy goal = public_products
- Brak sovereign environment gdy goal = cybersecurity
- Edge devices bez VPN
- Production env bez HA (single point of failure)
- Cleanup policy "Manual" dla test envs (cost waste risk)

### 3.13.4. Acceptance test (automated)

```bash
$ aeis-cli phase3-acceptance-test

Running Phase 3 acceptance test...

[Common requirements]
[1/5] At least 1 environment configured           ✓ PASS (4 environments)
[2/5] Network policy defined per env              ✓ PASS
[3/5] Cleanup policy defaults set                 ✓ PASS
[4/5] Cost monitoring enabled                     ✓ PASS
[5/5] Audit chain entry phase_3.complete          ✓ PASS

[Goal-specific: public_products]
[6/9] Cloud provider integrated                   ✓ PASS (Hetzner + AWS)
[7/9] Production environment exists               ✓ PASS (sylion-prod-1)
[8/9] Backup strategy per prod                    ✓ PASS (daily, 30d)
[9/9] Firewall rules for prod                     ⚠ WARN (only basic)

[Goal-specific: cybersecurity]
[10/12] Sovereign environment                      ✓ PASS (Hetzner warsaw)
[11/12] VPN for sensitive envs                     ✓ PASS (WireGuard)
[12/12] Compliance attestation available           ⚠ WARN (last audit > 6 mo)

DoD: 11/12 ✓ + 1 ⚠
Soft warnings: 2 (firewall rules basic, compliance audit due)
Hard blocks: 0

Phase 3 ACCEPTED. Ready to proceed to Phase 4 (Workspace Defaults).

Recommended pre-Phase-4 actions:
  • Tighten firewall rules for sylion-prod-1 (deny-by-default)
  • Schedule compliance audit (last: 7 months ago)
```

---

## Status fazy 3

🟢 **Wszystkie sekcje 3.1-3.13 complete**

**Zawiera**:
- ✓ Sense + iteracyjny charakter (3.1)
- ✓ Architektura środowisk — 3-poziom hierarchia + 3 widoki toggle (3.2)
- ✓ Auto-detection — szerokie scan + cloud CLI tools detection (3.3)
- ✓ Cloud providers — 10 providers w 3 tiers + multi-method auth (3.4)
- ✓ Sovereign environments — 3 typy (cloud-EU, on-prem, air-gapped) (3.5)
- ✓ Edge devices — Linux-based + 5 paring methods (3.6)
- ✓ Network topology — 4 modele (isolated/mesh/hub-spoke/custom) (3.7)
- ✓ VPN per environment — WireGuard config + firewall rules (3.8)
- ✓ Data residency enforcement — per-project rules + audit trail (3.9)
- ✓ Cost tracking — 3 levels (provider/env/resource) z forecasting (3.10)
- ✓ Cleanup policy — 4 strategies per environment (3.11)
- ✓ Edge cases — 30 cases w 6 hybrid kategoriach (3.12)
- ✓ Inheritance + DoD + acceptance test (3.13)

⏳ **Po Twojej akceptacji** → **soft freeze fazy 3** + przejście do **Faza 4 — Workspace Defaults**.
