package `in`.wcte.visurex

import org.json.JSONObject

data class PortableManifest(val category: String, val sha256: String, val bytes: Long, val threshold: Double) {
    companion object {
        fun parse(text: String): PortableManifest {
            val data = JSONObject(text)
            require(data.getInt("format_version") == 1) { "Unsupported portable bundle" }
            val category = data.getString("category")
            require(category in InspectionContract.categories) { "Unknown portable category" }
            val sha = data.getString("model_sha256")
            require(sha.matches(Regex("[a-f0-9]{64}"))) { "Invalid model checksum" }
            val bytes = data.getLong("bytes")
            require(bytes in 1..200L * 1024 * 1024) { "Portable model exceeds size limit" }
            require(data.get("threshold") is Number) { "Invalid model threshold" }
            val threshold = data.getDouble("threshold")
            require(threshold.isFinite()) { "Invalid model threshold" }
            require(data.getInt("images_checked") > 0 && data.getJSONArray("failures").length() == 0) { "Model verification did not pass" }
            val recipe = data.getJSONObject("preprocessing")
            require(recipe.getInt("resize_short_edge") == 256 && recipe.getInt("center_crop") == 224 && recipe.getString("colour") == "RGB") { "Unsupported preprocessing" }
            for ((key, values) in listOf("mean" to listOf(0.485, 0.456, 0.406), "std" to listOf(0.229, 0.224, 0.225))) {
                val actual = recipe.getJSONArray(key)
                require(actual.length() == 3 && values.indices.all { kotlin.math.abs(actual.getDouble(it) - values[it]) < 1e-9 }) { "Unsupported normalisation" }
            }
            return PortableManifest(category, sha, bytes, threshold)
        }
    }
}
