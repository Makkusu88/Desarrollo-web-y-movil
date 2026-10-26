// Secretos (Vault), identidad del llamador e identidad del usuario.
import { createPublicKey, timingSafeEqual, verify } from 'node:crypto';

const VAULT_ADDR = process.env.VAULT_ADDR ?? 'http://127.0.0.1:8200';
const VAULT_TOKEN = process.env.VAULT_TOKEN;
const TTL_CACHE_MS = 60_000;
const MAX_ANTIGUEDAD_MS = 600_000;
const ROLES_VALIDOS = new Set(['cliente', 'staff', 'admin']);

let cache = null;
let leidoEn = 0;

export class SecretoNoDisponible extends Error {}

export async function secretos() {
  if (!VAULT_TOKEN) throw new SecretoNoDisponible('VAULT_TOKEN no configurado');
  const ahora = Date.now();
  if (cache && ahora - leidoEn < TTL_CACHE_MS) return cache;
  try {
    const r = await fetch(`${VAULT_ADDR}/v1/secret/data/mrsandwich/graphql`, {
      headers: { 'X-Vault-Token': VAULT_TOKEN },
      signal: AbortSignal.timeout(3000),
    });
    if (!r.ok) throw new Error(`Vault ${r.status}`);
    cache = (await r.json()).data.data;
    leidoEn = ahora;
  } catch (err) {
    if (!cache || ahora - leidoEn > MAX_ANTIGUEDAD_MS) throw new SecretoNoDisponible('Gestor de secretos no disponible');
  }
  return cache;
}

function igualSeguro(a, b) {
  const x = Buffer.from(a ?? '');
  const y = Buffer.from(b ?? '');
  return x.length === y.length && timingSafeEqual(x, y);
}

// Solo el API Gateway puede invocar este servicio.
export function llamadorAutorizado(headers, s) {
  return headers['x-service-id'] === 'gateway' && igualSeguro(headers['x-service-secret'], s.in_gateway);
}

// Verifica el contexto de identidad firmado por el API Gateway (Ed25519).
export function verificarIdentidad(headers, s) {
  const carga = headers['x-identity'];
  const firma = headers['x-identity-sig'];
  if (!carga || !firma) return null;
  const clave = createPublicKey(s.identity_public_key);
  if (!verify(null, Buffer.from(carga), clave, Buffer.from(firma, 'base64url'))) return null;
  const ctx = JSON.parse(Buffer.from(carga, 'base64url').toString());
  if (!ctx.exp || ctx.exp * 1000 < Date.now()) return null;
  return {
    userId: ctx.sub,
    roles: (ctx.roles ?? []).filter((r) => ROLES_VALIDOS.has(r)),
    // Se reenvían las mismas cabeceras firmadas: este servicio no puede emitir identidades.
    cabeceras: { 'X-Identity': carga, 'X-Identity-Sig': firma },
  };
}
