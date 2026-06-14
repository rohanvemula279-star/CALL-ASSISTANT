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

        // On a non-rooted phone the only way the remote caller hears the greeting
        // is acoustic coupling: play it loud on the speaker so the call mic picks
        // it up. Force speakerphone on and push the in-call volume to max.
        var savedVolume = -1
        try {
            audioManager.mode = AudioManager.MODE_IN_COMMUNICATION
            audioManager.isSpeakerphoneOn = true
            val max = audioManager.getStreamMaxVolume(AudioManager.STREAM_VOICE_CALL)
            savedVolume = audioManager.getStreamVolume(AudioManager.STREAM_VOICE_CALL)
            audioManager.setStreamVolume(AudioManager.STREAM_VOICE_CALL, max, 0)
        } catch (_: Exception) {}

        val result = if (greetingFile != null && greetingFile.exists()) {
            playWavFile(greetingFile)
        } else {
            speakTeluguViaTts()
        }

        try {
            if (savedVolume >= 0) {
                audioManager.setStreamVolume(AudioManager.STREAM_VOICE_CALL, savedVolume, 0)
            }
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
            track.setVolume(1.0f)
            val fis = FileInputStream(file)
            // Skip the RIFF/WAVE header (and any LIST/INFO chunks) so we only feed
            // raw PCM samples to the track — otherwise the header bytes play as noise.
            skipToPcmData(fis)
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

    /**
     * Advances the stream past the WAV header to the start of the `data` chunk.
     * Reads RIFF/WAVE, then walks each chunk header (4-byte id + 4-byte LE size),
     * skipping non-`data` chunks (e.g. fmt, LIST/INFO) until `data` is reached.
     * If the stream isn't a recognizable WAV, leaves it at the start.
     */
    private fun skipToPcmData(input: FileInputStream) {
        val header = ByteArray(12)
        if (input.read(header) != 12) return
        // "RIFF" .... "WAVE"
        if (header[0].toInt().toChar() != 'R' || header[8].toInt().toChar() != 'W') return

        val chunkHeader = ByteArray(8)
        while (input.read(chunkHeader) == 8) {
            val id = String(chunkHeader, 0, 4, Charsets.US_ASCII)
            val size = (chunkHeader[4].toInt() and 0xFF) or
                ((chunkHeader[5].toInt() and 0xFF) shl 8) or
                ((chunkHeader[6].toInt() and 0xFF) shl 16) or
                ((chunkHeader[7].toInt() and 0xFF) shl 24)
            if (id == "data") return // stream is now positioned at PCM samples
            var remaining = size.toLong()
            while (remaining > 0) {
                val skipped = input.skip(remaining)
                if (skipped <= 0) return
                remaining -= skipped
            }
        }
    }

    companion object {
        private const val TAG = "GreetingTts"
    }
}
