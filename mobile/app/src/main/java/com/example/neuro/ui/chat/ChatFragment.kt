package com.example.neuro.ui.chat

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.appcompat.app.AppCompatActivity
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import androidx.recyclerview.widget.LinearLayoutManager
import com.example.neuro.databinding.FragmentChatBinding

class ChatFragment : Fragment() {

    private var _binding: FragmentChatBinding? = null
    private val binding get() = _binding!!
    private val viewModel: ChatViewModel by viewModels()
    private val adapter = ChatAdapter()
    private var chatId: Int = -1

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        _binding = FragmentChatBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        val prefs = requireContext().getSharedPreferences("neuro_prefs", AppCompatActivity.MODE_PRIVATE)
        val token = prefs.getString("auth_token", "") ?: ""

        binding.rvMessages.layoutManager = LinearLayoutManager(requireContext())
        binding.rvMessages.adapter = adapter
        binding.rvMessages.itemAnimator = null

        viewModel.messages.observe(viewLifecycleOwner) { messages ->
            adapter.setMessages(messages)
            if (messages.isNotEmpty()) {
                binding.rvMessages.scrollToPosition(messages.size - 1)
            }
        }

        viewModel.isLoading.observe(viewLifecycleOwner) { isLoading ->
            adapter.setLoading(isLoading)
            if (isLoading) {
                binding.rvMessages.scrollToPosition(adapter.itemCount - 1)
            }
        }

        viewModel.error.observe(viewLifecycleOwner) { error ->
            error?.let {
                android.widget.Toast.makeText(requireContext(), it, android.widget.Toast.LENGTH_LONG).show()
            }
        }

        chatId = arguments?.getInt("CHAT_ID", -1) ?: -1
        if (chatId != -1) {
            viewModel.loadMessages(token, chatId)
        }
    }

    fun loadChat(id: Int, title: String) {
        chatId = id
        val prefs = requireContext().getSharedPreferences("neuro_prefs", AppCompatActivity.MODE_PRIVATE)
        val token = prefs.getString("auth_token", "") ?: ""
        viewModel.loadMessages(token, chatId)
    }

    fun sendMessage(token: String, chatId: Int, content: String) {
        viewModel.sendMessage(token, chatId, content)
    }

    fun getMessagesCount(): Int {
        return adapter.itemCount
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }

    companion object {
        fun newInstance(chatId: Int, title: String): ChatFragment {
            return ChatFragment().apply {
                arguments = Bundle().apply {
                    putInt("CHAT_ID", chatId)
                    putString("CHAT_TITLE", title)
                }
            }
        }
    }
}
