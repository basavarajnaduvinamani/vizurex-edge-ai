package `in`.wcte.visurex

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Rect
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.face.FaceDetection
import com.google.mlkit.vision.face.FaceDetectorOptions
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlinx.coroutines.suspendCancellableCoroutine

/** Bundled offline face detection; pixelated boxes. Detection is not a privacy guarantee. */
class GlassesRedactor : AutoCloseable {
    private val detector = FaceDetection.getClient(FaceDetectorOptions.Builder()
        .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_ACCURATE).build())
    suspend fun redact(input: Bitmap): Pair<Bitmap, Int> = suspendCancellableCoroutine { continuation ->
        // Own the detector input until its asynchronous task completes, even if the activity stops.
        val detectorInput = input.copy(Bitmap.Config.ARGB_8888, false)
        detector.process(InputImage.fromBitmap(detectorInput, 0))
            .addOnSuccessListener { faces ->
                try {
                    val output = detectorInput.copy(Bitmap.Config.ARGB_8888, true)
                    val canvas = Canvas(output)
                    for (face in faces) {
                        val box = Rect(face.boundingBox)
                        box.inset(-box.width() / 3, -box.height() / 3)
                        if (!box.intersect(0, 0, detectorInput.width, detectorInput.height)) continue
                        val crop = Bitmap.createBitmap(detectorInput, box.left, box.top, box.width(), box.height())
                        val tiny = Bitmap.createScaledBitmap(crop, 4, 4, false)
                        canvas.drawBitmap(tiny, null, box, Paint().apply { isFilterBitmap = false })
                        tiny.recycle(); crop.recycle()
                    }
                    if (continuation.isActive) continuation.resume(output to faces.size) else output.recycle()
                } catch (error: Exception) { if (continuation.isActive) continuation.resumeWithException(error) }
            }.addOnFailureListener { if (continuation.isActive) continuation.resumeWithException(it) }
            .addOnCompleteListener { detectorInput.recycle() }
    }
    override fun close() = detector.close()
}
