"use client";

import { memo } from "react";
import type { VoiceState } from "../hooks/useRocky";

type Props = {
  state: VoiceState;
  alerting?: boolean;
  size?: number;
};

/**
 * Avatar animado de Rocky. Cada estado del pipeline tiene su gesto:
 *  - idle      → respiración suave + parpadeo ocasional
 *  - listening → anillos de sonar expandiéndose
 *  - thinking  → anillo giratorio + ojos escaneando
 *  - speaking  → boca ecualizador
 *  - error     → tinte rojo, boca plana
 *  - alerting  → sacudida + anillo rojo (sobrescribe el resto)
 */
function RockyAvatarBase({ state, alerting = false, size = 48 }: Props) {
  const accent = alerting
    ? "var(--color-alert)"
    : state === "error"
      ? "var(--color-alert)"
      : "var(--color-accent)";

  const listening = !alerting && state === "listening";
  const thinking = !alerting && (state === "thinking" || state === "transcribing");
  const speaking = !alerting && state === "speaking";
  const idle = !alerting && (state === "idle" || state === "error");

  return (
    <svg
      viewBox="0 0 100 100"
      width={size}
      height={size}
      className={`rocky-avatar ${alerting ? "avatar-shake" : ""}`}
      role="img"
      aria-label={`Rocky: ${state}${alerting ? " (alerta)" : ""}`}
    >
      {/* Anillos de sonar (escuchando) */}
      {listening ? (
        <>
          <circle cx="50" cy="50" r="44" fill="none" stroke={accent} strokeWidth="2" className="avatar-ping" />
          <circle cx="50" cy="50" r="44" fill="none" stroke={accent} strokeWidth="2" className="avatar-ping-late" />
        </>
      ) : null}

      {/* Anillo giratorio (pensando) */}
      {thinking ? (
        <circle
          cx="50"
          cy="50"
          r="44"
          fill="none"
          stroke={accent}
          strokeWidth="2.5"
          strokeDasharray="20 15"
          strokeLinecap="round"
          className="avatar-spin"
        />
      ) : (
        <circle
          cx="50"
          cy="50"
          r="44"
          fill="none"
          stroke={accent}
          strokeWidth="2"
          opacity={alerting || speaking ? 0.9 : 0.35}
          className={idle ? "avatar-breath" : undefined}
        />
      )}

      {/* Antena */}
      <line x1="50" y1="18" x2="50" y2="27" stroke={accent} strokeWidth="2.5" strokeLinecap="round" />
      <circle
        cx="50"
        cy="15"
        r="3.2"
        fill={accent}
        className={idle ? "avatar-breath" : undefined}
      />

      {/* Cabeza */}
      <rect
        x="26"
        y="28"
        width="48"
        height="44"
        rx="10"
        fill="var(--color-panel-2)"
        stroke="var(--color-edge-bright)"
        strokeWidth="1.5"
      />

      {/* Ojos */}
      <g className={thinking ? "avatar-scan" : undefined}>
        <rect x="36" y="41" width="8" height="11" rx="2.5" fill={accent} className={idle ? "avatar-eye" : undefined} />
        <rect x="56" y="41" width="8" height="11" rx="2.5" fill={accent} className={idle ? "avatar-eye" : undefined} />
      </g>

      {/* Boca */}
      {speaking ? (
        <g>
          {[38, 43.5, 49, 54.5, 60].map((x, i) => (
            <rect
              key={x}
              x={x}
              y="56"
              width="3"
              height="10"
              rx="1.5"
              fill={accent}
              className="avatar-eq"
              style={{ animationDelay: `${i * 0.11}s` }}
            />
          ))}
        </g>
      ) : (
        <rect
          x="41"
          y="60"
          width="18"
          height="3"
          rx="1.5"
          fill={accent}
          opacity={state === "error" || alerting ? 1 : 0.7}
        />
      )}
    </svg>
  );
}

export const RockyAvatar = memo(RockyAvatarBase);
