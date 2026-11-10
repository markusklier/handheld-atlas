plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// CI passes -PbuildNumber=<run number>; every build is installable over the previous one.
val buildNumber = (project.findProperty("buildNumber") as String?)?.toIntOrNull() ?: 1

android {
    namespace = "io.github.markusklier.handheldatlas"
    compileSdk = 34

    defaultConfig {
        applicationId = "io.github.markusklier.handheldatlas"
        minSdk = 30
        targetSdk = 34
        versionCode = buildNumber
        versionName = "0.1.$buildNumber"
        buildConfigField("String", "WEB_URL", "\"https://markusklier.github.io/handheld-atlas/\"")
        buildConfigField("String", "WEB_ORIGIN", "\"https://markusklier.github.io\"")
    }

    signingConfigs {
        create("atlas") {
            // Own key via environment (repository secrets), otherwise the pre-release key in the repo (docs/SETUP.md).
            val external = System.getenv("ATLAS_KEYSTORE")
            val pass = System.getenv("ATLAS_KEYSTORE_PASSWORD") ?: "handheldatlas"
            storeFile = if (!external.isNullOrBlank() && file(external).exists()) file(external) else rootProject.file("atlas-dev.keystore")
            storePassword = pass
            keyAlias = System.getenv("ATLAS_KEY_ALIAS") ?: "atlas"
            keyPassword = System.getenv("ATLAS_KEY_PASSWORD") ?: pass
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("atlas")
        }
        debug {
            signingConfig = signingConfigs.getByName("atlas")
        }
    }

    buildFeatures {
        aidl = true
        buildConfig = true
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    lint {
        abortOnError = false
        checkReleaseBuilds = false
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.webkit:webkit:1.11.0")
    implementation("dev.rikka.shizuku:api:13.1.5")
    implementation("dev.rikka.shizuku:provider:13.1.5")
}
