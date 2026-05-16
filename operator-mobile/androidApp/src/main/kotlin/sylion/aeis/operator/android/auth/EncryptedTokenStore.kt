package sylion.aeis.operator.android.auth

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

private const val PREFS_NAME = "sylion_secure_auth"
private const val KEY_TOKEN = "auth_token"
private const val KEY_EXPIRES_AT = "auth_expires_at"

class EncryptedTokenStore(context: Context) {

    private val masterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()

    private val prefs = EncryptedSharedPreferences.create(
        context,
        PREFS_NAME,
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
    )

    fun saveToken(token: String, expiresAt: Long) {
        prefs.edit()
            .putString(KEY_TOKEN, token)
            .putLong(KEY_EXPIRES_AT, expiresAt)
            .apply()
    }

    fun getToken(): String? = prefs.getString(KEY_TOKEN, null)

    fun getExpiresAt(): Long = prefs.getLong(KEY_EXPIRES_AT, 0L)

    fun clear() {
        prefs.edit().clear().apply()
    }

    fun hasValidToken(): Boolean {
        val token = getToken() ?: return false
        val expiresAt = getExpiresAt()
        return token.isNotBlank() && (expiresAt == 0L || expiresAt > System.currentTimeMillis())
    }
}
