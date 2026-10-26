import { useCallback, useEffect, useRef, useState } from "react";
import { getAudioUrl } from "../api/client";

/**
 * Player de áudio baseado em HTMLAudioElement.
 *
 * Espelha BasePlayer (player.py): load/play/pause/seek/setVolume,
 * eventos positionChanged/durationChanged/playingChanged/trackFinished.
 * O endpoint /api/audio/:sha1 suporta Range, então seek funciona nativo.
 */
/**
 * Shape devolvido por useAudioPlayer. Ficou num `type` separado para o
 * LibraryTab poder elevar o player e compartilhar entre a barra de transporte
 * e o play do inspetor (mockup: os dois acesos, mesmo estado).
 */
export type AudioPlayer = {
  positionMs: number;
  durationMs: number;
  isPlaying: boolean;
  loadedSha1: string | null;
  load: (sha1: string, durationMsHint: number) => void;
  play: () => void;
  pause: () => void;
  toggle: () => void;
  seek: (ms: number) => void;
  seekFraction: (fraction: number) => void;
  /** Volume do <audio>, 0..1. Estado do hook: o VolumeRail e controlado por ele. */
  volume: number;
  setVolume: (v: number) => void;
  loop: boolean;
  setLoop: (ligado: boolean) => void;
  rate: number;
  cycleRate: () => void;
};

/** Volume inicial do player (o trilho do mockup nasce em 80%). */
export const DEFAULT_VOLUME = 0.8;

/** Velocidades do chip do player (mockup mostra "1x"). */
export const PLAYBACK_RATES = [0.75, 1, 1.25, 1.5] as const;

export function useAudioPlayer(): AudioPlayer {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [positionMs, setPositionMs] = useState(0);
  const [durationMs, setDurationMs] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [loadedSha1, setLoadedSha1] = useState<string | null>(null);
  const [loop, setLoopState] = useState(false);
  const [rate, setRate] = useState(1);
  const [volume, setVolumeState] = useState(DEFAULT_VOLUME);
  // Espelho do estado para o load() reaplicar o volume sem depender dele: se
  // load() dependesse de `volume`, a identidade dele mudaria a cada arrasto do
  // trilho e o useEffect do LibraryTransport (que chama load) re-dispararia.
  const volumeRef = useRef(DEFAULT_VOLUME);
  const rafRef = useRef<number>(0);

  // Garante um único <audio>
  useEffect(() => {
    const audio = new Audio();
    audio.preload = "auto";
    // O <audio> nasce em 1.0, mas o trilho mostra DEFAULT_VOLUME: sem isto o
    // som sairia mais alto do que a tela diz ate o primeiro clique no trilho.
    audio.volume = volumeRef.current;
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
    // Reaplica o volume: o <audio> e recarregado a cada track e nao ha garantia
    // entre navegadores de que o volume sobreviva ao algoritmo de carga.
    audio.volume = volumeRef.current;
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
    const limitado = Math.max(0, Math.min(1, v));
    volumeRef.current = limitado;
    if (audioRef.current) audioRef.current.volume = limitado;
    setVolumeState(limitado);
  }, []);

  const setLoop = useCallback((ligado: boolean) => {
    if (audioRef.current) audioRef.current.loop = ligado;
    setLoopState(ligado);
  }, []);

  // defaultPlaybackRate junto com playbackRate: o `audio.src = ...` de load()
  // roda o algoritmo de carga do elemento, que devolve o playbackRate ao
  // default -- sem isso a velocidade escolhida voltava a 1x a cada track.
  const cycleRate = useCallback(() => {
    const proxima =
      PLAYBACK_RATES[(PLAYBACK_RATES.indexOf(rate as (typeof PLAYBACK_RATES)[number]) + 1) % PLAYBACK_RATES.length];
    if (audioRef.current) {
      audioRef.current.defaultPlaybackRate = proxima;
      audioRef.current.playbackRate = proxima;
    }
    setRate(proxima);
  }, [rate]);

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
    volume,
    setVolume,
    loop,
    setLoop,
    rate,
    cycleRate,
  };
}
