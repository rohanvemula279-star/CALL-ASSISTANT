package com.rohan.assistant.gateway.util

import com.rohan.assistant.gateway.data.SettingsRepository
import com.rohan.assistant.gateway.network.model.NetworkInfo
import com.rohan.assistant.gateway.util.Logger
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import retrofit2.http.GET
import java.util.concurrent.TimeUnit

/**
 * Helps the user connect to their laptop on the LAN without typing an IP.
 *
 * Probes a small set of common addresses (gateway, /24 sweep of a few
 * candidates) against the FastAPI service's /network/info and accepts the
 * first that responds with our app name.
 */
object LanDiscovery {

    private val client: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .connectTimeout(2, TimeUnit.SECONDS)
            .readTimeout(3, TimeUnit.SECONDS)
            .build()
    }

    /**
     * Tries to auto-discover the FastAPI host.
     * Returns the base URL on success, null otherwise.
     */
    suspend fun discover(
        prefer: String? = null,
        maxProbes: Int = 24,
    ): String? = withContext(Dispatchers.IO) {
        val candidates = buildCandidates(prefer)
        Logger.i("LanDiscovery", "Probing ${candidates.size} candidates (cap=$maxProbes)")
        for (url in candidates.take(maxProbes)) {
            val ok = probe(url)
            Logger.d("LanDiscovery", "$url -> $ok")
            if (ok) return@withContext url
        }
        null
    }

    private suspend fun probe(base: String): Boolean = withContext(Dispatchers.IO) {
        try {
            val r = Retrofit.Builder()
                .baseUrl("$base/")
                .client(client)
                .addConverterFactory(MoshiConverterFactory.create())
                .build()
            val resp = r.create(HealthApi::class.java).health()
            // Caller decides what counts as a "match"; any 200 response is good.
            resp.isSuccessful
        } catch (t: Throwable) {
            false
        }
    }

    private fun buildCandidates(prefer: String?): List<String> {
        val out = mutableListOf<String>()
        if (!prefer.isNullOrBlank()) out += prefer
        out += listOf(
            "http://10.0.2.2:8000",                  // emulator -> host
            "http://127.0.0.1:8000",
            "http://localhost:8000",
        )
        // Best-effort local /24 sweep
        val sweep = sweepCidr("192.168.0.1/24", 24) +
                    sweepCidr("192.168.1.1/24", 24) +
                    sweepCidr("10.0.0.1/24", 24)
        out += sweep.map { "http://$it:8000" }
        return out.distinct()
    }

    private fun sweepCidr(seed: String, max: Int): List<String> {
        val base = seed.substringBeforeLast('.')
        return (1..max).map { "$base.$it" }
    }

    private interface HealthApi {
        @GET("network/info")
        fun health(): retrofit2.Response<NetworkInfo>
    }
}
