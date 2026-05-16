package sylion.aeis.operator.model

data class AdvisorCard(
    val id: String,
    val type: CardType,
    val dLevel: DLevel,
    val riskLevel: RiskLevel,
    val title: String,
    val rationale: String,
    val expectedBenefit: String,
    val expectedDownside: String,
    val alternatives: List<String>,
    val confidence: ConfidenceBreakdown,
    val createdAt: Long,
    val status: CardStatus = CardStatus.PENDING,
    val dontLearn: Boolean = false,
)

data class ConfidenceBreakdown(
    val councilMatch: Float,
    val historyMatch: Float,
    val pricingQuality: Float,
    val acceptanceRate: Float,
) {
    val overall: Float
        get() = 0.4f * councilMatch + 0.4f * historyMatch + 0.2f * pricingQuality
}

enum class CardType { DECISION, FUNDING }
enum class DLevel { D0, D1, D2, D3, D4, D5 }
enum class RiskLevel { LOW, MEDIUM, HIGH, CRITICAL }
enum class CardStatus { PENDING, ACCEPTED, REJECTED, MODIFIED, DEFERRED, CONVERTED_HG }
