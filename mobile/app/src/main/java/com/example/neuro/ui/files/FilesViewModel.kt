package com.example.neuro.ui.files

import androidx.lifecycle.LiveData
import androidx.lifecycle.MutableLiveData
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.neuro.api.FileResponse
import com.example.neuro.api.RetrofitClient
import kotlinx.coroutines.launch
import okhttp3.MultipartBody

class FilesViewModel : ViewModel() {

    private val _files = MutableLiveData<List<FileResponse>>()
    val files: LiveData<List<FileResponse>> = _files

    private val _isLoading = MutableLiveData<Boolean>()
    val isLoading: LiveData<Boolean> = _isLoading

    private val _error = MutableLiveData<String?>()
    val error: LiveData<String?> = _error

    fun loadFiles(token: String) {
        _isLoading.value = true
        _error.value = null
        viewModelScope.launch {
            try {
                val response = RetrofitClient.instance.getFiles(token)
                if (response.isSuccessful) {
                    _files.value = response.body() ?: emptyList()
                } else {
                    _error.value = "Ошибка сервера: ${response.code()}"
                }
            } catch (e: Exception) {
                _error.value = "Ошибка сети: ${e.message}"
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun uploadFile(token: String, filePart: MultipartBody.Part) {
        _isLoading.value = true
        viewModelScope.launch {
            try {
                val response = RetrofitClient.instance.uploadFile(token, filePart)
                if (response.isSuccessful) {
                    loadFiles(token)
                } else {
                    _error.value = "Ошибка загрузки: ${response.code()}"
                }
            } catch (e: Exception) {
                _error.value = "Ошибка сети: ${e.message}"
            } finally {
                _isLoading.value = false
            }
        }
    }
}
