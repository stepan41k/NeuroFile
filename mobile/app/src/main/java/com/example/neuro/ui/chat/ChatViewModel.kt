package com.example.neuro.ui.chat

import androidx.lifecycle.LiveData
import androidx.lifecycle.MutableLiveData
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.neuro.api.ChatMessage
import com.example.neuro.api.ChatRequest
import com.example.neuro.api.RetrofitClient
import kotlinx.coroutines.launch

class ChatViewModel : ViewModel() {

    private val _messages = MutableLiveData<List<ChatMessage>>(emptyList())
    val messages: LiveData<List<ChatMessage>> = _messages

    private val _isLoading = MutableLiveData<Boolean>()
    val isLoading: LiveData<Boolean> = _isLoading

    private val _error = MutableLiveData<String?>()
    val error: LiveData<String?> = _error

    fun loadMessages(token: String, chatId: Int) {
        viewModelScope.launch {
            try {
                val response = RetrofitClient.instance.getChatMessages(token, chatId)
                if (response.isSuccessful) {
                    _messages.value = response.body() ?: emptyList()
                } else {
                    _error.value = "Ошибка загрузки сообщений: ${response.code()}"
                }
            } catch (e: Exception) {
                _error.value = "Ошибка сети: ${e.message}"
            }
        }
    }

    fun sendMessage(token: String, chatId: Int, content: String) {
        val currentMessages = _messages.value.orEmpty().toMutableList()
        currentMessages.add(ChatMessage(role = "user", content = content))
        _messages.value = currentMessages
        _error.value = null

        _isLoading.value = true
        viewModelScope.launch {
            try {
                val response = RetrofitClient.instance.sendMessage(
                    token,
                    ChatRequest(chatId, content)
                )
                if (response.isSuccessful) {
                    val aiResponse = response.body()
                    if (aiResponse != null && aiResponse.content.isNotEmpty()) {
                        val updatedMessages = _messages.value.orEmpty().toMutableList()
                        updatedMessages.add(ChatMessage(
                            role = aiResponse.role,
                            content = aiResponse.content,
                            filesUsed = aiResponse.filesUsed,
                            attention = aiResponse.attention
                        ))
                        _messages.value = updatedMessages
                    } else if (aiResponse != null) {
                        _error.value = "Пустой ответ от сервера"
                    } else {
                        _error.value = "Ошибка: null ответ"
                    }
                } else {
                    val errorBody = response.errorBody()?.string()
                    _error.value = "Ошибка сервера (${response.code()}): ${errorBody ?: "неизвестная ошибка"}"
                }
            } catch (e: Exception) {
                _error.value = "Ошибка сети: ${e.message ?: "неизвестная ошибка"}"
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun createChat(token: String, onComplete: (Int) -> Unit) {
        viewModelScope.launch {
            try {
                val response = RetrofitClient.instance.createChat(token, mapOf("title" to "New Chat"))
                if (response.isSuccessful) {
                    val chat = response.body()
                    if (chat != null) {
                        onComplete(chat.id)
                    }
                }
            } catch (e: Exception) {
                _error.value = "Ошибка создания чата: ${e.message}"
            }
        }
    }
}
