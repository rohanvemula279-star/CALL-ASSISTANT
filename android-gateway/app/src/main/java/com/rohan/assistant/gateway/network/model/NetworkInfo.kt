package com.rohan.assistant.gateway.network.model

import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class NetworkInfo(
    val host: String? = null,
    val ips: List<String> = emptyList(),
    val port: Int? = null,
    val base_urls: List<String> = emptyList(),
    val recommended: String? = null,
)
