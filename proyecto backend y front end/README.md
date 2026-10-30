# Mr. Sandwich: backend y frontend

Proyecto del caso N.15 (venta de sándwiches, hamburguesas, promociones y bebidas con retiro o delivery).
El frontend se comunica solo con el API Gateway, y el gateway reparte las solicitudes a los servicios internos.

## Qué se necesita

| Programa | Versión que usamos | Para qué |
|---|---|---|
| Python | 3.12 | Servicios del backend y pruebas |
| Node.js | 26 | GraphQL Gateway |
| MongoDB Community Server | 9.0 | Base de datos |
| HashiCorp Vault | 2.2 | Gestor de secretos |

MongoDB y Vault no necesitan instalador: basta con descargar el ZIP y descomprimirlo.

## Instalación

Desde la carpeta `proyecto backend y front end`:

```
pip install -r requirements-dev.txt
```

```
cd backend/graphql_gateway
npm install
```

`run_all.py` busca `vault` en el PATH y `mongod` en el PATH o en `C:\Program Files\MongoDB`.
Si están en otra carpeta, hay que indicarlo antes de arrancar (PowerShell):

```
$env:Path = "C:\ruta\a\vault;" + $env:Path
$env:MONGOD_PATH = "C:\ruta\a\mongodb\bin\mongod.exe"
```

## Levantar el sistema

```
python run_all.py --reset
```

Este comando inicia MongoDB y Vault, genera los secretos y los usuarios de la base de datos,
carga los datos de prueba y levanta todos los servicios. Cuando termina muestra `Sistema listo.`

- Frontend: http://localhost:8080
- API Gateway: http://localhost:8000/api/v1/...

Para detenerlo se usa `Ctrl+C`, o desde otra terminal:

```
python run_all.py stop
```

Opciones:

| Opción | Qué hace |
|---|---|
| `--reset` | Borra las bases y vuelve a cargar los datos de prueba |
| `--perfil carga` | Desactiva los límites de solicitudes para la prueba de carga |
| `--ttl-pago 30` | Un pedido sin pagar expira a los 30 segundos (para probar la expiración) |

Los datos y los logs quedan en `~/.mrsandwich/runtime`, fuera del repositorio.

## Puertos

| Componente | Puerto | Acceso |
|---|---|---|
| Frontend | 8080 | Público |
| API Gateway | 8000 | Público |
| Auth | 8101 | Privado |
| Clients | 8102 | Privado |
| Inventory | 8103 | Privado |
| Inventory gRPC | 50051 | Privado |
| Orders | 8104 | Privado |
| Payments | 8105 | Privado |
| Analytics | 8106 | Privado |
| GraphQL Gateway | 4000 | Privado |
| Proveedor de pagos simulado | 8300 | Privado |
| Vault | 8200 | Privado |
| MongoDB | 27018 | Privado |

Todos los componentes escuchan en `127.0.0.1`. Solo el frontend y el API Gateway están pensados para el navegador.

## Usuarios de prueba

| Usuario | Rol |
|---|---|
| admin@mrsandwich.test | admin |
| cocina@mrsandwich.test | staff |
| ana@cliente.test | cliente |
| pedro@cliente.test | cliente |

Las contraseñas están en `scripts/seed_data.json`. Son datos ficticios solo para pruebas.

## Pruebas

Con el sistema levantado:

```
python -m pytest -v
```

La prueba de expiración necesita el sistema iniciado con `--ttl-pago 30`; si no, aparece como omitida.

Pruebas del GraphQL Gateway (no necesitan el sistema levantado):

```
cd backend/graphql_gateway
npm test
```

Prueba de carga (con el sistema iniciado con `--perfil carga`):

```
python scripts/prueba_carga.py --concurrencia 20 --duracion 30 --etiqueta estres
```

Los resultados de nuestras ejecuciones están en `docs/evidencias`.

## Estructura

| Carpeta | Contenido |
|---|---|
| `backend/api_gateway` | API Gateway: rutas, permisos, límites y reenvío |
| `backend/auth_service` | Registro, inicio de sesión y validación de tokens |
| `backend/clients_service` | Perfil y direcciones |
| `backend/inventory_service` | Catálogo, stock y servidor gRPC |
| `backend/orders_service` | Pedidos y estados |
| `backend/payments_service` | Pagos y notificaciones del proveedor |
| `backend/analytics_service` | Reportes de ventas |
| `backend/graphql_gateway` | Agregaciones GraphQL privadas |
| `backend/provider_sim` | Proveedor de pagos simulado |
| `backend/common` | Código compartido: configuración, base de datos, secretos y seguridad |
| `backend/proto` | Contrato gRPC |
| `frontend` | Pantallas de la aplicación |
| `scripts` | Arranque, datos de prueba y prueba de carga |
| `tests` | Pruebas automatizadas |
| `docs` | Informe, diagramas y evidencias |

## Problemas comunes

| Mensaje | Solución |
|---|---|
| `Puertos ocupados` | Hay una instancia anterior corriendo. Ejecutar `python run_all.py stop` |
| `No se encontró mongod` | Definir `MONGOD_PATH` con la ruta a `mongod.exe` |
| `<servicio> terminó al iniciar` | Revisar el log del servicio en `~/.mrsandwich/runtime/logs` |
