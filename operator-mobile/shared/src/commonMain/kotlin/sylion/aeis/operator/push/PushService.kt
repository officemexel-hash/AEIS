package sylion.aeis.operator.push

interface PushService {
    suspend fun registerToken(deviceToken: String, platform: String)
    suspend fun unregisterToken(deviceToken: String)
}
