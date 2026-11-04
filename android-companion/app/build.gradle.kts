plugins { id("com.android.application"); id("org.jetbrains.kotlin.android") }
providers.gradleProperty("visurexBuildDir").orNull?.let { layout.buildDirectory.set(file(it)) }
android {
    namespace = "in.wcte.visurex"
    compileSdk = 36
    defaultConfig {
        applicationId = "in.wcte.visurex"; minSdk = 31; targetSdk = 36; versionCode = 2; versionName = "0.2.0-dev"
        manifestPlaceholders["mwdat_application_id"] = "0"
        manifestPlaceholders["mwdat_client_token"] = "0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }
    buildFeatures { buildConfig = true }
    buildTypes { release { isMinifyEnabled = false } }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
}
dependencies {
    implementation("com.meta.wearable:mwdat-core:1.0.1")
    implementation("com.meta.wearable:mwdat-camera:1.0.1")
    implementation("com.meta.wearable:mwdat-mockdevice:1.0.1")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.9.4")
    implementation("com.google.mlkit:face-detection:16.1.7")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test:runner:1.6.2")
    implementation("androidx.activity:activity-ktx:1.9.3")
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.microsoft.onnxruntime:onnxruntime-android:1.22.0")
    implementation("androidx.exifinterface:exifinterface:1.3.7")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
}
