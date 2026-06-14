package com.rohan.assistant.gateway.data

import android.content.Context
import android.content.SharedPreferences

class SettingsRepository(context: Context) {

    private val prefs: SharedPreferences =
        context.getSharedPreferences("rohan_gateway_prefs", Context.MODE_PRIVATE)

    var serverUrl: String
        get() = prefs.getString(KEY_SERVER_URL, null) ?: defaultServerUrl()
        set(value) = prefs.edit().putString(KEY_SERVER_URL, value.trimEnd('/')).apply()

    var serviceRunning: Boolean
        get() = prefs.getBoolean(KEY_SERVICE_RUNNING, false)
        set(value) = prefs.edit().putBoolean(KEY_SERVICE_RUNNING, value).apply()

    var autoAnswerEnabled: Boolean
        get() = prefs.getBoolean(KEY_AUTO_ANSWER, true)
        set(value) = prefs.edit().putBoolean(KEY_AUTO_ANSWER, value).apply()

    private fun defaultServerUrl(): String {
        val prop = runCatching {
            @Suppress("PrivateApi")
            Class.forName("android.os.SystemProperties")
                .getMethod("get", String::class.java, String::class.java)
                .invoke(null, "rohan.assistant.server", "") as String
        }.getOrNull()
        return if (!prop.isNullOrBlank()) prop else "http://10.0.2.2:8000"
    }

    companion object {
        private const val KEY_SERVER_URL = "server_url"
        private const val KEY_SERVICE_RUNNING = "service_running"
        private const val KEY_AUTO_ANSWER = "auto_answer"
    }
}
