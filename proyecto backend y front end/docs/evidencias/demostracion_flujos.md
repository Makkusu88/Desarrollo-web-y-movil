# Demostración de los flujos principales
Fecha: 2026-11-04 17:01:46. Sistema iniciado con: python run_all.py --reset
Todas las solicitudes pasan por el API Gateway (puerto 8000), salvo el paso 9, que intenta saltárselo.
Los tokens no se muestran.

## 1. Visitante consulta el catálogo sin iniciar sesión (RF01, P01, S01)
  [visitante] GET /products -> 200  (request_id 1ca29bac1700)  11 productos; campos: ['categoria', 'descripcion', 'disponible', 'id', 'imagen', 'nombre', 'precio']
  [visitante] GET /products/2 -> 200  (request_id 6fa637d9aa23)  Barros Luco $5490

## 2. Sin sesión no se puede ver un pedido (RF08, S17)
  [visitante] GET /orders/me -> 401  (request_id 84a6c15f33e6)  Autenticación requerida

## 3. Inicio de sesión (RF03, P03, S04)
  [ana] POST /auth/login -> 200  (request_id e9a5c4f24dd8)  roles=['cliente']
  [pedro] POST /auth/login -> 200  (request_id 74007ab88168)  roles=['cliente']
  [cocina] POST /auth/login -> 200  (request_id 0c927e7302c3)  roles=['staff']
  [admin] POST /auth/login -> 200  (request_id 886092d4856d)  roles=['admin']

## 4. Cotización calculada en el servidor (RF05, P05, S15)
  [visitante] POST /orders/quote -> 200  (request_id 0efc6124ab13)  precio unitario oficial $6190, subtotal $12380
  [visitante] POST /orders/quote (enviando precio_unitario=1) -> 200  (request_id df9d223353f6)  el servidor ignora el precio enviado: subtotal $12380

## 5. Pedido con delivery (RF06, P05, S16)
  [ana] POST /orders -> 201  (request_id f2ae21ab31e0)  pedido PED-5CDDFDDF estado PENDIENTE_PAGO total $14370

## 6. Pago con el proveedor de prueba (RF07, P06, S22, S24)
  [ana] POST /payments -> 201  (request_id c76b3abb3c57)  pago PAY-D6217FE15B estado INICIADO
  [proveedor] aprueba el pago -> 303 (envía el webhook firmado a /payments/webhook)
  [ana] GET /payments/order/PED-5CDDFDDF -> 200  (request_id ae932be3168b)  pago APROBADO comprobante CMP-2026-000001
  estado del pedido: PAGADO

## 7. Pedido propio permitido y pedido ajeno denegado (RF08, P06, S18; misma regla de propiedad en orders)
  [ana] GET /orders/PED-5CDDFDDF -> 200  (request_id 3424c96a4c34)  dueña: ve estado PAGADO y dirección Calle Falsa
  [pedro] GET /orders/PED-5CDDFDDF -> 404  (request_id 9b4fea07d960)  otra cuenta: 'Pedido no encontrado'; ¿la respuesta incluye datos del pedido? False
  [pedro] GraphQL resumenPedido -> data=None error=NOT_FOUND
  [cocina] GET /orders/PED-5CDDFDDF -> 200  (request_id 51ad17156462)  el personal sí lo ve, porque lo tiene que despachar

## 8. El personal despacha el pedido (RF10, P09, S21)
  [cocina] PUT /orders/PED-5CDDFDDF/status -> 200  (request_id 36bf8f1a488a)  EN_PREPARACION
  [cocina] PUT /orders/PED-5CDDFDDF/status -> 200  (request_id 571db87b9e5d)  LISTO
  [cocina] PUT /orders/PED-5CDDFDDF/status -> 200  (request_id 9502ed5292a2)  EN_REPARTO
  [cocina] PUT /orders/PED-5CDDFDDF/status -> 200  (request_id e5df6988ae90)  ENTREGADO
  [ana] PUT /orders/PED-5CDDFDDF/status -> 403  (request_id c7568d0d0e30)  un cliente no puede cambiar estados
  historial visto por ana: PENDIENTE_PAGO -> PAGADO -> EN_PREPARACION -> LISTO -> EN_REPARTO -> ENTREGADO

## 9. Acceso directo a un servicio privado sin pasar por el gateway (RF08)
  [navegador] GET http://127.0.0.1:8104/orders/PED-5CDDFDDF -> 403 {"error":{"codigo":403,"mensaje":"Componente no autorizado"}

## 10. Rol sin permiso (RF11, P09, S26)
  [ana] POST /admin/products -> 403  (request_id e6f75a660405)  Permiso insuficiente para esta operación

## 11. Reporte de ventas del administrador vía GraphQL y analytics (RF12, P09, S30)
  [admin] GraphQL panelAdmin -> pedidos pagados 1, total $14370, más vendido [{'nombre': 'Barros Luco', 'unidades': 2}]
  [ana]   GraphQL panelAdmin -> error FORBIDDEN

## 12. Cierre de sesión revoca el token (RF03, S05)
  [pedro] POST /auth/logout -> 200  (request_id 27eedab7d174)
  [pedro] GET /orders/me (con el token anterior) -> 401  (request_id b791c0f038ad)  Sesión inválida o expirada
