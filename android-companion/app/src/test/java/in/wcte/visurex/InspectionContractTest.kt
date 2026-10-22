package `in`.wcte.visurex

import org.junit.Assert.*
import org.junit.Test

class InspectionContractTest {
    private val good = """{"inspection_id":"id","timestamp":"2026-10-22T00:00:00Z","category":"bottle","decision":"GOOD","model_version":"v1","anomaly_score":0.3,"threshold":1.0,"timing":{"model_inference_ms":10,"server_processing_ms":12},"images":{"overlay":"data:image/png;base64,iVBORw0KGgo=","processed":"data:image/png;base64,iVBORw0KGgo="}}"""
    @Test fun parsesSuccess() { assertEquals("GOOD", InspectionContract.parse(good, "bottle").decision) }
    @Test fun parsesRetakeWithoutModelOutputs() {
        val raw = """{"inspection_id":"id","timestamp":"2026-10-22T00:00:00Z","category":"bottle","decision":"RETAKE","timing":{"server_processing_ms":1},"quality":{"passed":false,"reasons":["too dark"]}}"""
        val result = InspectionContract.parse(raw, "bottle")
        assertNull(result.score); assertTrue(result.spoken().contains("too dark"))
    }
    @Test(expected = IllegalArgumentException::class) fun rejectsCategoryMismatch() { InspectionContract.parse(good, "grid") }
    @Test(expected = Exception::class) fun rejectsMissingVersion() { InspectionContract.parse(good.replace("\"model_version\":\"v1\",", ""), "bottle") }
    @Test(expected = IllegalArgumentException::class) fun rejectsUnknownDecision() { InspectionContract.parse(good.replace("GOOD", "PASS"), "bottle") }
    @Test fun localDebugEndpoint() { assertEquals("http://10.0.2.2:8000/api/inspect", InspectionContract.endpoint("http://10.0.2.2:8000/", true)) }
    @Test(expected = IllegalArgumentException::class) fun releaseRequiresTls() { InspectionContract.endpoint("http://192.168.1.5:8000", false) }
    @Test(expected = IllegalArgumentException::class) fun rejectsEmbeddedCredentials() { InspectionContract.endpoint("http://user:pass@localhost:8000", true) }
    @Test(expected = IllegalArgumentException::class) fun rejectsApiPath() { InspectionContract.endpoint("http://localhost:8000/api/inspect", true) }
    @Test(expected = Exception::class) fun rejectsInvalidTimestamp() { InspectionContract.parse(good.replace("2026-10-22T00:00:00Z", "yesterday"), "bottle") }
    @Test(expected = IllegalArgumentException::class) fun rejectsNumericString() { InspectionContract.parse(good.replace("\"anomaly_score\":0.3", "\"anomaly_score\":\"0.3\""), "bottle") }
    @Test(expected = IllegalArgumentException::class) fun rejectsInvalidPng() { InspectionContract.parse(good.replace("iVBORw0KGgo=", "AA=="), "bottle") }
    @Test(expected = Exception::class) fun rejectsRetakeWithoutReasons() {
        InspectionContract.parse("""{"inspection_id":"id","timestamp":"2026-10-22T00:00:00Z","category":"bottle","decision":"RETAKE","timing":{"server_processing_ms":1},"quality":{"passed":false,"reasons":[]}}""", "bottle")
    }
}
