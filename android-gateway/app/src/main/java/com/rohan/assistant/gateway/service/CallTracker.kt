package com.rohan.assistant.gateway.service

import android.content.Context
import android.telecom.TelecomManager
import android.content.Intent
import android.os.Build
import com.rohan.assistant.gateway.GatewayApp
import com.rohan.assistant.gateway.network.model.IncomingCallRequest
import com.rohan.assistant.gateway.util.CallLogResolver
import com.rohan.assistant.gateway.util.Contacts
import com.rohan.assistant.gateway.util.Logger
import com.rohan.assistant.gateway.util.Network
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.util.UUID

object CallTracker {

    private const val TAG = "CallTracker"
    private const val RING_TIMEOUT_MS = 3_000L
    private const val MISSED_TIMEOUT_MS = 20_000L

    private data class PendingCall(val callId: String, val number: String, val job: Job)

    private val pending = mutableMapOf<String, PendingCall>()
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    var autoAnswerEnabled = true

    @Synchronized
    fun handleStateChange(context: Context, state: String, number: String) {
        val app = context.applicationContext as GatewayApp
        when (state) {
            "RINGING" -> {
                if (autoAnswerEnabled) {
                    startAutoAnswerTimer(context, number)
                } else {
                    startMissedCallTimer(context, number)
                }
            }
            "OFFHOOK" -> cancelTimer(number, reason = "user picked up")
            "IDLE" -> cancelTimer(number, reason = "call ended")
            else -> Logger.d(TAG, "Ignoring state=$state")
        }
    }

    private fun startAutoAnswerTimer(context: Context, number: String) {
        val callId = UUID.randomUUID().toString()
        val job = scope.launch {
            Logger.i(TAG, "Auto-answer timer started for $number (${RING_TIMEOUT_MS}ms)")
            delay(RING_TIMEOUT_MS)

            val app = context.applicationContext as GatewayApp
            if (!app.settings.autoAnswerEnabled) {
                Logger.i(TAG, "Auto-answer disabled, falling back to missed-call")
                startMissedCallTimer(context, number)
                return@launch
            }

            Logger.i(TAG, "Auto-answering call from $number")
            answerCall(context)

            delay(1000)

            val resolvedNumber = resolveNumber(context, number)
            val name = Contacts.lookupName(context, resolvedNumber)

            GatewayForegroundService.startCall(
                context, resolvedNumber, name, callId,
            )
            synchronized(this@CallTracker) { pending.remove(number) }
        }
        synchronized(this) { pending[number] = PendingCall(callId, number, job) }
    }

    private fun answerCall(context: Context) {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                val telecomManager = context.getSystemService(Context.TELECOM_SERVICE) as TelecomManager
                telecomManager.acceptRingingCall()
                Logger.i(TAG, "TelecomManager.acceptRingingCall() called")
            }
        } catch (e: SecurityException) {
            Logger.w(TAG, "No ANSWER_PHONE_CALLS permission: ${e.message}")
        } catch (e: Exception) {
            Logger.e(TAG, "Failed to answer call: ${e.message}", e)
        }
    }

    private fun startMissedCallTimer(context: Context, number: String) {
        val callId = UUID.randomUUID().toString()
        val job = scope.launch {
            Logger.i(TAG, "Missed-call timer started for $number (20s)")
            delay(MISSED_TIMEOUT_MS)
            Logger.i(TAG, "Timer elapsed without pickup -> reporting missed call")
            reportMissedCall(context, callId, number)
            synchronized(this@CallTracker) { pending.remove(number) }
        }
        synchronized(this) { pending[number] = PendingCall(callId, number, job) }
    }

    private fun cancelTimer(number: String, reason: String) {
        synchronized(this) {
            val p = pending.remove(number) ?: return
            p.job.cancel()
            Logger.i(TAG, "Cancelled timer for $number ($reason)")
        }
    }

    private fun resolveNumber(context: Context, rawNumber: String): String {
        if (rawNumber.isBlank() || rawNumber == "unknown") {
            val resolved = CallLogResolver.recentMissedCall(context)
            if (resolved != null) {
                Logger.i(TAG, "Resolved number from CallLog: ${resolved.number}")
                return resolved.number
            }
        }
        return if (rawNumber.isBlank()) "unknown" else rawNumber
    }

    private suspend fun reportMissedCall(context: Context, callId: String, rawNumber: String) {
        val app = context.applicationContext as GatewayApp
        if (!Network.isOnline(context)) {
            Logger.w(TAG, "Offline; skipping report for $rawNumber")
            return
        }

        val number = resolveNumber(context, rawNumber)
        if (number == "unknown") {
            Logger.w(TAG, "Could not resolve a number for callId=$callId")
            return
        }

        val name = Contacts.lookupName(context, number)
        val req = IncomingCallRequest(
            number = number,
            name = name,
            timestampMs = System.currentTimeMillis(),
            callId = callId,
            device = android.os.Build.MODEL ?: "android",
        )

        try {
            val resp = app.network.api().reportIncomingCall(req)
            Logger.i(TAG, "Server response: ok=${resp.ok} msg=${resp.message}")
        } catch (t: Throwable) {
            Logger.e(TAG, "Failed to report missed call: ${t.message}", t)
        }
    }

    fun shutdown() {
        scope.cancel()
    }
}
