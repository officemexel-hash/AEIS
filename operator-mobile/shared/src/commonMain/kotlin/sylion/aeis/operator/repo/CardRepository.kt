package sylion.aeis.operator.repo

import sylion.aeis.operator.model.AdvisorCard

interface CardRepository {
    suspend fun getCards(page: Int, pageSize: Int = 50): List<AdvisorCard>
    suspend fun getCard(id: String): AdvisorCard?
    suspend fun acceptCard(id: String)
    suspend fun rejectCard(id: String)
    suspend fun markNotUseful(id: String)
}

class CardRepositoryStub : CardRepository {
    override suspend fun getCards(page: Int, pageSize: Int): List<AdvisorCard> = emptyList()
    override suspend fun getCard(id: String): AdvisorCard? = null
    override suspend fun acceptCard(id: String) = Unit
    override suspend fun rejectCard(id: String) = Unit
    override suspend fun markNotUseful(id: String) = Unit
}
