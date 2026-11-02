# Módulo 9 Analítica y comunicación gRPC

En este módulo revisamos si Mr. Sandwich necesita un servicio de analítica separado y si alguna comunicación interna justifica gRPC. Para decidirlo primero describimos la carga del sistema y después dejamos cada decisión en un ADR.

## 9.1 Caracterización de la carga

Separamos lo que medimos de lo que suponemos. Los valores marcados como **proyección** son supuestos del equipo para un local de sándwiches de tamaño mediano; los marcados como **medición** salen de la prueba de carga de la sección 9.7.

| Característica | Valor | Tipo |
|---|---|---|
| Volumen del catálogo | 11 productos en 4 categorías | Medición (datos de prueba) |
| Pedidos por día | Hasta 500 | Proyección |
| Pedidos en la hora punta (almuerzo) | Alrededor de 60 | Proyección |
| Usuarios navegando al mismo tiempo | 20 | Medición (concurrencia usada en la prueba) |
| Tamaño de una cotización | Hasta 20 productos por pedido y 10 unidades por producto; mensaje gRPC limitado a 64 KB | Medición (límites del código) |
| Frecuencia de cotización | Cada vez que el cliente cambia el carrito | Proyección |
| Latencia esperada (p95) | Catálogo 200 ms, cotización 300 ms, agregación GraphQL 500 ms | Objetivo del equipo |
| Datos para reportes | Un registro por pedido; con 500 pedidos al día son unos 15.000 al mes | Proyección |
| Necesidad de streaming | No hay flujos continuos: el seguimiento del pedido se consulta | Análisis de requisitos |

Con estos números concluimos que los reportes **no necesitan big data**. Un mes de pedidos cabe sin problema en una colección de MongoDB con índices, y las agregaciones se resuelven en milisegundos.

## 9.2 Matriz de necesidades

| Necesidad | Requisito | ¿Aplica? | Decisión | Componente |
|---|---|---|---|---|
| Reportes de ventas para el administrador | RF12 | Sí | Servicio de analítica privado, separado de los pedidos | `analytics_service` |
| Cotizar y reservar stock en cada pedido | RF05, RF06 | Sí | Comunicación interna gRPC entre orders e inventory | `proto/inventory.proto` |
| Mostrar el reporte en una pantalla | RF12, P09 | Sí | El GraphQL Gateway consulta a analytics | `panelAdmin.ventas` |
| Procesamiento big data | — | No | La carga proyectada no lo justifica | — |
| Streaming gRPC | RF08 | No | El estado del pedido se consulta; no hay eventos continuos | — |
| Mensajería asíncrona (por ejemplo STOMP) | — | No | Ningún requisito pide notificaciones | — |
| Eventos en tiempo real al navegador | RF08 | No | La pantalla de seguimiento consulta el pedido | — |

## 9.3 ADR-01 Servicio de analítica separado

**Contexto.** El administrador necesita ver ventas por día, productos más vendidos, pedidos por estado y por tipo de entrega (RF12). Si estos reportes se calcularan directo sobre la base de pedidos, una consulta pesada podría hacer más lenta la creación de pedidos, y el reporte tendría acceso a datos personales que no necesita.

**Alternativas.**

| Alternativa | Ventaja | Desventaja |
|---|---|---|
| A. Calcular el reporte dentro de orders | Datos siempre al día | Mezcla consultas de reporte con transacciones y expone datos personales |
| B. Servicio de analítica con copia periódica (ETL) | Separa la carga y permite quitar datos personales | El reporte tiene un pequeño retraso |
| C. Plataforma de big data | Escala a volúmenes muy grandes | Excesivo para unos miles de pedidos al mes |

**Elección.** Elegimos la alternativa **B**. `analytics_service` copia los pedidos cada 15 segundos desde orders y calcula los reportes sobre su propia base (`ms_analytics`).

**Consecuencias.**
- Los reportes no compiten con la creación de pedidos.
- El reporte puede tener hasta unos 15 segundos de retraso; lo aceptamos porque el administrador no necesita el dato al segundo. La respuesta incluye `actualizado_en` para que se vea desde cuándo está actualizado.
- Si orders no responde, el reporte sigue mostrando la última copia y se reintenta en el siguiente ciclo.
- Analytics no es autoridad de ningún dato: si se pierde su base, se reconstruye desde orders.

## 9.4 ADR-02 gRPC entre orders e inventory

**Contexto.** Cada vez que el cliente revisa el carrito o confirma un pedido, orders necesita que inventory calcule el precio oficial y reserve el stock. Es la comunicación interna más frecuente del sistema y tiene reglas estrictas: el precio no puede venir del navegador y una reserva no puede hacerse dos veces.

**Alternativas.**

| Alternativa | Ventaja | Desventaja |
|---|---|---|
| A. REST interno con JSON | Igual al resto de los servicios | Contrato sin tipos fijos; los errores se mapean a mano |
| B. gRPC unary con contrato `.proto` | Mensajes tipados, deadlines y códigos de error propios | Requiere generar código y manejar certificados |
| C. gRPC con streaming | Útil para flujos continuos | No hay un flujo continuo: cada cotización es una pregunta y una respuesta |

**Elección.** Elegimos la alternativa **B**: cuatro métodos unary (`QuoteItems`, `ReserveStock`, `ReleaseReservation` y `CommitReservation`).

**Consecuencias.**
- El contrato queda definido en `backend/proto/inventory.proto` y cualquier cambio se nota al generar el código.
- Usamos mTLS: inventory solo acepta clientes con un certificado de la CA interna, y además revisa que el nombre del certificado sea `orders` en cada método.
- Cada llamada tiene un plazo de 2 segundos. Si se cumple sin respuesta, orders responde 503 y no guarda el pedido.
- gRPC no se expone al navegador: el frontend solo habla con el API Gateway por HTTP.
- No usamos streaming porque ningún flujo lo necesita (ver 9.2).

## 9.5 Detalle del servicio de analítica

| Aspecto | Cómo lo resolvimos |
|---|---|
| Origen de datos | `GET /internal/orders-export` de orders, que solo acepta llamadas de analytics |
| Actualización | Copia incremental cada 15 segundos, en lotes de hasta 500 pedidos, guardando la marca del último pedido copiado |
| Retraso aceptado | Hasta unos 15 segundos más el tiempo de la copia |
| Agregaciones | Total vendido, pedidos pagados, ticket promedio, clientes distintos, ventas por día, productos más vendidos, pedidos por estado y por tipo de entrega |
| Permisos | Solo el GraphQL Gateway puede llamar a analytics, y solo con la identidad de un administrador |
| Datos personales | La copia no incluye dirección, teléfono, nombre ni `user_id`. Cada cliente se representa con un código (`cliente_ref`) calculado con HMAC, que permite contar clientes distintos sin saber quiénes son |
| Consulta desde la pantalla | El panel del local (P09) pide `panelAdmin { ventas }` al GraphQL Gateway, que llama a `/reports/sales` |

## 9.6 Detalle de la comunicación gRPC

| Aspecto | Cómo lo resolvimos |
|---|---|
| Contrato | `backend/proto/inventory.proto`, con mensajes tipados para cada método |
| Modalidad | Unary en los cuatro métodos |
| Autenticación del servicio | mTLS con certificados emitidos por una CA interna al arrancar el sistema |
| Autorización por método | Cada método tiene una lista de servicios permitidos; hoy solo `orders` |
| Deadline | 2 segundos por llamada |
| Cancelación | Si se cumple el plazo, la llamada se cancela y orders responde 503 |
| Límites | Máximo 20 productos por cotización, 10 unidades por producto y mensajes de 64 KB |
| Errores | `INVALID_ARGUMENT` → 400, `NOT_FOUND` → 404, `FAILED_PRECONDITION` y `RESOURCE_EXHAUSTED` → 409, sin respuesta → 503 |
| Idempotencia | Las reservas usan el `order_id` como clave: repetir una reserva no descuenta el stock dos veces |

## 9.7 Prueba de carga

**Tipo:** medición, no proyección.

**Entorno:** Windows 11, 12 núcleos lógicos, 31,7 GB de RAM, Python 3.12.3. Todos los componentes y el generador de carga corren en el mismo computador, así que compiten por la CPU y los resultados son conservadores.

**Datos:** los datos de prueba de `scripts/seed_data.json` (11 productos, 4 usuarios).

**Comando:** `python scripts/prueba_carga.py --concurrencia 20 --duracion 30 --etiqueta estres`, con el sistema iniciado con `python run_all.py --reset --perfil carga`. El perfil de carga solo desactiva los límites de solicitudes del gateway, para medir los servicios y no el límite.

| Escenario | Concurrencia | Duración | Solicitudes | Throughput | p95 | Objetivo p95 | Errores | CPU prom./máx. | Memoria máx. | Resultado |
|---|---|---|---|---|---|---|---|---|---|---|
| E1 Catálogo | 20 | 30 s | 28.012 | 934,6 req/s | 33,1 ms | 200 ms | 0 % | 217 % / 251 % | 890 MB | Cumple |
| E2 Cotización (gRPC) | 20 | 30 s | 21.790 | 726,6 req/s | 40,7 ms | 300 ms | 0 % | 349 % / 388 % | 897 MB | Cumple |
| E3 Agregación GraphQL | 20 | 30 s | 18.023 | 601,2 req/s | 49,8 ms | 500 ms | 0 % | 301 % / 352 % | 1.038 MB | Cumple |

La CPU es la suma de los procesos del backend (100 % equivale a un núcleo completo) y la memoria es la suma de lo que usan esos procesos.

**Comparación con los objetivos.** Los tres escenarios cumplen el objetivo de p95 con bastante margen y sin errores. Aun así no afirmamos que gRPC sea "más rápido" que REST, porque no medimos una versión REST de la misma operación. Lo que sí muestra la prueba es que la cotización por gRPC, que es la operación más frecuente, se mantiene muy por debajo del objetivo.

Los resultados completos están en `docs/evidencias/prueba_carga_estres.md` y `docs/evidencias/prueba_carga_estres.json`.

## 9.8 Pruebas de integración

| Prueba | Qué comprueba | Resultado |
|---|---|---|
| `test_grpc_rechaza_sin_certificado_cliente` | inventory rechaza conexiones sin certificado | Pasó |
| `test_grpc_rechaza_certificado_de_ca_no_confiable` | inventory rechaza certificados de otra CA | Pasó |
| `test_grpc_autorizacion_por_metodo` | un servicio que no es orders no puede llamar a los métodos | Pasó |
| `test_inventory_no_responde_pedido_no_se_crea` | si inventory no responde, el pedido no se guarda | Pasó |
| `test_reserva_atomica_entre_productos` | si falta stock de un producto, se revierte la reserva de los demás | Pasó |
| `test_analitica_refleja_ventas` | un pedido pagado aparece en el reporte | Pasó |
| `test_analytics_no_responde_error_parcial` | si analytics cae, GraphQL devuelve el resto con un error parcial | Pasó |
| `test_agregacion_combina_tres_subsistemas` | GraphQL combina orders, inventory y payments | Pasó |

La salida completa de las pruebas está en `docs/evidencias/pruebas_pytest.txt`.
