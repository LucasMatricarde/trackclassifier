import { useCallback, useEffect, useRef, useState } from "react";
import { getAudioUrl } from "../api/client";

/**
 * Player de áudio baseado em HTMLAudioElement.
 *
 * Espelha BasePlayer (player.py): load/play/pause/seek/setVolume,
 * eventos positionChanged/durationChanged/playingChanged/trackFinished.
 * O endpoint /api/audio/:sha1 suporta Range, então seek funciona nativo.
 */
export function useAudioPlayer() {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [positionMs, setPositionMs] = useState(0);
  const [durationMs, setDurationMs] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [loadedSha1, setLoadedSha1] = useState<string | null>(null);
  const rafRef = useRef<number>(0);

  // Garante um único <audio>
  useEffect(() => {
    const audio = new Audio();
    audio.preload = "auto";
    audioRef.current = audio;

    const onTimeUpdate = () => setPositionMs(audio.currentTime * 1000);
    const onDurationChange = () =>
      setDurationMs(audio.duration * 1000 || 0);
    const onPlay = () => setIsPlaying(true);
    const onPause = () => setIsPlaying(false);
    const onEnded = () => setIsPlaying(false);

    audio.addEventListener("timeupdate", onTimeUpdate);
    audio.addEventListener("durationchange", onDurationChange);
    audio.addEventListener("play", onPlay);
    audio.addEventListener("pause", onPause);
    audio.addEventListener("ended", onEnded);

    return () => {
      cancelAnimationFrame(rafRef.current);
      audio.pause();
      audio.src = "";
      audio.removeEventListener("timeupdate", onTimeUpdate);
      audio.removeEventListener("durationchange", onDurationChange);
      audio.removeEventListener("play", onPlay);
      audio.removeEventListener("pause", onPause);
      audio.removeEventListener("ended", onEnded);
    };
  }, []);

  // Atualiza posição via rAF para playhead suave (60fps)
  useEffect(() => {
    if (!isPlaying) return;
    const tick = () => {
      if (audioRef.current) {
        setPositionMs(audioRef.current.currentTime * 1000);
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [isPlaying]);

  const load = useCallback((sha1: string, durationMsHint: number) => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.src = getAudioUrl(sha1);
    audio.load();
    setLoadedSha1(sha1);
    // Usa a duração da análise até o browser descobrir a real
    setDurationMs(durationMsHint);
    setPositionMs(0);
  }, []);

  const play = useCallback(() => {
    audioRef.current?.play().catch(() => {});
  }, []);

  const pause = useCallback(() => {
    audioRef.current?.pause();
  }, []);

  const toggle = useCallback(() => {
    if (audioRef.current?.paused) {
      play();
    } else {
      pause();
    }
  }, [play, pause]);

  const seek = useCallback((ms: number) => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = ms / 1000;
    setPositionMs(ms);
  }, []);

  const seekFraction = useCallback(
    (fraction: number) => {
      if (durationMs > 0) {
        seek(Math.max(0, Math.min(1, fraction)) * durationMs);
      }
    },
    [durationMs, seek]
  );

  const setVolume = useCallback((v: number) => {
    if (audioRef.current) {
      audioRef.current.volume = Math.max(0, Math.min(1, v));
    }
  }, []);

  return {
    positionMs,
    durationMs,
    isPlaying,
    loadedSha1,
    load,
    play,
    pause,
    toggle,
    seek,
    seekFraction,
    setVolume,
  };
}
