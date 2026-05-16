package sylion.aeis.operator.android.push

import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import sylion.aeis.operator.push.PushRepository

// Stub FCM token provider.
// Production implementation: subclass FirebaseMessagingService and call onNewToken from
// onNewToken() override. Requires google-services.json + com.google.gms:google-services plugin.
class FcmTokenProvider(
    private val pushRepository: PushRepository = PushRepository(),
    private val scope: CoroutineScope = CoroutineScope(Dispatchers.IO),
) {

    fun onNewToken(token: String) {
        Log.d(TAG, "FCM token received — registering with backend")
        scope.launch {
            pushRepository.registerToken(deviceToken = token, platform = "android")
        }
    }

    fun onTokenInvalidated(token: String) {
        scope.launch {
            pushRepository.unregisterToken(deviceToken = token)
        }
    }

    companion object {
        private const val TAG = "FcmTokenProvider"
    }
}
