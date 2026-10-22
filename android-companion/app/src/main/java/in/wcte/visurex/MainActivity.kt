package `in`.wcte.visurex

import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Bundle
import android.os.SystemClock
import android.speech.tts.TextToSpeech
import android.text.InputType
import android.util.Base64
import android.view.View
import android.widget.*
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.FileProvider
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File
import java.io.IOException
import java.util.Locale
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

class MainActivity : ComponentActivity() {
    private lateinit var url: EditText
    private lateinit var accessKey: EditText
    private lateinit var executionMode: Spinner
    private lateinit var importModel: Button
    private val offline by lazy { OfflineInspector(File(cacheDir, "portable-models")) }
    private lateinit var category: Spinner
    private lateinit var qualityMode: Spinner
    private lateinit var status: TextView
    private lateinit var preview: ImageView
    private lateinit var processed: ImageView
    private lateinit var overlay: ImageView
    private lateinit var capture: Button
    private lateinit var gallery: Button
    private lateinit var inspect: Button
    private var selected: File? = null
    private var pending: File? = null
    private var busy = false
    @Volatile private var destroyed = false
    private var tts: TextToSpeech? = null
    private var speechReady = false
    @Volatile private var currentCall: Call? = null
    private val executor = Executors.newSingleThreadExecutor()
    private val client = OkHttpClient.Builder().connectTimeout(10, TimeUnit.SECONDS).readTimeout(180, TimeUnit.SECONDS).callTimeout(200, TimeUnit.SECONDS).retryOnConnectionFailure(false).build()
    private val cameraResult = registerForActivityResult(ActivityResultContracts.TakePicture()) { ok ->
        val file = pending; pending = null
        if (ok && file != null) choose(file) else { file?.delete(); status.text = "Capture cancelled. No inspection performed." }
    }
    private val picker = registerForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri != null && !busy) importImage(uri)
    }
    private val modelPicker = registerForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri != null && !busy) {
            setBusy(true); clearResult("Loading trusted model archive. This may take a moment…")
            executor.execute {
                try {
                    val name = contentResolver.openInputStream(uri).use { input -> requireNotNull(input); offline.importBundle(input) }
                    runOnUiThread { if (!destroyed) { clearResult("Imported $name model. On-device mode is experimental and unvalidated on this device."); setBusy(false) } }
                } catch (error: Exception) { runOnUiThread { if (!destroyed) { clearResult("Model import failed: ${error.message}"); setBusy(false) } } }
            }
        }
    }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Requests are intentionally not retained through activity recreation; never attach an old result to a new image.
        val scroll = ScrollView(this)
        val layout = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(32, 32, 32, 32) }
        scroll.addView(layout); setContentView(scroll)
        fun label(text: String) { layout.addView(TextView(this).apply { this.text = text; textSize = 18f; setPadding(0, 12, 0, 8) }) }
        label("VisureX Companion · Research prototype")
        label("Phone camera only. No glasses connection. Use the model matching the product; scores are not confidence probabilities.")
        label("Processing location")
        executionMode = Spinner(this).apply { adapter = ArrayAdapter(this@MainActivity, android.R.layout.simple_spinner_dropdown_item, listOf("Laptop backend", "Experimental on-device CPU")) }
        layout.addView(executionMode)
        label("Backend base URL (trusted local network only)")
        url = EditText(this).apply { inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI; setText(getPreferences(MODE_PRIVATE).getString("backend", "http://127.0.0.1:8000")); contentDescription = "Backend base URL" }
        layout.addView(url)
        label("Wi-Fi session key (leave blank for local USB)")
        accessKey = EditText(this).apply { inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD; contentDescription = "Wi-Fi session access key"; isSaveEnabled = false; importantForAutofill = View.IMPORTANT_FOR_AUTOFILL_NO }
        layout.addView(accessKey)
        label("Product category")
        category = Spinner(this).apply { adapter = ArrayAdapter(this@MainActivity, android.R.layout.simple_spinner_dropdown_item, InspectionContract.categories) }
        layout.addView(category)
        label("Capture mode")
        qualityMode = Spinner(this).apply { adapter = ArrayAdapter(this@MainActivity, android.R.layout.simple_spinner_dropdown_item, listOf("benchmark", "quality_gated")) }
        layout.addView(qualityMode)
        fun button(title: String): Button = Button(this).apply { text = title; layout.addView(this) }
        importModel = button("Import trusted portable model ZIP")
        capture = button("Capture image")
        gallery = button("Choose PNG or JPEG")
        label("Original image")
        fun image(description: String): ImageView = ImageView(this).apply { adjustViewBounds = true; contentDescription = description; layout.addView(this, LinearLayout.LayoutParams(-1, 440)) }
        preview = image("Original uploaded image")
        inspect = button("Run inspection")
        status = TextView(this).apply { text = "Select an image to begin."; setTextIsSelectable(true); textSize = 16f }; layout.addView(status)
        label("Processed centre crop"); processed = image("Processed centre crop")
        label("Heatmap overlay on centre crop"); overlay = image("Anomaly heatmap overlay")
        category.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) { clearResult("Category selected. Run a new inspection.") }
            override fun onNothingSelected(parent: AdapterView<*>?) {}
        }
        qualityMode.onItemSelectedListener = category.onItemSelectedListener
        executionMode.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                qualityMode.setSelection(0)
                clearResult(if (position == 1) "Experimental on-device mode: import the correct model ZIP. No network request will be sent. Capture checks and smoothed heatmaps are backend-only." else "Laptop backend selected. Run a new inspection.")
                setBusy(false)
            }
            override fun onNothingSelected(parent: AdapterView<*>?) {}
        }
        importModel.setOnClickListener { if (!busy) modelPicker.launch("application/zip") }
        capture.setOnClickListener {
            if (!busy) try {
                val file = File.createTempFile("capture-", ".jpg", captureDir()); pending = file
                cameraResult.launch(FileProvider.getUriForFile(this, "$packageName.files", file))
            } catch (e: Exception) { pending?.delete(); pending = null; status.text = "Camera unavailable. Choose a gallery image instead." }
        }
        gallery.setOnClickListener { if (!busy) picker.launch("image/*") }
        inspect.setOnClickListener { runInspection() }
        tts = TextToSpeech(this) { code ->
            if (!destroyed && code == TextToSpeech.SUCCESS) {
                val engine = tts
                val voice = engine?.voices?.firstOrNull { !it.isNetworkConnectionRequired && it.locale.language == "en" }
                speechReady = voice != null
                if (voice != null) engine.voice = voice
                if (!speechReady) status.append("\nOffline English speech unavailable; visual results still work.")
            }
        }
        if (savedInstanceState != null) status.text = "Activity restarted. Select an image again; any previous request was cancelled."
        savedInstanceState?.getString("pendingCapture")?.let { name -> File(captureDir(), name).takeIf { it.exists() && it.name == name }?.let { pending = it } }
        setBusy(false)
    }
    private fun captureDir() = File(cacheDir, "captures").apply { mkdirs() }
    private fun clearResult(message: String) { if (::processed.isInitialized) processed.setImageDrawable(null); if (::overlay.isInitialized) overlay.setImageDrawable(null); if (::status.isInitialized) status.text = message; tts?.stop() }
    private fun setBusy(value: Boolean) {
        busy = value
        val local = executionMode.selectedItemPosition == 1
        capture.isEnabled = !value; gallery.isEnabled = !value; category.isEnabled = !value
        executionMode.isEnabled = !value; importModel.isEnabled = !value && local
        qualityMode.isEnabled = !value && !local; url.isEnabled = !value && !local; accessKey.isEnabled = !value && !local
        inspect.isEnabled = !value && selected != null
    }
    private fun choose(file: File) {
        try { validateImage(file) } catch (e: Exception) { file.delete(); selected?.delete(); selected = null; preview.setImageDrawable(null); clearResult("Invalid capture: ${e.message}. Select a new image."); setBusy(false); return }
        selected?.takeIf { it != file }?.delete(); selected = file
        val options = BitmapFactory.Options().apply { inSampleSize = 4 }
        preview.setImageBitmap(BitmapFactory.decodeFile(file.path, options)); clearResult("Image selected. Ready to inspect."); setBusy(false)
    }
    private fun importImage(uri: Uri) {
        setBusy(true); clearResult("Reading image…")
        executor.execute {
            val file = File.createTempFile("selected-", ".img", captureDir())
            try {
                contentResolver.openInputStream(uri).use { input ->
                    require(input != null) { "Cannot read selected image" }
                    file.outputStream().use { output ->
                        val buffer = ByteArray(8192); var total = 0
                        while (true) { val n = input.read(buffer); if (n < 0) break; total += n; require(total <= 10 * 1024 * 1024) { "Image exceeds 10 MiB" }; output.write(buffer, 0, n) }
                    }
                }
                validateImage(file)
                runOnUiThread { if (!destroyed) choose(file) else file.delete() }
            } catch (e: Exception) { file.delete(); runOnUiThread { if (!destroyed) { status.text = e.message ?: "Unable to read image"; setBusy(false) } } }
        }
    }
    private fun validateImage(file: File): String {
        require(file.length() in 1..10L * 1024 * 1024) { "Use an image no larger than 10 MiB" }
        val options = BitmapFactory.Options().apply { inJustDecodeBounds = true }; BitmapFactory.decodeFile(file.path, options)
        require(options.outMimeType in listOf("image/jpeg", "image/png")) { "Only PNG and JPEG are supported" }
        require(options.outWidth > 0 && options.outHeight > 0 && options.outWidth.toLong() * options.outHeight <= 16_000_000) { "Use an image at most 16 megapixels" }
        return options.outMimeType!!
    }
    private fun runInspection() {
        if (busy) return
        val file = selected ?: return
        if (executionMode.selectedItemPosition == 1) { runOffline(file); return }
        val endpoint: String
        try { endpoint = InspectionContract.endpoint(url.text.toString(), BuildConfig.DEBUG) } catch (e: Exception) { status.text = e.message; return }
        val chosen = category.selectedItem.toString()
        val mode = qualityMode.selectedItem.toString()
        val sessionKey = accessKey.text.toString().trim()
        getPreferences(MODE_PRIVATE).edit().putString("backend", url.text.toString()).apply()
        setBusy(true); clearResult("Inspecting… First request may load the model.")
        val start = SystemClock.elapsedRealtime()
        executor.execute {
            try {
                val mime = validateImage(file)
                val body = MultipartBody.Builder().setType(MultipartBody.FORM).addFormDataPart("category", chosen)
                    .addFormDataPart("quality_mode", mode)
                    .addFormDataPart("image", if (mime == "image/png") "capture.png" else "capture.jpg", file.readBytes().toRequestBody(mime.toMediaType())).build()
                val request = Request.Builder().url(endpoint).post(body)
                if (sessionKey.isNotEmpty()) request.header("X-Visurex-Key", sessionKey)
                val call = client.newCall(request.build()); currentCall = call
                call.execute().use { response ->
                    val raw = response.body?.string() ?: throw IOException("Empty server response")
                    if (!response.isSuccessful) {
                        val detail = try { org.json.JSONObject(raw).opt("detail")?.toString()?.take(500) ?: "Request failed" } catch (_: Exception) { "Check backend, image and model artifacts." }
                        throw IOException("Inspection unavailable (HTTP ${response.code}): $detail")
                    }
                    val result = InspectionContract.parse(raw, chosen)
                    val elapsed = SystemClock.elapsedRealtime() - start
                    runOnUiThread {
                        if (!destroyed) {
                            status.text = "${result.decision}\nCategory: ${result.category}\nScore: ${result.score ?: "not computed"}\nThreshold: ${result.threshold ?: "not computed"}\nModel: ${result.version}\nInspection: ${result.id}\nInference: ${result.inferenceMs ?: "not run"} ms\nServer: ${result.serverMs} ms\nClient round trip: $elapsed ms\n${result.warnings.joinToString("\n")}"
                            showDataImage(result.processed, processed); showDataImage(result.overlay, overlay)
                            if (speechReady) tts?.speak(result.spoken(), TextToSpeech.QUEUE_FLUSH, null, result.id)
                            setBusy(false)
                        }
                    }
                }
            } catch (e: Exception) {
                runOnUiThread { if (!destroyed) { clearResult("UNAVAILABLE: ${e.message}\nNo inspection verdict. Check USB connection, adb reverse, URL and backend; retry manually."); setBusy(false) } }
            } finally { currentCall = null }
        }
    }
    private fun runOffline(file: File) {
        val chosen = category.selectedItem.toString()
        setBusy(true); clearResult("Running experimental on-device CPU inference…")
        executor.execute {
            try {
                validateImage(file)
                val result = offline.inspect(file, chosen)
                runOnUiThread {
                    if (!destroyed) {
                        processed.setImageBitmap(result.crop)
                        status.text = "EXPERIMENTAL ON-DEVICE: ${result.decision}\nCategory: $chosen\nScore: ${result.score}\nThreshold: ${result.manifest.threshold}\nLocal processing: ${result.elapsedMs} ms\nModel: ${result.manifest.sha256.take(12)}\nNo network request. Not factory-validated. Android resizing can differ from reference preprocessing. No capture gate or smoothed heatmap in this mode."
                        if (speechReady) tts?.speak(if (result.decision == "ANOMALY") "Potential anomaly. Experimental local model; please review." else "No anomaly detected by the experimental local model. Not a safety guarantee.", TextToSpeech.QUEUE_FLUSH, null, "offline")
                        setBusy(false)
                    } else result.crop.recycle()
                }
            } catch (error: Exception) { runOnUiThread { if (!destroyed) { clearResult("UNAVAILABLE: ${error.message}. No offline verdict."); setBusy(false) } } }
        }
    }
    private fun showDataImage(value: String?, target: ImageView) {
        if (value == null) { target.setImageDrawable(null); return }
        try { val bytes = Base64.decode(value.substringAfter(','), Base64.DEFAULT); target.setImageBitmap(BitmapFactory.decodeByteArray(bytes, 0, bytes.size)) }
        catch (_: Exception) { target.setImageDrawable(null); status.append("\nImage overlay could not be displayed.") }
    }
    override fun onDestroy() {
        destroyed = true; currentCall?.cancel(); executor.execute { offline.close() }; executor.shutdown(); tts?.stop(); tts?.shutdown()
        selected?.delete(); if (!isChangingConfigurations) pending?.delete()
        super.onDestroy()
    }
    override fun onSaveInstanceState(outState: Bundle) { pending?.let { outState.putString("pendingCapture", it.name) }; super.onSaveInstanceState(outState) }
}
