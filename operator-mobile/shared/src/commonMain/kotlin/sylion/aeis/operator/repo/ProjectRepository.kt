package sylion.aeis.operator.repo

import sylion.aeis.operator.model.Project

interface ProjectRepository {
    suspend fun getProjects(): List<Project>
    suspend fun getProject(id: String): Project?
}

class ProjectRepositoryStub : ProjectRepository {
    override suspend fun getProjects(): List<Project> = emptyList()
    override suspend fun getProject(id: String): Project? = null
}
