package com.rohan.assistant.gateway.network

import com.rohan.assistant.gateway.network.model.IncomingCallRequest
import com.rohan.assistant.gateway.network.model.IncomingCallResponse
import com.rohan.assistant.gateway.network.model.VoicemailResponse
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Query

interface GatewayApi {
    @POST("/incoming-call")
    suspend fun reportIncomingCall(@Body body: IncomingCallRequest): IncomingCallResponse

    @Multipart
    @POST("/voicemail")
    suspend fun uploadVoicemail(
        @Part audio: MultipartBody.Part,
        @Part("number") number: RequestBody,
        @Part("name") name: RequestBody,
        @Part("call_id") callId: RequestBody,
    ): VoicemailResponse

    @GET("/api/greeting")
    suspend fun getGreeting(): okhttp3.ResponseBody
}
