package com.example.neuro.ui.chat

import android.animation.ObjectAnimator
import android.text.SpannableStringBuilder
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.view.animation.AccelerateDecelerateInterpolator
import androidx.core.text.HtmlCompat
import androidx.recyclerview.widget.RecyclerView
import com.example.neuro.R
import com.example.neuro.api.ChatMessage
import com.example.neuro.databinding.ItemMessageBinding

class ChatAdapter : RecyclerView.Adapter<ChatAdapter.MessageViewHolder>() {

    private var messages: List<ChatMessage> = emptyList()
    private var isLoading = false

    fun setMessages(newMessages: List<ChatMessage>) {
        messages = newMessages
        isLoading = false
        notifyDataSetChanged()
    }

    fun setLoading(loading: Boolean) {
        isLoading = loading
        if (loading) {
            notifyItemInserted(messages.size)
        } else {
            notifyItemRemoved(messages.size)
        }
    }

    override fun getItemViewType(position: Int): Int {
        return if (position == messages.size && isLoading) {
            VIEW_TYPE_LOADING
        } else {
            messages[position].role.hashCode()
        }
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): MessageViewHolder {
        val binding = ItemMessageBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return MessageViewHolder(binding, viewType)
    }

    override fun onBindViewHolder(holder: MessageViewHolder, position: Int) {
        if (holder.viewType == VIEW_TYPE_LOADING) {
            holder.bindLoading()
        } else {
            val message = messages[position]
            holder.bind(message)
        }
    }

    override fun getItemCount() = messages.size + if (isLoading) 1 else 0

    class MessageViewHolder(
        val binding: ItemMessageBinding,
        val viewType: Int
    ) : RecyclerView.ViewHolder(binding.root) {

        fun bind(message: ChatMessage) {
            if (message.role == "user") {
                binding.userMessageContainer.visibility = View.VISIBLE
                binding.aiMessageContainer.visibility = View.GONE
                binding.loadingContainer.visibility = View.GONE
                binding.tvUserMessageContent.text = formatMessageText(message.content)
            } else {
                binding.userMessageContainer.visibility = View.GONE
                binding.aiMessageContainer.visibility = View.VISIBLE
                binding.loadingContainer.visibility = View.GONE
                binding.tvAiMessageContent.text = formatMessageText(message.content)

                if (!message.filesUsed.isNullOrEmpty()) {
                    binding.tvFilesUsed.text = "Files: ${message.filesUsed.joinToString(", ")}"
                    binding.tvFilesUsed.visibility = View.VISIBLE
                } else {
                    binding.tvFilesUsed.visibility = View.GONE
                }
            }
        }

        fun bindLoading() {
            binding.userMessageContainer.visibility = View.GONE
            binding.aiMessageContainer.visibility = View.GONE
            binding.loadingContainer.visibility = View.VISIBLE

            // Анимация точек
            val dots = listOf(binding.dot1, binding.dot2, binding.dot3)
            dots.forEachIndexed { index, dot ->
                val scaleAnimator = ObjectAnimator.ofFloat(dot, "scaleX", 0f, 1f, 0f)
                scaleAnimator.duration = 600
                scaleAnimator.repeatCount = ObjectAnimator.INFINITE
                scaleAnimator.startDelay = index * 160L
                scaleAnimator.interpolator = AccelerateDecelerateInterpolator()
                scaleAnimator.start()

                val alphaAnimator = ObjectAnimator.ofFloat(dot, "alpha", 0.5f, 1f, 0.5f)
                alphaAnimator.duration = 600
                alphaAnimator.repeatCount = ObjectAnimator.INFINITE
                alphaAnimator.startDelay = index * 160L
                alphaAnimator.interpolator = AccelerateDecelerateInterpolator()
                alphaAnimator.start()
            }
        }

        private fun formatMessageText(text: String): CharSequence {
            var processedText = text

            // Remove internal reasoning tags
            processedText = Regex("<think>[\\s\\S]*?</think>").replace(processedText, "")

            // Заменяем табуляцию на пробелы
            processedText = processedText.replace("\t", "    ")

            // Обрабатываем блоки кода
            val codeBlockPattern = Regex("```([\\s\\S]*?)```")
            processedText = codeBlockPattern.replace(processedText) { match ->
                val code = match.groupValues[1].trim()
                "\n⌨️ $code\n"
            }

            // Заменяем **text** на жирный
            processedText = processedText.replace(Regex("\\*\\*(.+?)\\*\\*"), "<b>$1</b>")

            // Заменяем *text* на курсив
            processedText = processedText.replace(Regex("\\*(.+?)\\*"), "<i>$1</i>")

            // Заменяем `code` на моноширинный
            processedText = processedText.replace(Regex("`(.*?)`"), "<tt>$1</tt>")

            // Заменяем - item на списки
            processedText = processedText.replace(Regex("^\\s*-\\s+(.+)$", RegexOption.MULTILINE)) {
                "<br>• $1"
            }

            // Заменяем \n на <br>
            processedText = processedText.replace("\n", "<br>")

            return HtmlCompat.fromHtml(processedText, HtmlCompat.FROM_HTML_MODE_LEGACY)
        }
    }

    companion object {
        private const val VIEW_TYPE_LOADING = -1
    }
}
