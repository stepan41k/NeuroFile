package com.example.neuro.api

import retrofit2.Response
import retrofit2.http.*

interface NeuroApi {
    @POST("api/register")
    suspend fun register(@Body request: LoginRequest): Response<Map<String, String>>

    @POST("api/login")
    suspend fun login(@Body request: LoginRequest): Response<LoginResponse>

    @Multipart
    @POST("api/files")
    suspend fun uploadFile(
        @Header("Authorization") token: String,
        @Part file: okhttp3.MultipartBody.Part
    ): Response<FileResponse>

    @GET("api/files")
    suspend fun getFiles(@Header("Authorization") token: String): Response<List<FileResponse>>

    @GET("api/chats")
    suspend fun getChats(@Header("Authorization") token: String): Response<List<ChatListItem>>

    @POST("api/chat/send")
    suspend fun sendMessage(
        @Header("Authorization") token: String,
        @Body request: ChatRequest
    ): Response<ChatResponse>

    @GET("api/chats/{id}/messages")
    suspend fun getChatMessages(
        @Header("Authorization") token: String,
        @Path("id") chatId: Int
    ): Response<List<ChatMessage>>

    @POST("api/chats")
    suspend fun createChat(
        @Header("Authorization") token: String,
        @Body body: Map<String, String>
    ): Response<ChatListItem>

    @PUT("api/chats/{id}")
    suspend fun updateChat(
        @Header("Authorization") token: String,
        @Path("id") chatId: Int,
        @Body body: Map<String, String>
    ): Response<ChatListItem>

    @DELETE("api/chats/{id}")
    suspend fun deleteChat(
        @Header("Authorization") token: String,
        @Path("id") chatId: Int
    ): Response<Unit>

    @PUT("api/files/{id}")
    suspend fun updateFile(
        @Header("Authorization") token: String,
        @Path("id") fileId: Int,
        @Body body: Map<String, String>
    ): Response<FileResponse>

    @DELETE("api/files/{id}")
    suspend fun deleteFile(
        @Header("Authorization") token: String,
        @Path("id") fileId: Int
    ): Response<Unit>
}
