package com.rohan.assistant.gateway.util

import android.content.Context
import android.database.Cursor
import android.provider.CallLog
import android.telephony.TelephonyManager
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.util.concurrent.TimeUnit

/**
 * Best-effort number resolution when the PHONE_STATE broadcast arrives
 * with a blank/unknown EXTRA_INCOMING_NUMBER (common on Android 10+ for
 * callers not in the user's contacts).
 *
 * Strategy: after [CallTracker] flags a missed call, query the CallLog
 * provider for the most recent row matching the [PhoneNumberFilter].
 * CallLog requires READ_CALL_LOG, but a security exception is the
 * worst case — the request is best-effort.
 */
object CallLogResolver {

    data class ResolvedCall(
        val number: String,
        val timestampMs: Long,
    )

    suspend fun recentMissedCall(
        context: Context,
        withinMs: Long = TimeUnit.SECONDS.toMillis(5),
    ): ResolvedCall? = withContext(Dispatchers.IO) {
        val now = System.currentTimeMillis()
        val cursor: Cursor? = try {
            context.contentResolver.query(
                CallLog.Calls.CONTENT_URI,
                arrayOf(
                    CallLog.Calls.NUMBER,
                    CallLog.Calls.DATE,
                    CallLog.Calls.TYPE,
                ),
                "${CallLog.Calls.TYPE} = ? AND ${CallLog.Calls.DATE} >= ?",
                arrayOf(CallLog.Calls.MISSED_TYPE.toString(), (now - withinMs).toString()),
                "${CallLog.Calls.DATE} DESC",
            )
        } catch (t: SecurityException) {
            Logger.w("CallLogResolver", "READ_CALL_LOG denied: ${t.message}")
            null
        } catch (t: Throwable) {
            Logger.w("CallLogResolver", "query failed: ${t.message}")
            null
        }

        cursor?.use { c ->
            if (c.moveToFirst()) {
                val num = c.getString(0).orEmpty()
                val ts = c.getLong(1)
                if (num.isNotBlank() && (now - ts) < withinMs * 6) {
                    return@withContext ResolvedCall(num, ts)
                }
            }
        }
        null
    }
}
