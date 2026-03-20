package com.example.neuro.api

import com.google.gson.annotations.SerializedName

data class LoginRequest(
    val username: String,
    val password: String
)

data class LoginResponse(
    val token: String,
    val username: String
)

data class FileResponse(
    val id: Int,
    val name: String,
    val size: Long,
    val type: String
)

data class ChatRequest(
    @SerializedName("chat_id") val chatId: Int,
    val content: String,
    @SerializedName("separate_conflicts") val separateConflicts: Boolean = false
)

data class ChatMessage(
    val role: String,
    val content: String,
    @SerializedName("files_used") val filesUsed: List<String>? = null,
    val attention: List<List<String>>? = null
)

data class ChatResponse(
    val role: String,
    val content: String,
    @SerializedName("files_used") val filesUsed: List<String> = emptyList(),
    val attention: List<List<String>> = emptyList()
)

data class ChatListItem(
    val id: Int,
    val title: String,
    @SerializedName("last_activity") val lastActivity: String? = null
)
