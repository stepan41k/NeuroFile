package com.example.neuro.ui.chat

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.RecyclerView
import com.example.neuro.api.ChatListItem
import com.example.neuro.databinding.ItemChatBinding
import java.text.SimpleDateFormat
import java.util.*

class ChatsDrawerAdapter(
    private val chats: List<ChatListItem>,
    private val onChatClick: (ChatListItem) -> Unit
) : RecyclerView.Adapter<ChatsDrawerAdapter.ChatViewHolder>() {

    class ChatViewHolder(val binding: ItemChatBinding) : RecyclerView.ViewHolder(binding.root)

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ChatViewHolder {
        val binding = ItemChatBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return ChatViewHolder(binding)
    }

    override fun onBindViewHolder(holder: ChatViewHolder, position: Int) {
        val chat = chats[position]
        holder.binding.tvChatTitle.text = chat.title
        holder.binding.tvLastActivity.text = formatChatDate(chat.lastActivity)
        holder.itemView.setOnClickListener { onChatClick(chat) }
    }

    override fun getItemCount() = chats.size

    private fun formatChatDate(isoDate: String?): String {
        if (isoDate == null || isoDate.isEmpty()) {
            return ""
        }
        
        return try {
            val sdf = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS", Locale.US)
            sdf.timeZone = TimeZone.getTimeZone("UTC")
            val date = sdf.parse(isoDate)

            if (date == null) {
                isoDate.take(10)
            } else {
                val now = Calendar.getInstance()
                val chatCal = Calendar.getInstance().apply { time = date }

                val isToday = now.get(Calendar.DAY_OF_YEAR) == chatCal.get(Calendar.DAY_OF_YEAR) &&
                        now.get(Calendar.YEAR) == chatCal.get(Calendar.YEAR)

                val yesterday = Calendar.getInstance().apply { add(Calendar.DAY_OF_YEAR, -1) }
                val isYesterday = now.get(Calendar.DAY_OF_YEAR) - 1 == chatCal.get(Calendar.DAY_OF_YEAR)

                when {
                    isToday -> {
                        val timeSdf = SimpleDateFormat("HH:mm", Locale.getDefault())
                        timeSdf.format(date)
                    }
                    isYesterday -> "Yesterday"
                    else -> {
                        val dateSdf = SimpleDateFormat("dd.MM", Locale.getDefault())
                        dateSdf.format(date)
                    }
                }
            }
        } catch (e: Exception) {
            isoDate.take(10)
        }
    }
}
