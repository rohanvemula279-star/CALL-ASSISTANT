package com.rohan.assistant.gateway.service

import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.AudioManager
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.rohan.assistant.gateway.GatewayApp
import com.rohan.assistant.gateway.R
import com.rohan.assistant.gateway.network.model.IncomingCallRequest
import com.rohan.assistant.gateway.ui.MainActivity
import com.rohan.assistant.gateway.util.Logger
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File
import java.util.UUID

class GatewayForegroundService : Service() {

    private var audioHandler: CallAudioHandler? = null
    private var greetingFile: File? = null
    private var scope = CoroutineScope(Dispatchers.IO)
    private var processingJob: Job? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        Logger.i(TAG, "Service onCreate")
        audioHandler = CallAudioHandler(this)
        downloadGreeting()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        Logger.i(TAG, "Service onStartCommand action=${intent?.action}")
        try {
            startInForegroundCompat()
        } catch (t: Throwable) {
            Logger.e(TAG, "Failed to start foreground: ${t.message}", t)
        }

        when (intent?.action) {
            ACTION_DOWNLOAD_GREETING -> downloadGreeting()
            ACTION_HANDLE_CALL -> handleIncomingCall(intent)
            ACTION_STOP_PLAYBACK -> stopPlayback()
        }

        return START_STICKY
    }

    private fun handleIncomingCall(intent: Intent) {
        val number = intent.getStringExtra(EXTRA_NUMBER) ?: "unknown"
        val name = intent.getStringExtra(EXTRA_NAME)
        val callId = intent.getStringExtra(EXTRA_CALL_ID) ?: UUID.randomUUID().toString()

        Logger.i(TAG, "Handling incoming call from $number ($callId)")

        processingJob = scope.launch {
            val greeting = getGreetingFile()
            if (greeting != null) {
                Logger.i(TAG, "Playing greeting...")
                audioHandler?.playGreeting(greeting)

                delay(500)
                Logger.i(TAG, "Starting recording...")
                val recordingFile = audioHandler?.startRecording()

                delay(RECORD_DURATION_MS)

                val result = audioHandler?.stopRecording()
                Logger.i(TAG, "Recording done: ${result?.absolutePath}")

                if (result != null && result.exists()) {
                    uploadRecording(result, number, name ?: "", callId)
                }
            } else {
                Logger.w(TAG, "Greeting file not available, skipping greeting")
            }
        }
    }

    private fun getGreetingFile(): File? {
        greetingFile?.let { if (it.exists()) return it }

        val cached = File(cacheDir, "greeting.wav")
        if (cached.exists()) {
            greetingFile = cached
            return cached
        }
        return null
    }

    private fun downloadGreeting() {
        scope.launch {
            try {
                val app = application as GatewayApp
                val response = app.network.api().getGreeting()
                val file = File(cacheDir, "greeting.wav")
                file.outputStream().use { output ->
                    response.byteStream().use { input ->
                        input.copyTo(output)
                    }
                }
                greetingFile = file
                Logger.i(TAG, "Greeting downloaded: ${file.absolutePath}")
            } catch (t: Throwable) {
                Logger.e(TAG, "Failed to download greeting: ${t.message}", t)
            }
        }
    }

    private suspend fun uploadRecording(file: File, number: String, name: String, callId: String) {
        try {
            val app = application as GatewayApp
            val audioPart = MultipartBody.Part.createFormData(
                "audio", "voicemail.m4a",
                file.readBytes().toRequestBody("audio/mp4".toMediaTypeOrNull()),
            )
            val numberPart = number.toRequestBody("text/plain".toMediaTypeOrNull())
            val namePart = name.toRequestBody("text/plain".toMediaTypeOrNull())
            val callIdPart = callId.toRequestBody("text/plain".toMediaTypeOrNull())

            val resp = app.network.api().uploadVoicemail(audioPart, numberPart, namePart, callIdPart)
            Logger.i(TAG, "Voicemail uploaded: ok=${resp.ok} transcript=${resp.transcript}")
        } catch (t: Throwable) {
            Logger.e(TAG, "Failed to upload voicemail: ${t.message}", t)
        }
    }

    fun stopPlayback() {
        audioHandler?.stop()
        processingJob?.cancel()
    }

    private fun startInForegroundCompat() {
        val tapIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val pi = PendingIntent.getActivity(
            this, 0, tapIntent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )

        val notification: Notification = NotificationCompat.Builder(this, GatewayApp.CHANNEL_ID)
            .setContentTitle(getString(R.string.notif_title))
            .setContentText(getString(R.string.notif_text))
            .setSmallIcon(android.R.drawable.stat_sys_phone_call)
            .setContentIntent(pi)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            startForeground(
                GatewayApp.FG_NOTIF_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_PHONE_CALL,
            )
        } else {
            startForeground(GatewayApp.FG_NOTIF_ID, notification)
        }
    }

    override fun onDestroy() {
        Logger.i(TAG, "Service onDestroy")
        audioHandler?.stop()
        processingJob?.cancel()
        super.onDestroy()
    }

    companion object {
        private const val TAG = "GatewayService"
        private const val RECORD_DURATION_MS = 30_000L

        const val ACTION_DOWNLOAD_GREETING = "download_greeting"
        const val ACTION_HANDLE_CALL = "handle_call"
        const val ACTION_STOP_PLAYBACK = "stop_playback"
        const val EXTRA_NUMBER = "number"
        const val EXTRA_NAME = "name"
        const val EXTRA_CALL_ID = "call_id"

        fun start(context: Context) {
            val intent = Intent(context, GatewayForegroundService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }

        fun startWithAction(context: Context, action: String) {
            val intent = Intent(context, GatewayForegroundService::class.java).apply {
                this.action = action
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }

        fun startCall(context: Context, number: String, name: String?, callId: String) {
            val intent = Intent(context, GatewayForegroundService::class.java).apply {
                action = ACTION_HANDLE_CALL
                putExtra(EXTRA_NUMBER, number)
                putExtra(EXTRA_NAME, name)
                putExtra(EXTRA_CALL_ID, callId)
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, GatewayForegroundService::class.java))
        }
    }
}
