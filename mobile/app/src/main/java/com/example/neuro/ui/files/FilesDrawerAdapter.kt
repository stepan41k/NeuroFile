package com.example.neuro.ui.files

import android.app.AlertDialog
import android.view.LayoutInflater
import android.view.ViewGroup
import android.widget.EditText
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.RecyclerView
import com.example.neuro.api.FileResponse
import com.example.neuro.api.RetrofitClient
import com.example.neuro.databinding.ItemFileBinding
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.RequestBody.Companion.toRequestBody

class FilesDrawerAdapter(
    val files: List<FileResponse>,
    private val onRefresh: () -> Unit
) : RecyclerView.Adapter<FilesDrawerAdapter.FileViewHolder>() {

    class FileViewHolder(val binding: ItemFileBinding) : RecyclerView.ViewHolder(binding.root)

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): FileViewHolder {
        val binding = ItemFileBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return FileViewHolder(binding)
    }

    override fun onBindViewHolder(holder: FileViewHolder, position: Int) {
        val file = files[position]
        holder.binding.tvFileName.text = file.name
        holder.binding.tvFileInfo.text = "${file.type.uppercase()} • ${(file.size / 1024)} KB"

        // Обработка долгого нажатия для переименования
        holder.itemView.setOnLongClickListener {
            showRenameDialog(holder.itemView.context, file)
            true
        }

        // Обработка обычного нажатия для меню действий
        holder.itemView.setOnClickListener {
            showActionsDialog(holder.itemView.context, file)
        }
    }

    private fun showRenameDialog(context: android.content.Context, file: FileResponse) {
        val builder = AlertDialog.Builder(context)
        builder.setTitle("Переименовать файл")

        val input = EditText(context)
        input.hint = "Новое название"
        input.setText(file.name)
        builder.setView(input)

        builder.setPositiveButton("Сохранить") { _, _ ->
            val newName = input.text.toString().trim()
            if (newName.isNotEmpty() && newName != file.name) {
                renameFile(context, file.id, newName)
            }
        }
        builder.setNegativeButton("Отмена") { dialog, _ ->
            dialog.cancel()
        }

        builder.show()
    }

    private fun renameFile(context: android.content.Context, fileId: Int, newName: String) {
        val activity = context as? AppCompatActivity ?: return
        val prefs = activity.getSharedPreferences("neuro_prefs", AppCompatActivity.MODE_PRIVATE)
        val token = prefs.getString("auth_token", "") ?: ""

        CoroutineScope(Dispatchers.IO).launch {
            try {
                val response = RetrofitClient.instance.updateFile(
                    token,
                    fileId,
                    mapOf("name" to newName)
                )
                withContext(Dispatchers.Main) {
                    if (response.isSuccessful) {
                        Toast.makeText(context, "Файл переименован", Toast.LENGTH_SHORT).show()
                        onRefresh()
                    } else {
                        Toast.makeText(context, "Ошибка переименования", Toast.LENGTH_SHORT).show()
                    }
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    Toast.makeText(context, "Ошибка: ${e.message}", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun showActionsDialog(context: android.content.Context, file: FileResponse) {
        val items = arrayOf("Переименовать", "Удалить")
        AlertDialog.Builder(context)
            .setTitle(file.name)
            .setItems(items) { _, which ->
                when (which) {
                    0 -> showRenameDialog(context, file)
                    1 -> showDeleteDialog(context, file)
                }
            }
            .show()
    }

    private fun showDeleteDialog(context: android.content.Context, file: FileResponse) {
        AlertDialog.Builder(context)
            .setTitle("Удалить файл")
            .setMessage("Вы уверены, что хотите удалить \"${file.name}\"?")
            .setPositiveButton("Удалить") { _, _ ->
                deleteFile(context, file.id)
            }
            .setNegativeButton("Отмена") { dialog, _ ->
                dialog.cancel()
            }
            .show()
    }

    private fun deleteFile(context: android.content.Context, fileId: Int) {
        val activity = context as? AppCompatActivity ?: return
        val prefs = activity.getSharedPreferences("neuro_prefs", AppCompatActivity.MODE_PRIVATE)
        val token = prefs.getString("auth_token", "") ?: ""

        CoroutineScope(Dispatchers.IO).launch {
            try {
                val response = RetrofitClient.instance.deleteFile(token, fileId)
                withContext(Dispatchers.Main) {
                    if (response.isSuccessful) {
                        Toast.makeText(context, "Файл удалён", Toast.LENGTH_SHORT).show()
                        onRefresh()
                    } else {
                        Toast.makeText(context, "Ошибка удаления", Toast.LENGTH_SHORT).show()
                    }
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    Toast.makeText(context, "Ошибка: ${e.message}", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    override fun getItemCount() = files.size
}
