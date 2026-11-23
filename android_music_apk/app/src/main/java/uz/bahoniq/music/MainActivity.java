package uz.bahoniq.music;

import android.Manifest;
import android.annotation.SuppressLint;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.media.AudioManager;
import android.os.Build;
import android.os.Bundle;
import android.os.IBinder;
import android.view.KeyEvent;
import android.view.View;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import org.json.JSONObject;

import java.util.Locale;

/**
 * Основная Activity Android APK для BahonIQ Music:
 * - Не создаёт отдельный нативный плеер: управляет существующим HTMLAudioElement в WebView
 * - Передаёт команды MediaSessionCompat / мультируля в WebView через window.BahonIQNativeBridge
 * - Не перехватывает кнопки громкости (KEYCODE_VOLUME_*)
 * - Не приостанавливает WebView при сворачивании или выключении экрана
 */
public class MainActivity extends AppCompatActivity implements MediaPlaybackService.CommandListener {

    private static final String MUSIC_URL = "https://bahoniq-music.onrender.com/music/";
    private static final int REQ_POST_NOTIFICATIONS = 2001;

    private WebView webView;
    private MediaPlaybackService playbackService;
    private boolean isServiceBound = false;

    private final ServiceConnection serviceConnection = new ServiceConnection() {
        @Override
        public void onServiceConnected(ComponentName name, IBinder service) {
            MediaPlaybackService.LocalBinder binder = (MediaPlaybackService.LocalBinder) service;
            playbackService = binder.getService();
            playbackService.setCommandListener(MainActivity.this);
            isServiceBound = true;
        }

        @Override
        public void onServiceDisconnected(ComponentName name) {
            if (playbackService != null) {
                playbackService.setCommandListener(null);
            }
            playbackService = null;
            isServiceBound = false;
        }
    };

    @SuppressLint({"SetJavaScriptEnabled", "AddJavascriptInterface"})
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setVolumeControlStream(AudioManager.STREAM_MUSIC);

        webView = new WebView(this);
        webView.setBackgroundColor(Color.parseColor("#050b14"));
        setContentView(webView);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);

        webView.addJavascriptInterface(new WebAppBridge(), "BahonIQAndroid");
        webView.setWebChromeClient(new WebChromeClient());
        webView.setWebViewClient(new WebViewClient());

        requestNotificationPermissionIfNeeded();
        startAndBindPlaybackService();

        if (savedInstanceState != null) {
            webView.restoreState(savedInstanceState);
        } else {
            webView.loadUrl(MUSIC_URL);
        }
    }

    private void startAndBindPlaybackService() {
        Intent serviceIntent = new Intent(this, MediaPlaybackService.class);
        startService(serviceIntent);
        bindService(serviceIntent, serviceConnection, Context.BIND_AUTO_CREATE);
    }

    private void requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                    != PackageManager.PERMISSION_GRANTED) {
                ActivityCompat.requestPermissions(
                        this,
                        new String[]{Manifest.permission.POST_NOTIFICATIONS},
                        REQ_POST_NOTIFICATIONS
                );
            }
        }
    }

    @Override
    public void onMediaCommand(String action, Double seekSeconds, boolean isFocusEvent) {
        if (webView == null) return;
        String safeAction = sanitizeAction(action);
        if (safeAction == null) return;

        String payloadArg = (seekSeconds != null)
                ? String.format(Locale.US, "%.3f", seekSeconds)
                : "null";
        String fn = isFocusEvent ? "handleFocusCommand" : "handleCommand";
        String js = "if(window.BahonIQNativeBridge && typeof window.BahonIQNativeBridge." + fn + "==='function'){"
                + "window.BahonIQNativeBridge." + fn + "('" + safeAction + "', " + payloadArg + ");}";
        webView.evaluateJavascript(js, null);
    }

    private static String sanitizeAction(String action) {
        if (action == null) return null;
        switch (action) {
            case "play":
            case "pause":
            case "toggle":
            case "next":
            case "previous":
            case "stop":
            case "seekto":
            case "duck":
            case "unduck":
                return action;
            default:
                return null;
        }
    }

    @Override
    public boolean dispatchKeyEvent(KeyEvent event) {
        // Кнопки громкости (VOLUME_UP / VOLUME_DOWN / VOLUME_MUTE) никогда не перехватываются
        if (event != null && MediaPlaybackService.isSupportedMediaKey(event.getKeyCode())) {
            if (playbackService != null && playbackService.handleMediaKeyEvent(event)) {
                return true;
            }
        }
        return super.dispatchKeyEvent(event);
    }

    @Override
    protected void onSaveInstanceState(@NonNull Bundle outState) {
        super.onSaveInstanceState(outState);
        if (webView != null) {
            webView.saveState(outState);
        }
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            // Сворачиваем приложение в фон вместо уничтожения плеера
            moveTaskToBack(true);
        }
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {
            hideBars();
        }
    }

    private void hideBars() {
        View decor = getWindow().getDecorView();
        decor.setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                        | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                        | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_FULLSCREEN
        );
    }

    @Override
    protected void onDestroy() {
        if (isServiceBound) {
            if (playbackService != null) {
                playbackService.setCommandListener(null);
            }
            unbindService(serviceConnection);
            isServiceBound = false;
        }
        super.onDestroy();
    }

    /**
     * Безопасный JS-мост для передачи состояния веб-плеера в Android MediaSessionCompat.
     * Секреты/токены Telegram сюда никогда не передаются.
     */
    private class WebAppBridge {
        @JavascriptInterface
        public void onPlaybackState(String jsonState) {
            if (jsonState == null || jsonState.isEmpty()) return;
            try {
                JSONObject obj = new JSONObject(jsonState);
                boolean playing = obj.optBoolean("isPlaying", false);
                String title = obj.optString("title", "BahonIQ Music");
                String artist = obj.optString("artist", "Музыка ДИТ");
                String album = obj.optString("album", "BahonIQ Music");
                String coverUrl = obj.optString("coverUrl", "");
                long durationMs = obj.optLong("duration", 0L);
                long positionMs = obj.optLong("position", 0L);

                runOnUiThread(() -> {
                    if (playbackService != null) {
                        playbackService.updateFromWebState(
                                playing, title, artist, album, coverUrl, durationMs, positionMs
                        );
                    }
                });
            } catch (Exception ignored) {
            }
        }
    }
}
