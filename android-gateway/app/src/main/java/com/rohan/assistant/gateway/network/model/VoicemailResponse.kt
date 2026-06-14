package com.rohan.assistant.gateway.network.model

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class VoicemailResponse(
    val ok: Boolean,
    val message: String? = null,
    @Json(name = "call_id") val callId: String? = null,
    val transcript: String? = null,
    val summary: String? = null,
    @Json(name = "callback_id") val callbackId: Int? = null,
    @Json(name = "telegram_sent") val telegramSent: Boolean = false,
)
