// GraphQL Gateway privado. Escucha solo en 127.0.0.1 y rechaza cualquier
// solicitud que no traiga la credencial del API Gateway.
import { readFileSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
import { ApolloServer } from '@apollo/server';
import { startStandaloneServer } from '@apollo/server/standalone';
import DataLoader from 'dataloader';
import { GraphQLError } from 'graphql';

import { pluginLimites } from './limites.js';
import { resolvers } from './resolvers.js';
import { llamadorAutorizado, secretos, SecretoNoDisponible, verificarIdentidad } from './seguridad.js';
import { crearCliente } from './subsistemas.js';

const PUERTO = Number(process.env.GRAPHQL_PORT ?? 4000);
const typeDefs = readFileSync(new URL('./schema.graphql', import.meta.url), 'utf8');
const CODIGOS_VISIBLES = new Set([
  'UNAUTHENTICATED', 'FORBIDDEN', 'NOT_FOUND', 'BAD_USER_INPUT', 'DEPENDENCY_UNAVAILABLE',
  'QUERY_TOO_DEEP', 'QUERY_TOO_COSTLY', 'GRAPHQL_VALIDATION_FAILED', 'GRAPHQL_PARSE_FAILED',
]);

function log(evento, campos) {
  console.log(JSON.stringify({ ts: new Date().toISOString(), servicio: 'graphql', evento, ...campos }));
}

function crearLoaders(llamar) {
  return {
    producto: new DataLoader(async (ids) => {
      const lista = await llamar('inventory', 'POST', '/internal/products/batch', { body: { ids: [...new Set(ids)] } });
      const porId = new Map(lista.map((p) => [p.id, p]));
      return ids.map((id) => porId.get(id) ?? null);
    }),
    pago: new DataLoader(async (orderIds) => {
      const lista = await llamar('payments', 'GET', '/internal/payments/by-orders', { query: { ids: orderIds.join(',') } });
      const porPedido = new Map(lista.map((p) => [p.order_id, { estado: p.estado, comprobante: p.comprobante }]));
      return orderIds.map((id) => porPedido.get(id) ?? null);
    }),
  };
}

const servidor = new ApolloServer({
  typeDefs,
  resolvers,
  introspection: process.env.GRAPHQL_INTROSPECTION === 'true',
  allowBatchedHttpRequests: false,
  plugins: [
    pluginLimites(),
    {
      async requestDidStart({ contextValue }) {
        const inicio = Date.now();
        return {
          async willSendResponse({ response, operationName }) {
            const errores = response.body.kind === 'single' ? response.body.singleResult.errors?.length ?? 0 : 0;
            log('operacion', { request_id: contextValue.requestId, operacion: operationName ?? null, errores, ms: Date.now() - inicio });
          },
        };
      },
    },
  ],
  // Mensajes controlados: nunca se exponen trazas ni detalles internos.
  formatError(formatted) {
    const code = formatted.extensions?.code;
    if (CODIGOS_VISIBLES.has(code)) {
      return { message: formatted.message, path: formatted.path, extensions: { code, ...(formatted.extensions?.subsistema ? { subsistema: formatted.extensions.subsistema } : {}) } };
    }
    return { message: 'Error interno', path: formatted.path, extensions: { code: 'INTERNAL_SERVER_ERROR' } };
  },
});

const { url } = await startStandaloneServer(servidor, {
  listen: { port: PUERTO, host: '127.0.0.1' },
  async context({ req }) {
    const requestId = /^[A-Za-z0-9-]{8,64}$/.test(req.headers['x-request-id'] ?? '') ? req.headers['x-request-id'] : randomUUID();
    let s;
    try {
      s = await secretos();
    } catch (err) {
      if (err instanceof SecretoNoDisponible) {
        throw new GraphQLError('Configuración segura no disponible', { extensions: { code: 'DEPENDENCY_UNAVAILABLE', http: { status: 503 } } });
      }
      throw err;
    }
    if (!llamadorAutorizado(req.headers, s)) {
      log('llamador_rechazado', { request_id: requestId });
      throw new GraphQLError('Componente no autorizado', { extensions: { code: 'FORBIDDEN', http: { status: 403 } } });
    }
    let identidad = null;
    try {
      identidad = verificarIdentidad(req.headers, s);
    } catch {
      identidad = null;
    }
    const ctx = { requestId, secretos: s, identidad };
    ctx.llamar = crearCliente(ctx);
    ctx.loaders = crearLoaders(ctx.llamar);
    return ctx;
  },
});

log('inicio', { url });
