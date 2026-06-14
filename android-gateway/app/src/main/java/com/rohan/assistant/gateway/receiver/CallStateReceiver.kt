package com.rohan.assistant.gateway.receiver

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.telephony.TelephonyManager
import com.rohan.assistant.gateway.service.CallTracker
import com.rohan.assistant.gateway.util.Logger

/**
 * Listens for PHONE_STATE broadcasts and forwards them to [CallTracker],
 * which runs the 20-second timer logic.
 */
class CallStateReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != TelephonyManager.ACTION_PHONE_STATE_CHANGED) return

        val state = intent.getStringExtra(TelephonyManager.EXTRA_STATE) ?: return
        val number = intent.getStringExtra(TelephonyManager.EXTRA_INCOMING_NUMBER) ?: "unknown"

        Logger.i(TAG, "Phone state changed: state=$state number=$number")
        CallTracker.handleStateChange(context.applicationContext, state, number)
    }

    companion object {
        private const val TAG = "CallStateReceiver"
    }
}
