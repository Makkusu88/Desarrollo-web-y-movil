// Adaptadores REST hacia los microservicios privados. Cada llamada lleva la
// credencial servicio-a-servicio del destino, la identidad firmada del usuario y
// el X-Request-ID. Plazo máximo por llamada: 3 s.
import { GraphQLError } from 'graphql';

const URLS = {
  orders: process.env.URL_ORDERS ?? 'http://127.0.0.1:8104',
  inventory: process.env.URL_INVENTORY ?? 'http://127.0.0.1:8103',
  payments: process.env.URL_PAYMENTS ?? 'http://127.0.0.1:8105',
  analytics: process.env.URL_ANALYTICS ?? 'http://127.0.0.1:8106',
};
const PLAZO_MS = 3000;

export function crearCliente(ctx) {
  return async function llamar(destino, metodo, ruta, { query, body } = {}) {
    const url = new URL(ruta, URLS[destino]);
    for (const [k, v] of Object.entries(query ?? {})) if (v !== undefined && v !== null) url.searchParams.set(k, v);
    let resp;
    try {
      resp = await fetch(url, {
        method: metodo,
        headers: {
          'X-Service-Id': 'graphql',
          'X-Service-Secret': ctx.secretos[`out_${destino}`],
          'X-Request-ID': ctx.requestId,
          ...(ctx.identidad?.cabeceras ?? {}),
          ...(body ? { 'Content-Type': 'application/json' } : {}),
        },
        body: body ? JSON.stringify(body) : undefined,
        signal: AbortSignal.timeout(PLAZO_MS),
      });
    } catch {
      throw new GraphQLError(`Subsistema ${destino} no disponible`, { extensions: { code: 'DEPENDENCY_UNAVAILABLE', subsistema: destino } });
    }
    if (resp.status === 404) throw new GraphQLError('Recurso no encontrado', { extensions: { code: 'NOT_FOUND' } });
    if (resp.status === 401 || resp.status === 403) throw new GraphQLError('No autorizado', { extensions: { code: 'FORBIDDEN' } });
    if (resp.status === 400) throw new GraphQLError('Parámetros inválidos', { extensions: { code: 'BAD_USER_INPUT' } });
    if (!resp.ok) throw new GraphQLError(`Subsistema ${destino} no disponible`, { extensions: { code: 'DEPENDENCY_UNAVAILABLE', subsistema: destino } });
    return resp.json();
  };
}
