package uz.bahoniq.music;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.media.AudioAttributes;
import android.media.AudioFocusRequest;
import android.media.AudioManager;
import android.os.Binder;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.PowerManager;
import android.os.SystemClock;
import android.support.v4.media.MediaMetadataCompat;
import android.support.v4.media.session.MediaSessionCompat;
import android.support.v4.media.session.PlaybackStateCompat;
import android.view.KeyEvent;

import androidx.annotation.Nullable;
import androidx.core.app.NotificationCompat;
import androidx.media.app.NotificationCompat.MediaStyle;
import androidx.media.session.MediaButtonReceiver;

import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Нативный MediaPlaybackService для BahonIQ Music:
 * - Создаёт MediaSessionCompat с поддержкой Bluetooth AVRCP и аппаратных медиа-кнопок мультируля
 * - Управляет AudioFocus (звонки, навигатор, приглушение duck)
 * - Поддерживает воспроизведение при выключенном экране и свёрнутом APK через Foreground Service
 * - Обновляет MediaMetadata и системное уведомление без создания второго аудиоплеера
 */
public class MediaPlaybackService extends Service {

    public static final String CHANNEL_ID = "bahoniq_music_playback";
    public static final int NOTIFICATION_ID = 1001;

    private static final String ACTION_BRIDGE_PLAY = "uz.bahoniq.music.ACTION_PLAY";
    private static final String ACTION_BRIDGE_PAUSE = "uz.bahoniq.music.ACTION_PAUSE";
    private static final String ACTION_BRIDGE_NEXT = "uz.bahoniq.music.ACTION_NEXT";
    private static final String ACTION_BRIDGE_PREV = "uz.bahoniq.music.ACTION_PREV";
    private static final String ACTION_BRIDGE_STOP = "uz.bahoniq.music.ACTION_STOP";

    public interface CommandListener {
        void onMediaCommand(String action, @Nullable Double seekSeconds, boolean isFocusEvent);
    }

    public class LocalBinder extends Binder {
        public MediaPlaybackService getService() {
            return MediaPlaybackService.this;
        }
    }

    private final IBinder binder = new LocalBinder();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final ExecutorService artworkExecutor = Executors.newSingleThreadExecutor();

    private MediaSessionCompat mediaSession;
    private AudioManager audioManager;
    private AudioFocusRequest audioFocusRequest;
    private PowerManager.WakeLock wakeLock;
    private CommandListener commandListener;

    private boolean isPlaying = false;
    private boolean hasAudioFocus = false;
    private boolean pausedByTransientFocusLoss = false;
    private boolean isDucked = false;

    private String currentTitle = "BahonIQ Music";
    private String currentArtist = "Музыка ДИТ";
    private String currentAlbum = "BahonIQ Music";
    private String currentCoverUrl = "";
    private long currentDurationMs = 0L;
    private long currentPositionMs = 0L;
    private Bitmap cachedCoverBitmap = null;
    private String cachedCoverUrl = "";

    private long lastMediaKeyAt = 0L;
    private int lastMediaKeyCode = 0;

    private final AudioManager.OnAudioFocusChangeListener audioFocusListener = focusChange -> {
        switch (focusChange) {
            case AudioManager.AUDIOFOCUS_GAIN:
                hasAudioFocus = true;
                if (isDucked) {
                    isDucked = false;
                    dispatchToWeb("unduck", null, true);
                }
                if (pausedByTransientFocusLoss) {
                    pausedByTransientFocusLoss = false;
                    dispatchToWeb("play", null, true);
                }
                break;

            case AudioManager.AUDIOFOCUS_LOSS_TRANSIENT:
                if (isPlaying) {
                    pausedByTransientFocusLoss = true;
                    dispatchToWeb("pause", null, true);
                }
                break;

            case AudioManager.AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK:
                if (isPlaying) {
                    isDucked = true;
                    dispatchToWeb("duck", null, true);
                }
                break;

            case AudioManager.AUDIOFOCUS_LOSS:
                hasAudioFocus = false;
                pausedByTransientFocusLoss = false;
                isDucked = false;
                if (isPlaying) {
                    dispatchToWeb("pause", null, true);
                }
                abandonAudioFocus();
                break;
        }
    };

    @Override
    public void onCreate() {
        super.onCreate();
        audioManager = (AudioManager) getSystemService(Context.AUDIO_SERVICE);
        PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
        if (pm != null) {
            wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "BahonIQMusic::PlaybackWakeLock");
            wakeLock.setReferenceCounted(false);
        }

        createNotificationChannel();

        ComponentName mediaButtonReceiver = new ComponentName(this, MediaButtonReceiver.class);
        Intent mediaButtonIntent = new Intent(Intent.ACTION_MEDIA_BUTTON);
        mediaButtonIntent.setComponent(mediaButtonReceiver);
        PendingIntent mediaButtonPendingIntent = PendingIntent.getBroadcast(
                this,
                0,
                mediaButtonIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        mediaSession = new MediaSessionCompat(this, "BahonIQMusicSession", mediaButtonReceiver, mediaButtonPendingIntent);
        mediaSession.setFlags(
                MediaSessionCompat.FLAG_HANDLES_MEDIA_BUTTONS
                        | MediaSessionCompat.FLAG_HANDLES_TRANSPORT_CONTROLS
        );
        mediaSession.setMediaButtonReceiver(mediaButtonPendingIntent);
        mediaSession.setCallback(new MediaSessionCompat.Callback() {
            @Override
            public void onPlay() {
                if (requestAudioFocus()) {
                    dispatchToWeb("play", null, false);
                }
            }

            @Override
            public void onPause() {
                pausedByTransientFocusLoss = false;
                dispatchToWeb("pause", null, false);
            }

            @Override
            public void onSkipToNext() {
                if (requestAudioFocus()) {
                    dispatchToWeb("next", null, false);
                }
            }

            @Override
            public void onSkipToPrevious() {
                if (requestAudioFocus()) {
                    dispatchToWeb("previous", null, false);
                }
            }

            @Override
            public void onStop() {
                pausedByTransientFocusLoss = false;
                dispatchToWeb("stop", null, false);
                abandonAudioFocus();
                stopForegroundCompat(true);
            }

            @Override
            public void onSeekTo(long posMs) {
                dispatchToWeb("seekto", posMs / 1000.0, false);
            }

            @Override
            public boolean onMediaButtonEvent(Intent mediaButtonEvent) {
                if (mediaButtonEvent != null && Intent.ACTION_MEDIA_BUTTON.equals(mediaButtonEvent.getAction())) {
                    KeyEvent keyEvent = mediaButtonEvent.getParcelableExtra(Intent.EXTRA_KEY_EVENT);
                    if (keyEvent != null && handleMediaKeyEvent(keyEvent)) {
                        return true;
                    }
                }
                return super.onMediaButtonEvent(mediaButtonEvent);
            }
        });

        mediaSession.setActive(true);
        updatePlaybackState(false, 0L);
        updateMetadata();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null) {
            String action = intent.getAction();
            if (ACTION_BRIDGE_PLAY.equals(action)) {
                if (requestAudioFocus()) dispatchToWeb("play", null, false);
            } else if (ACTION_BRIDGE_PAUSE.equals(action)) {
                pausedByTransientFocusLoss = false;
                dispatchToWeb("pause", null, false);
            } else if (ACTION_BRIDGE_NEXT.equals(action)) {
                dispatchToWeb("next", null, false);
            } else if (ACTION_BRIDGE_PREV.equals(action)) {
                dispatchToWeb("previous", null, false);
            } else if (ACTION_BRIDGE_STOP.equals(action)) {
                pausedByTransientFocusLoss = false;
                dispatchToWeb("stop", null, false);
                stopForegroundCompat(true);
            } else {
                MediaButtonReceiver.handleIntent(mediaSession, intent);
            }
        }
        return START_STICKY;
    }

    @Nullable
    @Override
    public IBinder onBind(Intent intent) {
        return binder;
    }

    public void setCommandListener(@Nullable CommandListener listener) {
        this.commandListener = listener;
    }

    /**
     * Обрабатывает аппаратные клавиши мультируля / Bluetooth AVRCP / гарнитуры.
     * Кнопки громкости (KEYCODE_VOLUME_*) НЕ перехватываются.
     */
    public boolean handleMediaKeyEvent(KeyEvent event) {
        if (event == null || event.getAction() != KeyEvent.ACTION_DOWN || event.getRepeatCount() > 0) {
            return false;
        }
        int keyCode = event.getKeyCode();
        if (!isSupportedMediaKey(keyCode)) {
            return false;
        }
        long now = SystemClock.elapsedRealtime();
        if (keyCode == lastMediaKeyCode && (now - lastMediaKeyAt) < 300) {
            return true;
        }
        lastMediaKeyCode = keyCode;
        lastMediaKeyAt = now;

        switch (keyCode) {
            case KeyEvent.KEYCODE_MEDIA_PLAY:
                if (requestAudioFocus()) dispatchToWeb("play", null, false);
                return true;
            case KeyEvent.KEYCODE_MEDIA_PAUSE:
                pausedByTransientFocusLoss = false;
                dispatchToWeb("pause", null, false);
                return true;
            case KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE:
            case KeyEvent.KEYCODE_HEADSETHOOK:
                if (isPlaying) {
                    pausedByTransientFocusLoss = false;
                    dispatchToWeb("pause", null, false);
                } else if (requestAudioFocus()) {
                    dispatchToWeb("play", null, false);
                }
                return true;
            case KeyEvent.KEYCODE_MEDIA_NEXT:
                dispatchToWeb("next", null, false);
                return true;
            case KeyEvent.KEYCODE_MEDIA_PREVIOUS:
                dispatchToWeb("previous", null, false);
                return true;
            case KeyEvent.KEYCODE_MEDIA_STOP:
                pausedByTransientFocusLoss = false;
                dispatchToWeb("stop", null, false);
                abandonAudioFocus();
                return true;
            default:
                return false;
        }
    }

    public static boolean isSupportedMediaKey(int keyCode) {
        return keyCode == KeyEvent.KEYCODE_MEDIA_PLAY
                || keyCode == KeyEvent.KEYCODE_MEDIA_PAUSE
                || keyCode == KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE
                || keyCode == KeyEvent.KEYCODE_HEADSETHOOK
                || keyCode == KeyEvent.KEYCODE_MEDIA_NEXT
                || keyCode == KeyEvent.KEYCODE_MEDIA_PREVIOUS
                || keyCode == KeyEvent.KEYCODE_MEDIA_STOP;
    }

    public void updateFromWebState(
            boolean playing,
            String title,
            String artist,
            String album,
            String coverUrl,
            long durationMs,
            long positionMs
    ) {
        boolean wasPlaying = this.isPlaying;
        this.isPlaying = playing;
        this.currentTitle = (title != null && !title.isEmpty()) ? title : "BahonIQ Music";
        this.currentArtist = (artist != null && !artist.isEmpty()) ? artist : "Музыка ДИТ";
        this.currentAlbum = (album != null && !album.isEmpty()) ? album : "BahonIQ Music";
        this.currentDurationMs = Math.max(0L, durationMs);
        this.currentPositionMs = Math.max(0L, positionMs);

        if (playing && !wasPlaying) {
            requestAudioFocus();
            acquireWakeLock();
        } else if (!playing && wasPlaying) {
            releaseWakeLock();
        }

        if (mediaSession != null && !mediaSession.isActive()) {
            mediaSession.setActive(true);
        }

        updatePlaybackState(playing, this.currentPositionMs);
        updateMetadata();
        refreshNotification();

        if (coverUrl != null && !coverUrl.isEmpty() && !coverUrl.equals(cachedCoverUrl)) {
            fetchCoverAsync(coverUrl);
        }
    }

    private void dispatchToWeb(String action, @Nullable Double seekSeconds, boolean isFocusEvent) {
        mainHandler.post(() -> {
            if (commandListener != null) {
                commandListener.onMediaCommand(action, seekSeconds, isFocusEvent);
            }
        });
    }

    private boolean requestAudioFocus() {
        if (audioManager == null) return true;
        if (hasAudioFocus) return true;
        int res;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            AudioAttributes attrs = new AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                    .build();
            audioFocusRequest = new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN)
                    .setAudioAttributes(attrs)
                    .setAcceptsDelayedFocusGain(true)
                    .setWillPauseWhenDucked(false)
                    .setOnAudioFocusChangeListener(audioFocusListener, mainHandler)
                    .build();
            res = audioManager.requestAudioFocus(audioFocusRequest);
        } else {
            res = audioManager.requestAudioFocus(
                    audioFocusListener,
                    AudioManager.STREAM_MUSIC,
                    AudioManager.AUDIOFOCUS_GAIN
            );
        }
        hasAudioFocus = (res == AudioManager.AUDIOFOCUS_REQUEST_GRANTED);
        return hasAudioFocus;
    }

    private void abandonAudioFocus() {
        hasAudioFocus = false;
        if (audioManager == null) return;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && audioFocusRequest != null) {
            audioManager.abandonAudioFocusRequest(audioFocusRequest);
        } else {
            audioManager.abandonAudioFocus(audioFocusListener);
        }
    }

    private void updatePlaybackState(boolean playing, long positionMs) {
        if (mediaSession == null) return;
        long actions = PlaybackStateCompat.ACTION_PLAY
                | PlaybackStateCompat.ACTION_PAUSE
                | PlaybackStateCompat.ACTION_PLAY_PAUSE
                | PlaybackStateCompat.ACTION_SKIP_TO_NEXT
                | PlaybackStateCompat.ACTION_SKIP_TO_PREVIOUS
                | PlaybackStateCompat.ACTION_STOP
                | PlaybackStateCompat.ACTION_SEEK_TO;
        int state = playing ? PlaybackStateCompat.STATE_PLAYING : PlaybackStateCompat.STATE_PAUSED;
        PlaybackStateCompat playbackState = new PlaybackStateCompat.Builder()
                .setActions(actions)
                .setState(state, positionMs, playing ? 1.0f : 0.0f, SystemClock.elapsedRealtime())
                .build();
        mediaSession.setPlaybackState(playbackState);
    }

    private void updateMetadata() {
        if (mediaSession == null) return;
        MediaMetadataCompat.Builder builder = new MediaMetadataCompat.Builder()
                .putString(MediaMetadataCompat.METADATA_KEY_TITLE, currentTitle)
                .putString(MediaMetadataCompat.METADATA_KEY_ARTIST, currentArtist)
                .putString(MediaMetadataCompat.METADATA_KEY_ALBUM, currentAlbum)
                .putLong(MediaMetadataCompat.METADATA_KEY_DURATION, currentDurationMs);
        if (cachedCoverBitmap != null) {
            builder.putBitmap(MediaMetadataCompat.METADATA_KEY_ALBUM_ART, cachedCoverBitmap);
        }
        mediaSession.setMetadata(builder.build());
    }

    private void fetchCoverAsync(String coverUrl) {
        currentCoverUrl = coverUrl;
        artworkExecutor.execute(() -> {
            if (!coverUrl.startsWith("https://") && !coverUrl.startsWith("http://")) {
                return;
            }
            HttpURLConnection conn = null;
            try {
                URL url = new URL(coverUrl);
                conn = (HttpURLConnection) url.openConnection();
                conn.setConnectTimeout(4000);
                conn.setReadTimeout(4000);
                conn.setInstanceFollowRedirects(true);
                if (conn.getResponseCode() == HttpURLConnection.HTTP_OK) {
                    try (InputStream is = conn.getInputStream()) {
                        Bitmap bmp = BitmapFactory.decodeStream(is);
                        if (bmp != null) {
                            mainHandler.post(() -> {
                                if (coverUrl.equals(currentCoverUrl)) {
                                    cachedCoverUrl = coverUrl;
                                    cachedCoverBitmap = bmp;
                                    updateMetadata();
                                    refreshNotification();
                                }
                            });
                        }
                    }
                }
            } catch (Exception ignored) {
            } finally {
                if (conn != null) conn.disconnect();
            }
        });
    }

    private void refreshNotification() {
        Intent openIntent = new Intent(this, MainActivity.class);
        openIntent.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent contentIntent = PendingIntent.getActivity(
                this,
                0,
                openIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        PendingIntent prevIntent = serviceActionIntent(ACTION_BRIDGE_PREV, 1);
        PendingIntent playPauseIntent = serviceActionIntent(isPlaying ? ACTION_BRIDGE_PAUSE : ACTION_BRIDGE_PLAY, 2);
        PendingIntent nextIntent = serviceActionIntent(ACTION_BRIDGE_NEXT, 3);
        PendingIntent stopIntent = serviceActionIntent(ACTION_BRIDGE_STOP, 4);

        NotificationCompat.Builder builder = new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle(currentTitle)
                .setContentText(currentArtist)
                .setSubText(currentAlbum)
                .setSmallIcon(R.mipmap.ic_launcher)
                .setLargeIcon(cachedCoverBitmap)
                .setContentIntent(contentIntent)
                .setDeleteIntent(stopIntent)
                .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
                .setOnlyAlertOnce(true)
                .setOngoing(isPlaying)
                .addAction(android.R.drawable.ic_media_previous, "Previous", prevIntent)
                .addAction(
                        isPlaying ? android.R.drawable.ic_media_pause : android.R.drawable.ic_media_play,
                        isPlaying ? "Pause" : "Play",
                        playPauseIntent
                )
                .addAction(android.R.drawable.ic_media_next, "Next", nextIntent)
                .setStyle(new MediaStyle()
                        .setMediaSession(mediaSession.getSessionToken())
                        .setShowActionsInCompactView(0, 1, 2));

        Notification notification = builder.build();
        if (isPlaying) {
            startForeground(NOTIFICATION_ID, notification);
        } else {
            stopForegroundCompat(false);
            NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm != null) {
                nm.notify(NOTIFICATION_ID, notification);
            }
        }
    }

    private PendingIntent serviceActionIntent(String action, int requestCode) {
        Intent intent = new Intent(this, MediaPlaybackService.class);
        intent.setAction(action);
        return PendingIntent.getService(
                this,
                requestCode,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID,
                    "BahonIQ Music",
                    NotificationManager.IMPORTANCE_LOW
            );
            channel.setDescription("Управление воспроизведением музыки и радио");
            channel.setShowBadge(false);
            NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm != null) {
                nm.createNotificationChannel(channel);
            }
        }
    }

    private void acquireWakeLock() {
        try {
            if (wakeLock != null && !wakeLock.isHeld()) {
                wakeLock.acquire(4 * 60 * 60 * 1000L);
            }
        } catch (Exception ignored) {
        }
    }

    private void releaseWakeLock() {
        try {
            if (wakeLock != null && wakeLock.isHeld()) {
                wakeLock.release();
            }
        } catch (Exception ignored) {
        }
    }

    private void stopForegroundCompat(boolean removeNotification) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            stopForeground(removeNotification ? STOP_FOREGROUND_REMOVE : STOP_FOREGROUND_DETACH);
        } else {
            stopForeground(removeNotification);
        }
    }

    @Override
    public void onDestroy() {
        releaseWakeLock();
        abandonAudioFocus();
        if (mediaSession != null) {
            mediaSession.setActive(false);
            mediaSession.release();
        }
        artworkExecutor.shutdownNow();
        super.onDestroy();
    }
}
