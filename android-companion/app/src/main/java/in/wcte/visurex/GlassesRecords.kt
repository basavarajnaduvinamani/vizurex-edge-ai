package `in`.wcte.visurex

import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.util.UUID

/** S1 envelopes. Suggested values are deliberately unconfirmed; a model verdict is not a human label. */
object GlassesRecords {
    fun keyword(text: String): String? = Regex("^(note|check)(?:\\s|$)", RegexOption.IGNORE_CASE)
        .find(text.trim())?.groupValues?.get(1)?.lowercase(java.util.Locale.ROOT)

    private fun value(v: Any?, source: String = "rule", confirmed: Boolean = false) =
        JSONObject().put("value", v ?: JSONObject.NULL).put("source", source).put("confirmed", confirmed)

    private fun envelope(kind: String, fields: JSONObject) = JSONObject()
        .put("schemaVersion", "$kind.v1").put("id", UUID.randomUUID().toString()).put("revision", 1).put("fields", fields)

    fun create(plant: String, station: String, note: String, fromVoice: Boolean, photo: JSONObject,
               decision: String?, score: Double?, bank: String?, demo: Boolean, now: Instant = Instant.now()): Pair<JSONObject, JSONObject> {
        require(plant.isNotBlank() && station.isNotBlank()) { "Enter plant and station" }
        require(decision in listOf(null, "GOOD", "ANOMALY", "RETAKE"))
        require(score == null || score.isFinite())
        fun common() = JSONObject().put("createdAt", value(now.toString(), confirmed = true))
            .put("demo", value(demo, confirmed = true)).put("plantId", value(plant, "human", true))
            .put("station", value(station, "human", true)).put("photo", value(photo, confirmed = true))
            .put("note", value(note, if (fromVoice) "asr" else "human", !fromVoice))
        val event = envelope("CaptureEvent", common().put("origin", value("glasses", confirmed = true))
            .put("decision", value(decision, "detector")).put("modelScore", value(score, "detector"))
            .put("bankVersion", value(bank, "detector")))
        val finding = envelope("Finding", common().put("walkId", value(null))
            .put("category", value("quality")).put("severity", value("medium"))
            .put("dueDate", value(LocalDate.ofInstant(now, ZoneId.of("Asia/Kolkata")).plusDays(3).toString()))
            .put("ownerRole", value("qa_lead")).put("checklist", value(JSONArray())).put("status", value("open", confirmed = true)))
        return event to finding
    }
}
