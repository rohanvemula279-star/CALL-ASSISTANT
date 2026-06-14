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
import java.util.Locale
import java.util.UUID
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

class GreetingTts(private val context: Context) {

    private var tts: TextToSpeech? = null
    private var ttsReady = false

    fun speak(greetingFile: File?): Boolean {
        if (greetingFile != null && greetingFile.exists()) {
            return playWavFile(greetingFile)
        }
        return speakViaTts()
    }

    private fun speakViaTts(): Boolean {
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
                tts?.language = Locale.US
                tts?.setOnUtteranceProgressListener(listener)

                val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
                audioManager.mode = AudioManager.MODE_IN_COMMUNICATION
                audioManager.isSpeakerphoneOn = false

                val uid = UUID.randomUUID().toString()
                tts?.speak(
                    "Hi, Rohan is currently busy. Please leave a message after the beep, and he will get back to you as soon as possible.",
                    TextToSpeech.QUEUE_FLUSH,
                    null,
                    uid,
                )

                try {
                    latch.await(15, TimeUnit.SECONDS)
                } catch (_: InterruptedException) {}
            } else {
                Logger.w(TAG, "TTS initialization failed: $status")
                latch.countDown()
            }
        }

        try {
            latch.await(20, TimeUnit.SECONDS)
        } catch (_: InterruptedException) {}

        tts?.stop()
        tts?.shutdown()
        tts = null

        return success
    }

    private fun playWavFile(file: File): Boolean {
        try {
            val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
            audioManager.mode = AudioManager.MODE_IN_COMMUNICATION
            audioManager.isSpeakerphoneOn = false

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
                        .setSampleRate(16000)
                        .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                        .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                        .build()
                )
                .setBufferSizeInBytes(bufferSize)
                .setTransferMode(AudioTrack.MODE_STREAM)
                .build()

            track.play()
            val fis = java.io.FileInputStream(file)
            val buffer = ByteArray(bufferSize)
            var bytesRead: Int
            while (fis.read(buffer).also { bytesRead = it } != -1) {
                track.write(buffer, 0, bytesRead)
            }
            fis.close()
            track.stop()
            track.release()
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
