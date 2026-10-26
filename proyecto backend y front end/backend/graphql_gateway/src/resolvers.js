// Resolvers. La autorización se aplica por operación (Query) y por campo
// sensible; además cada subsistema vuelve a verificar la identidad recibida.
import { GraphQLError } from 'graphql';

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

function exigirSesion(ctx) {
  if (!ctx.identidad) throw new GraphQLError('Autenticación requerida', { extensions: { code: 'UNAUTHENTICATED' } });
}

function tieneRol(ctx, ...roles) {
  return roles.some((r) => ctx.identidad?.roles.includes(r));
}

function exigirRol(ctx, ...roles) {
  exigirSesion(ctx);
  if (!tieneRol(ctx, ...roles)) throw new GraphQLError('Permiso insuficiente', { extensions: { code: 'FORBIDDEN' } });
}

function paginacion(pagina, tamano, maximo) {
  if (!Number.isInteger(pagina) || pagina < 1 || !Number.isInteger(tamano) || tamano < 1 || tamano > maximo) {
    throw new GraphQLError(`Paginación inválida (pagina >= 1, 1 <= tamano <= ${maximo})`, { extensions: { code: 'BAD_USER_INPUT' } });
  }
  return { limit: tamano, offset: (pagina - 1) * tamano };
}

// DTO de orders -> tipo GraphQL. Solo se copian los campos del schema.
function aResumen(p) {
  return {
    id: p.id, estado: p.estado, tipoEntrega: p.tipo_entrega, creadoEn: p.creado_en, actualizadoEn: p.actualizado_en,
    expiraEn: p.expira_en, subtotal: p.subtotal, costoEnvio: p.costo_envio, total: p.total, notas: p.notas,
    requiereReembolso: p.requiere_reembolso ?? false,
    items: p.items.map((i) => ({
      productoId: i.product_id, nombre: i.nombre, opcion: i.opcion, extras: i.extras, cantidad: i.qty,
      precioUnitario: i.precio_unitario, totalLinea: i.total_linea,
    })),
    historial: p.historial.map((h) => ({ estado: h.estado, en: h.en, motivo: h.motivo ?? null })),
    _direccion: p.direccion ?? null,
    _contacto: p.contacto ?? null,
  };
}

export const resolvers = {
  Query: {
    async resumenPedido(_, { id }, ctx) {
      exigirSesion(ctx);
      if (!/^PED-[A-F0-9]{8}$/.test(id)) throw new GraphQLError('Identificador inválido', { extensions: { code: 'BAD_USER_INPUT' } });
      // orders aplica la regla de propiedad: un pedido ajeno responde 404.
      return aResumen(await ctx.llamar('orders', 'GET', `/orders/${id}`));
    },

    async misPedidos(_, { pagina, tamano }, ctx) {
      exigirSesion(ctx);
      const { limit, offset } = paginacion(pagina, tamano, 10);
      const r = await ctx.llamar('orders', 'GET', '/orders/me', { query: { limit, offset } });
      return { items: r.items.map(aResumen), pagina, tamano, total: r.total };
    },

    async pedidosLocal(_, { estado, pagina, tamano }, ctx) {
      exigirRol(ctx, 'staff', 'admin');
      const { limit, offset } = paginacion(pagina, tamano, 20);
      const r = await ctx.llamar('orders', 'GET', '/orders', { query: { estado, limit, offset } });
      return { items: r.items.map(aResumen), pagina, tamano, total: r.total };
    },

    async panelAdmin(_, { desde, hasta }, ctx) {
      exigirRol(ctx, 'admin');
      for (const f of [desde, hasta]) {
        if (f && !DATE_RE.test(f)) throw new GraphQLError('Fecha inválida (AAAA-MM-DD)', { extensions: { code: 'BAD_USER_INPUT' } });
      }
      return { desde, hasta };
    },
  },

  ResumenPedido: {
    // Se usa DataLoader: todos los pedidos de una página se consultan en una sola llamada.
    pago: (p, _, ctx) => ctx.loaders.pago.load(p.id),
    direccionEntrega(p) {
      // orders solo devuelve pedidos que la identidad puede ver (propios o staff),
      // por lo que la dirección llega únicamente a su dueño o al personal.
      return p._direccion;
    },
    contacto(p, _, ctx) {
      if (!tieneRol(ctx, 'staff', 'admin')) {
        if (p._contacto) throw new GraphQLError('Campo restringido', { extensions: { code: 'FORBIDDEN', campo: 'contacto' } });
        return null;
      }
      return p._contacto;
    },
  },

  LineaPedido: {
    producto: (l, _, ctx) => ctx.loaders.producto.load(l.productoId),
  },

  PanelAdmin: {
    async ventas(panel, _, ctx) {
      const r = await ctx.llamar('analytics', 'GET', '/reports/sales', { query: { desde: panel.desde, hasta: panel.hasta } });
      return {
        desde: r.desde, hasta: r.hasta, totalVentas: r.total_ventas, pedidosPagados: r.pedidos_pagados,
        ticketPromedio: r.ticket_promedio, clientesDistintos: r.clientes_distintos, porDia: r.por_dia,
        topProductos: r.top_productos.map((t) => ({ productId: t.product_id, nombre: t.nombre, unidades: t.unidades, ventas: t.ventas })),
        porEstado: r.por_estado, porTipoEntrega: r.por_tipo_entrega, actualizadoEn: r.actualizado_en,
      };
    },
    async stockBajo(_, __, ctx) {
      const r = await ctx.llamar('inventory', 'GET', '/internal/low-stock');
      return r.map((p) => ({ id: p.id, nombre: p.nombre, stock: p.stock, stockMinimo: p.stock_minimo }));
    },
  },
};
