package `in`.wcte.visurex

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test

class PortableManifestTest {
    private fun fixture() = JSONObject("""{"format_version":1,"category":"bottle","model_sha256":"${"a".repeat(64)}","bytes":100,"threshold":1.0,"images_checked":83,"failures":[],"preprocessing":{"resize_short_edge":256,"center_crop":224,"colour":"RGB","mean":[0.485,0.456,0.406],"std":[0.229,0.224,0.225]}}""")
    @Test fun validManifest() { assertEquals("bottle", PortableManifest.parse(fixture().toString()).category) }
    @Test(expected = IllegalArgumentException::class) fun rejectsUnverified() { PortableManifest.parse(fixture().put("images_checked", 0).toString()) }
    @Test(expected = IllegalArgumentException::class) fun rejectsWrongRecipe() { val json = fixture(); json.getJSONObject("preprocessing").put("center_crop", 256); PortableManifest.parse(json.toString()) }
    @Test(expected = IllegalArgumentException::class) fun rejectsLargeModel() { PortableManifest.parse(fixture().put("bytes", 300L * 1024 * 1024).toString()) }
    @Test(expected = IllegalArgumentException::class) fun rejectsUnknownCategory() { PortableManifest.parse(fixture().put("category", "factory-anything").toString()) }
}
