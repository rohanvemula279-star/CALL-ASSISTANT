package com.rohan.assistant.gateway.network.model

import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class IncomingCallRequest(
    val number: String,
    val name: String?,
    val timestampMs: Long,
    val callId: String,
    val device: String,
)

@JsonClass(generateAdapter = true)
data class IncomingCallResponse(
    val ok: Boolean,
    val message: String? = null,
    val replyAudioUrl: String? = null,
    val replyText: String? = null,
)
