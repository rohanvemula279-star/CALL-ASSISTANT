package com.rohan.assistant.gateway.service

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioTrack
import android.media.MediaRecorder
import android.os.Build
import com.rohan.assistant.gateway.util.Logger
import java.io.File
import java.io.FileInputStream
import java.io.InputStream
import java.util.UUID

class CallAudioHandler(private val context: Context) {

    private var audioTrack: AudioTrack? = null
    private var mediaRecorder: MediaRecorder? = null
    private var recordingFile: File? = null
    private var isPlaying = false
    private var isRecording = false

    fun playGreeting(greetingFile: File) {
        if (isPlaying) return
        isPlaying = true

        try {
            val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
            audioManager.mode = AudioManager.MODE_IN_COMMUNICATION
            audioManager.isSpeakerphoneOn = true

            val streamVolume = audioManager.getStreamVolume(AudioManager.STREAM_VOICE_CALL)
            val streamMax = audioManager.getStreamMaxVolume(AudioManager.STREAM_VOICE_CALL)
            audioManager.setStreamVolume(AudioManager.STREAM_VOICE_CALL, streamMax, 0)

            val bufferSize = AudioTrack.getMinBufferSize(
                16000,
                AudioFormat.CHANNEL_OUT_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
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

            audioTrack = track
            track.play()

            val fis = FileInputStream(greetingFile)
            val pcmStream = skipToPcmData(fis)
            val buffer = ByteArray(bufferSize)
            var bytesRead: Int
            while (pcmStream.read(buffer).also { bytesRead = it } != -1 && isPlaying) {
                track.write(buffer, 0, bytesRead)
            }
            fis.close()

            track.stop()
            track.release()
            audioTrack = null

            audioManager.setStreamVolume(AudioManager.STREAM_VOICE_CALL, streamVolume, 0)
            audioManager.isSpeakerphoneOn = false
            audioManager.mode = AudioManager.MODE_NORMAL
        } catch (e: Exception) {
            Logger.e(TAG, "Greeting playback failed: ${e.message}", e)
        } finally {
            isPlaying = false
        }
    }

    private fun skipToPcmData(input: InputStream): InputStream {
        val header = ByteArray(12)
        if (input.read(header) < 12) return input
        val riff = String(header, 0, 4, Charsets.US_ASCII)
        val wave = String(header, 8, 4, Charsets.US_ASCII)
        if (riff != "RIFF" || wave != "WAVE") {
            input.close()
            throw IllegalArgumentException("Not a valid WAV file")
        }
        while (true) {
            val chunkId = ByteArray(4)
            val sizeBuf = ByteArray(4)
            if (input.read(chunkId) < 4 || input.read(sizeBuf) < 4) break
            val size = ((sizeBuf[3].toInt() and 0xFF) shl 24) or
                       ((sizeBuf[2].toInt() and 0xFF) shl 16) or
                       ((sizeBuf[1].toInt() and 0xFF) shl 8) or
                       (sizeBuf[0].toInt() and 0xFF)
            val id = String(chunkId, 0, 4, Charsets.US_ASCII)
            if (id == "data") return input
            val padded = size + (size % 2)
            input.skip(padded.toLong())
        }
        return input
    }

    fun startRecording(): File? {
        if (isRecording) return null
        isRecording = true

        try {
            val dir = File(context.cacheDir, "voicemails")
            dir.mkdirs()
            val file = File(dir, "${UUID.randomUUID()}.wav")
            recordingFile = file

            val recorder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                MediaRecorder(context)
            } else {
                MediaRecorder()
            }

            recorder.setAudioSource(MediaRecorder.AudioSource.MIC)
            recorder.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
            recorder.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
            recorder.setAudioSamplingRate(16000)
            recorder.setAudioChannels(1)
            recorder.setAudioEncodingBitRate(32000)
            recorder.setOutputFile(file.absolutePath)
            recorder.prepare()
            recorder.start()

            mediaRecorder = recorder
            Logger.i(TAG, "Recording started: ${file.absolutePath}")
            return file
        } catch (e: Exception) {
            Logger.e(TAG, "Failed to start recording: ${e.message}", e)
            isRecording = false
            return null
        }
    }

    fun stopRecording(): File? {
        if (!isRecording) return null
        isRecording = false

        try {
            mediaRecorder?.apply {
                stop()
                release()
            }
            mediaRecorder = null
            Logger.i(TAG, "Recording stopped")
        } catch (e: Exception) {
            Logger.e(TAG, "Failed to stop recording: ${e.message}", e)
        }

        val file = recordingFile
        recordingFile = null
        return file
    }

    fun stop() {
        isPlaying = false
        isRecording = false

        try {
            audioTrack?.apply {
                stop()
                release()
            }
            audioTrack = null
        } catch (_: Exception) {}

        try {
            mediaRecorder?.apply {
                stop()
                release()
            }
            mediaRecorder = null
        } catch (_: Exception) {}
    }

    companion object {
        private const val TAG = "CallAudioHandler"
    }
}
