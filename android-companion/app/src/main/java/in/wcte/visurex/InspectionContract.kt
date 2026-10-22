package `in`.wcte.visurex

import org.json.JSONObject
import java.net.URI
import java.time.Instant
import java.util.Base64

data class InspectionResult(val id: String, val category: String, val decision: String,
    val version: String, val score: Double?, val threshold: Double?, val inferenceMs: Double?,
    val serverMs: Double, val overlay: String?, val processed: String?, val warnings: List<String>) {
    fun spoken(): String = when (decision) {
        "GOOD" -> "No anomaly detected by the $category model. Research prototype."
        "ANOMALY" -> "Potential anomaly detected. Please review the inspection."
        "RETAKE" -> "Please retake the image. ${warnings.joinToString(". ")}"
        else -> "Inspection unavailable. Please try again."
    }
}

object InspectionContract {
    val categories = listOf("bottle", "grid", "transistor")
    fun endpoint(input: String, debug: Boolean): String {
        val uri = URI(input.trim())
        require(uri.scheme in listOf("http", "https") && uri.host != null && uri.userInfo == null && uri.query == null && uri.fragment == null) { "Enter a backend URL without credentials, query or fragment." }
        require(debug || uri.scheme == "https") { "Release builds require HTTPS." }
        require(uri.path.isNullOrEmpty() || uri.path == "/") { "Enter the base URL only, without /api/inspect." }
        return input.trim().trimEnd('/') + "/api/inspect"
    }
    private fun number(j: JSONObject, key: String): Double {
        val value = j.get(key)
        require(value is Number) { "$key must be a JSON number" }
        return value.toDouble().also { require(it.isFinite()) { "Invalid $key" } }
    }
    private fun png(value: String): String {
        require(value.startsWith("data:image/png;base64,")) { "Unsupported image encoding" }
        val bytes = Base64.getDecoder().decode(value.substringAfter(','))
        require(bytes.size >= 8 && bytes.take(8) == listOf(137,80,78,71,13,10,26,10).map { it.toByte() }) { "Invalid PNG payload" }
        return value
    }
    fun parse(body: String, expectedCategory: String): InspectionResult {
        val j = JSONObject(body)
        val decision = j.getString("decision")
        require(decision in listOf("GOOD", "ANOMALY", "RETAKE", "UNAVAILABLE")) { "Unknown inspection decision" }
        require(j.getString("category") == expectedCategory) { "Response category mismatch" }
        val id = j.getString("inspection_id").also { require(it.isNotBlank()) }
        Instant.parse(j.getString("timestamp"))
        val timing = j.getJSONObject("timing")
        val successful = decision == "GOOD" || decision == "ANOMALY"
        val version = if (successful) j.getString("model_version").also { require(it.isNotBlank()) } else j.optString("model_version", "not run")
        val score = if (successful) number(j, "anomaly_score") else null
        val threshold = if (successful) number(j, "threshold") else null
        val inference = if (successful) number(timing, "model_inference_ms").also { require(it >= 0) } else null
        val server = number(timing, "server_processing_ms").also { require(it >= 0) }
        val images = j.optJSONObject("images")
        val overlay = if (successful) png(images!!.getString("overlay")) else null
        val processed = if (successful) png(images!!.getString("processed")) else null
        val warnings = mutableListOf<String>()
        j.optJSONArray("warnings")?.let { a -> for (i in 0 until a.length()) warnings.add(a.getString(i)) }
        j.optJSONObject("quality")?.optJSONArray("reasons")?.let { a -> for (i in 0 until a.length()) warnings.add(a.getString(i)) }
        if (decision == "RETAKE") {
            val quality = j.getJSONObject("quality")
            require(quality.get("passed") == false) { "RETAKE requires quality.passed=false" }
            val reasons = quality.getJSONArray("reasons")
            require(reasons.length() > 0) { "RETAKE requires quality reasons" }
            for (i in 0 until reasons.length()) require(reasons.get(i) is String && reasons.getString(i).isNotBlank()) { "Invalid quality reason" }
        }
        return InspectionResult(id, expectedCategory, decision, version, score, threshold, inference, server, overlay, processed, warnings.distinct())
    }
}
