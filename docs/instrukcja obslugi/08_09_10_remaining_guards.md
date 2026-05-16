# FAZY 8-10 — Pozostałe Guards (Security / Quality / Provenance)

> **Status**: 🟢 Active draft (przed soft-freeze)
> **Grupa**: A — Przygotowanie Operatora (8-10 z 11) — Guards Setup (3-5 z 5)
> **Typ**: jednorazowa konfiguracja, ciągłe działanie w tle
> **Zależności**: Fazy 1-7 zakończone
> **Następnik**: Faza 11 (Skills Library Bootstrap)
>
> **Decyzja architektoniczna**: 3 fazy w jednym pliku ponieważ:
> - Wszystkie używają tej samej structural architecture (sep worker,
>   aggregated panel, per-Guard autonomy override)
> - Wszystkie używają tej samej findings infrastructure z fazy 6
> - Operator widzi je jako spójną grupę "Guards Setup"
>
> **Architectural defaults wspólne dla wszystkich 3 Guards**:
> - Separate worker process (jak Cost/Coherence)
> - Aggregated panel integration (faza 6.9)
> - Per-Guard autonomy override (faza 6 pattern)
> - 5 severity levels (INFO/WARNING/ERROR/CRITICAL/BLOCKER)
> - Adaptive findings handling per autonomy preset
> - Smart caching (jak Coherence Guard)
> - Tiered cost (rules cheap, LLM expensive)

---

# FAZA 8 — Security Guard

> **Spis sekcji**:
> - 8.1 — Sense fazy + Security Guard scope
> - 8.2 — 6 obszarów security (code/infra/data/ops/threat/compliance)
> - 8.3 — Triggers (continuous + phase boundaries + on-demand)
> - 8.4 — Severity levels + auto-escalation
> - 8.5 — Detection mechanisms (rules + scanners + LLM + threat intel)
> - 8.6 — Baseline 25 checks + custom + community
> - 8.7 — Findings handling (security-specific patterns)
> - 8.8 — Threat intelligence integration
> - 8.9 — Incident response automation
> - 8.10 — Compliance reporting (GDPR/KSeF/HIPAA/PCI/etc.)
> - 8.11 — Edge cases (22) + inheritance + DoD

---

## 8.1. Sense fazy + Security Guard scope

### 8.1.1. Co Security Guard robi

Security Guard to **najważniejszy z 5 Guards** w Conservative i Production
presets. Dla cybersecurity-focused operatorów (Robert), to subsystem który
wymaga największej uwagi.

Security Guard NIE jest pojedynczym security scannerem — to **agregator**
wielu mechanizmów:

```
┌──────────────────────────────────────────────────────────────┐
│  Security Guard — Layered Architecture                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  LAYER 1 — Static analysis (code-level)                      │
│   • SAST scanners (Semgrep, CodeQL)                          │
│   • Secret detection (TruffleHog, GitLeaks)                  │
│   • Dependency vulnerability (Snyk, Trivy)                   │
│                                                              │
│  LAYER 2 — Dynamic analysis (runtime)                        │
│   • DAST scanning of running app                             │
│   • Runtime behavior monitoring                              │
│   • Anomalous access detection                               │
│                                                              │
│  LAYER 3 — Infrastructure security                           │
│   • Cloud misconfig (CloudSploit, Prowler)                   │
│   • Network exposure (open ports, public buckets)            │
│   • IAM analysis (overprivileged accounts)                   │
│                                                              │
│  LAYER 4 — Data security                                     │
│   • Encryption verification (at rest, in transit)            │
│   • PII detection w logs/databases                           │
│   • Data leakage prevention                                  │
│                                                              │
│  LAYER 5 — Operational security                              │
│   • Audit chain integrity (z fazy 10 Provenance)             │
│   • MFA enforcement                                          │
│   • Key rotation tracking                                    │
│   • Session anomaly detection                                │
│                                                              │
│  LAYER 6 — Threat intelligence                               │
│   • CVE database integration                                 │
│   • Known bad IPs / domains                                  │
│   • Industry threat feeds                                    │
│                                                              │
│  LAYER 7 — Compliance verification                           │
│   • GDPR (EU)                                                │
│   • KSeF (PL invoicing)                                      │
│   • PCI DSS (payment cards)                                  │
│   • HIPAA (healthcare)                                       │
│   • Industry-specific                                        │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 8.1.2. Scope per project type

Different projects need different security focus:

```
┌──────────────────────────────────────────────────────────────┐
│  Default Security Scope per Goal                             │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Goal: cybersecurity (Robert's primary)                       │
│   ALL 7 layers active                                         │
│   Custom: penetration testing simulation                      │
│   Custom: threat modeling integration                         │
│                                                              │
│  Goal: public_products                                        │
│   Layers 1, 2, 3, 4, 7 (no advanced threat intel)             │
│   Focus: customer data protection                            │
│                                                              │
│  Goal: research                                              │
│   Layers 1, 4 (basic code + data security)                    │
│   Focus: protect research data, low operational overhead      │
│                                                              │
│  Goal: apps_internal                                         │
│   Layers 1, 5 (code + operational)                            │
│   Focus: prevent insider threats                             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 8.1.3. Wynik fazy 8 (DoD)

```
✓ 7 layers configured (enabled/disabled per scope)
✓ Baseline 25 checks reviewed
✓ Custom security checks defined (jeśli specific potrzeby)
✓ Compliance frameworks selected (GDPR baseline minimum)
✓ Incident response workflows configured
✓ Threat intel feeds enabled
✓ Audit chain entry: phase_8.complete
```

---

## 8.2. 6 obszarów security

### 8.2.1. Code Security

```
┌──────────────────────────────────────────────────────────────┐
│  Code Security                                               │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ☑ SAST (Static Application Security Testing)                │
│    Tools: Semgrep, CodeQL                                    │
│    Frequency: per build                                      │
│    Languages: Python, JS/TS, Go, Rust, Java                  │
│    Cost: lokalne (free) / managed services (premium)         │
│                                                              │
│  ☑ Secret detection                                          │
│    Tools: TruffleHog, GitLeaks                               │
│    Scope: code, configs, env files, comments                 │
│    Triggers: pre-commit, per build, periodic full scan       │
│    Action: block commit/build with detected secret           │
│                                                              │
│  ☑ Dependency vulnerability scanning                         │
│    Tools: Snyk, Trivy, npm audit, pip-audit                  │
│    Frequency: per build, daily background                    │
│    Action: block on CRITICAL CVEs, warn na lower             │
│                                                              │
│  ☑ Container security                                        │
│    Tools: Trivy, Grype                                       │
│    Scans: base images, dependencies, configs                 │
│    Frequency: per container build                            │
│                                                              │
│  ☐ License compliance (advanced)                             │
│    Tools: FOSSA, license-checker                             │
│    Detects: incompatible licenses (GPL w commercial)         │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 8.2.2. Infrastructure Security

```
┌──────────────────────────────────────────────────────────────┐
│  Infrastructure Security                                     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ☑ Cloud misconfiguration                                    │
│    Tools: CloudSploit, Prowler, ScoutSuite                   │
│    Checks:                                                   │
│     • Public S3 buckets                                      │
│     • Open security groups (0.0.0.0/0)                       │
│     • Unencrypted EBS volumes                                │
│     • IAM users z console access bez MFA                     │
│     • Default VPC usage                                      │
│    Frequency: hourly background, per deploy                  │
│                                                              │
│  ☑ Network security                                          │
│    Checks:                                                   │
│     • Open ports beyond expected                             │
│     • TLS/SSL certificate validity                           │
│     • Weak ciphers                                           │
│     • DNS misconfigurations                                  │
│    Tools: nmap, sslyze, dig                                  │
│                                                              │
│  ☑ IAM analysis                                              │
│    Checks:                                                   │
│     • Overprivileged service accounts                        │
│     • Unused permissions                                     │
│     • Cross-account trust relationships                      │
│     • Root account activity                                  │
│    Tools: cloud-native (AWS Access Analyzer, etc.)           │
│                                                              │
│  ☑ Container runtime security                                │
│    Tools: Falco                                              │
│    Detects: container escape attempts, suspicious syscalls   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 8.2.3. Data Security

```
┌──────────────────────────────────────────────────────────────┐
│  Data Security                                               │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ☑ Encryption verification                                   │
│    At-rest:                                                  │
│     • Database encryption enabled                            │
│     • S3 bucket encryption                                   │
│     • Backup encryption                                      │
│     • Local SQLite (z fazy 1, master password)               │
│    In-transit:                                               │
│     • TLS 1.2+ everywhere                                    │
│     • Certificate validity                                   │
│     • HSTS headers                                           │
│                                                              │
│  ☑ PII detection                                             │
│    Scans logs/databases dla:                                 │
│     • Email addresses w plaintext logs                       │
│     • Credit card numbers                                    │
│     • Phone numbers                                          │
│     • PESEL/SSN/passport numbers                             │
│     • Health information                                     │
│    Action: alert + recommend redaction                       │
│                                                              │
│  ☑ Data leakage prevention                                   │
│    Detects:                                                  │
│     • Sensitive data w error messages                        │
│     • PII in API responses bez authorization                 │
│     • Data exfiltration patterns                             │
│     • Unauthorized backup downloads                          │
│                                                              │
│  ☑ GDPR-specific data handling                               │
│    Verifies:                                                 │
│     • Data subject access requests honored                   │
│     • Right-to-erasure implemented                           │
│     • Data retention limits enforced                         │
│     • Cross-border transfer documented                       │
│     • DPA agreements in place dla sub-processors             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 8.2.4. Operational Security

```
┌──────────────────────────────────────────────────────────────┐
│  Operational Security                                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ☑ Audit chain integrity                                     │
│    (Linked z faza 10 Provenance Guard)                        │
│    Verifies:                                                  │
│     • Hash chain unbroken                                    │
│     • No tampering detected                                  │
│     • All operations logged                                  │
│                                                              │
│  ☑ Authentication monitoring                                 │
│    Checks:                                                   │
│     • Failed login attempts                                  │
│     • Unusual login locations                                │
│     • Master password attempts                               │
│     • Mobile app pairing events (faza 4.5)                   │
│                                                              │
│  ☑ MFA enforcement                                           │
│    Checks:                                                   │
│     • All admin accounts have MFA                            │
│     • API keys have appropriate scopes                       │
│     • Service accounts use IAM roles vs static keys          │
│                                                              │
│  ☑ Key rotation tracking                                     │
│    Monitors:                                                  │
│     • Provider API keys age                                  │
│     • Cloud access keys rotation                             │
│     • TLS certificate expiry                                 │
│     • Master password age                                    │
│    Alerts: 30 days przed expiry                              │
│                                                              │
│  ☑ Session security                                          │
│    Detects:                                                  │
│     • Sessions z unusual locations                           │
│     • Concurrent sessions z different IPs                    │
│     • Session token reuse anomalies                          │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 8.2.5. Threat Detection

```
┌──────────────────────────────────────────────────────────────┐
│  Threat Detection                                            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ☑ Intrusion detection                                       │
│    Monitors:                                                  │
│     • Port scanning attempts                                 │
│     • Brute force attacks                                    │
│     • SQL injection patterns                                 │
│     • XSS attempts                                           │
│     • Command injection                                      │
│    Tools: ModSecurity, Falco, Suricata                       │
│                                                              │
│  ☑ Anomalous access                                          │
│    Detects:                                                  │
│     • Unusual API call patterns                              │
│     • Geographic anomalies (admin login z Russia)            │
│     • Time-of-day anomalies (3am admin work)                 │
│     • Privilege escalation attempts                          │
│                                                              │
│  ☑ Exfiltration detection                                    │
│    Monitors:                                                  │
│     • Large data downloads                                   │
│     • Outbound connections do suspicious destinations        │
│     • DNS tunneling patterns                                 │
│     • Encrypted traffic do non-business endpoints            │
│                                                              │
│  ☑ Cryptojacking detection                                   │
│    (z fazy 3 EC-C3 — RPi hijacked)                            │
│    Indicators: CPU 95%+ sustained, mining pool connections   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 8.2.6. Compliance Verification

```
┌──────────────────────────────────────────────────────────────┐
│  Compliance Frameworks                                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ☑ GDPR (EU)                                                 │
│    Auto-verified:                                            │
│     • Data residency (EU regions only dla PII)               │
│     • Encryption requirements                                │
│     • Audit trail completeness                               │
│     • Sub-processor disclosure                               │
│    Manual verification:                                       │
│     • Privacy policy current                                 │
│     • DPIA dla high-risk processing                          │
│                                                              │
│  ☑ KSeF (Polish e-invoicing)                                 │
│    Required dla projektów z PL invoicing:                    │
│     • Invoice format compliance (FA(2))                      │
│     • Signature/timestamp verification                       │
│     • Submission to KSeF system                              │
│     • Archive retention                                      │
│                                                              │
│  ☐ PCI DSS (payment cards)                                   │
│    Activate dla projects z card processing:                  │
│     • PAN data never stored                                  │
│     • Tokenization implemented                               │
│     • Network segmentation                                   │
│     • Encryption requirements                                │
│                                                              │
│  ☐ HIPAA (US healthcare)                                     │
│    Activate dla healthcare projektów (rare dla operator)     │
│                                                              │
│  ☐ ISO 27001 (general info security)                         │
│    Comprehensive framework                                   │
│                                                              │
│  ☐ SOC 2 (service organizations)                             │
│    Customer-required dla some B2B SaaS                       │
│                                                              │
│  ☐ CCPA (California privacy)                                 │
│    Activate dla US customers w California                    │
│                                                              │
│  ☑ KRI-PL (Polish national security)                         │
│    Activate dla government workloads:                        │
│     • Classification levels respected                        │
│     • Sovereign processing only                              │
│     • Authorized personnel verification                      │
│                                                              │
│  Operator-defined custom compliance:                          │
│   [+ Add framework]                                          │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 8.3. Triggers

### 8.3.1. Continuous + phase boundaries + on-demand

```
┌──────────────────────────────────────────────────────────────┐
│  Security Guard — Triggers                                    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Continuous:                                                 │
│   • SAST: per file save (debounced)                          │
│   • Secret detection: per commit                             │
│   • Cloud misconfig: hourly background                       │
│   • Threat detection: real-time stream                       │
│   • Audit integrity: per audit entry                         │
│                                                              │
│  Phase boundaries:                                           │
│   Faza 25 (Book): compliance review                          │
│   Faza 28 (Masterplan): architecture security review         │
│   Faza 35 (Build): full SAST + dependency scan               │
│   Faza 37 (Quality Gates): DAST + integration security       │
│   Faza 39 (Deployment Config): infra security review         │
│   Faza 41 (Closure): final security audit + report           │
│                                                              │
│  On-demand:                                                  │
│   • Operator klika "Run security scan"                       │
│   • Compliance report generation                             │
│   • Incident response (z faza 8.9)                           │
│                                                              │
│  Pre-deploy hard gates:                                      │
│   • Security scan must pass dla production deploy            │
│   • CRITICAL/BLOCKER findings block deploy                   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 8.4. Severity levels + auto-escalation

### 8.4.1. Security-specific severity assignment

```
Same 5 levels (INFO/WARNING/ERROR/CRITICAL/BLOCKER) ale Security
ma stricter defaults:

  Hardcoded credentials w code        CRITICAL
  Secret w git history                 CRITICAL
  Public S3 bucket z customer data    BLOCKER
  Unencrypted database                 CRITICAL
  Open SSH port (0.0.0.0/0)            ERROR
  Missing MFA na admin account         ERROR
  TLS cert expires w 30 dni            WARNING
  TLS cert expires w 7 dni             ERROR
  TLS cert expired                     CRITICAL
  CVE w dependency (CVSS 9.0+)         BLOCKER
  CVE w dependency (CVSS 7.0-8.9)      CRITICAL
  CVE w dependency (CVSS 4.0-6.9)      ERROR
  CVE w dependency (CVSS <4.0)         WARNING
  Brute force attack detected          CRITICAL
  Cryptojacking detected               BLOCKER
  Data exfiltration pattern            BLOCKER
  GDPR non-compliance dla PII project  CRITICAL
  PCI DSS violation                    BLOCKER
```

### 8.4.2. Auto-escalation

Security findings auto-escalate jeśli not addressed:

```
┌──────────────────────────────────────────────────────────────┐
│  Security Auto-Escalation                                    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  WARNING unattended 7 dni → ERROR                            │
│  ERROR unattended 24h → CRITICAL                             │
│  CRITICAL unattended 4h → notification to ALL channels       │
│  BLOCKER → immediate block + emergency notification           │
│                                                              │
│  Escalation includes:                                        │
│   • Mobile push notification                                 │
│   • Email z explicit context                                 │
│   • Slack alert (jeśli configured)                           │
│   • SMS dla CRITICAL+                                        │
│   • Audit chain entry                                        │
│                                                              │
│  De-escalation (jeśli operator addressed):                    │
│   • Auto-recheck po fix                                      │
│   • Marked "resolved" w panel                                │
│   • Audit entry: resolution                                  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 8.5. Detection mechanisms

### 8.5.1. Multi-layer detection

```
Different layer = different mechanism:

  CODE SECURITY
   • SAST tools (Semgrep): rule-based, deterministic
   • Secret detection: pattern matching + entropy
   • Dependency scan: CVE database lookup
   Cost: $0 (lokalne)
   Speed: fast (seconds)
  
  INFRASTRUCTURE
   • Cloud APIs: structured queries
   • Configuration parsers
   Cost: $0 (cloud APIs free dla read)
   Speed: medium (cloud API rate limits)
  
  DATA SECURITY
   • Pattern detection (regex + semantic)
   • LLM-based PII detection (Tier 2)
   Cost: low to medium
   Speed: medium
  
  OPERATIONAL
   • Log analysis
   • Audit chain hashing
   Cost: $0
   Speed: fast
  
  THREAT DETECTION
   • Behavioral analysis (statistical/ML)
   • Threat intel lookups
   Cost: subscription dla premium feeds
   Speed: real-time
  
  COMPLIANCE
   • Rule-based checklists
   • LLM-based document review (Tier 2)
   Cost: medium dla LLM checks
   Speed: slow (deep analysis)
```

### 8.5.2. Threat intelligence integration

```
Settings → Security Guard → Threat Intelligence

  Free feeds:
   ☑ CISA Known Exploited Vulnerabilities
   ☑ AbuseIPDB (free tier — 1000 lookups/day)
   ☑ AlienVault OTX (free)
   ☑ Spamhaus DBL (free)
  
  Paid feeds (operator's subscriptions):
   ☐ VirusTotal API ($)
   ☐ Recorded Future ($$$$)
   ☐ Mandiant Threat Intelligence ($$$$)
  
  Sources update frequency:
   ☑ Daily refresh CVE database
   ☑ Hourly refresh blocklists (IPs/domains)
   ☑ Real-time event feeds (jeśli configured)
  
  Local cache:
   ☑ Cache feeds locally (offline operation)
   Storage: ~/.sylion/<op>/security/threat-intel/
   Size: ~500 MB (refreshed daily)
```

---

## 8.6. Baseline 25 checks + custom + community

### 8.6.1. Baseline 25 checks

```
┌──────────────────────────────────────────────────────────────┐
│  Security Baseline Checks (25)                               │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  CODE (5)                                                    │
│   1. SAST scan na build (Semgrep ruleset OWASP)              │
│   2. Secret detection w code/configs                          │
│   3. Dependency CVE scan (CVSS 7.0+ blocks)                  │
│   4. Container image scan                                    │
│   5. Insecure crypto usage detection                         │
│                                                              │
│  INFRASTRUCTURE (5)                                          │
│   6. Public cloud resources detection                        │
│   7. Open port enumeration                                   │
│   8. TLS configuration verification                          │
│   9. IAM least-privilege check                               │
│   10. Default credentials detection                          │
│                                                              │
│  DATA (5)                                                    │
│   11. Encryption-at-rest verification                        │
│   12. PII detection w logs                                   │
│   13. Backup encryption check                                │
│   14. Data residency compliance (z faza 3)                   │
│   15. Data retention policy enforcement                      │
│                                                              │
│  OPERATIONAL (5)                                             │
│   16. Audit chain integrity (z faza 10)                      │
│   17. MFA enforcement check                                  │
│   18. Key/certificate expiry monitoring                      │
│   19. Failed authentication tracking                         │
│   20. Session anomaly detection                              │
│                                                              │
│  THREAT (3)                                                  │
│   21. Brute force attack detection                           │
│   22. Anomalous access patterns                              │
│   23. Outbound connection monitoring                         │
│                                                              │
│  COMPLIANCE (2)                                              │
│   24. GDPR compliance baseline                               │
│   25. KSeF readiness (jeśli PL invoicing)                    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 8.6.2. Custom + community checks

Same 3 mechanisms jak Coherence (templates / DSL / LLM prompts), plus
**community marketplace**:

```
Community security checks:
  Operators share checks via marketplace
  Examples available:
   • "OWASP Top 10 deep scan" (LLM-based, ~$0.50/scan)
   • "GDPR compliance walkthrough" (template-based)
   • "Polish KRI requirements" (rules + LLM hybrid)
   • "PCI DSS readiness" (comprehensive checklist)
   • "Common Polish security gov requirements"
  
  Trust levels:
   ✓ Verified (AEIS team reviewed)
   ⚠ Community (operator at own risk)
   ✓ Self-published (operator's own)
```

---

## 8.7. Findings handling — security-specific

### 8.7.1. Security findings nigdy nie są auto-fixed

```
KRITYCZNA ZASADA: Security findings nigdy nie są auto-fixed bez
operator approval, nawet w Aggressive/Research presets.

Rationale:
 • Security fixes wymagają contextual understanding
 • Auto-fixed security może introduce new vulnerabilities
 • Operator must approve dla audit trail
 • Compliance często wymaga human-in-the-loop

Exception:
 • Auto-isolate compromised resources (cryptojacking, attack)
 • Auto-revoke leaked credentials
 • Auto-block exfiltration attempts
 • These są emergency containment, NIE fixes
```

### 8.7.2. Security finding workflow

```
┌──────────────────────────────────────────────────────────────┐
│  🚨  Security Finding — Hardcoded credential detected        │
│                                                              │
│  Severity: CRITICAL                                          │
│  Detected: 30 sek temu                                       │
│  Source: backend/config.py line 45                           │
│                                                              │
│  Finding:                                                    │
│   AWS_SECRET_ACCESS_KEY = "AKIAIOSFODNN7..." (hardcoded)     │
│                                                              │
│  Impact:                                                     │
│   • If code committed do public repo → key compromised       │
│   • Anyone z access to source code → has AWS credentials     │
│   • Potential data breach risk                               │
│                                                              │
│  Recommended action:                                         │
│   1. Move secret do environment variable                     │
│   2. Rotate AWS key (current may be compromised)             │
│   3. Audit AWS account dla unauthorized usage                │
│   4. Update .gitignore z config files                        │
│                                                              │
│  Fix template (operator approves before apply):              │
│   ┌────────────────────────────────────────────────────────┐ │
│   │  # backend/config.py                                   │ │
│   │  -AWS_SECRET_ACCESS_KEY = "AKIAIOSFODNN7..."           │ │
│   │  +AWS_SECRET_ACCESS_KEY = os.environ["AWS_SECRET_KEY"] │ │
│   │                                                        │ │
│   │  # .env (add to .gitignore)                            │ │
│   │  +AWS_SECRET_KEY=<new_rotated_key>                     │ │
│   └────────────────────────────────────────────────────────┘ │
│                                                              │
│  Compliance impact:                                          │
│   ⚠ GDPR: potential data breach if leaked                    │
│   ⚠ SOC 2: secret management failure                         │
│                                                              │
│  Akcje:                                                      │
│   [● Apply fix template]                                     │
│   [○ Operator manual fix]                                    │
│   [○ Defer (NOT recommended for CRITICAL)]                   │
│   [○ Mark false positive (z reason)]                         │
│                                                              │
│  ⚠ Pipeline blocked until resolved (CRITICAL severity)       │
└──────────────────────────────────────────────────────────────┘
```

---

## 8.8. Threat intelligence integration

### 8.8.1. Real-time threat detection

```
┌──────────────────────────────────────────────────────────────┐
│  🚨  Threat Intel Alert — Active Exploit Detected            │
│                                                              │
│  Source: CISA KEV (Known Exploited Vulnerabilities)          │
│  Updated: 2 hours ago                                        │
│                                                              │
│  Vulnerability: CVE-2026-1234                                │
│  Affected: log4j 2.x (≤ 2.20.0)                              │
│  Status: Active exploitation w wild                          │
│  Exploit difficulty: LOW (publicly available)                │
│                                                              │
│  Operator's exposure:                                        │
│   ⚠ Found w 3 projects:                                       │
│   • Sylion Tailor v3 (production)                            │
│   • Customer Acme (production)                               │
│   • Internal Dashboard (staging)                             │
│                                                              │
│  Recommended urgent action:                                  │
│   1. Update log4j to 2.21.0+ w wszystkich projektach         │
│   2. Apply mitigation: -Dlog4j2.formatMsgNoLookups=true      │
│   3. Scan logs dla exploitation attempts                     │
│   4. Notify customers if production at risk                  │
│                                                              │
│  Auto-actions taken:                                         │
│   ✓ Threat intel updated                                     │
│   ✓ Operator notified (all channels)                         │
│   ✓ Affected projects flagged                                │
│   ✓ Mitigation suggestion ready                              │
│                                                              │
│  Manual actions needed:                                      │
│   [Generate update PRs dla wszystkich projects]              │
│   [Scan logs dla exploitation]                               │
│   [Notify customers]                                         │
│   [Escalate do incident response]                            │
└──────────────────────────────────────────────────────────────┘
```

---

## 8.9. Incident response automation

### 8.9.1. Incident response workflows

```
┌──────────────────────────────────────────────────────────────┐
│  Incident Response Automation                                │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Predefined runbooks dla common incidents:                   │
│                                                              │
│  1. CREDENTIAL LEAK                                          │
│     Auto-actions:                                            │
│      ✓ Revoke credential immediately                         │
│      ✓ Audit recent activity (24h)                           │
│      ✓ Alert operator (all channels)                         │
│      ✓ Generate incident report                              │
│     Manual:                                                  │
│      • Investigate exposure scope                            │
│      • Notify affected users (jeśli customer data)           │
│                                                              │
│  2. CRYPTOJACKING                                            │
│     Auto-actions:                                            │
│      ✓ Isolate affected device/instance                      │
│      ✓ Snapshot dla forensic                                 │
│      ✓ Block outbound do mining pools                        │
│     Manual:                                                  │
│      • Investigate root cause                                │
│      • Wipe and redeploy                                     │
│      • Notify customer                                       │
│                                                              │
│  3. DATA EXFILTRATION                                        │
│     Auto-actions:                                            │
│      ✓ Block outbound transfer                               │
│      ✓ Alert all channels                                    │
│      ✓ Snapshot system state                                 │
│      ✓ Audit access logs                                     │
│     Manual:                                                  │
│      • Forensic analysis                                     │
│      • Customer notification (likely required)               │
│      • Regulatory notification (GDPR Art. 33)                │
│                                                              │
│  4. BRUTE FORCE ATTACK                                       │
│     Auto-actions:                                            │
│      ✓ Rate-limit offending IP                               │
│      ✓ Add to firewall blocklist                             │
│      ✓ Alert operator                                        │
│     Manual:                                                  │
│      • Review affected accounts                              │
│      • Force password reset jeśli compromise suspected       │
│                                                              │
│  5. RANSOMWARE INDICATORS                                    │
│     Auto-actions:                                            │
│      ✓ Isolate all affected systems                          │
│      ✓ Disable backup writes (preserve clean backups)        │
│      ✓ Emergency notification                                │
│     Manual:                                                  │
│      • Forensic analysis                                     │
│      • Restore from clean backups                            │
│      • Law enforcement notification (jeśli applicable)       │
│                                                              │
│  Custom runbooks: operator może dodawać własne                │
│  [+ Add custom runbook]                                      │
└──────────────────────────────────────────────────────────────┘
```

---

## 8.10. Compliance reporting

### 8.10.1. Auto-generated compliance reports

```
┌──────────────────────────────────────────────────────────────┐
│  Compliance Reports                                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  GDPR — Monthly Report                                       │
│   • Sub-processor inventory                                  │
│   • Data flows visualization                                 │
│   • DSR (Data Subject Requests) handled                      │
│   • Breach notifications (none = good)                       │
│   • Incident log summary                                     │
│   Format: PDF + JSON                                         │
│                                                              │
│  KSeF — Per Invoice                                          │
│   • Invoice format compliance                                │
│   • Submission status                                        │
│   • Archive proof                                            │
│   • Signature verification                                   │
│   Format: XML (for KSeF system)                              │
│                                                              │
│  Customer-specific compliance                                │
│   Per customer demands:                                       │
│    • Polish bank: KNF compliance attestation                 │
│    • Healthcare provider: HIPAA-equivalent                   │
│    • Government: KRI-PL                                      │
│                                                              │
│  Audit-ready package                                         │
│   On-demand: complete export dla external auditor            │
│   Includes:                                                  │
│    • All security findings + resolutions                     │
│    • Audit chain (signed, integrity-verified)                │
│    • Compliance attestations                                 │
│    • Sub-processor agreements                                │
│    • Data flow diagrams                                      │
│    • Encryption certifications                               │
│    Format: encrypted ZIP, ~50-500 MB                         │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 8.11. Edge Cases — Security Guard (22 cases)

### Kategoria A — False positives (5 cases)

#### EC-A1: Test code flagged as vulnerable

**Trigger**: Test fixtures use intentional weak passwords. Security Guard
flags as critical.

```
ℹ Security finding — test code

  Code: tests/fixtures/test_users.py
  Finding: Hardcoded password "password123"
  
  Operator response:
   [Mark test directory exempt from secret detection]
       Pattern: tests/**, fixtures/**
   [Use proper test secrets manager]
       Replace fixtures z env vars
```

#### EC-A2: Documentation example flagged

**Trigger**: README.md contains example "API_KEY=your_key_here" as
template. Flagged as exposed secret.

```
ℹ Security finding — documentation example

  File: README.md
  Finding: Possible API key (matches pattern)
  Actual: documentation placeholder
  
  Akcje:
   [Mark documentation patterns exempt]
   [Use clearly fake example: "<YOUR_API_KEY_HERE>"]
   [Suppress this finding]
```

#### EC-A3: Internal IP flagged as external

**Trigger**: Code references 192.168.x.x (internal network). Security Guard
flags as suspicious external IP.

```
ℹ Network finding — internal IP

  Code: docker-compose.yml
  Finding: Connection to 192.168.10.50
  Detected as: external connection (false positive)
  Actual: internal LAN address
  
  Akcje:
   [Mark RFC1918 ranges as internal]
       192.168.x.x, 10.x.x.x, 172.16-31.x.x
```

#### EC-A4: Open-source library license flagged

**Trigger**: Library uses GPL license. Operator's commercial project flags
as compliance issue. Actually OK because operator's not redistributing.

```
ℹ License compliance — context matters

  Library: libsomething (GPL-3.0)
  Operator project: SaaS (not redistributed)
  Initial flag: GPL incompatible z commercial
  
  Reality: GPL OK dla SaaS (not "distribution")
  
  Akcje:
   [Mark SaaS-specific exemption]
   [Add license exception note]
```

#### EC-A5: Compliance check too strict

**Trigger**: GDPR check flags every email log entry. Operator legitimately
needs email logs dla customer support.

```
ℹ Compliance balance

  Finding: 247 PII (emails) w application logs
  GDPR concern: PII exposure
  Business need: customer support requires email lookup
  
  Akcje:
   [Implement email hashing dla logs]
       Privacy-preserving but less convenient
   [Restrict log access do support team only]
       Audit log access
   [Reduce log retention (30d instead of 365d)]
   [Document business justification (DPIA)]
```

### Kategoria B — Detection gaps (5 cases)

#### EC-B1: Custom code patterns nie detected

**Trigger**: Operator's custom auth implementation has subtle bug. SAST
nie detects bo nie pasuje do standard patterns.

```
ℹ Detection gap — custom code

  Custom auth implementation w backend/auth.py
  Standard SAST: no findings
  Manual review: SQL injection possible w line 47
  
  Akcje:
   [Add custom Semgrep rule dla operator's pattern]
   [Submit pattern do Semgrep community]
   [Code review by Council Security role]
```

#### EC-B2: New CVE not yet w database

**Trigger**: 0-day vulnerability published. Operator's dependency vulnerable
ale CVE database nie updated.

```
ℹ Threat intel lag

  CVE: not yet published (0-day)
  Public report: 2 hours ago (Twitter security researcher)
  
  Risk: operator's dependency vulnerable
  
  Akcje:
   [Manually flag dependency]
       Treat as critical until CVE confirmed
   [Subscribe to security researcher feeds]
       Twitter, Mastodon, security blogs
   [Premium threat intel feed]
       Faster updates ($$$$)
```

#### EC-B3: Container scan false negative

**Trigger**: Trivy didn't detect vulnerability. Manual review found it.

```
⚠ Scanner gap

  Tool: Trivy (latest version)
  Finding: missed CVE w base image
  
  Operator's response:
   [Use multiple scanners (Grype + Trivy + Snyk)]
       Defense in depth
   [Report to Trivy maintainers]
   [Mark dependency as flagged manually]
```

#### EC-B4: Encrypted exfiltration nie detected

**Trigger**: Attacker uses HTTPS to exfiltrate (encrypted). Network
monitoring sees only encrypted traffic, can't inspect.

```
⚠ Encrypted traffic blind spot

  Detection: outbound HTTPS to unknown domain
  Volume: 850 GB w 48h
  Content: encrypted (cannot inspect)
  
  Likely: data exfiltration
  
  Akcje:
   [Block outbound to unknown destinations]
       Whitelist-only outbound policy
   [TLS inspection (corporate-grade)]
       Requires CA installation, performance hit
   [Behavioral analysis]
       Flag based on volume/timing/destination
```

#### EC-B5: Insider threat blind spot

**Trigger**: Authorized operator legitimately downloads customer data
mid-night. System cannot distinguish from compromise.

```
⚠ Anomaly vs legitimate

  Event: large customer data download by operator
  Time: 3:14 AM
  Location: unusual (operator's home, but VPN)
  
  Possible:
   • Operator working late (legitimate)
   • Operator account compromised
   • Operator's machine compromised
  
  Akcje:
   [Require MFA confirmation]
       Quick check, doesn't block work
   [Notify operator: "Confirm this was you?"]
   [Audit chain entry z context]
   [Don't block (operator may be legitimately working)]
```

### Kategoria C — Compliance issues (4 cases)

#### EC-C1: New regulation requires new check

**Trigger**: NIS2 directive aktywne. Operator's projekt requires new
compliance checks not yet w baseline.

```
ℹ New compliance requirement

  Regulation: NIS2 (EU, effective 2026-Q3)
  Affected: critical infrastructure projects
  Operator's exposure: 1 project (Sylion Tailor — payment platform)
  
  Required new checks:
   • Incident reporting within 24h
   • Risk management documentation
   • Supply chain security
   • Business continuity planning
  
  Akcje:
   [Enable NIS2 compliance framework]
       Adds 12 new checks
   [Use community NIS2 template]
   [Manual compliance work]
```

#### EC-C2: Compliance frameworks conflict

**Trigger**: GDPR wymaga data minimization. Customer wymaga 7-year
retention dla audit. Conflict.

```
⚠ Compliance frameworks conflict

  GDPR: minimize data, default short retention
  Customer audit: 7-year retention requirement
  
  Resolution:
   [Document business justification (DPIA)]
   [Implement minimization w other dimensions]
       Anonymize after 2 years, keep aggregate dla audit
   [Customer contractual override (z operator approval)]
   [Operator manual decision z legal advice]
```

#### EC-C3: Compliance certification expired

**Trigger**: ISO 27001 cert expired (Polcom example z faza 3).

```
⚠ Vendor certification lapsed

  Vendor: Polcom (sovereign cloud)
  Cert: ISO 27001 expired
  Customer impact: 4 projects use Polcom
  
  Akcje (z faza 3 EC-D5):
   [Notify high-risk customers]
   [Migrate critical workloads]
   [Track recertification timeline]
```

#### EC-C4: Audit-ready package generation

**Trigger**: Customer audit requires complete export. System generates
compliance package.

```
ℹ Audit Package Generation

  Project: Sylion Tailor v3
  Customer: KNF audit (Polish Financial Supervision)
  
  Generated:
   • Security findings + resolutions log
   • Audit chain (signed, integrity verified)
   • Compliance attestations (GDPR + KSeF)
   • Sub-processor agreements
   • Data flow diagrams
   • Encryption verification
   • Penetration test reports (if available)
  
  Format: encrypted ZIP, 187 MB
  
  Operator review przed sharing:
   [Review contents]  [Encrypt z customer's pubkey]  [Share]
```

### Kategoria D — Threat response (4 cases)

#### EC-D1: Auto-isolation breaks production

**Trigger**: Cryptojacking detected na production server. Auto-isolated.
Customer-facing service down.

```
🚨 Auto-isolation customer impact

  Server: hetzner-prod-1
  Detected: cryptojacking
  Auto-action: isolated (per incident response runbook)
  
  Side effect: customer-facing API down
  
  Tradeoffs:
   ✓ Stopped active attack
   ✗ Service degradation
  
  Akcje:
   [Failover do backup region]
       Restore service while investigating
   [Quick forensic snapshot, then restore]
       30 min downtime
   [Customer notification]
       Transparent communication
```

#### EC-D2: False positive triggers incident

**Trigger**: Threat intel feed has false positive. Auto-blocks legitimate
service.

```
⚠ False positive — auto-block

  Blocked: outbound to legitimate-cloud-provider.com
  Reason: threat intel listed as suspicious (false positive)
  Impact: deploys failing dla 30 min
  
  Akcje:
   [Whitelist legitimate destination]
   [Report false positive do threat intel provider]
   [Adjust auto-block threshold (require human approve)]
```

#### EC-D3: Response runbook fails

**Trigger**: Custom runbook script has bug. Incident response failed.

```
✗ Runbook execution failed

  Incident: detected attack
  Runbook: "Isolate compromised resources"
  Error: script syntax error w line 23
  
  Status: incident NOT contained automatically
  
  Manual response:
   [Operator manually isolates]
   [Fix runbook]
   [Test runbook regularly]
```

#### EC-D4: Multiple incidents same time

**Trigger**: 3 simultaneous incidents (coordinated attack?). Operator
overwhelmed.

```
🚨 Multiple incidents

  Active incidents:
   1. Brute force on Sylion Tailor login
   2. Suspicious outbound z Customer Acme
   3. Privilege escalation attempt na sovereign env
  
  Likely: coordinated attack
  
  Auto-coordination:
   ✓ All 3 isolated
   ✓ Forensic snapshots taken
   ✓ Threat intel feeds notified
   ✓ Operator emergency notification
  
  Manual prioritization:
   [Sovereign env first (highest sensitivity)]
   [Production projects next]
```

### Kategoria E — Recovery / migration (4 cases)

#### EC-E1: Threat intel feeds out of date

**Trigger**: Operator was offline 30 dni. Threat intel stale.

```
ℹ Threat intel refresh needed

  Last update: 32 dni temu
  Current state: stale
  
  Akcje:
   [Auto-refresh wszystkich feeds]
       ~5 min processing
   [Run scan z updated intel]
       Identify any newly-known threats
```

#### EC-E2: Custom rules broken po AEIS update

**Trigger**: AEIS update changed rule API. Custom security rules broken.

```
⚠ Custom rules incompatible

  AEIS: v3.0 → v3.1
  Affected: 3 custom security rules
  
  Akcje:
   [Auto-migrate rules]
   [Manual rewrite]
   [Disable until fixed]
```

#### EC-E3: Compliance framework deprecated

**Trigger**: Old version of GDPR framework retired. Operator's checks based
on old version.

```
ℹ Compliance framework update

  Framework: GDPR baseline
  Old version: v2024-Q1
  New version: v2026-Q1 (incorporates EDPB guidelines)
  
  Akcje:
   [Migrate to new framework]
       Recheck all GDPR compliance
   [Stay on old (operator's choice)]
       Marked as outdated
```

#### EC-E4: Audit chain integrity check fails po restore

**Trigger**: Operator restored backup. Audit chain hash mismatch.

```
⚠ Audit chain integrity broken po restore

  Issue: hash chain doesn't match z backup point onwards
  Reason: restored older state, but new entries continued
  
  Akcje:
   [Mark restoration point w audit chain]
       New chain segment z reference to restoration
   [Full audit re-validation]
   [Notify operator (chain forked)]
```

---

## 8.12. Inheritance + DoD — Security Guard

### 8.12.1. Acceptance test

```bash
$ aeis-cli phase8-acceptance-test

[Common requirements]
[1/6] 7 layers configured                            ✓ PASS
[2/6] Baseline 25 checks reviewed                    ✓ PASS
[3/6] Compliance frameworks selected                 ✓ PASS (GDPR + KSeF)
[4/6] Threat intel feeds enabled                     ✓ PASS (4 free)
[5/6] Incident response workflows                    ✓ PASS (5 runbooks)
[6/6] Audit chain entry phase_8.complete             ✓ PASS

[Goal-specific: cybersecurity]
[7/9] All 7 layers active                            ✓ PASS
[8/9] Threat modeling integration                    ⚠ WARN (manual)
[9/9] Penetration testing simulation                 ⚠ WARN (planned)

DoD: 7/9 ✓ + 2 ⚠
Phase 8 ACCEPTED.
```

---

# FAZA 9 — Quality Guard

> **Spis sekcji**:
> - 9.1 — Sense fazy + relacja do test strategy z fazy 4
> - 9.2 — Test levels (L1-L5) integration
> - 9.3 — Triggers + quality gates
> - 9.4 — Severity levels + thresholds
> - 9.5 — Detection (test runners + analyzers)
> - 9.6 — Baseline 20 quality checks
> - 9.7 — Findings handling + auto-fix iterations
> - 9.8 — Performance metrics tracking
> - 9.9 — Quality reporting
> - 9.10 — Edge cases (22) + inheritance + DoD

---

## 9.1. Sense fazy + relacja do test strategy

### 9.1.1. Quality Guard vs test strategy

Test strategy z fazy 4 zdefiniowała **co testować**. Quality Guard z fazy 9
**enforces** test execution + analyzes results + generates verdicts.

```
┌──────────────────────────────────────────────────────────────┐
│  Quality Guard vs Test Strategy                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Test Strategy (Faza 4):                                     │
│   • Defines what tests exist                                 │
│   • Defines coverage targets                                 │
│   • Defines mandatory human-like UI testing                  │
│                                                              │
│  Quality Guard (Faza 9):                                     │
│   • Enforces test execution                                  │
│   • Analyzes results                                         │
│   • Generates pass/fail verdicts                             │
│   • Tracks regression                                        │
│   • Auto-fix iterations (per autonomy)                       │
│   • Performance benchmarking                                 │
│   • Code quality metrics                                     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 9.1.2. Wynik fazy 9 (DoD)

```
✓ Test execution gates configured per phase
✓ Quality thresholds defined (z DIM-7 z fazy 5)
✓ Auto-fix behavior set per autonomy
✓ Performance benchmarks established
✓ Quality reports auto-generated
✓ Audit chain entry: phase_9.complete
```

---

## 9.2. Test levels integration

### 9.2.1. L1-L5 test levels

```
┌──────────────────────────────────────────────────────────────┐
│  Test Levels (z faza 4 expanded)                             │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  L1 — Unit                                                   │
│   Frameworks: pytest, vitest, jest                            │
│   Coverage target: 80%                                       │
│   Run frequency: per build, per commit                       │
│   Cost: ~$0.10 per build                                     │
│                                                              │
│  L2 — Integration                                            │
│   Frameworks: pytest fixtures, supertest                     │
│   Coverage: API contracts, DB integration                    │
│   Run: per build                                             │
│   Cost: ~$0.30 per build                                     │
│                                                              │
│  L3 — E2E                                                    │
│   Frameworks: Playwright                                     │
│   Coverage: critical user journeys                           │
│   Run: per build                                             │
│   Cost: ~$0.80 per build                                     │
│                                                              │
│  L4 — Performance                                            │
│   Frameworks: k6, Locust                                     │
│   Coverage: load testing, latency benchmarks                 │
│   Run: pre-prod only (default off)                           │
│   Cost: ~$3-10 per build                                     │
│                                                              │
│  L5 — Human-like UI testing (MANDATORY z fazy 4)              │
│   Framework: Playwright + AEIS observation engine            │
│   Coverage: 25-40 scenarios per project                      │
│   Run: pre-prod always, optionally per build                 │
│   Cost: ~$8-16 per project                                   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 9.3. Triggers + quality gates

```
Continuous: per file save (relevant tests run incrementally)
Phase boundaries:
  Faza 35 (Build): full L1+L2 run
  Faza 37 (Quality Gates): all enabled levels
  Faza 39 (Pre-deploy): L5 human-like + L4 if enabled

Hard gate dla deploy:
  L1+L2+L3 must pass dla production deploy
  L5 (human-like) must pass dla customer-facing deploys
  L4 (performance) optional, configurable per project
```

---

## 9.4. Severity levels + thresholds

```
Per finding type:
  Test failure (L1):              ERROR
  Test failure (L2):              ERROR
  Test failure (L3):              CRITICAL
  Test failure (L5 human-like):   CRITICAL (impacts users)
  Coverage below target:          WARNING
  Coverage drop > 10%:            ERROR
  Performance regression > 20%:   CRITICAL
  Performance regression < 20%:   WARNING
  Code complexity over threshold: WARNING
  New code uncovered:             WARNING
  Linter errors:                  WARNING
  Type errors:                    ERROR
```

---

## 9.5. Detection — test runners + analyzers

```
┌──────────────────────────────────────────────────────────────┐
│  Quality Detection Stack                                     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Test runners (per language):                                │
│   Python:    pytest                                          │
│   JS/TS:     vitest, jest                                    │
│   Go:        go test                                         │
│   Rust:      cargo test                                      │
│   E2E:       Playwright                                      │
│                                                              │
│  Coverage tools:                                             │
│   Python:    coverage.py                                     │
│   JS/TS:     c8, istanbul                                    │
│   Combined:  reports aggregated                              │
│                                                              │
│  Code analyzers:                                             │
│   Linters: pylint, ruff, eslint, biome                       │
│   Type:    mypy, pyright, tsc                                │
│   Complexity: radon, ccnewline                               │
│   Security (cross-Guard): semgrep                            │
│                                                              │
│  Performance:                                                │
│   Load:     k6, Locust                                       │
│   Benchmark: pytest-benchmark, vitest bench                  │
│   Profile:  py-spy, clinic.js                                │
│                                                              │
│  Visual regression (L5):                                     │
│   Playwright screenshots vs baseline                         │
│   Pixel diff threshold: 5% default                           │
│                                                              │
│  Human-like observation (L5):                                │
│   AEIS observation engine                                    │
│   • Console error detection                                  │
│   • Network error detection                                  │
│   • Visual regression                                        │
│   • Layout shift                                             │
│   • Animation issues                                         │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 9.6. Baseline 20 quality checks

```
┌──────────────────────────────────────────────────────────────┐
│  Quality Baseline Checks (20)                                │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  TEST EXECUTION (5)                                          │
│   1. L1 unit tests pass                                      │
│   2. L2 integration tests pass                               │
│   3. L3 E2E tests pass                                       │
│   4. L5 human-like UI scenarios pass                         │
│   5. Test execution time within budget                       │
│                                                              │
│  COVERAGE (4)                                                │
│   6. L1 coverage >= 80%                                      │
│   7. New code coverage >= 90%                                │
│   8. Coverage trend (no regression)                          │
│   9. Critical paths covered (auth, payment, data)            │
│                                                              │
│  CODE QUALITY (4)                                            │
│   10. Linter errors = 0                                      │
│   11. Type errors = 0                                        │
│   12. Cyclomatic complexity < 15 per function                │
│   13. Duplicate code < 5%                                    │
│                                                              │
│  PERFORMANCE (3)                                             │
│   14. P95 latency within budget                              │
│   15. Memory usage stable                                    │
│   16. Throughput meets target                                │
│                                                              │
│  RELIABILITY (4)                                             │
│   17. Error rate < 0.1%                                      │
│   18. Retry/resilience patterns implemented                  │
│   19. Logging completeness                                   │
│   20. Monitoring instrumentation                             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 9.7. Findings handling + auto-fix iterations

### 9.7.1. Auto-fix iteration model

```
Auto-fix workflow per autonomy:

  Conservative: max 0 auto-fix iterations (operator manual)
  Balanced:     max 3 auto-fix iterations
  Aggressive:   max 5 auto-fix iterations
  Production:   max 0 auto-fix iterations (review każdą fix)
  Research:     max 10 auto-fix iterations

Per iteration:
  1. Quality Guard detects test failure
  2. LLM analyzes failure + suggests fix
  3. Fix applied
  4. Tests re-run
  5. If passes → success, exit loop
  6. If fails → next iteration (if budget remains)
  7. If budget exhausted → operator review

Each iteration costs $1-5 (LLM analysis + test re-run)
```

### 9.7.2. Smart fix prioritization

```
LLM analyzes failure type:

  Easy fixes (high confidence auto-fix):
   • Off-by-one errors
   • Wrong import paths
   • Linter style issues
   • Missing test assertions
  
  Medium difficulty (operator confirms):
   • Logic errors
   • Edge case handling
   • Race conditions
  
  Hard (always operator):
   • Architecture issues
   • Security vulnerabilities
   • Performance regressions root cause
   • Customer-facing changes
```

---

## 9.8. Performance metrics tracking

```
┌──────────────────────────────────────────────────────────────┐
│  Performance Metrics                                         │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Tracked per project:                                        │
│   • API endpoint latency (P50/P95/P99)                       │
│   • Database query times                                     │
│   • Frontend render times                                    │
│   • Memory usage profiles                                    │
│   • Throughput (requests/second)                             │
│   • Error rates                                              │
│                                                              │
│  Baselines:                                                   │
│   Established po first 3 builds                              │
│   Auto-update gdy operator approves new baseline             │
│   Regression alerts gdy >20% degradation                     │
│                                                              │
│  Per-deployment comparison:                                  │
│   • Before vs after deploy                                   │
│   • Trend over last 30 deployments                           │
│   • Compared to similar projects                             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 9.9. Quality reporting

```
Reports:
  Per-build: pass/fail summary
  Per-PR: detailed findings + auto-fix log
  Per-deployment: production readiness
  Project closure: comprehensive quality report
  
  Closure report includes:
   • Total tests run
   • Coverage achieved
   • Performance benchmarks
   • Auto-fix history
   • Manual operator interventions
   • Quality trends
   • Recommendations dla future projects
```

---

## 9.10. Edge Cases — Quality Guard (22 cases)

### Kategoria A — Test execution (5 cases)

#### EC-A1: Flaky tests

**Trigger**: Same test passes/fails randomly (10% failure rate).

```
⚠ Flaky test detected

  Test: test_payment_concurrent_processing
  Failure rate: 12% (last 50 runs)
  Pattern: random, no clear trigger
  
  Akcje:
   [Mark as flaky (run 3x, accept majority)]
   [Investigate root cause]
       Likely: race condition
   [Disable until fixed]
       Risk: missing real bugs
```

#### EC-A2: Test environment unavailable

**Trigger**: Test database down. L2 tests cannot run.

```
✗ Test environment failure

  Component: test PostgreSQL container
  Status: failed to start
  
  Akcje:
   [Auto-restart container]
   [Skip L2, run L1 only]
       Mark build incomplete quality
   [Fail build (require all levels)]
```

#### EC-A3: Test exceeds timeout

**Trigger**: E2E test taking 10+ minutes. Default timeout 5 min.

```
⚠ Test timeout

  Test: test_full_user_journey
  Timeout: 5 min reached
  Actual progress: 60% complete
  
  Akcje:
   [Increase timeout to 15 min]
   [Optimize test (split into smaller scenarios)]
   [Investigate slowdown]
       Could be performance regression
```

#### EC-A4: Tests pass locally, fail w CI

**Trigger**: Operator's local environment works. CI environment fails.

```
⚠ Environment-specific failure

  Local: tests pass
  CI: tests fail
  
  Likely causes:
   • Different OS (macOS local, Linux CI)
   • Different timezone
   • Missing dependency
   • Race condition (different concurrency)
  
  Akcje:
   [Replicate CI locally w Docker]
   [Add environment-specific test config]
   [Pin dependencies more strictly]
```

#### EC-A5: Test data corruption

**Trigger**: Test fixtures corrupted. Tests use stale/wrong data.

```
⚠ Test fixtures issue

  Issue: test_users.json contains stale data
  Tests assume specific user IDs that no longer exist
  
  Akcje:
   [Regenerate fixtures from current schema]
   [Use factory pattern instead of static fixtures]
   [Snapshot fixtures z each migration]
```

### Kategoria B — Coverage issues (4 cases)

#### EC-B1: Coverage drops po refactor

**Trigger**: Operator refactored auth module. Coverage dropped 80% → 65%.

```
⚠ Coverage regression

  Before: 80% coverage
  After: 65% coverage
  Reason: refactor introduced untested code paths
  
  Akcje:
   [Generate tests dla new code (LLM-assisted)]
   [Operator manually adds tests]
   [Accept temporary drop, fix in follow-up]
```

#### EC-B2: Coverage gaming (low-quality tests)

**Trigger**: Operator added many shallow tests just dla coverage. Real
quality didn't improve.

```
ℹ Coverage quality analysis

  Coverage: 92% (high)
  Mutation testing: 45% mutations survive (low)
  Implication: many tests don't actually verify behavior
  
  Akcje:
   [Run mutation testing dla quality assessment]
   [Review low-quality tests]
   [Set mutation testing threshold]
```

#### EC-B3: Critical paths uncovered

**Trigger**: Overall coverage 85%, ale payment processing 30% covered.

```
⚠ Critical path coverage gap

  Overall: 85%
  Payment module: 30%
  Auth module: 95%
  
  Recommendation: weighted coverage by criticality
  
  Akcje:
   [Set per-module coverage targets]
       Payment: 95%, Auth: 90%, Other: 70%
   [Block deploy if critical paths < threshold]
```

#### EC-B4: Coverage tool inconsistent

**Trigger**: Different coverage tools report different numbers (78% vs 84%).

```
ℹ Coverage tool variance

  Tool A (coverage.py): 78%
  Tool B (codecov): 84%
  Difference: 6%
  
  Cause: different inclusion criteria
  
  Akcje:
   [Standardize on one tool]
   [Document criteria w docs]
```

### Kategoria C — Auto-fix issues (5 cases)

#### EC-C1: Auto-fix causes regression

**Trigger**: Auto-fix attempt 1 introduced new bug. Iteration 2 fixed but
broke something else.

```
⚠ Auto-fix regression cycle

  Iteration 1: fixed test_payment, broke test_refund
  Iteration 2: fixed test_refund, broke test_payment
  Pattern: oscillation
  
  Akcje:
   [Stop auto-fix, operator review]
       Both tests likely have shared dependency issue
   [Different LLM model dla next attempt]
       Try opus instead of sonnet
   [Increase iteration budget]
```

#### EC-C2: Auto-fix exceeds budget

**Trigger**: 5 iterations consumed, tests still failing.

```
⚠ Auto-fix budget exhausted

  Iterations used: 5/5
  Cost so far: $7.40
  Tests passing: 47/52 (5 still failing)
  
  Akcje:
   [Increase budget (operator approve)]
   [Operator manual review]
   [Mark project failed (require manual)]
```

#### EC-C3: Auto-fix changes break unrelated code

**Trigger**: Auto-fix dla test A modified shared module. Test B (passing)
now fails.

```
⚠ Auto-fix collateral damage

  Fix dla: test_login
  Modified: shared/auth_helpers.py
  New failures: test_signup, test_password_reset
  
  Akcje:
   [Revert and try different approach]
   [Operator review shared module changes]
```

#### EC-C4: Auto-fix touches forbidden files

**Trigger**: Auto-fix wants modify migration file. Migrations should be
immutable.

```
⚠ Auto-fix forbidden file

  Attempted: modify db/migrations/0042_add_users.sql
  Policy: migrations immutable (audit trail integrity)
  
  Akcje:
   [Block fix, suggest different approach]
   [Operator manual: write new migration]
```

#### EC-C5: Auto-fix introduces security issue

**Trigger**: Auto-fix made test pass by bypassing security check. Security
Guard catches issue.

```
🚨 Auto-fix bypassed security

  Auto-fix: removed authentication check w test
  Security Guard: flagged as security regression
  
  Akcje:
   [Revert auto-fix immediately]
   [Block similar auto-fix patterns]
   [Operator manual fix z security review]
```

### Kategoria D — Performance issues (4 cases)

#### EC-D1: Performance regression na production

**Trigger**: Latency P95 jumped 200ms → 800ms po deploy.

```
🚨 Performance regression

  Metric: API P95 latency
  Before: 200ms
  After: 800ms (+300%)
  
  Likely cause: recent deploy
  
  Akcje:
   [Auto-rollback]
   [Investigate root cause]
   [Performance test before next deploy]
```

#### EC-D2: Memory leak detected

**Trigger**: Memory usage steadily increasing over 24h.

```
⚠ Memory leak

  Pattern: 50MB/h increase
  After 24h: +1.2GB usage
  Will OOM w ~5 dni
  
  Akcje:
   [Restart service (temporary)]
   [Profile memory (find leak)]
   [Auto-restart schedule weekly]
```

#### EC-D3: Performance baseline outdated

**Trigger**: Project grew 10x. Old baselines irrelevant.

```
ℹ Performance baseline obsolete

  Baseline: established 6 months ago
  Project size: grew 10x
  Baseline irrelevant
  
  Akcje:
   [Establish new baseline (recent 30 builds)]
   [Operator approve new baseline]
```

#### EC-D4: Performance test costly

**Trigger**: L4 tests cost $10 per run. Operator running too often.

```
ℹ Performance test cost

  L4 cost: $10/run
  Frequency: 8/day (excessive)
  Monthly cost: $2400 dla L4 alone
  
  Akcje:
   [Reduce to pre-prod only]
   [Use smaller test load]
   [Schedule (nightly)]
```

### Kategoria E — Recovery / migration (4 cases)

#### EC-E1: Test history lost

**Trigger**: Test history database corrupted. Cannot show trends.

```
⚠ Test history loss

  Lost: 3 months of test results
  Impact: no trend analysis possible
  
  Akcje:
   [Rebuild from CI artifacts (jeśli archived)]
   [Start fresh history]
   [Restore z backup]
```

#### EC-E2: Framework migration

**Trigger**: Operator migrates jest → vitest. Old test results compare to
new differently.

```
ℹ Test framework migration

  Old: Jest
  New: Vitest
  Impact: different test naming, different timing
  
  Akcje:
   [Mark transition w history]
   [Establish new baseline]
```

#### EC-E3: Coverage tool change

**Trigger**: Switched coverage tool. Numbers don't compare.

```
ℹ Coverage tool change

  Old: coverage.py (78% historical)
  New: codecov (84% same code)
  Difference: criteria
  
  Akcje:
   [Document tool change w timeline]
   [Re-baseline]
```

#### EC-E4: Test data sync

**Trigger**: Operator imports workspace. Test fixtures missing.

```
ℹ Test data import

  Workspace import: missing test fixtures
  Tests will fail without fixtures
  
  Akcje:
   [Generate fixtures from schema]
   [Operator provides fixtures separately]
   [Use minimal fixtures + mark coverage incomplete]
```

---

## 9.11. Inheritance + DoD — Quality Guard

```bash
$ aeis-cli phase9-acceptance-test

[Common requirements]
[1/6] Test levels integration                        ✓ PASS (L1-L5)
[2/6] Quality thresholds (z DIM-7)                   ✓ PASS
[3/6] Auto-fix configured per autonomy               ✓ PASS
[4/6] Performance baselines                          ✓ PASS
[5/6] Reporting cadence                              ✓ PASS
[6/6] Audit chain entry phase_9.complete             ✓ PASS

DoD: 6/6 ✓
Phase 9 ACCEPTED.
```

---

# FAZA 10 — Provenance Guard

> **Spis sekcji**:
> - 10.1 — Sense fazy + provenance jako foundation
> - 10.2 — Audit chain architecture
> - 10.3 — Artifact provenance tracking
> - 10.4 — Cryptographic integrity
> - 10.5 — Operator action attribution
> - 10.6 — External event correlation
> - 10.7 — Compliance evidence generation
> - 10.8 — Forensic capabilities
> - 10.9 — Edge cases (22) + inheritance + DoD

---

## 10.1. Sense fazy + provenance jako foundation

### 10.1.1. Czym jest Provenance Guard

Provenance Guard to **foundation Guard** — inne Guards bazują na audit
chain który Provenance Guard maintains.

```
┌──────────────────────────────────────────────────────────────┐
│  Provenance Guard — The Foundation                            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Czym jest provenance:                                       │
│   • Każda akcja w AEIS ma origin (kto/co zrobiło)            │
│   • Każdy artifact ma traceable history                       │
│   • Każda decyzja ma cryptographic proof                     │
│   • Każda zmiana jest tamper-evident                         │
│                                                              │
│  Po co:                                                      │
│   • Compliance (GDPR, ISO 27001, audit-ready)                │
│   • Debugging (jak doszło do tego stanu?)                    │
│   • Trust (operator może verify że nic nie zmienione)        │
│   • Forensic (post-incident investigation)                    │
│   • Customer protection (audit-able dla customers)            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 10.1.2. Wynik fazy 10 (DoD)

```
✓ Audit chain configured (hash algorithm, signing key)
✓ Artifact provenance tracking enabled
✓ Cryptographic integrity verified
✓ Compliance evidence templates ready
✓ Forensic capabilities available
✓ Audit chain entry: phase_10.complete
```

---

## 10.2. Audit chain architecture

### 10.2.1. Hash chain structure

```
┌──────────────────────────────────────────────────────────────┐
│  Audit Chain Structure                                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Each entry:                                                 │
│   {                                                          │
│     "ts": "2026-04-29T14:32:18.234Z",                        │
│     "event": "council.decision_made",                        │
│     "actor": {                                               │
│       "type": "system|operator|external",                    │
│       "id": "council-chair",                                 │
│       "model": "claude-opus-4-7"                             │
│     },                                                       │
│     "subject": {                                             │
│       "project": "sylion-tailor-v3",                         │
│       "phase": "23",                                         │
│       "decision_id": "dec_xyz789"                            │
│     },                                                       │
│     "data": { ...event-specific... },                        │
│     "prev_hash": "sha256:...",                               │
│     "hash": "sha256:..."                                     │
│   }                                                          │
│                                                              │
│  Hash chain:                                                 │
│   entry[N].hash = sha256(entry[N].data + entry[N-1].hash)    │
│   Genesis: entry[0].prev_hash = "0" * 64                     │
│                                                              │
│  Tamper detection:                                           │
│   Any modification breaks chain                               │
│   Verification: re-compute hashes from genesis                │
│                                                              │
│  Storage:                                                     │
│   ~/.sylion/<op>/audit/chain.jsonl                           │
│   Append-only file                                            │
│   Periodic checkpointing dla performance                     │
│                                                              │
│  Optional signing:                                           │
│   ☑ Sign każdą entry z operator's Ed25519 key                │
│   ☑ Sign checkpoints dla efficient verification              │
│   ☐ External timestamp authority (RFC 3161)                  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 10.2.2. Event categories

```
Audit chain captures all events:

  WORKSPACE
   • workspace.created
   • workspace.exported
   • workspace.imported
   • settings.changed
   • master_password.changed
  
  PROJECT
   • project.created
   • project.phase_transitioned
   • project.completed
   • project.archived
  
  COUNCIL
   • council.formed
   • council.deliberation_started
   • council.decision_made
   • council.finalized
  
  BUILD
   • build.started
   • build.phase_completed
   • build.failed
   • build.completed
   • build.artifact_created
  
  DEPLOY
   • deploy.proposed
   • deploy.approved
   • deploy.executed
   • deploy.rolled_back
  
  GUARD
   • guard.finding_detected
   • guard.finding_resolved
   • guard.finding_suppressed
   • guard.action_taken
  
  OPERATOR
   • operator.approved
   • operator.rejected
   • operator.overrode
   • operator.bypassed_gate
  
  EXTERNAL
   • external.api_called
   • external.notification_sent
   • external.deploy_received
   • external.customer_action
  
  SECURITY
   • security.incident_detected
   • security.incident_resolved
   • security.credential_rotated
```

---

## 10.3. Artifact provenance tracking

### 10.3.1. Per-artifact lineage

```
Artifact: sylion-tailor-v3-build-abc123.tar.gz

Provenance:
  Created: 2026-04-29 14:32
  Sources:
   • Code: git commit a1b2c3d (Sylion Tailor repo)
   • Council decision: dec_xyz789 (faza 23)
   • Masterplan: ms_def456 (faza 28)
   • Test results: tr_ghi789 (faza 37)
   • Build environment: build-worker-7
   • Dependencies: package-lock.json hash
  
  Transformations:
   1. Code compilation (build script v1.2)
   2. Asset bundling (webpack 5.x)
   3. Container packaging (Docker buildx)
   4. Signing (operator's Ed25519 key)
  
  Verification:
   ✓ All sources hash-verified
   ✓ All transformations logged
   ✓ Signature valid
   ✓ Audit chain references complete
  
  Used by:
   • Deployed do hetzner-prod-1 (deploy_id: dep_jkl012)
   • Customer Acme deploy: scheduled
```

### 10.3.2. Artifact verification API

```bash
$ aeis-cli verify-artifact sylion-tailor-v3-build-abc123.tar.gz

Verifying artifact provenance...

✓ Artifact hash matches manifest
✓ Source code commit verified (a1b2c3d)
✓ Council decision present (dec_xyz789, faza 23)
✓ Masterplan reference valid (ms_def456)
✓ Test results present (tr_ghi789, all passed)
✓ Build environment authenticated
✓ Dependencies match lock file
✓ All transformations documented
✓ Signature valid (operator Ed25519)
✓ Audit chain unbroken from genesis

Verification: PASSED
Artifact authentic and tamper-free.
```

---

## 10.4. Cryptographic integrity

### 10.4.1. Multi-layer signing

```
┌──────────────────────────────────────────────────────────────┐
│  Cryptographic Integrity                                     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Layer 1 — Hash chain                                        │
│   Algorithm: SHA-256                                         │
│   Purpose: detect any tampering                              │
│   Cost: $0 (lokalne computation)                             │
│                                                              │
│  Layer 2 — Operator signing                                  │
│   Algorithm: Ed25519                                         │
│   Purpose: prove operator authorized actions                 │
│   Storage: encrypted z master password                       │
│                                                              │
│  Layer 3 — Periodic checkpointing                            │
│   Frequency: hourly                                          │
│   Purpose: efficient verification (don't recompute from genesis)│
│   Format: signed checkpoint z hash range                     │
│                                                              │
│  Layer 4 — External timestamping (optional)                  │
│   Service: RFC 3161 TSA                                      │
│   Purpose: prove "this happened before time T"               │
│   Cost: $X per timestamp (operator's TSA subscription)       │
│                                                              │
│  Layer 5 — Blockchain anchoring (optional, advanced)         │
│   Service: Bitcoin OP_RETURN, Ethereum, OpenTimestamps       │
│   Purpose: ultimate immutability                             │
│   Cost: $X per anchor                                        │
│   Use: high-stakes compliance only                            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 10.4.2. Key management

```
Operator's signing keypair:
  Private key: Ed25519
  Storage: encrypted z master password (faza 1)
  Backup: 24-word seed (operator stores offline)
  Rotation: yearly recommended
  
Recovery:
  Lost master password → cannot decrypt private key
  Lost seed → cannot recover key → audit chain unsignable from this point
  Mitigation: operator must backup seed safely
```

---

## 10.5. Operator action attribution

### 10.5.1. Per-action attribution

```
Every operator action attributed:
  
  Operator approves hard gate:
   {
     "event": "operator.approved",
     "actor": "robert.k",
     "device": "mobile",
     "auth_method": "biometric",
     "ip": "192.168.1.x",
     "user_agent": "AEIS Mobile iOS 17.2",
     "decision": "deploy_to_production",
     "context": { ... },
     "signature": "ed25519:..."
   }
  
  Operator overrides Guard finding:
   {
     "event": "operator.overrode",
     "actor": "robert.k",
     "guard": "security",
     "finding": "f_xyz789",
     "reason": "False positive, internal IP",
     "signature": "ed25519:..."
   }
  
  Operator changes settings:
   {
     "event": "settings.changed",
     "actor": "robert.k",
     "setting": "autonomy_preset",
     "old_value": "Balanced",
     "new_value": "Aggressive",
     "signature": "ed25519:..."
   }
```

---

## 10.6. External event correlation

### 10.6.1. Multi-source event linking

```
Provenance Guard correlates events z different sources:
  
  Customer reports bug → linked do:
   • Specific deploy event
   • Build that produced version
   • Council deliberation that approved feature
   • Code commits that introduced
   
  Cost spike → linked do:
   • Specific Council session
   • Models used
   • Operator decisions made
   
  Security incident → linked do:
   • Configuration changes
   • Operator actions
   • External access events
```

---

## 10.7. Compliance evidence generation

### 10.7.1. Per-compliance evidence packages

```
GDPR Article 30 (Records of processing):
  Auto-generated z audit chain:
   • All processing activities listed
   • Categories of data
   • Recipients
   • Cross-border transfers
   • Retention periods
   • Security measures
  
ISO 27001 evidence:
  • Access logs
  • Change management records
  • Incident response records
  • Audit trails
  • Vendor management
  
SOC 2 evidence:
  • Operational effectiveness
  • Change management
  • Logical access
  • System monitoring
```

---

## 10.8. Forensic capabilities

### 10.8.1. Time-travel queries

```
$ aeis-cli forensic --project sylion-tailor-v3 \
                    --time "2026-04-29 14:00 - 16:00"

Reconstructing project state...

State at 2026-04-29 14:00:
  Project status: building (faza 35)
  Active workers: 4
  Cost so far: $42.20
  Council decisions: 12 (all approved)
  
Events 14:00-16:00:
  14:32:08 — Council Chair finalized decision dec_xyz789
  14:35:21 — Build worker 3 started component "PaymentForm"
  14:42:15 — Test failure: test_payment_validation
  14:42:18 — Auto-fix triggered (iteration 1)
  14:45:30 — Auto-fix succeeded
  14:48:00 — Build phase 2 complete
  ...

State at 2026-04-29 16:00:
  Project status: testing (faza 37)
  Active workers: 0
  Cost so far: $58.40
  ...

[Full forensic export]  [Specific event details]
```

### 10.8.2. Causal chain reconstruction

```
$ aeis-cli forensic --incident sec_inc_456 \
                    --reconstruct-chain

Causal chain dla incident "Hardcoded credential leak":

  Root cause: 2026-04-25 09:14
   Operator (robert.k) committed config.py z hardcoded key
   Reason: debugging session, forgot to remove
  
  Detection: 2026-04-29 14:32
   Security Guard SAST scan detected
   Severity: CRITICAL
  
  Response: 2026-04-29 14:33-14:45
   ✓ Auto-isolated affected service
   ✓ Operator notified
   ✓ Key rotated
   ✓ Code fixed
  
  Resolution: 2026-04-29 15:02
   Operator confirmed key rotated, no exploitation detected
  
  Lessons learned (auto-generated):
   • Pre-commit hook nie caught hardcoded key
   • Recommend: enable pre-commit secret detection
   • Recommend: code review by Security role
```

---

## 10.9. Edge Cases — Provenance Guard (22 cases)

### Kategoria A — Chain integrity (5 cases)

#### EC-A1: Hash chain broken

**Trigger**: Disk corruption broke audit chain. Hash mismatch.

```
🚨 Audit chain integrity broken

  Issue: hash mismatch at entry #8472
  Suspect: disk corruption (no tampering evidence)
  
  Akcje:
   [Restore z backup]
       Lose recent entries
   [Mark broken segment]
       Continue z new chain segment z reference
   [Forensic analysis]
       Determine if tampering or corruption
```

#### EC-A2: Signing key lost

**Trigger**: Operator lost master password, cannot decrypt signing key.

```
🚨 Signing key inaccessible

  Issue: cannot decrypt key (master password required)
  Impact: future entries cannot be signed
  
  Akcje:
   [Recover z seed (operator's offline backup)]
       Best case
   [Generate new keypair]
       Mark transition w chain
       Old entries remain signed z old key
       New entries signed z new key
```

#### EC-A3: Time skew

**Trigger**: Operator's machine clock wrong. Audit timestamps inconsistent.

```
⚠ Clock skew detected

  System clock: 2026-04-29 14:32
  NTP truth: 2026-04-29 14:45
  Skew: -13 minutes
  
  Recent entries timestamps wrong.
  
  Akcje:
   [Sync clock z NTP]
   [Mark affected entries w correction]
   [Re-sign affected entries z corrected timestamps]
```

#### EC-A4: Chain too large

**Trigger**: Audit chain has 10M+ entries. Verification slow.

```
ℹ Chain optimization needed

  Entries: 10.4 million
  Full verification time: 4 hours
  
  Akcje:
   [Enable checkpointing (hourly)]
       Verification: ~5 min vs 4 hours
   [Archive old segments]
       Move > 1 year old do cold storage
   [Compress storage]
       JSONL → binary format
```

#### EC-A5: External timestamping fails

**Trigger**: TSA service down. Cannot get external timestamps.

```
⚠ External timestamping unavailable

  TSA: ⚠ down (last 30 min)
  Pending entries: 47
  
  Akcje:
   [Queue entries dla later timestamping]
   [Use backup TSA]
   [Continue without external timestamps (degraded)]
```

### Kategoria B — Provenance gaps (5 cases)

#### EC-B1: External tool no provenance

**Trigger**: Operator used external tool (text editor) bez AEIS integration.
Changes lost from provenance.

```
⚠ Provenance gap

  Detected: file modified outside AEIS
  File: docs/architecture.md
  Modified: 2 hours ago
  Source: unknown (external editor)
  
  Akcje:
   [Mark provenance gap]
       Note: changes nie tracked
   [Operator provides context]
       Manual provenance entry
   [Auto-detect changes z file watcher]
       For future
```

#### EC-B2: Multi-machine operator

**Trigger**: Operator works on laptop + desktop. Provenance fragmented.

```
ℹ Multi-machine provenance

  Devices: laptop + desktop
  Audit chains: 2 separate chains
  
  Akcje:
   [Sync chains via cloud]
       Periodic merge
   [Designate primary (desktop)]
       Laptop syncs do desktop
   [Manual reconciliation]
```

#### EC-B3: Air-gapped provenance

**Trigger**: Air-gapped environment can't sync provenance real-time.

```
ℹ Air-gapped provenance

  Environment: air-gap-customer-x
  Sync: manual via USB
  
  Akcje:
   [Local audit chain w air-gap]
       Periodic export do main chain
   [Cryptographic linking on sync]
       Maintain integrity across boundary
```

#### EC-B4: Customer-side actions

**Trigger**: Customer modified deployed application. Operator's provenance
doesn't include.

```
ℹ Customer-side changes

  Customer: Tailor Master
  Action: changed product catalog (legitimate)
  Operator's audit: no record
  
  Akcje:
   [Customer-side AEIS agent (z faza 3 edge)]
       Send events do operator's chain
   [Periodic snapshot]
       Compare current state z operator's expectations
   [Treat customer ops as external events]
```

#### EC-B5: Lost notebook

**Trigger**: Operator's mobile lost. Mobile actions chain segment lost.

```
⚠ Mobile chain segment lost

  Device: stolen mobile
  Last sync: 6 hours before incident
  Lost: ~15 entries (mobile actions)
  
  Akcje:
   [Mark segment as lost]
   [Reconstruct z desktop logs jeśli possible]
   [Operator manual provenance entry]
```

### Kategoria C — Compliance evidence (4 cases)

#### EC-C1: Evidence package incomplete

**Trigger**: Customer audit requires evidence not w current scope.

```
⚠ Evidence gap

  Customer: KNF audit
  Required: evidence of multi-factor auth dla all admin
  Current: MFA enforced ale not documented w audit chain
  
  Akcje:
   [Add MFA enforcement events do future audit]
   [Generate retroactive evidence z config snapshots]
   [Operator manual attestation]
```

#### EC-C2: Evidence format conflict

**Trigger**: Customer wants PDF, AEIS produces JSON. Conversion needed.

```
ℹ Evidence format conversion

  AEIS native: JSON + Markdown
  Customer requires: PDF + signed
  
  Akcje:
   [Generate PDF z native data]
   [Sign PDF z operator's key]
   [Provide both formats]
```

#### EC-C3: Compliance period changed

**Trigger**: Auditor wants 5 years of evidence. Operator only kept 2.

```
⚠ Retention insufficient

  Auditor requires: 5 years evidence
  Operator retention: 2 years (default)
  
  Akcje:
   [Provide 2 years (with note)]
   [Increase retention dla future]
   [Negotiate scope z auditor]
```

#### EC-C4: Evidence accuracy challenge

**Trigger**: Customer disputes audit evidence accuracy.

```
⚠ Evidence dispute

  Customer claims: action X happened at time Y
  AEIS audit: shows action at time Z (different)
  
  Investigation:
   [Verify audit chain integrity]
       If intact: AEIS is authoritative
   [Compare external event sources]
   [Forensic deep dive]
```

### Kategoria D — Forensic capabilities (4 cases)

#### EC-D1: Forensic query expensive

**Trigger**: Time-travel reconstruction takes 30 min, costs $5.

```
ℹ Forensic query cost

  Query: reconstruct state at specific time
  Time: 30 min processing
  Cost: $5 (LLM analysis)
  
  Akcje:
   [Optimize z checkpoints]
   [Cache common queries]
   [Use cheaper model dla reconstruction]
```

#### EC-D2: Privacy concerns w forensic

**Trigger**: Forensic export includes PII. Customer data exposed do
auditor.

```
⚠ Forensic privacy

  Export contains: customer PII (per audit chain)
  Auditor cleared: only operator data, NOT customer PII
  
  Akcje:
   [Redact customer PII z export]
       Keep audit integrity proof
   [Separate exports]
       Operator data + redacted customer data
```

#### EC-D3: Causal chain ambiguous

**Trigger**: Multiple potential root causes. Cannot definitively identify
single cause.

```
ℹ Forensic ambiguity

  Multiple potential causes dla incident:
   • Operator change A (likely)
   • External event B (possible)
   • Hardware issue C (possible)
  
  Akcje:
   [Document all possibilities]
   [Probabilistic analysis]
   [Operator judgment]
```

#### EC-D4: Forensic across machines

**Trigger**: Incident spans operator's laptop + cloud + edge. Forensic
requires multi-source.

```
ℹ Multi-source forensic

  Sources:
   • Laptop audit chain
   • Cloud event logs
   • Edge device logs
   • Customer reports
  
  Akcje:
   [Aggregate sources]
   [Time-correlated reconstruction]
   [Single timeline view]
```

### Kategoria E — Recovery / migration (4 cases)

#### EC-E1: Audit chain corruption

**Trigger**: SQLite chain corrupted. Some entries lost.

```
⚠ Chain corruption

  Lost: ~200 entries (last 4 hours)
  Akcje:
   [Restore z backup]
   [Mark gap]
   [Reconstruct from secondary sources]
```

#### EC-E2: Workspace migration — chain integrity

**Trigger**: Migration breaks chain (different machine, different keys).

```
ℹ Migration provenance

  Original chain: continues z bridging entry
  New machine: signs continuation z new key
  
  Akcje:
   [Generate bridging entry]
       Cryptographically linked
   [Operator confirms migration legitimacy]
   [Mark transition w timeline]
```

#### EC-E3: AEIS update changes audit format

**Trigger**: New AEIS version uses different audit format. Old entries
incompatible.

```
ℹ Audit format migration

  AEIS: v3.0 → v3.1
  Format: JSON → JSON+protobuf
  
  Akcje:
   [Migrate old entries to new format]
       Preserve hash integrity
   [Maintain compatibility layer]
```

#### EC-E4: Long-term archive

**Trigger**: 10-year-old audit data needed dla regulatory inquiry.

```
ℹ Long-term archive retrieval

  Required: 2016 audit chain
  Status: archived w cold storage
  
  Akcje:
   [Restore z cold storage]
       1-2 day delay
   [Verify integrity (10-year-old hashes)]
   [Convert do current format jeśli needed]
```

---

## 10.10. Inheritance + DoD — Provenance Guard

```bash
$ aeis-cli phase10-acceptance-test

[Common requirements]
[1/6] Audit chain configured                         ✓ PASS
[2/6] Hash algorithm + signing                       ✓ PASS (SHA-256 + Ed25519)
[3/6] Artifact provenance enabled                    ✓ PASS
[4/6] Compliance evidence templates                  ✓ PASS (GDPR + ISO + SOC2)
[5/6] Forensic capabilities                          ✓ PASS
[6/6] Audit chain entry phase_10.complete            ✓ PASS

[Optional features]
[7/9] External timestamping                          ⚠ WARN (not configured)
[8/9] Blockchain anchoring                           ⚠ WARN (not configured)
[9/9] Multi-machine sync                             ⚠ WARN (single machine)

DoD: 6/9 ✓ + 3 ⚠
Phase 10 ACCEPTED.
```

---

# Status faz 8-10

🟢 **Wszystkie 3 fazy complete**

**Zawiera**:
- ✓ Faza 8 — Security Guard (7 layers, 25 baseline checks, threat intel,
  incident response, compliance verification, 22 edge cases)
- ✓ Faza 9 — Quality Guard (test levels L1-L5 integration, auto-fix
  iterations, performance tracking, 22 edge cases)
- ✓ Faza 10 — Provenance Guard (audit chain, cryptographic integrity,
  artifact provenance, compliance evidence, forensic capabilities,
  22 edge cases)

**Total edge cases w tym pliku**: 66 cases (22 × 3 phases)

**5 Guards complete**: Coherence (faza 6), Cost (faza 7), Security
(faza 8), Quality (faza 9), Provenance (faza 10).

⏳ **Po Twojej akceptacji** → **soft freeze faz 8-10** + przejście do **Faza 11 — Skills Library Bootstrap** (ostatnia faza grupy A "Przygotowanie Operatora").
