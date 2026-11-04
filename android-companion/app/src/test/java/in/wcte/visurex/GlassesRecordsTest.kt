package `in`.wcte.visurex

import org.junit.Test
import org.junit.Assert.*
import org.json.JSONObject
import java.io.File
import java.time.Instant

class GlassesRecordsTest {
    @Test fun commandsRequireWholeLeadingKeyword() {
        assertEquals("check",GlassesRecords.keyword(" CHECK washer"))
        assertEquals("note",GlassesRecords.keyword("note"))
        assertNull(GlassesRecords.keyword("noteworthy"))
        assertNull(GlassesRecords.keyword("do not check"))
        assertNull(GlassesRecords.keyword("checker"))
    }
    private fun records() = GlassesRecords.create("test-plant","station","check washer",true,
        JSONObject().put("redacted",true),"ANOMALY",0.8,"a".repeat(64),false,Instant.parse("2026-11-03T23:30:00Z"))
    @Test fun provenanceDoesNotTurnModelIntoHumanLabel() {
        val (event,finding) = records()
        assertEquals("CaptureEvent.v1",event.getString("schemaVersion"))
        val fields = event.getJSONObject("fields")
        assertFalse(fields.getJSONObject("decision").getBoolean("confirmed"))
        assertEquals("detector",fields.getJSONObject("decision").getString("source"))
        assertEquals("asr",fields.getJSONObject("note").getString("source"))
        assertFalse(fields.getJSONObject("demo").getBoolean("value"))
        assertFalse(finding.getJSONObject("fields").getJSONObject("category").getBoolean("confirmed"))
        assertEquals("2026-11-07",finding.getJSONObject("fields").getJSONObject("dueDate").getString("value"))
    }
    @Test fun fixtureForS1SchemaValidation() {
        val (event,finding) = records()
        val dir = File("build/glasses-fixtures").apply { mkdirs() }
        File(dir,"capture.json").writeText(event.toString(2))
        File(dir,"finding.json").writeText(finding.toString(2))
        assertNotEquals(event.getString("id"),finding.getString("id"))
    }
    @Test(expected = IllegalArgumentException::class) fun rejectMissingPlant() {
        GlassesRecords.create("","station","",false,JSONObject(),null,null,null,false)
    }
    @Test(expected = IllegalArgumentException::class) fun rejectNonFiniteScore() {
        GlassesRecords.create("plant","station","",false,JSONObject(),"GOOD",Double.NaN,null,false)
    }
}
