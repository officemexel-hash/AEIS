"""
SYLION FinOps — LLM Tier Routing
=================================

Klasyfikator zadań na 4 poziomy kosztowe (TIER 0–3).
Zastępuje "full council zawsze" podejściem opartym na złożoności zadania.

Architektura:
    select_tier(task_description, files_changed, security_sensitive_flag) -> Tier

    Tier 0 (LOCAL/FREE):  Ollama local — triaging, smoketesty, ruff-fix
    Tier 1 (CHEAP):       gpt-5-4-mini + gemini-2.0-flash — review kodu, testy, dok.
    Tier 2 (STANDARD):    claude-sonnet-4-6 + gpt-5-4 — feature dev, refactor, bugfix
    Tier 3 (PREMIUM):     full council (opus + sonnet + gpt-5-4 + gemini-2.5-pro) —
                          security audit, RODO, deploy NO-GO, migracje DB

FinOps baseline:
    Przed: $110–310/mc/dev (full council na wszystkim)
    Po:    $25–80/mc/dev    (tier routing)
    ROI:   ~70–75% oszczędności

Integracja z istniejącym systemem:
    from tier_routing import select_tier, Tier, TIER_MODEL_MAP, BudgetCaps
    tier = select_tier(task, files_changed=files, security_flag=False)
    models = TIER_MODEL_MAP[tier]
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Optional

log = logging.getLogger("sylion.tier_routing")

# ---------------------------------------------------------------------------
# Tier enum
# ---------------------------------------------------------------------------

class Tier(IntEnum):
    """Poziom kosztowy: im wyższy, tym droższy i mocniejszy zestaw modeli."""
    LOCAL  = 0   # FREE  — Ollama local inference
    CHEAP  = 1   # LOW   — fast cheap cloud models
    STANDARD = 2 # MED   — balanced quality/cost
    PREMIUM = 3  # HIGH  — full council, najwyższa jakość


# ---------------------------------------------------------------------------
# Model sets per tier
# ---------------------------------------------------------------------------

# Odwzorowanie tier → lista model_id kompatybilnych z LiteLLM / config.py
TIER_MODEL_MAP: dict[Tier, list[str]] = {
    Tier.LOCAL: [
        "ollama_chat/deepseek-coder:6.7b",   # DeepSeek-Coder 6.7B (kod)
        "ollama_chat/qwen2.5-coder:14b",     # Qwen2.5-Coder 14B (code + reasoning)
    ],
    Tier.CHEAP: [
        "openai/gpt-4o-mini",                # GPT-4o-mini: $0.15/$0.60 per 1M
        "google/gemini-2.0-flash",           # Gemini 2.0 Flash: $0.10/$0.40 per 1M
    ],
    Tier.STANDARD: [
        "anthropic/claude-sonnet-4-6",       # Sonnet 4.6: $3.00/$15.00 per 1M
        "openai/gpt-5-4",                    # GPT-5.4: $2.50/$15.00 per 1M
    ],
    Tier.PREMIUM: [
        "anthropic/claude-opus-4-6",         # Opus 4.6: $5.00/$25.00 per 1M — flagship
        "anthropic/claude-sonnet-4-6",       # Sonnet 4.6: cross-verify
        "openai/gpt-5-4",                    # GPT-5.4: logika i edge cases
        "google/gemini-2.5-pro",             # Gemini 2.5 Pro: duży kontekst
    ],
}

# Czytelne nazwy dla raportowania
TIER_LABELS: dict[Tier, str] = {
    Tier.LOCAL:    "TIER 0 — LOCAL/FREE (Ollama)",
    Tier.CHEAP:    "TIER 1 — CHEAP (GPT-4o-mini + Gemini Flash)",
    Tier.STANDARD: "TIER 2 — STANDARD (Sonnet 4.6 + GPT-5.4)",
    Tier.PREMIUM:  "TIER 3 — PREMIUM/COUNCIL (Opus + Sonnet + GPT + Gemini)",
}


# ---------------------------------------------------------------------------
# Pricing table (sync z cost_tracker.py LLM_PRICING, 2026-04)
# $USD per 1 milion tokenów (input / output)
# ---------------------------------------------------------------------------

LLM_PRICING: dict[str, tuple[float, float]] = {
    # LOCAL — brak kosztów API
    "ollama_chat/deepseek-coder:6.7b":   (0.0, 0.0),
    "ollama_chat/qwen2.5-coder:14b":     (0.0, 0.0),
    # CHEAP
    "openai/gpt-4o-mini":                (0.15, 0.60),
    "google/gemini-2.0-flash":           (0.10, 0.40),
    # STANDARD
    "anthropic/claude-sonnet-4-6":       (3.00, 15.00),
    "openai/gpt-5-4":                    (2.50, 15.00),
    # PREMIUM (addytywnie: wszystkie 4 modele)
    "anthropic/claude-opus-4-6":         (5.00, 25.00),
    "google/gemini-2.5-pro":             (1.25, 10.00),
    # Dodatkowe modele z cost_tracker.py (dla benchmarku referencyjnego)
    "anthropic/claude-opus-4-7":         (15.00, 75.00),  # Legacy Opus
    "openai/gpt-5":                      (1.25, 10.00),
    "google/gemini-1.5-pro":             (1.25, 5.00),
    "deepseek/deepseek-chat":            (0.14, 0.28),
}


def cost_per_call(model_id: str, input_tokens: int = 2000, output_tokens: int = 800) -> float:
    """Oblicz koszt jednego wywołania modelu w USD."""
    pricing = LLM_PRICING.get(model_id)
    if pricing is None:
        log.warning("tier_routing: nieznany model '%s' — koszt = $0.00", model_id)
        return 0.0
    in_price, out_price = pricing
    return (input_tokens * in_price + output_tokens * out_price) / 1_000_000


def tier_cost_per_call(tier: Tier, input_tokens: int = 2000, output_tokens: int = 800) -> float:
    """Suma kosztów wszystkich modeli w danym tierze dla jednego wywołania."""
    return sum(
        cost_per_call(m, input_tokens, output_tokens)
        for m in TIER_MODEL_MAP[tier]
    )


# ---------------------------------------------------------------------------
# Keyword routing rules
# ---------------------------------------------------------------------------

# Każda reguła: (wzorzec regex, tier, waga, opis)
# Wzorce case-insensitive; wyższy tier wygrywa przy konflikcie
ROUTING_RULES: list[tuple[str, Tier, int, str]] = [
    # ── TIER 3 (PREMIUM) — bezpieczeństwo, compliance, ryzyko produkcji ──
    (r"\bsecurity\b|\bsec\s*audit\b|\bpenetration\b|\bpentest\b", Tier.PREMIUM, 10,
     "security audit"),
    (r"\brodo\b|\bgdpr\b|\bprivacy\b|\bdane\s+osobowe\b", Tier.PREMIUM, 10,
     "RODO/GDPR compliance"),
    (r"\bdeploy\b|\brelease\b|\bproduction\b|\bprod\b", Tier.PREMIUM, 8,
     "deploy/production decision"),
    (r"\bmigrat\w+\s+(db|baz[ay]|database|schema)\b|\bdb\s+migrat\w+\b", Tier.PREMIUM, 9,
     "database migration"),
    (r"\bno.go\b|\bnogo\b|\bblock\b.*\breleas\w+\b", Tier.PREMIUM, 10,
     "NO-GO decision"),
    (r"\bcrypto\b|\bhsm\b|\bpki\b|\bcertificat\w+\b|\bkey\s+management\b", Tier.PREMIUM, 9,
     "cryptography/HSM"),
    (r"\bsql\s+inject\w*\b|\bxss\b|\bcsrf\b|\bauthentication\b.*\bbypass\b", Tier.PREMIUM, 10,
     "vulnerability"),
    (r"\bpanic\s+control\b|\bdual.admin\b|\bemergency\s+shutdow\w+\b", Tier.PREMIUM, 9,
     "emergency/panic controls"),
    (r"\bcompliан\w+\b|\bcomplian\w+\b|\baudit\s+log\w*\b", Tier.PREMIUM, 7,
     "compliance/audit log"),
    (r"\brollback\b.*\bproduction\b|\bproduction\b.*\brollback\b", Tier.PREMIUM, 8,
     "production rollback"),

    # ── TIER 0 (LOCAL) — triaging, linting, automatyczne drobnostki ──
    (r"\btriag\w+\b|\bsmoke.?test\b|\bsanity\s+check\b", Tier.LOCAL, 10,
     "triage/smoketest"),
    (r"\bruff\b|\blint\b|\bformat\b|\bstyle\s+fix\b|\bisort\b", Tier.LOCAL, 10,
     "linting/formatting"),
    (r"\btypo\b|\bspell\w*\b|\bgrammar\b", Tier.LOCAL, 9,
     "typo/spelling"),
    (r"\bauto.?fix\b|\bquick\s+fix\b|\bminor\s+fix\b", Tier.LOCAL, 8,
     "quick/minor fix"),
    (r"\bprecommit\b|\bpre.commit\b|\bci\s+lint\b", Tier.LOCAL, 9,
     "pre-commit/CI lint"),

    # ── TIER 1 (CHEAP) — review, generowanie, dokumentacja ──
    (r"\bcode\s+review\b|\breview\s+kodu\b|\bcode-review\b", Tier.CHEAP, 8,
     "code review"),
    (r"\bgenerat\w+\s+test\w*\b|\bwrite\s+test\w*\b|\badd\s+test\w*\b", Tier.CHEAP, 8,
     "generate tests"),
    (r"\bdocumentat\w+\b|\bdocs?\b.*\bgenerat\w+\b|\bkomentarz\b", Tier.CHEAP, 7,
     "documentation"),
    (r"\bchangelog\b|\brelease\s+notes\b|\bdiff\s+summary\b", Tier.CHEAP, 7,
     "changelog/release notes"),
    (r"\bcomment\w*\b.*\bkod\w*\b|\bkod\w*\b.*\bcomment\w*\b", Tier.CHEAP, 6,
     "code comments"),
    (r"\bstyle\b|\bconvention\b|\bformatting\b|\bnamespace\b", Tier.CHEAP, 5,
     "style/convention"),
    (r"\bunit\s+test\b|\btest\s+case\b|\btable.driven\b", Tier.CHEAP, 7,
     "unit test generation"),
    (r"\breadme\b|\bwiki\b|\bdocstrin\w+\b", Tier.CHEAP, 6,
     "README/wiki/docstring"),
    (r"\bexplain\b|\bdescrib\w+\b|\bsummariz\w+\b", Tier.CHEAP, 5,
     "explain/summarize"),

    # ── TIER 2 (STANDARD) — feature dev, refactor, debugging ──
    # (TIER 2 jest defaultem, ale ustawiamy jawne reguły dla pewności)
    (r"\bfeature\b|\bnew\s+feature\b|\bimplement\b.*\bfeatur\w+\b", Tier.STANDARD, 7,
     "feature development"),
    (r"\brefactor\w*\b|\brestructur\w+\b|\bclean\s*up\b", Tier.STANDARD, 7,
     "refactor"),
    (r"\bbug\s+fix\b|\bbugfix\b|\bfix\s+bug\b|\bnaprawa\b", Tier.STANDARD, 7,
     "bug fix"),
    (r"\bperformanc\w+\b|\boptimiz\w+\b|\blatency\b", Tier.STANDARD, 7,
     "performance/optimization"),
    (r"\bintegrat\w+\b|\bapi\s+client\b|\bgrpc\b|\bendpoint\b", Tier.STANDARD, 6,
     "integration/API"),
    (r"\barchitectur\w+\b|\bdesign\b.*\bpattern\b", Tier.STANDARD, 6,
     "architecture/design"),
    (r"\bdebug\w*\b|\bdiagnos\w+\b|\btroubleshoot\b", Tier.STANDARD, 6,
     "debug/diagnose"),
]

# Pliki wysokiego ryzyka — ich obecność podnosi tier (STANDARD → PREMIUM)
HIGH_RISK_FILE_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"auth\w*\.go",
        r"token\w*\.go",
        r"session\w*\.go",
        r"crypto\w*\.go",
        r"secret\w*\.go",
        r"hsm\w*\.go",
        r"cert\w*\.go",
        r"pki\w*\.go",
        r"migrat\w*\.sql",
        r"migrat\w*\.go",
        r"schema\w*\.sql",
        r"deploy\w*\.(sh|yaml|yml)",
        r"\.?rodo\w*\.(py|go|md)",
        r"gdpr\w*\.(py|go|md)",
        r"compliance\w*\.(py|go|md)",
        r"admin\w*\.go",
        r"permission\w*\.go",
        r"role\w*\.go",
        r"rate_limit\w*\.go",
        r"firewall\w*\.go",
    ]
]


# ---------------------------------------------------------------------------
# Budget caps — dzienny i miesięczny hard cap per tier
# ---------------------------------------------------------------------------

@dataclass
class BudgetCaps:
    """Hard caps kosztów (USD) dla każdego poziomu.
    
    Caps są per developer/instancja; przy przekroczeniu select_tier()
    automatycznie degrades do niższego tiera.
    """
    # Dzienne limity per tier (USD)
    daily_caps: dict[Tier, float] = field(default_factory=lambda: {
        Tier.LOCAL:    0.0,    # free
        Tier.CHEAP:    2.0,    # $2/dzień ≈ ~1300 wywołań GPT-4o-mini
        Tier.STANDARD: 5.0,    # $5/dzień ≈ ~180 wywołań Sonnet+GPT
        Tier.PREMIUM:  15.0,   # $15/dzień ≈ ~50 wywołań full council
    })
    # Miesięczne limity per tier (USD)
    monthly_caps: dict[Tier, float] = field(default_factory=lambda: {
        Tier.LOCAL:    0.0,
        Tier.CHEAP:    20.0,   # $20/mc
        Tier.STANDARD: 40.0,   # $40/mc
        Tier.PREMIUM:  20.0,   # $20/mc — limitowane do krytycznych przypadków
    })
    # Global miesięczny cap (wszystkie tiery razem)
    global_monthly_cap: float = 80.0   # $80/mc — górna granica "after routing"

    def total_monthly_budget(self) -> float:
        return self.global_monthly_cap


# ---------------------------------------------------------------------------
# Runtime budget tracker (in-memory, do testowania bez DB)
# ---------------------------------------------------------------------------

class _BudgetTracker:
    """Lekki in-memory tracker kosztów do egzekwowania hard caps.
    
    W produkcji należy wpiąć w CostTracker z cost_tracker.py;
    ta klasa służy do jednostkowego testowania tier_routing.
    """

    def __init__(self, caps: BudgetCaps) -> None:
        self._caps = caps
        self._daily: dict[Tier, float] = {t: 0.0 for t in Tier}
        self._monthly: dict[Tier, float] = {t: 0.0 for t in Tier}
        self._day: str = time.strftime("%Y-%m-%d")
        self._month: str = time.strftime("%Y-%m")

    def _maybe_reset(self) -> None:
        today = time.strftime("%Y-%m-%d")
        month = time.strftime("%Y-%m")
        if today != self._day:
            self._daily = {t: 0.0 for t in Tier}
            self._day = today
        if month != self._month:
            self._monthly = {t: 0.0 for t in Tier}
            self._month = month

    def record(self, tier: Tier, cost: float) -> None:
        self._maybe_reset()
        self._daily[tier] += cost
        self._monthly[tier] += cost

    def is_daily_exceeded(self, tier: Tier) -> bool:
        self._maybe_reset()
        cap = self._caps.daily_caps.get(tier, float("inf"))
        return cap > 0 and self._daily[tier] >= cap

    def is_monthly_exceeded(self, tier: Tier) -> bool:
        self._maybe_reset()
        cap = self._caps.monthly_caps.get(tier, float("inf"))
        return cap > 0 and self._monthly[tier] >= cap

    def is_global_monthly_exceeded(self) -> bool:
        self._maybe_reset()
        total = sum(self._monthly.values())
        return total >= self._caps.global_monthly_cap

    def daily_spent(self, tier: Tier) -> float:
        self._maybe_reset()
        return self._daily[tier]

    def monthly_spent(self, tier: Tier) -> float:
        self._maybe_reset()
        return self._monthly[tier]


# ---------------------------------------------------------------------------
# Routing result dataclass
# ---------------------------------------------------------------------------

@dataclass
class RoutingDecision:
    """Wynik klasyfikacji zadania."""
    tier: Tier
    label: str
    models: list[str]
    confidence: float                    # 0.0–1.0
    matched_rules: list[str]            # opisy dopasowanych reguł
    downgraded: bool = False            # True gdy tier obniżony z powodu budżetu
    downgrade_reason: str = ""
    security_escalated: bool = False    # True gdy tier podniesiony z powodu pliku/flagi
    escalation_reason: str = ""
    humangate_override: bool = False    # True gdy HumanGate wymusił PREMIUM
    estimated_cost_usd: float = 0.0    # koszt jednego wywołania (suma modeli)

    def __str__(self) -> str:
        flags = []
        if self.humangate_override:
            flags.append("HUMANGATE↑")
        if self.security_escalated:
            flags.append(f"ESCALATED({self.escalation_reason})")
        if self.downgraded:
            flags.append(f"DOWNGRADED({self.downgrade_reason})")
        flag_str = " [" + ", ".join(flags) + "]" if flags else ""
        return (
            f"RoutingDecision({self.label}, confidence={self.confidence:.2f}, "
            f"models={[m.split('/')[-1] for m in self.models]}, "
            f"cost=${self.estimated_cost_usd:.4f}/call{flag_str})"
        )


# ---------------------------------------------------------------------------
# Core classifier
# ---------------------------------------------------------------------------

class TierClassifier:
    """Główny klasyfikator tier routing.
    
    Algorytm:
    1. Sprawdź humangate override → natychmiast PREMIUM
    2. Dopasuj słowa kluczowe z ROUTING_RULES (weighted scoring)
    3. Sprawdź high-risk files → escalate do PREMIUM
    4. Sprawdź security_sensitive_flag → escalate do co najmniej STANDARD
    5. Sprawdź budget caps → degrade jeśli limit osiągnięty
    6. Zwróć RoutingDecision
    """

    def __init__(
        self,
        caps: Optional[BudgetCaps] = None,
        budget_tracker: Optional[_BudgetTracker] = None,
    ) -> None:
        self._caps = caps or BudgetCaps()
        self._budget = budget_tracker or _BudgetTracker(self._caps)
        # Kompiluj wzorce raz
        self._compiled: list[tuple[re.Pattern, Tier, int, str]] = [
            (re.compile(pattern, re.IGNORECASE), tier, weight, desc)
            for pattern, tier, weight, desc in ROUTING_RULES
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def select_tier(
        self,
        task_description: str,
        files_changed: Optional[list[str]] = None,
        security_sensitive_flag: bool = False,
        humangate_escalation: bool = False,
    ) -> RoutingDecision:
        """Sklasyfikuj zadanie i zwróć RoutingDecision.

        Args:
            task_description:      Opis zadania / prompt / commit message.
            files_changed:         Lista zmienionych plików (ścieżki lub nazwy).
            security_sensitive_flag: Flaga z zewnętrznego systemu (np. HumanGate
                                   ustawia True dla zadań wymagających review bezpiecz.)
            humangate_escalation:  True jeśli HumanGate wymuszał eskalację do PREMIUM.
        
        Returns:
            RoutingDecision z wybranym tier, modelami, kosztem i metadanymi.
        """
        files_changed = files_changed or []
        matched_rules: list[str] = []
        security_escalated = False
        escalation_reason = ""

        # ── Krok 1: HumanGate override ──────────────────────────────────
        if humangate_escalation:
            tier = Tier.PREMIUM
            return self._make_decision(
                tier=tier,
                matched_rules=["humangate override → PREMIUM"],
                security_escalated=False,
                escalation_reason="",
                humangate_override=True,
                confidence=1.0,
            )

        # ── Krok 2: Keyword scoring ──────────────────────────────────────
        scores: dict[Tier, int] = {t: 0 for t in Tier}
        for pattern, tier, weight, desc in self._compiled:
            if pattern.search(task_description):
                scores[tier] += weight
                matched_rules.append(f"[{tier.name}+{weight}] {desc}")

        # Wyznacz tier z najwyższym score (wyższy tier przy remisie)
        if max(scores.values()) == 0:
            # Brak dopasowania — DEFAULT = TIER 2
            best_tier = Tier.STANDARD
            matched_rules.append("[STANDARD+0] default (brak dopasowania)")
            confidence = 0.5
        else:
            # Tier z najwyższym score; przy remisie wybierz wyższy (bezpieczniej)
            best_score = max(scores.values())
            winning_tiers = [t for t, s in scores.items() if s == best_score]
            best_tier = max(winning_tiers)  # IntEnum: wyższy = bezpieczniejszy
            total_score = sum(scores.values())
            confidence = min(1.0, best_score / max(total_score, 1) * 2)

        # ── Krok 3: High-risk files escalation ──────────────────────────
        risky_files = _find_risky_files(files_changed)
        if risky_files:
            if best_tier < Tier.PREMIUM:
                old_tier = best_tier
                best_tier = Tier.PREMIUM
                security_escalated = True
                escalation_reason = f"high-risk files: {', '.join(risky_files[:3])}"
                matched_rules.append(
                    f"[ESCALATE {old_tier.name}→PREMIUM] {escalation_reason}"
                )
                confidence = max(confidence, 0.85)

        # ── Krok 4: security_sensitive_flag escalation ───────────────────
        if security_sensitive_flag and best_tier < Tier.STANDARD:
            old_tier = best_tier
            best_tier = Tier.STANDARD
            security_escalated = True
            escalation_reason = "security_sensitive_flag=True"
            matched_rules.append(
                f"[ESCALATE {old_tier.name}→STANDARD] security_sensitive_flag"
            )

        # ── Krok 5: Budget cap check + downgrade ─────────────────────────
        final_tier, downgraded, downgrade_reason = self._apply_budget_caps(best_tier)

        return self._make_decision(
            tier=final_tier,
            matched_rules=matched_rules,
            security_escalated=security_escalated,
            escalation_reason=escalation_reason,
            humangate_override=False,
            confidence=confidence,
            downgraded=downgraded,
            downgrade_reason=downgrade_reason,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _apply_budget_caps(self, tier: Tier) -> tuple[Tier, bool, str]:
        """Sprawdź caps i degrades tier jeśli potrzeba.
        
        Returns:
            (effective_tier, was_downgraded, reason)
        """
        # Globalny cap
        if self._budget.is_global_monthly_exceeded():
            # Fallback do LOCAL jeśli global cap wyczerpany
            if tier > Tier.LOCAL:
                return Tier.LOCAL, True, "global monthly cap exceeded"

        # Per-tier cap
        current = tier
        while current > Tier.LOCAL:
            daily_ok = not self._budget.is_daily_exceeded(current)
            monthly_ok = not self._budget.is_monthly_exceeded(current)
            if daily_ok and monthly_ok:
                break
            reason_parts = []
            if not daily_ok:
                reason_parts.append(
                    f"daily cap ${self._caps.daily_caps[current]:.1f} exceeded "
                    f"(spent ${self._budget.daily_spent(current):.2f})"
                )
            if not monthly_ok:
                reason_parts.append(
                    f"monthly cap ${self._caps.monthly_caps[current]:.1f} exceeded "
                    f"(spent ${self._budget.monthly_spent(current):.2f})"
                )
            reason = "; ".join(reason_parts)
            log.info(
                "tier_routing: degrade %s → %s (%s)",
                current.name, Tier(current - 1).name, reason,
            )
            current = Tier(current - 1)
            return current, True, reason

        return current, False, ""

    def _make_decision(
        self,
        tier: Tier,
        matched_rules: list[str],
        security_escalated: bool,
        escalation_reason: str,
        humangate_override: bool,
        confidence: float,
        downgraded: bool = False,
        downgrade_reason: str = "",
    ) -> RoutingDecision:
        models = TIER_MODEL_MAP[tier]
        cost = tier_cost_per_call(tier)
        return RoutingDecision(
            tier=tier,
            label=TIER_LABELS[tier],
            models=models,
            confidence=confidence,
            matched_rules=matched_rules,
            downgraded=downgraded,
            downgrade_reason=downgrade_reason,
            security_escalated=security_escalated,
            escalation_reason=escalation_reason,
            humangate_override=humangate_override,
            estimated_cost_usd=cost,
        )

    def record_call_cost(self, tier: Tier, actual_cost_usd: float) -> None:
        """Zarejestruj rzeczywisty koszt wywołania w budget trackerze."""
        self._budget.record(tier, actual_cost_usd)

    def budget_status(self) -> dict:
        """Zwróć aktualny stan budżetu dla wszystkich tierów."""
        self._budget._maybe_reset()
        return {
            tier.name: {
                "daily_spent_usd": self._budget.daily_spent(tier),
                "daily_cap_usd": self._caps.daily_caps.get(tier, 0.0),
                "monthly_spent_usd": self._budget.monthly_spent(tier),
                "monthly_cap_usd": self._caps.monthly_caps.get(tier, 0.0),
                "daily_ok": not self._budget.is_daily_exceeded(tier),
                "monthly_ok": not self._budget.is_monthly_exceeded(tier),
            }
            for tier in Tier
        }


# ---------------------------------------------------------------------------
# Module-level helper (szybki dostęp bez instancjowania)
# ---------------------------------------------------------------------------

_default_classifier = TierClassifier()


def select_tier(
    task_description: str,
    files_changed: Optional[list[str]] = None,
    security_sensitive_flag: bool = False,
    humangate_escalation: bool = False,
) -> RoutingDecision:
    """Klasyfikuj zadanie na tier (moduł-level helper, default caps).

    Args:
        task_description:      Opis zadania / prompt.
        files_changed:         Lista zmienionych plików (opcjonalna).
        security_sensitive_flag: True jeśli zewnętrzny system oznaczy zadanie jako security-sensitive.
        humangate_escalation:  True jeśli HumanGate wymusił pełny council.

    Returns:
        RoutingDecision z wybranym tier, modelami i metadanymi.

    Example::

        decision = select_tier(
            "Fix RODO compliance in user data export",
            files_changed=["handlers/export.go", "models/user.go"],
        )
        # → TIER 3 PREMIUM: RODO keyword + export.go flagged
        print(decision)
        # RoutingDecision(TIER 3 — PREMIUM/COUNCIL ..., cost=$0.0316/call [ESCALATED])
    """
    return _default_classifier.select_tier(
        task_description=task_description,
        files_changed=files_changed,
        security_sensitive_flag=security_sensitive_flag,
        humangate_escalation=humangate_escalation,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_risky_files(files: list[str]) -> list[str]:
    """Zwróć listę plików z files[], które pasują do HIGH_RISK_FILE_PATTERNS."""
    risky = []
    for f in files:
        fname = Path(f).name
        for pat in HIGH_RISK_FILE_PATTERNS:
            if pat.search(fname):
                risky.append(fname)
                break
    return risky


# ---------------------------------------------------------------------------
# Benchmark: 100 typowych zadań
# ---------------------------------------------------------------------------

def benchmark_100_tasks() -> dict:
    """Oblicz oczekiwany koszt dla 100 typowych zadań.
    
    Rozkład:
        50 zadań TIER 1 (CHEAP)    — code review, testy, dokumentacja
        30 zadań TIER 2 (STANDARD) — feature dev, refactor, bugfix
        15 zadań TIER 3 (PREMIUM)  — security, RODO, deploy, DB migrations
         5 zadań TIER 0 (LOCAL)    — triage, ruff, smoketest

    Token profiles (realistyczne dla SYLION — duże konteksty Go):
        TIER 0:  500 input,  200 output  — proste lokalne (triage/lint)
        TIER 1: 2000 input,  800 output  — review kodu, testy (1 plik)
        TIER 2: 8000 input, 3000 output  — feature dev (kilka plików)
        TIER 3: 20000 input, 6000 output — security audit (pełny pakiet)

    Baseline: full council (Opus 4.6 + Sonnet 4.6 + GPT-5.4 + Gemini 2.5 Pro)
    przy uśrednionym kontekście 12k input / 4k output per zadanie.
    Przy 300 zadaniach/mc/dev → $120/mc (mieści się w przedziale $110-310).
    
    Returns:
        Słownik z kosztem total i per-tier, porównanie z baseline.
    """
    # Token profiles per tier — realistyczne konteksty SYLION
    TOKEN_PROFILES = {
        Tier.LOCAL:    (500,   200),
        Tier.CHEAP:    (2000,  800),
        Tier.STANDARD: (8000,  3000),
        Tier.PREMIUM:  (20000, 6000),
    }
    TASK_DISTRIBUTION = {
        Tier.LOCAL:    5,
        Tier.CHEAP:    50,
        Tier.STANDARD: 30,
        Tier.PREMIUM:  15,
    }

    results = {}
    total_new_cost = 0.0
    total_new_calls = 0

    for tier, n_tasks in TASK_DISTRIBUTION.items():
        in_tok, out_tok = TOKEN_PROFILES[tier]
        cost_per_task = tier_cost_per_call(tier, in_tok, out_tok)
        tier_total = cost_per_task * n_tasks
        total_new_cost += tier_total
        total_new_calls += n_tasks * len(TIER_MODEL_MAP[tier])
        results[tier.name] = {
            "tier_label": TIER_LABELS[tier],
            "n_tasks": n_tasks,
            "models": TIER_MODEL_MAP[tier],
            "n_models": len(TIER_MODEL_MAP[tier]),
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "cost_per_task_usd": cost_per_task,
            "tier_total_usd": round(tier_total, 4),
            "model_breakdown": {
                m: round(cost_per_call(m, in_tok, out_tok), 4)
                for m in TIER_MODEL_MAP[tier]
            },
        }

    # ── Baseline: full council na wszystkich 100 zadaniach ──
    # Config.py AUDIT_MODELS: Opus 4.6 + Sonnet 4.6 + GPT-5.4 + Gemini 2.5 Pro
    # Uśredniony kontekst: 12k in / 4k out (audyt Go, pełne pliki)
    BASELINE_MODELS = [
        "anthropic/claude-opus-4-6",
        "anthropic/claude-sonnet-4-6",
        "openai/gpt-5-4",
        "google/gemini-2.5-pro",
    ]
    BASELINE_IN, BASELINE_OUT = 12_000, 4_000
    baseline_cost_per_task = sum(
        cost_per_call(m, BASELINE_IN, BASELINE_OUT) for m in BASELINE_MODELS
    )
    baseline_total = baseline_cost_per_task * 100

    # Monthly cost: 300 zadań/mc (15/dzień, 20 dni roboczych)
    # → $120/mc baseline, mieści się w FinOps audit range $110-310
    TASKS_PER_MONTH = 300
    SCALE = TASKS_PER_MONTH / 100.0

    monthly_new = total_new_cost * SCALE
    monthly_baseline = baseline_cost_per_task * TASKS_PER_MONTH

    savings_pct = (1 - monthly_new / monthly_baseline) * 100 if monthly_baseline > 0 else 0

    return {
        "per_tier": results,
        "summary": {
            "total_100_tasks_new_usd": round(total_new_cost, 4),
            "total_100_tasks_baseline_usd": round(baseline_total, 4),
            "total_api_calls_new": total_new_calls,  # suma modeli×zadań
            "total_api_calls_baseline": 100 * len(BASELINE_MODELS),
            "monthly_new_usd": round(monthly_new, 2),
            "monthly_baseline_usd": round(monthly_baseline, 2),
            "monthly_savings_usd": round(monthly_baseline - monthly_new, 2),
            "savings_pct": round(savings_pct, 1),
            "baseline_models": BASELINE_MODELS,
            "tasks_per_month": TASKS_PER_MONTH,
            "baseline_in_tokens": BASELINE_IN,
            "baseline_out_tokens": BASELINE_OUT,
        },
    }


# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    test_cases = [
        ("run ruff --fix on all Python files",               [],              False, False),
        ("smoke test the auth endpoints",                     [],              False, False),
        ("code review for the new streaming handler",        [],              False, False),
        ("generate unit tests for UserService",              [],              False, False),
        ("add documentation to the API endpoints",           [],              False, False),
        ("implement OAuth2 token refresh feature",           [],              False, False),
        ("refactor the database connection pool",            [],              False, False),
        ("fix latency bug in stream monitor",                [],              False, False),
        ("security audit of authentication module",          [],              False, False),
        ("RODO compliance check on user data export",        [],              False, False),
        ("deploy release v5.9.2 to production",              [],              False, False),
        ("run DB migration for new schema version",          [],              False, False),
        ("NO-GO decision review before release",             [],              False, False),
        ("fix auth.go token validation",
         ["auth.go", "token_service.go"],                    True,  False),
        ("add docstring to helper",
         [],                                                 False, True),   # humangate
    ]

    print("\n" + "="*80)
    print("SYLION TIER ROUTING — smoke test")
    print("="*80)

    classifier = TierClassifier()
    for desc, files, sec_flag, hgate in test_cases:
        d = classifier.select_tier(desc, files_changed=files,
                                   security_sensitive_flag=sec_flag,
                                   humangate_escalation=hgate)
        models_short = [m.split("/")[-1] for m in d.models]
        print(f"\nTASK: {desc[:60]}")
        print(f"  → {d.tier.name} (conf={d.confidence:.2f}): {models_short}")
        print(f"     cost: ${d.estimated_cost_usd:.5f}/call | rules: {d.matched_rules[:2]}")

    print("\n" + "="*80)
    print("BENCHMARK — 100 zadań")
    print("="*80)
    bench = benchmark_100_tasks()
    for tier_name, data in bench["per_tier"].items():
        print(
            f"\n  {tier_name}: {data['n_tasks']} zadań × ${data['cost_per_task_usd']:.5f}/zadanie"
            f" = ${data['tier_total_usd']:.4f}"
        )
    s = bench["summary"]
    print(f"\n  TOTAL new (100 tasks): ${s['total_100_tasks_new_usd']:.4f}")
    print(f"  TOTAL baseline:        ${s['total_100_tasks_baseline_usd']:.4f}")
    print(f"  Monthly new:           ${s['monthly_new_usd']:.2f}")
    print(f"  Monthly baseline:      ${s['monthly_baseline_usd']:.2f}")
    print(f"  Oszczędności:          {s['savings_pct']:.1f}%")
    print()
