package com.example.neuro.ui.splash

import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import androidx.appcompat.app.AppCompatActivity
import com.example.neuro.ui.login.LoginActivity
import com.example.neuro.ui.main.MainActivity

class SplashActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        Handler(Looper.getMainLooper()).postDelayed({
            val prefs = getSharedPreferences("neuro_prefs", MODE_PRIVATE)
            val token = prefs.getString("auth_token", null)

            val nextActivity = if (!token.isNullOrEmpty()) {
                MainActivity::class.java
            } else {
                LoginActivity::class.java
            }

            startActivity(Intent(this, nextActivity))
            finish()
        }, 1500)
    }
}
