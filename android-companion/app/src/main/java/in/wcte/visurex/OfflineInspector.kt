package `in`.wcte.visurex

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import ai.onnxruntime.TensorInfo
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import androidx.exifinterface.media.ExifInterface
import java.io.File
import java.io.InputStream
import java.nio.FloatBuffer
import java.nio.file.Files
import java.security.MessageDigest
import java.util.zip.ZipInputStream

data class OfflineResult(val score: Float, val manifest: PortableManifest, val crop: Bitmap, val elapsedMs: Double) {
    val decision: String get() = if (score >= manifest.threshold) "ANOMALY" else "GOOD"
}

/** Experimental CPU path. Imported bundles must come from the trusted project export. */
class OfflineInspector(private val root: File) : AutoCloseable {
    private val environment by lazy { OrtEnvironment.getEnvironment().apply { setTelemetry(false) } }
    private var session: OrtSession? = null
    private var directory: File? = null
    private var manifest: PortableManifest? = null

    @Synchronized fun importBundle(input: InputStream): String {
        root.mkdirs()
        val temporary = Files.createTempDirectory(root.toPath(), "model-").toFile()
        try {
            val names = mutableSetOf<String>()
            ZipInputStream(input).use { zip ->
                while (true) {
                    val entry = zip.nextEntry ?: break
                    require(entry.name in listOf("detector.onnx", "manifest.json") && names.add(entry.name) && !entry.isDirectory) { "Unexpected or repeated archive entry" }
                    val limit = if (entry.name == "manifest.json") 1024L * 1024 else 200L * 1024 * 1024
                    File(temporary, entry.name).outputStream().use { output ->
                        val buffer = ByteArray(65536); var total = 0L
                        while (true) { val size = zip.read(buffer); if (size < 0) break; total += size; require(total <= limit) { "Model archive exceeds size limit" }; output.write(buffer, 0, size) }
                    }
                    zip.closeEntry()
                }
            }
            require(names == setOf("detector.onnx", "manifest.json")) { "Incomplete model archive" }
            val metadata = PortableManifest.parse(File(temporary, "manifest.json").readText())
            val model = File(temporary, "detector.onnx")
            require(model.length() == metadata.bytes) { "Model size mismatch" }
            val digest = MessageDigest.getInstance("SHA-256")
            model.inputStream().use { source -> val buffer = ByteArray(65536); while (true) { val size = source.read(buffer); if (size < 0) break; digest.update(buffer, 0, size) } }
            val actual = digest.digest().joinToString("") { "%02x".format(it.toInt() and 255) }
            require(actual == metadata.sha256) { "Model checksum mismatch" }
            val loaded = OrtSession.SessionOptions().use { options ->
                options.setIntraOpNumThreads(2)
                environment.createSession(model.path, options)
            }
            try {
                val info = loaded.inputInfo["normalised_rgb"]?.info as? TensorInfo
                require(info?.shape?.contentEquals(longArrayOf(1, 3, 224, 224)) == true) { "Unexpected model input" }
                require(loaded.outputNames.containsAll(listOf("anomaly_score", "patch_distances"))) { "Unexpected model output" }
            } catch (error: Exception) { loaded.close(); throw error }
            session?.close(); directory?.deleteRecursively()
            session = loaded; manifest = metadata; directory = temporary
            return metadata.category
        } catch (error: Exception) { temporary.deleteRecursively(); throw error }
    }

    @Synchronized fun inspect(file: File, category: String): OfflineResult {
        val metadata = manifest ?: error("Import a trusted portable model ZIP first")
        require(category == metadata.category) { "Imported model is for ${metadata.category}, not $category" }
        val started = System.nanoTime()
        val bitmap = BitmapFactory.decodeFile(file.path) ?: error("Cannot decode image")
        val orientation = ExifInterface(file).getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL)
        val matrix = Matrix()
        when (orientation) {
            2 -> matrix.setScale(-1f, 1f)
            3 -> matrix.setRotate(180f)
            4 -> matrix.setScale(1f, -1f)
            5 -> { matrix.setRotate(90f); matrix.postScale(-1f, 1f) }
            6 -> matrix.setRotate(90f)
            7 -> { matrix.setRotate(-90f); matrix.postScale(-1f, 1f) }
            8 -> matrix.setRotate(-90f)
        }
        val oriented = if (matrix.isIdentity) bitmap else Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
        val width = if (oriented.width <= oriented.height) 256 else (256L * oriented.width / oriented.height).toInt()
        val height = if (oriented.height <= oriented.width) 256 else (256L * oriented.height / oriented.width).toInt()
        val resized = Bitmap.createScaledBitmap(oriented, width, height, true)
        // Math.rint matches Python round's ties-to-even crop coordinates.
        val crop = Bitmap.createBitmap(resized, Math.rint((width - 224) / 2.0).toInt(), Math.rint((height - 224) / 2.0).toInt(), 224, 224)
        val pixels = IntArray(224 * 224); crop.getPixels(pixels, 0, 224, 0, 0, 224, 224)
        val tensor = FloatArray(3 * pixels.size)
        val means = floatArrayOf(0.485f, 0.456f, 0.406f); val stds = floatArrayOf(0.229f, 0.224f, 0.225f)
        for (channel in 0..2) for (index in pixels.indices) {
            val value = (pixels[index] shr (16 - channel * 8)) and 255
            tensor[channel * pixels.size + index] = (value / 255f - means[channel]) / stds[channel]
        }
        val score = OnnxTensor.createTensor(environment, FloatBuffer.wrap(tensor), longArrayOf(1, 3, 224, 224)).use { input ->
            session!!.run(mapOf("normalised_rgb" to input)).use { result -> (result[0].value as FloatArray)[0] }
        }
        require(score.isFinite()) { "Non-finite offline prediction" }
        for (temporary in listOf(bitmap, oriented, resized).distinct()) if (temporary !== crop) temporary.recycle()
        return OfflineResult(score, metadata, crop, (System.nanoTime() - started) / 1_000_000.0)
    }

    @Synchronized override fun close() {
        session?.close(); session = null; manifest = null
        directory?.deleteRecursively(); directory = null
    }
}
