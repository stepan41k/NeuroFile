package com.example.neuro.ui.files

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.RecyclerView
import com.example.neuro.api.FileResponse
import com.example.neuro.databinding.ItemFileBinding

class FilesAdapter(private val files: List<FileResponse>) : RecyclerView.Adapter<FilesAdapter.FileViewHolder>() {

    class FileViewHolder(val binding: ItemFileBinding) : RecyclerView.ViewHolder(binding.root)

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): FileViewHolder {
        val binding = ItemFileBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return FileViewHolder(binding)
    }

    override fun onBindViewHolder(holder: FileViewHolder, position: Int) {
        val file = files[position]
        holder.binding.tvFileName.text = file.name
        holder.binding.tvFileInfo.text = "${file.type.uppercase()} • ${(file.size / 1024)} KB"
    }

    override fun getItemCount() = files.size
}
