"""
Автоматические проверки нативного Android-моста и конфигурации Android APK (BahonIQ Music)
для управления с мультируля, Bluetooth AVRCP, AudioFocus и фонового воспроизведения.
"""
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


class TestMusicAndroidBridge(unittest.TestCase):
    def test_frontend_native_bridge_and_deduplication(self):
        music_js = (ROOT_DIR / "web_app" / "static" / "music" / "music.js").read_text(encoding="utf-8")

        # Мост с Android и сохранение navigator.mediaSession для Chrome/PWA
        self.assertIn("window.BahonIQNativeBridge", music_js)
        self.assertIn("window.BahonIQAndroid", music_js)
        self.assertIn("navigator.mediaSession.setActionHandler", music_js)
        self.assertIn("MEDIA_CMD_DEBOUNCE_MS", music_js)
        self.assertIn("runMediaCommand", music_js)
        self.assertIn("syncStateToAndroid", music_js)
        self.assertIn("handleFocusCommand", music_js)

        # Поддержка приглушения (duck/unduck) и всех команд мультируля
        for cmd in ("'play'", "'pause'", "'toggle'", "'next'", "'previous'", "'stop'", "'duck'", "'unduck'"):
            self.assertIn(cmd, music_js)

        # Убеждаемся, что секреты Telegram не передаются в JS-мост
        bridge_section_start = music_js.index("buildPlaybackStatePayload()")
        bridge_section_end = music_js.index("function updateMediaSession", bridge_section_start)
        bridge_section = music_js[bridge_section_start:bridge_section_end]
        for forbidden in ("TELEGRAM_SESSION", "api_hash", "access_hash", "file_reference", "token"):
            self.assertNotIn(forbidden, bridge_section)

    def test_android_manifest_permissions_and_media_components(self):
        manifest = (
            ROOT_DIR / "android_music_apk" / "app" / "src" / "main" / "AndroidManifest.xml"
        ).read_text(encoding="utf-8")

        self.assertIn("android.permission.FOREGROUND_SERVICE", manifest)
        self.assertIn("android.permission.FOREGROUND_SERVICE_MEDIA_PLAYBACK", manifest)
        self.assertIn("android.permission.WAKE_LOCK", manifest)
        self.assertIn("MediaPlaybackService", manifest)
        self.assertIn('android:foregroundServiceType="mediaPlayback"', manifest)
        self.assertIn("androidx.media.session.MediaButtonReceiver", manifest)
        self.assertIn("android.intent.action.MEDIA_BUTTON", manifest)

    def test_android_media_service_keys_audio_focus_and_notification(self):
        service_java = (
            ROOT_DIR
            / "android_music_apk"
            / "app"
            / "src"
            / "main"
            / "java"
            / "uz"
            / "bahoniq"
            / "music"
            / "MediaPlaybackService.java"
        ).read_text(encoding="utf-8")

        # MediaSessionCompat и все 6 требуемых медиа-кнопок
        self.assertIn("MediaSessionCompat", service_java)
        for keycode in (
            "KEYCODE_MEDIA_PLAY",
            "KEYCODE_MEDIA_PAUSE",
            "KEYCODE_MEDIA_PLAY_PAUSE",
            "KEYCODE_MEDIA_NEXT",
            "KEYCODE_MEDIA_PREVIOUS",
            "KEYCODE_MEDIA_STOP",
        ):
            self.assertIn(keycode, service_java)

        # Кнопки громкости не должны перехватываться
        self.assertNotIn("KEYCODE_VOLUME_UP", service_java)
        self.assertNotIn("KEYCODE_VOLUME_DOWN", service_java)

        # AudioFocus (звонки, навигатор, ducking)
        for focus_flag in (
            "AUDIOFOCUS_GAIN",
            "AUDIOFOCUS_LOSS_TRANSIENT",
            "AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK",
            "AUDIOFOCUS_LOSS",
        ):
            self.assertIn(focus_flag, service_java)

        # Foreground service + MediaStyle уведомление + MediaMetadataCompat
        self.assertIn("startForeground(", service_java)
        self.assertIn("MediaStyle", service_java)
        self.assertIn("MediaMetadataCompat", service_java)
        self.assertIn("PARTIAL_WAKE_LOCK", service_java)

    def test_android_main_activity_webview_and_bridge(self):
        activity_java = (
            ROOT_DIR
            / "android_music_apk"
            / "app"
            / "src"
            / "main"
            / "java"
            / "uz"
            / "bahoniq"
            / "music"
            / "MainActivity.java"
        ).read_text(encoding="utf-8")

        self.assertIn("https://bahoniq-music.onrender.com/music/", activity_java)
        self.assertIn("setMediaPlaybackRequiresUserGesture(false)", activity_java)
        self.assertIn('addJavascriptInterface(new WebAppBridge(), "BahonIQAndroid")', activity_java)
        self.assertIn("BahonIQNativeBridge", activity_java)
        self.assertIn("moveTaskToBack(true)", activity_java)
        self.assertNotIn("webView.onPause()", activity_java)
        self.assertNotIn("pauseTimers()", activity_java)
        self.assertNotIn("KEYCODE_VOLUME_UP", activity_java)
        self.assertNotIn("KEYCODE_VOLUME_DOWN", activity_java)


if __name__ == "__main__":
    unittest.main()
