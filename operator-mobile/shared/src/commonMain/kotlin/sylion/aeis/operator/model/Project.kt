package sylion.aeis.operator.model

data class Project(
    val id: String,
    val name: String,
    val description: String,
    val currentPhase: Int,
    val phases: List<ProjectPhase>,
    val status: ProjectStatus,
    val createdAt: Long,
)

data class ProjectPhase(
    val index: Int,
    val name: String,
    val status: PhaseStatus,
)

enum class ProjectStatus { ACTIVE, PAUSED, COMPLETED, ARCHIVED }
enum class PhaseStatus { PENDING, IN_PROGRESS, APPROVED, BLOCKED }
