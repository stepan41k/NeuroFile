package com.example.neuro.ui.files

import android.net.Uri
import android.os.Bundle
import android.provider.OpenableColumns
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import com.example.neuro.databinding.FragmentFilesBinding
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody

class FilesFragment : Fragment() {

    private var _binding: FragmentFilesBinding? = null
    private val binding get() = _binding!!
    private val viewModel: FilesViewModel by viewModels()

    private val filePickerLauncher = registerForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
        uri?.let { uploadFile(it) }
    }

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        _binding = FragmentFilesBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        binding.toolbarFiles.setNavigationOnClickListener {
            parentFragmentManager.popBackStack()
        }

        val prefs = requireContext().getSharedPreferences("neuro_prefs", AppCompatActivity.MODE_PRIVATE)
        val token = prefs.getString("auth_token", "") ?: ""

        viewModel.files.observe(viewLifecycleOwner) { files ->
            binding.rvFiles.adapter = FilesAdapter(files)
        }

        viewModel.isLoading.observe(viewLifecycleOwner) { isLoading ->
            binding.progressBar.visibility = if (isLoading) View.VISIBLE else View.GONE
        }

        viewModel.error.observe(viewLifecycleOwner) { error ->
            error?.let { Toast.makeText(requireContext(), it, Toast.LENGTH_LONG).show() }
        }

        binding.fabUpload.setOnClickListener {
            filePickerLauncher.launch("*/*")
        }

        viewModel.loadFiles(token)
    }

    private fun uploadFile(uri: Uri) {
        val contentResolver = requireContext().contentResolver
        val fileName = contentResolver.query(uri, null, null, null, null)?.use { cursor ->
            val nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
            cursor.moveToFirst()
            cursor.getString(nameIndex)
        } ?: "file"

        val fileBytes = contentResolver.openInputStream(uri)?.readBytes()
        if (fileBytes != null) {
            val requestFile = fileBytes.toRequestBody("application/octet-stream".toMediaTypeOrNull())
            val body = MultipartBody.Part.createFormData("file", fileName, requestFile)
            
            val prefs = requireContext().getSharedPreferences("neuro_prefs", AppCompatActivity.MODE_PRIVATE)
            val token = prefs.getString("auth_token", "") ?: ""
            viewModel.uploadFile(token, body)
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
