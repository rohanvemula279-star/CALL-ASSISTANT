package com.rohan.assistant.gateway.network

import com.rohan.assistant.gateway.data.SettingsRepository
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import java.util.concurrent.TimeUnit

class NetworkModule(private val settings: SettingsRepository) {

    private val logging = HttpLoggingInterceptor().apply {
        level = HttpLoggingInterceptor.Level.BASIC
    }

    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .writeTimeout(20, TimeUnit.SECONDS)
        .addInterceptor(logging)
        .build()

    private val moshi: Moshi = Moshi.Builder()
        .add(KotlinJsonAdapterFactory())
        .build()

    /** Lazily-built Retrofit tied to the current server URL. Re-create on URL change. */
    @Volatile private var cachedBase: String? = null
    @Volatile private var cachedApi: GatewayApi? = null

    fun api(): GatewayApi {
        val base = settings.serverUrl
        val existing = cachedApi
        if (existing != null && cachedBase == base) return existing

        val retrofit = Retrofit.Builder()
            .baseUrl("$base/")
            .client(client)
            .addConverterFactory(MoshiConverterFactory.create(moshi))
            .build()

        val newApi = retrofit.create(GatewayApi::class.java)
        cachedBase = base
        cachedApi = newApi
        return newApi
    }
}
