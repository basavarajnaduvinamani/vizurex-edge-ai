plugins { id("com.android.application"); id("org.jetbrains.kotlin.android") }
android {
    namespace = "in.wcte.visurex"
    compileSdk = 34
    defaultConfig { applicationId = "in.wcte.visurex"; minSdk = 26; targetSdk = 34; versionCode = 1; versionName = "0.1.0" }
    buildFeatures { buildConfig = true }
    buildTypes { release { isMinifyEnabled = false } }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
}
dependencies {
    implementation("androidx.activity:activity-ktx:1.9.3")
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.microsoft.onnxruntime:onnxruntime-android:1.22.0")
    implementation("androidx.exifinterface:exifinterface:1.3.7")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
}
