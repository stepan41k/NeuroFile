package com.example.neuro.ui.main

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.KeyEvent
import android.view.View
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.GravityCompat
import androidx.recyclerview.widget.LinearLayoutManager
import com.example.neuro.R
import com.example.neuro.api.ChatListItem
import com.example.neuro.api.FileResponse
import com.example.neuro.api.RetrofitClient
import com.example.neuro.databinding.ActivityMainBinding
import com.example.neuro.ui.chat.ChatFragment
import com.example.neuro.ui.chat.ChatsDrawerAdapter
import com.example.neuro.ui.files.FilesDrawerAdapter
import com.example.neuro.ui.login.LoginActivity
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private var token: String = ""
    private var currentChatId: Int = -1
    private var chatsAdapter: ChatsDrawerAdapter? = null
    private var filesAdapter: FilesDrawerAdapter? = null
    private var chatsList: List<ChatListItem> = emptyList()
    private var isChatsLoaded = false
    private var isCreatingChat = false

    private val filePickerLauncher = registerForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
        uri?.let { uploadFile(it) }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val prefs = getSharedPreferences("neuro_prefs", MODE_PRIVATE)
        token = prefs.getString("auth_token", "") ?: ""

        if (token.isEmpty()) {
            startActivity(Intent(this, LoginActivity::class.java))
            finish()
            return
        }

        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupToolbar()
        setupChatsDrawer()
        setupFilesDrawer()
        setupMessageInput()

        // Скрываем кнопку меню чата по умолчанию
        binding.btnChatMenu.visibility = View.GONE

        // Загружаем чаты и создаём один если пусто
        loadChatsAndCreateIfEmpty()
        loadFiles()
    }

    private fun loadChatsAndCreateIfEmpty() {
        if (isChatsLoaded) return

        CoroutineScope(Dispatchers.IO).launch {
            try {
                val response = RetrofitClient.instance.getChats(token)
                withContext(Dispatchers.Main) {
                    if (response.isSuccessful) {
                        chatsList = response.body() ?: emptyList()
                        updateChatsAdapter()

                        if (chatsList.isNotEmpty()) {
                            // Открываем первый чат
                            openChat(chatsList[0].id, chatsList[0].title)
                        } else {
                            // Создаём один пустой чат при первом запуске
                            createInitialChat()
                        }
                        isChatsLoaded = true
                    } else {
                        // Если ошибка - создаём чат всё равно
                        createInitialChat()
                        isChatsLoaded = true
                    }
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@MainActivity, "Ошибка: ${e.message}", Toast.LENGTH_SHORT).show()
                    createInitialChat()
                    isChatsLoaded = true
                }
            }
        }
    }

    private fun createInitialChat() {
        if (isCreatingChat) return
        isCreatingChat = true

        CoroutineScope(Dispatchers.IO).launch {
            try {
                val response = RetrofitClient.instance.createChat(token, mapOf("title" to "New Chat"))
                withContext(Dispatchers.Main) {
                    if (response.isSuccessful) {
                        val newChat = response.body()
                        if (newChat != null) {
                            chatsList = listOf(newChat)
                            updateChatsAdapter()
                            openChat(newChat.id, newChat.title)
                        }
                    }
                    isCreatingChat = false
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    isCreatingChat = false
                }
            }
        }
    }

    private fun setupToolbar() {
        binding.toolbar.setNavigationIcon(android.R.drawable.ic_menu_sort_by_size)
        binding.toolbar.setNavigationOnClickListener {
            binding.drawerLayout.openDrawer(GravityCompat.START)
        }

        binding.btnFilesMenu.setOnClickListener {
            binding.drawerLayout.openDrawer(GravityCompat.END)
        }

        binding.btnChatMenu.setOnClickListener {
            showChatMenuPopup()
        }
    }

    private fun setupChatsDrawer() {
        chatsAdapter = ChatsDrawerAdapter(emptyList()) { chat ->
            openChat(chat.id, chat.title)
            binding.drawerLayout.closeDrawer(GravityCompat.START)
        }

        binding.rvChatsList.layoutManager = LinearLayoutManager(this)
        binding.rvChatsList.adapter = chatsAdapter

        binding.btnNewChat.setOnClickListener {
            createNewChat()
            binding.drawerLayout.closeDrawer(GravityCompat.START)
        }

        binding.btnLogout.setOnClickListener {
            getSharedPreferences("neuro_prefs", MODE_PRIVATE)
                .edit()
                .remove("auth_token")
                .apply()
            startActivity(Intent(this, LoginActivity::class.java))
            finish()
        }

        // Отображаем имя пользователя
        val username = token.split(".").lastOrNull()?.take(8) ?: "User"
        binding.tvUsername.text = username
    }

    private fun setupFilesDrawer() {
        filesAdapter = FilesDrawerAdapter(emptyList()) {
            // Refresh callback
            loadFiles()
        }

        binding.rvFilesList.layoutManager = LinearLayoutManager(this)
        binding.rvFilesList.adapter = filesAdapter

        binding.btnUploadFile.setOnClickListener {
            filePickerLauncher.launch("*/*")
        }

        binding.btnRefreshFiles.setOnClickListener {
            loadFiles()
        }

        // Поиск файлов
        binding.etSearchFiles.addTextChangedListener(object : android.text.TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {
                filterFiles(s.toString())
            }
            override fun afterTextChanged(s: android.text.Editable?) {}
        })

        // Фильтры по типу
        setupFileFilters()
    }

    private fun setupFileFilters() {
        val chips = listOf(
            binding.chipAll to "all",
            binding.chipPdf to "pdf",
            binding.chipDoc to "doc",
            binding.chipDocx to "docx",
            binding.chipRtf to "rtf"
        )

        chips.forEach { (chip, type) ->
            chip.setOnCheckedChangeListener { _, isChecked ->
                if (isChecked) {
                    // Снимаем выделение с остальных
                    chips.forEach { (c, _) ->
                        if (c != chip) c.isChecked = false
                    }
                    // Фильтруем
                    filterFilesByType(type)
                }
            }
        }
    }

    private var currentFileTypeFilter = "all"

    private fun filterFilesByType(type: String) {
        currentFileTypeFilter = type
        val files = when (type) {
            "all" -> filesAdapter?.files ?: emptyList()
            else -> (filesAdapter?.files ?: emptyList()).filter {
                it.type.equals(type, ignoreCase = true) ||
                (type == "doc" && it.name.endsWith(".doc", ignoreCase = true)) ||
                (type == "docx" && it.name.endsWith(".docx", ignoreCase = true))
            }
        }
        filesAdapter = FilesDrawerAdapter(files) { loadFiles() }
        binding.rvFilesList.adapter = filesAdapter
    }

    private fun filterFiles(query: String) {
        val filtered = if (query.isEmpty()) {
            when (currentFileTypeFilter) {
                "all" -> filesAdapter?.files ?: emptyList()
                else -> (filesAdapter?.files ?: emptyList()).filter {
                    it.type.equals(currentFileTypeFilter, ignoreCase = true)
                }
            }
        } else {
            when (currentFileTypeFilter) {
                "all" -> (filesAdapter?.files ?: emptyList()).filter {
                    it.name.contains(query, ignoreCase = true)
                }
                else -> (filesAdapter?.files ?: emptyList()).filter {
                    it.name.contains(query, ignoreCase = true) &&
                    it.type.equals(currentFileTypeFilter, ignoreCase = true)
                }
            }
        }
        filesAdapter = FilesDrawerAdapter(filtered) { loadFiles() }
        binding.rvFilesList.adapter = filesAdapter
    }

    private fun setupMessageInput() {
        binding.btnSend.setOnClickListener {
            sendMessage()
        }

        binding.etMessage.setOnKeyListener { _, keyCode, event ->
            if (keyCode == KeyEvent.KEYCODE_ENTER && event.action == KeyEvent.ACTION_DOWN) {
                sendMessage()
                true
            } else {
                false
            }
        }
    }

    private fun updateChatsAdapter() {
        chatsAdapter = ChatsDrawerAdapter(chatsList) { chat ->
            openChat(chat.id, chat.title)
            binding.drawerLayout.closeDrawer(GravityCompat.START)
        }
        binding.rvChatsList.adapter = chatsAdapter
    }

    private fun loadFiles() {
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val response = RetrofitClient.instance.getFiles(token)
                withContext(Dispatchers.Main) {
                    if (response.isSuccessful) {
                        val files = response.body() ?: emptyList()
                        filesAdapter = FilesDrawerAdapter(files) { loadFiles() }
                        binding.rvFilesList.adapter = filesAdapter
                        filterFilesByType(currentFileTypeFilter)
                    }
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@MainActivity, "Ошибка загрузки файлов: ${e.message}", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun createNewChat() {
        // Защита от множественного создания
        if (isCreatingChat) {
            Toast.makeText(this, "Чат уже создаётся...", Toast.LENGTH_SHORT).show()
            return
        }

        // Не создаём новый чат если текущий пустой (первый чат при запуске)
        if (currentChatId != -1) {
            val fragment = supportFragmentManager.findFragmentById(R.id.chatFragmentContainer) as? ChatFragment
            val currentMessages = fragment?.let { f ->
                f.getMessagesCount()
            } ?: 0
            
            if (currentMessages == 0) {
                Toast.makeText(this, "Вы уже в новом чате", Toast.LENGTH_SHORT).show()
                return
            }
        }

        isCreatingChat = true

        CoroutineScope(Dispatchers.IO).launch {
            try {
                val response = RetrofitClient.instance.createChat(token, mapOf("title" to "New Chat"))
                withContext(Dispatchers.Main) {
                    if (response.isSuccessful) {
                        val newChat = response.body()
                        if (newChat != null) {
                            // Добавляем в начало списка
                            chatsList = listOf(newChat) + chatsList
                            updateChatsAdapter()
                            // Переключаемся на новый чат
                            openChat(newChat.id, newChat.title)
                            // Сбрасываем флаг с задержкой
                            android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
                                isCreatingChat = false
                            }, 500)
                        } else {
                            isCreatingChat = false
                        }
                    } else {
                        Toast.makeText(this@MainActivity, "Ошибка создания чата", Toast.LENGTH_SHORT).show()
                        isCreatingChat = false
                    }
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@MainActivity, "Ошибка: ${e.message}", Toast.LENGTH_SHORT).show()
                    isCreatingChat = false
                }
            }
        }
    }

    fun openChat(chatId: Int, title: String) {
        // Защита от повторного открытия того же чата (но не для -1)
        if (currentChatId == chatId && chatId != -1) {
            return
        }

        currentChatId = chatId
        binding.toolbar.title = title
        binding.btnChatMenu.visibility = if (chatId != -1) View.VISIBLE else View.GONE

        val fragment = supportFragmentManager.findFragmentById(R.id.chatFragmentContainer) as? ChatFragment

        if (fragment != null) {
            fragment.loadChat(chatId, title)
        } else {
            val newFragment = ChatFragment.newInstance(chatId, title)
            supportFragmentManager.beginTransaction()
                .replace(R.id.chatFragmentContainer, newFragment)
                .commit()
        }
    }

    private fun uploadFile(uri: Uri) {
        val contentResolver = contentResolver
        val fileName = contentResolver.query(uri, null, null, null, null)?.use { cursor ->
            val nameIndex = cursor.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME)
            cursor.moveToFirst()
            cursor.getString(nameIndex)
        } ?: "file"

        val fileBytes = contentResolver.openInputStream(uri)?.readBytes()
        if (fileBytes != null) {
            val requestBody = fileBytes.toRequestBody("application/octet-stream".toMediaTypeOrNull())
            val body = MultipartBody.Part.createFormData("file", fileName, requestBody)

            CoroutineScope(Dispatchers.IO).launch {
                try {
                    val response = RetrofitClient.instance.uploadFile(token, body)
                    withContext(Dispatchers.Main) {
                        if (response.isSuccessful) {
                            Toast.makeText(this@MainActivity, "Файл загружен", Toast.LENGTH_SHORT).show()
                            loadFiles()
                        } else {
                            Toast.makeText(this@MainActivity, "Ошибка загрузки файла", Toast.LENGTH_SHORT).show()
                        }
                    }
                } catch (e: Exception) {
                    withContext(Dispatchers.Main) {
                        Toast.makeText(this@MainActivity, "Ошибка: ${e.message}", Toast.LENGTH_SHORT).show()
                    }
                }
            }
        }
    }

    fun getCurrentChatId(): Int = currentChatId

    fun getToken(): String = token

    fun refreshChatsList() {
        isChatsLoaded = false
        loadChatsAndCreateIfEmpty()
    }

    private fun showChatMenuPopup() {
        if (currentChatId == -1) return

        val popup = android.widget.PopupMenu(this, binding.btnChatMenu)
        popup.menu.add(0, 1, 0, "✏️ Изменить название")
        popup.menu.add(0, 2, 1, "🗑️ Удалить чат")

        popup.setOnMenuItemClickListener { item ->
            when (item.itemId) {
                1 -> {
                    showEditChatTitleDialog()
                    true
                }
                2 -> {
                    showDeleteChatDialog()
                    true
                }
                else -> false
            }
        }

        popup.show()
    }

    private fun showEditChatTitleDialog() {
        if (currentChatId == -1) return

        val builder = android.app.AlertDialog.Builder(this)
        builder.setTitle("Изменить название чата")

        val input = android.widget.EditText(this)
        input.hint = "Введите новое название"
        input.setText(binding.toolbar.title.toString())
        builder.setView(input)

        builder.setPositiveButton("Сохранить") { _, _ ->
            val newTitle = input.text.toString().trim()
            if (newTitle.isNotEmpty()) {
                updateChatTitle(newTitle)
            }
        }
        builder.setNegativeButton("Отмена") { dialog, _ ->
            dialog.cancel()
        }

        builder.show()
    }

    private fun updateChatTitle(newTitle: String) {
        // Сначала обновляем локально
        binding.toolbar.title = newTitle
        
        // Обновляем в списке чатов
        val chatIndex = chatsList.indexOfFirst { it.id == currentChatId }
        if (chatIndex != -1) {
            val updatedChat = chatsList[chatIndex].copy(title = newTitle)
            chatsList = chatsList.mapIndexed { index, chat ->
                if (index == chatIndex) updatedChat else chat
            }
            updateChatsAdapter()
        }
        
        Toast.makeText(this, "Название обновлено", Toast.LENGTH_SHORT).show()
        
        // Затем отправляем на сервер
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val response = RetrofitClient.instance.updateChat(token, currentChatId, mapOf("title" to newTitle))
                withContext(Dispatchers.Main) {
                    if (!response.isSuccessful) {
                        Toast.makeText(this@MainActivity, "Не удалось сохранить на сервере", Toast.LENGTH_SHORT).show()
                    }
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    // Игнорируем ошибку - название уже обновлено локально
                }
            }
        }
    }

    private fun showDeleteChatDialog() {
        if (currentChatId == -1) return

        val builder = android.app.AlertDialog.Builder(this)
        builder.setTitle("Удалить чат")
        builder.setMessage("Вы уверены, что хотите удалить чат \"${binding.toolbar.title}\"? Это действие нельзя отменить.")

        builder.setPositiveButton("Удалить") { _, _ ->
            deleteChat()
        }
        builder.setNegativeButton("Отмена") { dialog, _ ->
            dialog.cancel()
        }

        builder.show()
    }

    private fun deleteChat() {
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val response = RetrofitClient.instance.deleteChat(token, currentChatId)
                withContext(Dispatchers.Main) {
                    if (response.isSuccessful) {
                        Toast.makeText(this@MainActivity, "Чат удалён", Toast.LENGTH_SHORT).show()
                        currentChatId = -1
                        binding.toolbar.title = "NeuroChat"
                        binding.btnChatMenu.visibility = View.GONE

                        val fragment = supportFragmentManager.findFragmentById(R.id.chatFragmentContainer) as? ChatFragment
                        fragment?.loadChat(-1, "NeuroChat")

                        refreshChatsList()
                    } else {
                        Toast.makeText(this@MainActivity, "Ошибка удаления чата", Toast.LENGTH_SHORT).show()
                    }
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@MainActivity, "Ошибка: ${e.message}", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun sendMessage() {
        val content = binding.etMessage.text.toString().trim()
        if (content.isEmpty()) {
            Toast.makeText(this, "Введите сообщение", Toast.LENGTH_SHORT).show()
            return
        }

        if (currentChatId == -1) {
            Toast.makeText(this, "Сначала выберите или создайте чат", Toast.LENGTH_SHORT).show()
            return
        }

        val fragment = supportFragmentManager.findFragmentById(R.id.chatFragmentContainer) as? ChatFragment
        fragment?.sendMessage(token, currentChatId, content)

        binding.etMessage.text.clear()
    }
}
