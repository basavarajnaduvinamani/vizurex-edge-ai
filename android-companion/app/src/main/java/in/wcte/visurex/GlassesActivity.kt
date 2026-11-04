package `in`.wcte.visurex

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.media.AudioAttributes
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.util.Base64
import android.widget.*
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.lifecycle.lifecycleScope
import com.meta.wearable.dat.camera.Camera
import com.meta.wearable.dat.camera.addCamera
import com.meta.wearable.dat.camera.types.PhotoData
import com.meta.wearable.dat.camera.types.StreamConfiguration
import com.meta.wearable.dat.camera.types.StreamState
import com.meta.wearable.dat.camera.types.VideoQuality
import com.meta.wearable.dat.core.Wearables
import com.meta.wearable.dat.core.selectors.AutoDeviceSelector
import com.meta.wearable.dat.core.session.DeviceSession
import com.meta.wearable.dat.core.session.DeviceSessionState
import com.meta.wearable.dat.core.types.Permission
import com.meta.wearable.dat.core.types.PermissionStatus
import com.meta.wearable.dat.core.types.RegistrationState
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.File

/** Thin development bridge. No sensor data leaves the phone through this activity. */
class GlassesActivity : ComponentActivity() {
    private var camera: Camera? = null
    private var session: DeviceSession? = null
    private var streamState = StreamState.STOPPED
    private var sessionJob: Job? = null
    private var captureJob: Job? = null
    private var busy = false
    private var addingCamera = false
    private var active = false
    private var recognizer: SpeechRecognizer? = null
    private var tts: TextToSpeech? = null
    private var speechReady = false
    private val redactor = GlassesRedactor()
    private val offline by lazy { OfflineInspector(File(cacheDir, "glasses-model")) }
    private lateinit var status: TextView
    private lateinit var plant: EditText
    private lateinit var station: EditText
    private lateinit var note: EditText
    private lateinit var category: Spinner
    private var latest = ""
    private val export = registerForActivityResult(ActivityResultContracts.CreateDocument("application/json")) { uri ->
        if (uri != null && latest.isNotEmpty()) contentResolver.openOutputStream(uri)?.bufferedWriter()?.use { it.write(latest) }
    }
    private val modelPicker = registerForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri != null && !busy) lifecycleScope.launch {
            busy = true
            try {
                val name = withContext(Dispatchers.IO) { contentResolver.openInputStream(uri).use { offline.importBundle(requireNotNull(it)) } }
                status.text = "Imported $name. Select this category before Check."
            } catch (e: Exception) { status.text = "Import failed: ${e.message}" }
            finally { busy = false }
        }
    }
    private val bluetooth = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) register() else status.text = "Bluetooth denied. No glasses connection."
    }
    private val microphone = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) listen() else status.text = "Microphone denied. Use phone Note/Check buttons."
    }
    private val datPermission = registerForActivityResult(Wearables.RequestPermissionContract()) { result ->
        result.onSuccess { if (it == PermissionStatus.Granted) startStream() else status.text = "DAT camera denied." }
            .onFailure { error, _ -> status.text = "Camera permission: ${error.description}" }
    }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val layout = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(24,24,24,24) }
        setContentView(ScrollView(this).apply { addView(layout) })
        fun text(value: String) { layout.addView(TextView(this).apply { text = value }) }
        fun input(hint: String) = EditText(this).apply { this.hint = hint; contentDescription = hint; layout.addView(this) }
        fun button(title: String, action: () -> Unit) { layout.addView(Button(this).apply { text = title; setOnClickListener { action() } }) }
        text("Glasses bridge · In progress · DAT 1.0.1")
        text("Developer Mode only. Pair glasses in Meta AI first. Use phone controls or phone-side Note/Check voice. A glasses tap pauses streaming; it is not a trigger. No real-glasses validation yet.")
        plant = input("Plant ID (required)"); station = input("Station (required)"); note = input("Finding note")
        category = Spinner(this).apply { adapter = ArrayAdapter(this@GlassesActivity, android.R.layout.simple_spinner_dropdown_item, InspectionContract.categories) }; layout.addView(category)
        button("Connect via Meta AI") {
            if (checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED) register()
            else bluetooth.launch(Manifest.permission.BLUETOOTH_CONNECT)
        }
        button("Start glasses stream") {
            if (Wearables.registrationState.value != RegistrationState.REGISTERED) status.text = "Connect/register first."
            else datPermission.launch(Permission.CAMERA)
        }
        button("Import trusted portable model ZIP") { if (!busy) modelPicker.launch("application/zip") }
        button("Note · capture without model") { capture("note", false) }
        button("Check · local ONNX") { capture("check", false) }
        button("Listen once · phone microphone") {
            if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) listen()
            else microphone.launch(Manifest.permission.RECORD_AUDIO)
        }
        button("Export latest Finding + CaptureEvent JSON") { if (latest.isNotEmpty()) export.launch("visurex-glasses.json") }
        button("Stop session") { stopStream() }
        status = TextView(this).apply { text = "Not connected. No capture saved."; setTextIsSelectable(true) }; layout.addView(status)
        Wearables.initialize(this).onFailure { error, _ -> status.text = "SDK initialization: ${error.description}" }
        handleRegistrationIntent(intent)
        lifecycleScope.launch { Wearables.registrationState.collect { status.text = "Registration: $it. Start stream after REGISTERED." } }
        tts = TextToSpeech(this) { code ->
            if (code == TextToSpeech.SUCCESS) {
                val voice = tts?.voices?.firstOrNull { !it.isNetworkConnectionRequired && it.locale.language == "en" }
                speechReady = voice != null
                if (voice != null) tts?.voice = voice
                tts?.setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
            }
        }
    }
    private fun register() { try { Wearables.startRegistration(this) } catch (e: Exception) { status.text = "Registration unavailable: ${e.message}" } }
    private fun handleRegistrationIntent(incoming: Intent?) {
        if (incoming?.action != Intent.ACTION_VIEW || incoming.data?.scheme != "visurex") return
        Wearables.handleIntent(incoming) { request ->
            android.app.AlertDialog.Builder(this).setTitle("Connect VisureX to Meta AI?")
                .setMessage("Continue the registration you started. Camera access is requested separately.")
                .setPositiveButton("Continue") { _, _ -> request.continueRegistration(this) }
                .setNegativeButton("Cancel") { _, _ -> request.cancelRegistration() }.show()
        }.onFailure { error, _ -> status.text = "Registration callback: ${error.description}" }
    }
    override fun onNewIntent(intent: Intent) { super.onNewIntent(intent); setIntent(intent); handleRegistrationIntent(intent) }
    private fun startStream() {
        if (session != null) { status.text = "Session already exists. Stop before restarting."; return }
        Wearables.createSession(AutoDeviceSelector()).onSuccess { created ->
            session = created
            sessionJob = lifecycleScope.launch {
                launch { created.errors.collect { status.text = "Session error: ${it.description}" } }
                created.state.collect { state ->
                    status.text = "Session: $state"
                    if (state == DeviceSessionState.STARTED && camera == null && !addingCamera) {
                        addingCamera = true
                        created.addCamera(StreamConfiguration(videoQuality = VideoQuality.MEDIUM, frameRate = 2))
                            .onSuccess { added ->
                                camera = added
                                launch { added.stream.state.collect { streamState = it; status.text = "Stream: $it" } }
                                launch { added.stream.errorStream.collect { status.text = "Stream error: ${it.description}" } }
                                added.stream.start().onFailure { error, _ -> status.text = "Start failed: ${error.description}" }
                            }.onFailure { error, _ -> status.text = "Camera unavailable: ${error.description}" }
                        addingCamera = false
                    }
                    if (state != DeviceSessionState.STARTED) streamState = StreamState.STOPPED
                }
            }
            created.start()
        }.onFailure { error, _ -> status.text = "Session unavailable: ${error.description}" }
    }
    private fun capture(command: String, fromVoice: Boolean) {
        if (busy) { status.text = "Capture already in progress."; return }
        val current = camera ?: return run { status.text = "Start glasses stream first." }
        if (streamState != StreamState.STREAMING) { status.text = "Stream not active ($streamState). Resume before capture."; return }
        if (plant.text.isBlank() || station.text.isBlank()) { status.text = "Enter plant and station first."; return }
        val plantId = plant.text.toString(); val stationId = station.text.toString(); val memo = note.text.toString(); val chosen = category.selectedItem.toString()
        busy = true
        captureJob = lifecycleScope.launch {
            var raw: Bitmap? = null
            var sanitized: Bitmap? = null
            var temporary: File? = null
            try {
                current.stream.capturePhoto().onSuccess { photo ->
                    raw = when (photo) {
                        is PhotoData.Bitmap -> photo.bitmap
                        is PhotoData.HEIC -> { val buffer = photo.data.duplicate(); val bytes = ByteArray(buffer.remaining()); buffer.get(bytes); BitmapFactory.decodeByteArray(bytes,0,bytes.size) }
                    }
                }.onFailure { error, _ -> throw IllegalStateException(error.description) }
                val input = requireNotNull(raw) { "Frame cannot be decoded" }
                val (redacted, faces) = redactor.redact(input); sanitized = redacted
                val bytes = withContext(Dispatchers.Default) { ByteArrayOutputStream().use { require(redacted.compress(Bitmap.CompressFormat.JPEG,90,it)); it.toByteArray() } }
                temporary = File.createTempFile("redacted-", ".jpg", cacheDir).apply { writeBytes(bytes) }
                val result = if (command == "check") withContext(Dispatchers.Default) { offline.inspect(requireNotNull(temporary), chosen) } else null
                val photo = JSONObject().put("dataUrl", "data:image/jpeg;base64," + Base64.encodeToString(bytes,Base64.NO_WRAP))
                    .put("redacted", true).put("faceBoxes", faces).put("method", "mlkit-16.1.7-pixelation").put("metadataStripped", true)
                val records = GlassesRecords.create(plantId,stationId,memo,fromVoice,photo,result?.decision,result?.score?.toDouble(),result?.manifest?.sha256,false)
                latest = JSONObject().put("captureEvent",records.first).put("finding",records.second).toString(2)
                withContext(Dispatchers.IO) {
                    val dir = File(filesDir,"glasses-records").apply { mkdirs() }
                    File(dir,records.first.getString("id") + ".json").writeText(records.first.toString(2))
                    File(dir,records.second.getString("id") + ".json").writeText(records.second.toString(2))
                }
                val verdict = result?.decision ?: "Note saved"
                val elapsed = result?.elapsedMs
                result?.crop?.recycle()
                status.text = "$verdict. Local draft saved; suggested fields need human review. ONNX ms: ${elapsed ?: "not run"}. Glasses audio routing must be checked."
                if (speechReady) tts?.speak("$verdict. Please review.",TextToSpeech.QUEUE_FLUSH,null,records.first.getString("id"))
            } catch (e: Exception) { if (active) status.text = "RETAKE / unavailable: ${e.message}. No new record or verdict saved." }
            finally { temporary?.delete(); sanitized?.recycle(); raw?.recycle(); busy = false }
        }
    }
    private fun listen() {
        if (!SpeechRecognizer.isOnDeviceRecognitionAvailable(this)) { status.text = "Offline recognition unavailable. Use phone buttons; no cloud ASR fallback."; return }
        recognizer?.destroy()
        recognizer = SpeechRecognizer.createOnDeviceSpeechRecognizer(this).apply {
            setRecognitionListener(object : RecognitionListener {
                override fun onResults(results: Bundle?) {
                    val text = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty()
                    val command = GlassesRecords.keyword(text)
                    if (command == null) status.text = "No Note/Check keyword. No capture." else {
                        note.setText(text.trim().substringAfter(' ', "")); capture(command,true)
                    }
                }
                override fun onError(error: Int) { status.text = "Voice unavailable ($error). Use phone buttons." }
                override fun onReadyForSpeech(params: Bundle?) { status.text = "Say Note or Check, then optional note. Phone-side recognition." }
                override fun onBeginningOfSpeech() {}
                override fun onRmsChanged(rmsdB: Float) {}
                override fun onBufferReceived(buffer: ByteArray?) {}
                override fun onEndOfSpeech() {}
                override fun onPartialResults(partialResults: Bundle?) {}
                override fun onEvent(eventType: Int, params: Bundle?) {}
            })
            startListening(Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,RecognizerIntent.LANGUAGE_MODEL_FREE_FORM).putExtra(RecognizerIntent.EXTRA_LANGUAGE,"en-IN").putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE,true))
        }
    }
    private fun stopStream() {
        captureJob?.cancel(); sessionJob?.cancel(); recognizer?.cancel(); camera?.stop(); session?.stop()
        camera = null; session = null; streamState = StreamState.STOPPED; addingCamera = false
        if (::status.isInitialized) status.text = "Session stopped. Start again explicitly."
    }
    override fun onStart() { super.onStart(); active = true }
    override fun onStop() { active = false; stopStream(); super.onStop() }
    override fun onDestroy() { recognizer?.destroy(); tts?.shutdown(); redactor.close(); offline.close(); super.onDestroy() }
}
