package com.rohan.assistant.gateway.service

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioTrack
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import com.rohan.assistant.gateway.util.Logger
import java.io.File
import java.io.FileInputStream
import java.util.Locale
import java.util.UUID
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

class GreetingTts(private val context: Context) {

    private var tts: TextToSpeech? = null
    private var ttsReady = false

    fun speak(greetingFile: File?): Boolean {
        val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        try {
            audioManager.mode = AudioManager.MODE_IN_COMMUNICATION
            audioManager.isSpeakerphoneOn = true
        } catch (_: Exception) {}

        val result = if (greetingFile != null && greetingFile.exists()) {
            playWavFile(greetingFile)
        } else {
            speakTeluguViaTts()
        }

        try {
            audioManager.isSpeakerphoneOn = false
            audioManager.mode = AudioManager.MODE_NORMAL
        } catch (_: Exception) {}

        return result
    }

    private fun speakTeluguViaTts(): Boolean {
        val latch = CountDownLatch(1)
        var success = false

        val listener = object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String?) {}
            override fun onDone(utteranceId: String?) {
                success = true
                latch.countDown()
            }
            override fun onError(utteranceId: String?) {
                latch.countDown()
            }
        }

        tts = TextToSpeech(context) { status ->
            if (status == TextToSpeech.SUCCESS) {
                val teluguLocale = Locale("te", "IN")
                val available = tts?.setLanguage(teluguLocale)
                if (available == TextToSpeech.LANG_NOT_SUPPORTED || available == TextToSpeech.LANG_MISSING_DATA) {
                    tts?.language = Locale.US
                }

                tts?.setOnUtteranceProgressListener(listener)

                val uid = UUID.randomUUID().toString()
                tts?.speak(
                    "రోహన్ సర్ బిజీగా ఉన్నారు. నేను అతని అసిస్టెంట్ మాక్స్ ని. నేను మీరు చెప్పిన సమాచారాన్ని సర్ కి పంపిస్తాను.",
                    TextToSpeech.QUEUE_FLUSH, null, uid,
                )

                try { latch.await(15, TimeUnit.SECONDS) } catch (_: InterruptedException) {}
            } else {
                Logger.w(TAG, "TTS init failed: $status")
                latch.countDown()
            }
        }

        try { latch.await(20, TimeUnit.SECONDS) } catch (_: InterruptedException) {}
        tts?.stop(); tts?.shutdown(); tts = null
        return success
    }

    private fun playWavFile(file: File): Boolean {
        try {
            val bufferSize = AudioTrack.getMinBufferSize(
                16000, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT,
            )
            val track = AudioTrack.Builder()
                .setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .build()
                )
                .setAudioFormat(
                    AudioFormat.Builder()
                        .setSampleRate(16000).setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                        .setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build()
                )
                .setBufferSizeInBytes(bufferSize)
                .setTransferMode(AudioTrack.MODE_STREAM)
                .build()

            track.play()
            track.setVolume(0.4f)
            val fis = FileInputStream(file)
            val buffer = ByteArray(bufferSize)
            var bytesRead: Int
            while (fis.read(buffer).also { bytesRead = it } != -1) {
                track.write(buffer, 0, bytesRead)
            }
            fis.close()
            track.stop(); track.release()
            return true
        } catch (e: Exception) {
            Logger.e(TAG, "WAV playback failed: ${e.message}", e)
            return false
        }
    }

    companion object {
        private const val TAG = "GreetingTts"
    }
}
