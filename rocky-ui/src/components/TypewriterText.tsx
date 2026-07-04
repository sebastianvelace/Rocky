"use client";

import { useEffect, useRef, useState } from "react";

const CHAR_INTERVAL_MS = 16;

/**
 * Revela el texto carácter a carácter con cursor de bloque, como una
 * terminal real. `animate=false` lo muestra completo de inmediato
 * (mensajes históricos).
 */
export function TypewriterText({ text, animate }: { text: string; animate: boolean }) {
  const [visible, setVisible] = useState(animate ? 0 : text.length);
  const done = visible >= text.length;
  const textRef = useRef(text);

  useEffect(() => {
    if (textRef.current !== text) {
      // Nuevo texto en el mismo slot: reiniciar solo si toca animar.
      textRef.current = text;
      setVisible(animate ? 0 : text.length);
    }
  }, [text, animate]);

  useEffect(() => {
    if (!animate || done) return;
    const interval = setInterval(() => {
      setVisible((v) => Math.min(v + 1, text.length));
    }, CHAR_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [animate, done, text.length]);

  return (
    <span>
      {text.slice(0, visible)}
      {animate && !done ? <span className="rocky-caret" aria-hidden /> : null}
    </span>
  );
}
