package com.rohan.assistant.gateway

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import com.rohan.assistant.gateway.data.SettingsRepository
import com.rohan.assistant.gateway.network.NetworkModule

class GatewayApp : Application() {

    val settings: SettingsRepository by lazy { SettingsRepository(this) }
    val network: NetworkModule by lazy { NetworkModule(settings) }

    override fun onCreate() {
        super.onCreate()
        createNotificationChannels()
    }

    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val mgr = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

            val mainChannel = NotificationChannel(
                CHANNEL_ID,
                getString(R.string.notif_channel_name),
                NotificationManager.IMPORTANCE_LOW,
            ).apply {
                description = getString(R.string.notif_channel_desc)
            }
            mgr.createNotificationChannel(mainChannel)

            val callChannel = NotificationChannel(
                CALL_CHANNEL_ID,
                "Call Handling",
                NotificationManager.IMPORTANCE_HIGH,
            ).apply {
                description = "Notifications for incoming calls and voicemails"
            }
            mgr.createNotificationChannel(callChannel)
        }
    }

    companion object {
        const val CHANNEL_ID = "gateway_service"
        const val CALL_CHANNEL_ID = "call_handling"
        const val FG_NOTIF_ID = 1001
    }
}
