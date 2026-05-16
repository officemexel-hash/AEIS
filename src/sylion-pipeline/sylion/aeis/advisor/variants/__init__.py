"""AEIS Advisor — Variants module.

Generates 3 strategic variants (cost-saving / balanced / aggressive)
for any project context.
"""

from sylion.aeis.advisor.variants._models import Variant, VariantSet, ComparisonMatrix, ComparisonDimension
from sylion.aeis.advisor.variants.generator import generate_variants, compare_variants
from sylion.aeis.advisor.variants.service import VariantsService, get_variants_service

__all__ = [
    "Variant",
    "VariantSet",
    "ComparisonMatrix",
    "ComparisonDimension",
    "generate_variants",
    "compare_variants",
    "VariantsService",
    "get_variants_service",
]
