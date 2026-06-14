package com.rohan.assistant.gateway.ui

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.rohan.assistant.gateway.GatewayApp
import com.rohan.assistant.gateway.R
import com.rohan.assistant.gateway.databinding.ActivityMainBinding
import com.rohan.assistant.gateway.service.CallTracker
import com.rohan.assistant.gateway.service.GatewayForegroundService
import com.rohan.assistant.gateway.util.LanDiscovery
import com.rohan.assistant.gateway.util.Logger
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private var discoverJob: Job? = null

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) { granted ->
        Logger.i(TAG, "Permission result: $granted")
        if (granted.values.all { it }) startService()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        try {
            super.onCreate(savedInstanceState)
            binding = ActivityMainBinding.inflate(layoutInflater)
            setContentView(binding.root)

            val app = application as GatewayApp
            binding.urlInput.setText(app.settings.serverUrl)
            binding.autoAnswerSwitch.isChecked = app.settings.autoAnswerEnabled

            binding.startButton.setOnClickListener {
                val url = binding.urlInput.text?.toString().orEmpty().trim()
                if (url.isNotBlank()) app.settings.serverUrl = url
                requestPermissionsThenStart()
            }

            binding.stopButton.setOnClickListener { stopService() }
            binding.discoverButton.setOnClickListener { startDiscover() }

            binding.autoAnswerSwitch.setOnCheckedChangeListener { _, isChecked ->
                app.settings.autoAnswerEnabled = isChecked
                CallTracker.autoAnswerEnabled = isChecked
            }

            binding.accessibilityButton.setOnClickListener {
                openAccessibilitySettings()
            }
        } catch (t: Throwable) {
            Toast.makeText(this, "Error: ${t.message}", Toast.LENGTH_LONG).show()
        }
    }

    private fun openAccessibilitySettings() {
        val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
        startActivity(intent)
        Toast.makeText(this, "Enable 'Rohan Call Assistant' in Accessibility Services", Toast.LENGTH_LONG).show()
    }

    private fun startDiscover() {
        if (discoverJob?.isActive == true) return
        binding.statusText.text = getString(R.string.label_status, "discovering…")
        discoverJob = CoroutineScope(Dispatchers.IO).launch {
            try {
                val found = LanDiscovery.discover(prefer = (application as GatewayApp).settings.serverUrl)
                withContext(Dispatchers.Main) {
                    if (found != null) {
                        binding.urlInput.setText(found)
                        (application as GatewayApp).settings.serverUrl = found
                        binding.statusText.text = "Found: $found"
                    } else {
                        binding.statusText.text = "Not found. Make sure the laptop is on the same Wi-Fi."
                    }
                }
            } catch (t: Throwable) {
                withContext(Dispatchers.Main) {
                    binding.statusText.text = "Discover error: ${t.message}"
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        refreshStatus()
    }

    private fun refreshStatus() {
        val app = application as GatewayApp
        val running = app.settings.serviceRunning
        binding.startButton.isEnabled = !running
        binding.stopButton.isEnabled = running
        binding.statusText.text = getString(
            R.string.label_status,
            if (running) "running" else "stopped",
        )
    }

    private fun requestPermissionsThenStart() {
        val needed = mutableListOf<String>()
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.READ_PHONE_STATE)
            != PackageManager.PERMISSION_GRANTED
        ) needed.add(Manifest.permission.READ_PHONE_STATE)
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.READ_CONTACTS)
            != PackageManager.PERMISSION_GRANTED
        ) needed.add(Manifest.permission.READ_CONTACTS)
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.READ_CALL_LOG)
            != PackageManager.PERMISSION_GRANTED
        ) needed.add(Manifest.permission.READ_CALL_LOG)
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
            != PackageManager.PERMISSION_GRANTED && Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU
        ) needed.add(Manifest.permission.POST_NOTIFICATIONS)
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.ANSWER_PHONE_CALLS)
            != PackageManager.PERMISSION_GRANTED
        ) needed.add(Manifest.permission.ANSWER_PHONE_CALLS)
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) needed.add(Manifest.permission.RECORD_AUDIO)

        if (needed.isEmpty()) {
            startService()
        } else {
            permissionLauncher.launch(needed.toTypedArray())
        }
    }

    private fun startService() {
        val app = application as GatewayApp
        app.settings.serviceRunning = true
        GatewayForegroundService.start(this)
        refreshStatus()
    }

    private fun stopService() {
        val app = application as GatewayApp
        app.settings.serviceRunning = false
        GatewayForegroundService.stop(this)
        refreshStatus()
    }

    companion object {
        private const val TAG = "MainActivity"
    }
}
