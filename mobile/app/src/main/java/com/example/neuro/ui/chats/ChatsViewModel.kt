package com.example.neuro.ui.chats

import androidx.lifecycle.LiveData
import androidx.lifecycle.MutableLiveData
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.neuro.api.ChatListItem
import com.example.neuro.api.RetrofitClient
import kotlinx.coroutines.launch

class ChatsViewModel : ViewModel() {

    private val _chats = MutableLiveData<List<ChatListItem>>()
    val chats: LiveData<List<ChatListItem>> = _chats

    private val _isLoading = MutableLiveData<Boolean>()
    val isLoading: LiveData<Boolean> = _isLoading

    private val _newChatCreated = MutableLiveData<ChatListItem?>()
    val newChatCreated: LiveData<ChatListItem?> = _newChatCreated

    fun loadChats(token: String) {
        _isLoading.value = true
        viewModelScope.launch {
            try {
                val response = RetrofitClient.instance.getChats(token)
                if (response.isSuccessful) {
                    _chats.value = response.body() ?: emptyList()
                }
            } catch (e: Exception) {
                // Handle error
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun createChat(token: String) {
        viewModelScope.launch {
            try {
                val response = RetrofitClient.instance.createChat(token, mapOf("title" to "New Chat"))
                if (response.isSuccessful) {
                    _newChatCreated.value = response.body()
                }
            } catch (e: Exception) {
                // Handle error
            }
        }
    }

    fun onChatCreatedHandled() {
        _newChatCreated.value = null
    }
}
