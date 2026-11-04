package `in`.wcte.visurex

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.meta.wearable.dat.core.Wearables
import com.meta.wearable.dat.core.types.Permission
import com.meta.wearable.dat.core.types.PermissionStatus
import com.meta.wearable.dat.core.types.RegistrationState
import com.meta.wearable.dat.mockdevice.MockDeviceKit
import com.meta.wearable.dat.mockdevice.api.GlassesModel
import kotlinx.coroutines.runBlocking
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.Assert.*

/** Instrumentation only. Compile is not an executed Mock Device Kit result. */
@RunWith(AndroidJUnit4::class)
class GlassesMockTest {
    @Test fun mockRegistrationAndDeniedPermission() = runBlocking {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val kit = MockDeviceKit.getInstance(context)
        try {
            kit.enable()
            assertEquals(RegistrationState.REGISTERED,Wearables.registrationState.value)
            val device = kit.pairGlasses(GlassesModel.RAYBAN_META).getOrThrow()
            device.powerOn(); device.unfold(); device.don()
            assertTrue(kit.pairedDevices.isNotEmpty())
            kit.permissions.set(Permission.CAMERA,PermissionStatus.Denied)
            assertEquals(PermissionStatus.Denied,Wearables.checkPermissionStatus(Permission.CAMERA).getOrThrow())
        } finally { kit.disable() }
    }
}
