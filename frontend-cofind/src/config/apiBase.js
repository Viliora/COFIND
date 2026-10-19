/**
 * URL dasar backend Flask.
 *
 * Development: default same-origin + proxy Vite (/api → 127.0.0.1:5000) supaya
 * rekomendasi LLM tidak mengarah ke deploy Railway lama dari salinan .env production.
 * Set VITE_API_BASE=http://localhost:5000 untuk langsung ke Flask, atau
 * VITE_USE_REMOTE_API=true + VITE_API_BASE=<url> untuk uji remote dari dev.
 */
const envBase = (import.meta.env.VITE_API_BASE || '').trim();
const forceRemote = import.meta.env.VITE_USE_REMOTE_API === 'true';

function devApiBase() {
  if (forceRemote && envBase) return envBase;
  if (
    envBase.startsWith('http://localhost:')
    || envBase.startsWith('http://127.0.0.1:')
  ) {
    return envBase;
  }
  return '';
}

export const API_BASE = import.meta.env.DEV
  ? devApiBase()
  : (envBase || 'http://localhost:5000');
