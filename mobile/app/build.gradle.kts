import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
}

android {
    namespace = "ai.empirico.app"
    compileSdk = 36

    defaultConfig {
        applicationId = "ai.empirico.app"
        minSdk = 26
        targetSdk = 36
        versionCode = 2
        versionName = "1.1"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        // API_BASE_URL: leave empty to use https://empirico.ai/api/v2/. For local backend: set in gradle.properties or -PAPI_BASE_URL=http://10.0.2.2:8050/api/v2/ (emulator) or http://YOUR_IP:8050/api/v2/ (device).
        val apiBase = project.findProperty("API_BASE_URL")?.toString()?.trim()?.takeIf { it.isNotEmpty() }
            ?: (project.rootProject.file("local.properties").takeIf { it.exists() }?.let { f ->
                Properties().apply { load(f.inputStream()) }.getProperty("api.base.url", "")?.trim()?.takeIf { it.isNotEmpty() }
            } ?: "")
        buildConfigField("String", "API_BASE_URL", "\"${apiBase}\"")
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
    kotlinOptions {
        jvmTarget = "11"
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
}

dependencies {

    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.ui)
    implementation(libs.androidx.ui.graphics)
    implementation(libs.androidx.ui.tooling.preview)
    implementation(libs.androidx.material3)
    implementation("androidx.compose.material:material-icons-extended")
    
    // Navigation
    implementation(libs.androidx.navigation.compose)
    
    // ViewModel
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    
    // Networking
    implementation(libs.retrofit)
    implementation(libs.retrofit.gson)
    implementation(libs.okhttp)
    implementation(libs.okhttp.logging)
    implementation(libs.gson)
    
    // Coroutines
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.kotlinx.coroutines.play.services)
    
    // DataStore
    implementation(libs.androidx.datastore.preferences)
    
    // Google Sign-In
    implementation("com.google.android.gms:play-services-auth:21.2.0")
    
    // Image Loading
    implementation(libs.coil.compose)
    
    testImplementation(libs.junit)
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.ui.test.junit4)
    debugImplementation(libs.androidx.ui.tooling)
    debugImplementation(libs.androidx.ui.test.manifest)
}