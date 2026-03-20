package com.example.neuro.ui.login

import androidx.lifecycle.LiveData
import androidx.lifecycle.MutableLiveData
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.neuro.api.LoginRequest
import com.example.neuro.api.RetrofitClient
import kotlinx.coroutines.launch

class LoginViewModel : ViewModel() {

    private val _loginResult = MutableLiveData<Result<String>>()
    val loginResult: LiveData<Result<String>> = _loginResult

    private val _isLoading = MutableLiveData<Boolean>()
    val isLoading: LiveData<Boolean> = _isLoading

    private val _registerResult = MutableLiveData<Result<String>>()
    val registerResult: LiveData<Result<String>> = _registerResult

    fun register(username: String, password: String) {
        _isLoading.value = true
        viewModelScope.launch {
            try {
                val response = RetrofitClient.instance.register(LoginRequest(username, password))
                if (response.isSuccessful) {
                    _registerResult.value = Result.success("Аккаунт создан! Теперь войдите.")
                } else {
                    val errorBody = response.errorBody()?.string()
                    _registerResult.value = Result.failure(Exception("Ошибка регистрации: ${response.code()} - $errorBody"))
                }
            } catch (e: Exception) {
                _registerResult.value = Result.failure(e)
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun login(username: String, password: String) {
        _isLoading.value = true
        viewModelScope.launch {
            try {
                val response = RetrofitClient.instance.login(LoginRequest(username, password))
                if (response.isSuccessful) {
                    val token = response.body()?.token
                    if (token != null) {
                        _loginResult.value = Result.success(token)
                    } else {
                        _loginResult.value = Result.failure(Exception("Пустой токен"))
                    }
                } else {
                    val errorBody = response.errorBody()?.string()
                    _loginResult.value = Result.failure(Exception("Ошибка входа: ${response.code()} - $errorBody"))
                }
            } catch (e: Exception) {
                _loginResult.value = Result.failure(e)
            } finally {
                _isLoading.value = false
            }
        }
    }
}
