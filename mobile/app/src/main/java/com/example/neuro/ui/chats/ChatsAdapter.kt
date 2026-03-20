package com.example.neuro.ui.chats

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.RecyclerView
import com.example.neuro.api.ChatListItem
import com.example.neuro.databinding.ItemChatBinding

class ChatsAdapter(
    private val chats: List<ChatListItem>,
    private val onChatClick: (ChatListItem) -> Unit
) : RecyclerView.Adapter<ChatsAdapter.ChatViewHolder>() {

    class ChatViewHolder(val binding: ItemChatBinding) : RecyclerView.ViewHolder(binding.root)

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ChatViewHolder {
        val binding = ItemChatBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return ChatViewHolder(binding)
    }

    override fun onBindViewHolder(holder: ChatViewHolder, position: Int) {
        val chat = chats[position]
        holder.binding.tvChatTitle.text = chat.title
        holder.binding.tvLastActivity.text = chat.lastActivity
        holder.itemView.setOnClickListener { onChatClick(chat) }
    }

    override fun getItemCount() = chats.size
}
