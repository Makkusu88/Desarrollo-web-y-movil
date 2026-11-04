# Módulo 10 Backend completo e integración verificable

En este módulo mostramos que el sistema funciona completo y que los controles de seguridad se cumplen mientras corre, no solo en el papel. Todo lo que aparece acá se ejecutó en un computador del equipo y sus resultados están en `docs/evidencias`.

## 10.1 Requisitos implementados

| Requisito | Estado | Observación |
|---|---|---|
| RF01 Ver el menú y buscar | Implementado | La búsqueda trata el texto como texto, no como expresión regular |
| RF02 Detalle y personalización | Implementado | Opciones y extras vienen de inventory |
| RF03 Registro, inicio y cierre de sesión | Implementado | Cerrar sesión revoca el token en el servidor |
| RF04 Recuperar contraseña | Implementado con limitación | El correo se guarda como archivo `.eml` en `~/.mrsandwich/runtime/outbox` en vez de enviarse |
| RF05 Carrito y precio oficial | Implementado | El precio lo calcula inventory; lo que mande el navegador se ignora |
| RF06 Confirmar pedido con retiro o delivery | Implementado | La dirección debe ser del mismo cliente |
| RF07 Pagar en línea | Implementado con proveedor de prueba | Ver 10.4 |
| RF08 Seguir el pedido e historial | Implementado | Solo el dueño y el personal ven el pedido |
| RF09 Perfil y direcciones | Implementado | |
| RF10 Preparar y despachar | Implementado | Solo se permiten las transiciones válidas |
| RF11 Administrar productos y stock | Implementado | Los productos se dan de baja sin borrar el historial |
| RF12 Reportes y stock bajo | Implementado | Mediante analytics y GraphQL (módulo 9) |
| RF13 Anular pedidos | Implementado con limitación | El administrador puede anular un pedido pagado y queda marcado `requiere_reembolso`; la devolución del dinero no se ejecuta porque el proveedor de prueba no tiene esa operación |

## 10.2 Persistencia

| Aspecto | Cómo lo resolvimos |
|---|---|
| Motor | MongoDB 9.0 con autenticación activada |
| Separación | Una base por servicio: `ms_auth`, `ms_clients`, `ms_inventory`, `ms_orders`, `ms_payments` y `ms_analytics` |
| Usuarios de base de datos | Cada servicio tiene su propio usuario, que solo puede leer y escribir su base. Las claves se generan en cada arranque y se guardan en Vault |
| Esquema e índices | Cada servicio crea sus índices al iniciar (por ejemplo, el índice único que impide dos pagos aprobados para el mismo pedido) |
| Scripts de creación | `scripts/bootstrap.py` crea los usuarios, los certificados y los secretos; `scripts/seed.py` carga los datos de prueba |
| Datos de prueba | `scripts/seed_data.json`: 4 categorías, 11 productos y 4 usuarios ficticios |
| Validaciones | Los datos que llegan se validan en el servidor con modelos Pydantic (tamaños, formatos y rangos) |
| Control de estados | Los pedidos solo cambian de estado con actualizaciones condicionales, así dos cambios simultáneos no se pisan |
| Errores | Todas las respuestas de error tienen el mismo formato `{"error": {...}, "request_id": ...}` y no muestran detalles internos |

## 10.3 Integración de los componentes

| Componente | Puerto | Expuesto al navegador | Cómo se protege |
|---|---|---|---|
| Frontend | 8080 | Sí | Solo archivos estáticos; no guarda secretos |
| API Gateway | 8000 | Sí | Rutas declaradas, permisos por rol, límites de solicitudes y cabeceras anti-CSRF |
| Auth Service | 8101 | No | Solo acepta llamadas del gateway |
| Microservicios | 8102–8106 | No | Cada uno solo acepta a los servicios autorizados, con un secreto por pareja de servicios |
| GraphQL Gateway | 4000 | No | Solo acepta al API Gateway; límites de profundidad y de costo |
| Inventory gRPC | 50051 | No | mTLS con certificados de la CA interna |
| Vault | 8200 | No | Cada servicio tiene un token que solo puede leer sus propios secretos |
| MongoDB | 27018 | No | Usuario y clave por servicio |

Todos los componentes escuchan en `127.0.0.1`. La identidad del usuario la verifica el gateway y la reenvía firmada; los servicios internos no confían en cabeceras enviadas por el navegador. Ningún secreto está escrito en el código: todos se generan al arrancar y se leen desde Vault.

Para demostrar la separación entre la parte pública y la privada usamos `run_all.py`, que es el entorno reproducible del proyecto. No usamos contenedores porque lo visto en clase con Vault funcionó como ejecutable, y `run_all.py` deja el mismo resultado: solo el frontend y el gateway quedan pensados para el navegador.

## 10.4 Frontend e integraciones externas

El frontend llama solo al API Gateway (`frontend/js/api.js`). No hay datos escritos en el frontend: el catálogo, los pedidos, el perfil y los reportes vienen de las APIs reales.

| Integración externa | Situación | Cómo la resolvimos |
|---|---|---|
| Proveedor de pagos | No usamos un proveedor real | `provider_sim` es un adaptador de prueba que mantiene el contrato: sesión de pago, autenticación con clave de API, webhook firmado con HMAC y estados aprobado o rechazado |
| Correo electrónico | No hay servidor de correo | Los correos de recuperación se guardan como archivos `.eml` |

El adaptador de pagos no reemplaza a `payments`: nuestro servicio sigue verificando la firma, consultando el estado al proveedor y evitando pagos duplicados.

## 10.5 Pruebas automatizadas

Ejecutamos 51 pruebas con el sistema corriendo y todas pasaron (`docs/evidencias/pruebas_pytest.txt` y `docs/evidencias/prueba_expiracion.txt`). Además, el GraphQL Gateway tiene 5 pruebas propias (`npm test`).

| Grupo | Pruebas | Resultado |
|---|---|---|
| Contratos (`test_01_contratos.py`) | 11 | 11 pasaron |
| Seguridad (`test_02_seguridad.py`) | 15 | 15 pasaron |
| Reglas de negocio (`test_03_negocio.py`) | 11 | 11 pasaron |
| GraphQL, gRPC y caídas (`test_04_graphql_grpc_resiliencia.py`) | 13 | 13 pasaron |
| Límite de solicitudes (`test_99_limite_solicitudes.py`) | 1 | 1 pasó |
| Límites del GraphQL Gateway (`npm test`) | 5 | 5 pasaron |

Lo que pide revisar la pauta y la prueba que lo cubre:

| Control | Prueba |
|---|---|
| Propiedad de recursos | `test_caso4_pedido_ajeno`, `test_caso4_direccion_de_otro_cliente` |
| Roles | `test_caso3_rol_sin_permiso` |
| Rechazo del acceso directo | `test_caso5_acceso_directo_a_servicios_privados`, `test_caso5_identidad_inyectada_por_el_navegador` |
| Límites GraphQL | `test_paginacion_limitada`, `test_limite_de_costo`, `test_introspeccion_y_lotes_deshabilitados` |
| Caída de dependencias | `test_inventory_no_responde_pedido_no_se_crea`, `test_analytics_no_responde_error_parcial`, `test_payments_no_responde_resumen_parcial`, `test_proveedor_de_pagos_no_responde`, `test_gestor_de_secretos_no_responde_usa_cache` |
| Pagos duplicados | `test_pago_duplicado_y_notificacion_repetida`, `test_idempotency_key_evita_pedidos_duplicados` |
| Recuperación de stock | `test_anulacion_recupera_stock`, `test_expiracion_libera_stock` |
| gRPC | `test_grpc_rechaza_sin_certificado_cliente`, `test_grpc_rechaza_certificado_de_ca_no_confiable`, `test_grpc_autorizacion_por_metodo` |
| Analítica | `test_analitica_refleja_ventas` |

## 10.6 Matriz de trazabilidad

| Requisito | Pantalla | Servicio | Prueba | Resultado | Evidencia |
|---|---|---|---|---|---|
| RF01 | P01 `index.html` | S01, S01b (inventory) | `test_S01_catalogo_anonimo_solo_campos_publicos`, `test_S01_filtros`, `test_S01_busqueda_no_interpreta_regex` | Pasó | `pruebas_pytest.txt`; demostración paso 1 |
| RF02 | P02 `producto.html` | S02 (inventory) | `test_S02_detalle_con_personalizacion` | Pasó | `pruebas_pytest.txt`; demostración paso 1 |
| RF03 | P03 `login.html`, P04 `registro.html` | S03, S04, S05 (auth) | `test_S03_registro_y_perfil`, `test_S03_politica_de_contrasena`, `test_caso2_logout_revoca_token` | Pasó | `pruebas_pytest.txt`; demostración pasos 3 y 12 |
| RF04 | P08 `restablecer.html` | S06, S07 (auth) | `test_S06_S07_recuperacion_de_contrasena` | Pasó | `pruebas_pytest.txt` |
| RF05 | P05 `carrito.html` | S15 (orders → inventory por gRPC) | `test_S15_cotizacion_calcula_en_servidor`, `test_caso6_precio_alterado_se_ignora` | Pasó | `pruebas_pytest.txt`; demostración paso 4 |
| RF06 | P05 `carrito.html` | S16 (orders) | `test_flujo_completo_delivery`, `test_stock_insuficiente_no_crea_pedido`, `test_reserva_atomica_entre_productos`, `test_idempotency_key_evita_pedidos_duplicados` | Pasó | `pruebas_pytest.txt`; demostración paso 5 |
| RF07 | P06 `pedido.html`, P10 página de pago | S22, S23, S24 (payments) | `test_caso6_cliente_no_puede_marcar_pagado`, `test_caso6_webhook_falsificado`, `test_caso6_pago_rechazado_no_confirma`, `test_pago_duplicado_y_notificacion_repetida` | Pasó | `pruebas_pytest.txt`; demostración paso 6 |
| RF08 | P06 `pedido.html`, P07 `cuenta.html` | S17, S18 (orders); `resumenPedido` (GraphQL) | `test_caso4_pedido_ajeno`, `test_agregacion_combina_tres_subsistemas`, `test_caso2_sin_sesion` | Pasó | `pruebas_pytest.txt`; demostración pasos 2 y 7 |
| RF09 | P07 `cuenta.html` | S09–S14 (clients) | `test_S11_S14_direcciones_crud`, `test_caso4_direccion_de_otro_cliente` | Pasó | `pruebas_pytest.txt` |
| RF10 | P09 `admin.html` | S20, S21 (orders) | `test_flujo_completo_delivery`, `test_transiciones_invalidas` | Pasó | `pruebas_pytest.txt`; demostración paso 8 |
| RF11 | P09 `admin.html` | S25–S29 (inventory) | `test_caso3_rol_sin_permiso`, `test_baja_logica_de_producto_conserva_historial` | Pasó | `pruebas_pytest.txt`; demostración paso 10 |
| RF12 | P09 `admin.html` | S30 `panelAdmin` (GraphQL → analytics, inventory) | `test_analitica_refleja_ventas`, `test_analytics_no_responde_error_parcial` | Pasó | `pruebas_pytest.txt`; demostración paso 11 |
| RF13 | P07 `cuenta.html`, P09 `admin.html` | S19 (orders) | `test_anulacion_recupera_stock`, `test_expiracion_libera_stock` | Pasó | `pruebas_pytest.txt`, `prueba_expiracion.txt` |

## 10.7 Demostración de los flujos principales

Además de las pruebas, ejecutamos los flujos principales uno por uno contra el sistema real y guardamos la salida en `docs/evidencias/demostracion_flujos.md`. Cada línea muestra quién hace la solicitud, el código de respuesta y el `request_id` con que quedó registrada en los logs.

El caso que pide la pauta como ejemplo es el **paso 7**. Ana crea un pedido y lo consulta sin problema; Pedro, con otra cuenta, pide el mismo pedido y recibe `404 Pedido no encontrado`, y la respuesta no trae ningún dato del pedido. Por GraphQL pasa lo mismo: `resumenPedido` devuelve `null` con el error `NOT_FOUND`. Las dos respuestas salen de la misma regla, la función `puede_ver` de orders, que deja ver un pedido solo a su dueño o al personal. Por eso el personal de cocina sí lo puede ver: lo necesita para despacharlo.

| Paso | Flujo | Resultado |
|---|---|---|
| 1 | Visitante ve el catálogo | 200, solo campos públicos |
| 2 | Visitante pide sus pedidos sin sesión | 401 |
| 3 | Inicio de sesión de los cuatro usuarios | 200 |
| 4 | Cotización enviando un precio falso | El servidor ignora el precio y calcula el oficial |
| 5 | Pedido con delivery | 201, queda pendiente de pago |
| 6 | Pago con el proveedor de prueba | Pago aprobado con comprobante y pedido pagado |
| 7 | Pedido propio y pedido ajeno | 200 para la dueña, 404 sin datos para otra cuenta |
| 8 | El personal despacha y un cliente intenta cambiar el estado | 200 para el personal, 403 para el cliente |
| 9 | Llamar directo a orders sin pasar por el gateway | 403 |
| 10 | Un cliente intenta crear un producto | 403 |
| 11 | Reporte de ventas del administrador | Aparece la venta; un cliente recibe `FORBIDDEN` |
| 12 | Cierre de sesión | El token anterior pasa a dar 401 |

## 10.8 Inicio, configuración y operación

| Lo que pide la pauta | Dónde está |
|---|---|
| Iniciar y detener | `README.md`: `python run_all.py --reset` y `python run_all.py stop` |
| Configurar secretos | Los genera `run_all.py` en cada arranque y los guarda en Vault; ningún archivo del repositorio tiene valores reales |
| Variables de configuración | `.env.example`, con valores de ejemplo y `VAULT_TOKEN` vacío |
| Crear datos de prueba | `python run_all.py --reset` ejecuta `scripts/seed.py` |
| Ejecutar las pruebas | `python -m pytest -v` y `npm test` en `backend/graphql_gateway` |
| Dependencias versionadas | `requirements.txt`, `requirements-dev.txt` y `backend/graphql_gateway/package-lock.json` |
| Health checks | Cada servicio responde `GET /health`; `run_all.py` espera esa respuesta antes de seguir |
| Logs con identificador | Cada solicitud lleva un `X-Request-ID` que pasa por todos los servicios. Los logs no guardan tokens, claves ni datos personales (`test_logs_sin_secretos_ni_credenciales`) |

## 10.9 Limitaciones

- El sistema corre completo en un solo computador; no lo probamos repartido en varias máquinas.
- Vault funciona en modo desarrollo y en memoria: al detener el sistema se pierden los secretos y se generan otros al volver a arrancar. Para producción habría que usar un Vault persistente.
- Los pagos y los correos usan adaptadores de prueba (10.4).
- La devolución del dinero de un pedido anulado queda marcada, pero no se ejecuta (RF13).
- No usamos HTTPS entre el navegador y el gateway porque todo corre en `localhost`; la comunicación gRPC interna sí va cifrada con mTLS.
