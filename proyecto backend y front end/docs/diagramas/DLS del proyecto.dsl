workspace "Mr. Sandwich" "Plataforma de pedidos Mr. Sandwich" {

    !identifiers hierarchical

    model {
        // =========================================
        // 1. ACTORES DEL SISTEMA
        // =========================================

        visitante = person "Visitante" "Persona que consulta el catalogo y cotiza sin iniciar sesion."

        cliente = person "Cliente" "Persona autenticada que arma su carrito, realiza pedidos y los paga."

        staff = person "Staff del local" "Personal que gestiona los pedidos en curso y actualiza el stock."

        administrador = person "Administrador" "Personal autorizado para administrar el catalogo y revisar las ventas."

        // =========================================
        // 2. SISTEMA PRINCIPAL
        // =========================================

        sistema = softwareSystem "Mr. Sandwich" "Sistema que integra catalogo, pedidos, pagos y reportes de venta mediante microservicios." {

            tags "SistemaEvaluado"

            // CAPA DE PRESENTACION

            frontend = container "Frontend responsivo" "Interfaz web para visitantes, clientes, staff y administradores." "HTML, CSS y JavaScript" {
                tags "Frontend"
            }

            // PUNTO DE ENTRADA

            apiGateway = container "API Gateway" "Punto de entrada al backend: enruta peticiones, valida sesion y roles, y aplica limites de uso." "Python, FastAPI" {
                tags "Gateway"

                httpEntry = component "Adaptador HTTP" "Recibe solicitudes /api/v1, aplica CORS, limite de tamano y cabeceras seguras." "Componente: Entrada HTTP" {
                    tags "EntradaC3"
                }

                rateLimiter = component "Limitador de solicitudes" "Token bucket por IP y politica (general, sensible, graphql, webhook)." "Componente: Control de uso" {
                    tags "ControlC3"
                }

                identityFilter = component "Filtro de acceso" "Lee la cookie de sesion o el token Bearer, valida la cabecera anti-CSRF, introspecciona la sesion y compara roles." "Componente: Control de acceso" {
                    tags "ControlC3"
                }

                routeDispatcher = component "Despachador de rutas" "Resuelve la ruta (S01 a S30) y reenvia la solicitud al servicio interno que corresponde." "Componente: Enrutamiento" {
                    tags "AplicacionC3"
                }

                identitySigner = component "Firmador de identidad" "Agrega la credencial servicio a servicio y firma con Ed25519 la identidad del usuario." "Componente: Adaptador de integracion" {
                    tags "IntegracionC3"
                }

                errorMapper = component "Traductor de errores" "Uniforma fallas (401, 403, 429, 503, 504) en respuestas JSON con request_id." "Componente: Manejo de errores" {
                    tags "ErrorC3"
                }
            }

            // AGREGACION GRAPHQL

            graphqlGateway = container "GraphQL Gateway" "Expone una API de consulta y agrega informacion de varios subsistemas autorizados." "Node.js, Apollo Server" {
                tags "Gateway"

                graphqlEndpoint = component "Endpoint GraphQL" "Recibe operaciones GraphQL de solo lectura que llegan desde el API Gateway." "Componente: Entrada GraphQL" {
                    tags "EntradaC3"
                }

                queryValidator = component "Validador de consultas" "Verifica sintaxis, esquema, profundidad maxima (6) y costo maximo (600)." "Componente: Servicio de validacion" {
                    tags "ControlC3"
                }

                fieldAccess = component "Control de acceso a campos" "Acepta solo al API Gateway, verifica la firma Ed25519 de la identidad y el rol por campo." "Componente: Control de acceso" {
                    tags "ControlC3"
                }

                resolvers = component "Resolvers" "Resuelven resumenPedido, misPedidos, pedidosLocal y panelAdmin usando DataLoader." "Componente: Logica de consulta" {
                    tags "AplicacionC3"
                }

                serviceConnectors = component "Conectores de subsistemas" "Llaman por REST a los servicios internos con plazo maximo de 3 s." "Componente: Adaptador de integracion" {
                    tags "IntegracionC3"
                }

                responseComposer = component "Ensamblador de respuesta" "Combina los datos y entrega errores parciales si un subsistema no responde." "Componente: Composicion" {
                    tags "AplicacionC3"
                }
            }

            // SERVICIOS DE NEGOCIO

            authService = container "Auth Service" "Registra usuarios, autentica, emite y valida sesiones y restablece contrasenas." "Python, FastAPI" {
                tags "Identidad"

                authApi = component "Controlador de autenticacion" "Expone register, login, logout, introspect y password-reset." "Componente: Entrada HTTP" {
                    tags "EntradaC3"
                }

                callerCheck = component "Verificador de llamador" "Acepta solo solicitudes del API Gateway con credencial de servicio valida." "Componente: Control de acceso" {
                    tags "ControlC3"
                }

                credentialVerifier = component "Verificador de credenciales" "Valida la politica de claves, compara hashes scrypt y bloquea la cuenta 5 minutos tras 5 intentos fallidos." "Componente: Servicio de validacion" {
                    tags "AplicacionC3"
                }

                sessionManager = component "Gestor de sesiones" "Crea, valida y revoca sesiones con vencimiento." "Componente: Servicio de sesion" {
                    tags "AplicacionC3"
                }

                resetManager = component "Restablecimiento de contrasena" "Genera tokens de un solo uso y confirma el cambio de clave." "Componente: Servicio de recuperacion" {
                    tags "AplicacionC3"
                }

                identityRepository = component "Repositorio de identidades" "Accede a usuarios, sesiones y tokens de restablecimiento." "Componente: Acceso a datos" {
                    tags "DatosC3"
                }

                secretClient = component "Cliente de secretos" "Obtiene credenciales de base de datos y secretos de servicio con cache." "Componente: Adaptador de integracion" {
                    tags "IntegracionC3"
                }

                profileConnector = component "Conector de clientes" "Crea el perfil del cliente en Clients Service al registrarse." "Componente: Adaptador de integracion" {
                    tags "IntegracionC3"
                }

                mailNotifier = component "Notificador de correo" "Deja el correo de recuperacion como archivo .eml en la bandeja de salida." "Componente: Adaptador de integracion" {
                    tags "IntegracionC3"
                }
            }

            clients = container "clients" "Gestiona perfiles de clientes y direcciones de entrega." "Python, FastAPI" {
                tags "Servicio"
            }

            inventory = container "inventory" "Gestiona catalogo, disponibilidad y stock. Atiende reservas por gRPC." "Python, FastAPI, gRPC" {
                tags "Servicio"
            }

            orders = container "orders" "Cotiza, crea y controla el estado de los pedidos; expira pedidos impagos." "Python, FastAPI" {
                tags "Servicio"
            }

            payments = container "payments" "Inicia pagos, recibe webhooks firmados y confirma el pago del pedido." "Python, FastAPI" {
                tags "Servicio"
            }

            analytics = container "analytics" "Copia los pedidos cada 15 segundos con el cliente seudonimizado y genera reportes de ventas." "Python, FastAPI" {
                tags "Servicio"
            }

            // PERSISTENCIA ILUSTRATIVA

            dbIdentity = container "Datos de identidad" "Persistencia de identidades, sesiones y tokens de restablecimiento." "MongoDB" {
                tags "BaseDatos"
            }

            dbClients = container "Datos de clientes" "Persistencia del subsistema clients." "MongoDB" {
                tags "BaseDatos"
            }

            dbInventory = container "Datos de inventario" "Persistencia del subsistema inventory." "MongoDB" {
                tags "BaseDatos"
            }

            dbOrders = container "Datos de pedidos" "Persistencia del subsistema orders." "MongoDB" {
                tags "BaseDatos"
            }

            dbPayments = container "Datos de pagos" "Persistencia del subsistema payments." "MongoDB" {
                tags "BaseDatos"
            }

            dbAnalytics = container "Datos analiticos" "Copia de los pedidos con el cliente seudonimizado." "MongoDB" {
                tags "BaseDatos"
            }
        }

        // =========================================
        // 3. SISTEMAS EXTERNOS
        // =========================================

        secretManager = softwareSystem "Administrador de secretos" "Guarda credenciales, claves de firma y certificados para integraciones (HashiCorp Vault)." {
            tags "Externo"
        }

        pasarela = softwareSystem "Pasarela de pagos" "Procesa el pago del cliente y notifica el resultado por webhook firmado." {
            tags "Externo"
        }

        correo = softwareSystem "Servicio de correo" "Entrega los correos de restablecimiento de contrasena." {
            tags "Externo"
        }

        // =========================================
        // 4. RELACIONES DEL C1
        // =========================================

        visitante -> sistema "Consulta productos publicos"
        cliente -> sistema "Consulta productos y gestiona sus pedidos"
        staff -> sistema "Gestiona pedidos y stock"
        administrador -> sistema "Administra catalogo y revisa ventas"
        cliente -> pasarela "Paga su pedido" "HTTPS"
        sistema -> secretManager "Obtiene credenciales autorizadas para integraciones"
        sistema -> pasarela "Solicita procesamiento de pagos" "HTTPS/JSON"
        pasarela -> sistema "Notifica el resultado del pago" "HTTPS/Webhook"
        sistema -> correo "Envia enlaces de restablecimiento"

        // =========================================
        // 5. ACTORES Y FRONTEND
        // =========================================

        visitante -> sistema.frontend "Consulta el catalogo" "Navegador web"
        cliente -> sistema.frontend "Consulta y gestiona sus pedidos" "Navegador web"
        staff -> sistema.frontend "Gestiona pedidos en curso" "Navegador web"
        administrador -> sistema.frontend "Administra catalogo y ventas" "Navegador web"

        // =========================================
        // 6. ENTRADA AL BACKEND
        // =========================================

        sistema.frontend -> sistema.apiGateway "Envia solicitudes de la interfaz" "HTTPS/JSON"
        pasarela -> sistema.apiGateway "Envia webhook de pago" "HTTPS/Webhook"

        // =========================================
        // 7. SESIONES Y SECRETOS
        // =========================================

        sistema.apiGateway -> sistema.authService "Solicita validacion de identidad o sesion" "HTTPS/JSON"

        sistema.apiGateway -> secretManager "Obtiene secretos autorizados" "Canal autenticado"
        sistema.graphqlGateway -> secretManager "Obtiene secretos autorizados" "Canal autenticado"
        sistema.authService -> secretManager "Obtiene credenciales autorizadas" "Canal autenticado"
        sistema.clients -> secretManager "Obtiene credenciales autorizadas" "Canal autenticado"
        sistema.inventory -> secretManager "Obtiene credenciales y certificados gRPC" "Canal autenticado"
        sistema.orders -> secretManager "Obtiene credenciales y certificados gRPC" "Canal autenticado"
        sistema.payments -> secretManager "Obtiene credenciales y API key de la pasarela" "Canal autenticado"
        sistema.analytics -> secretManager "Obtiene credenciales autorizadas" "Canal autenticado"

        // =========================================
        // 8. ENRUTAMIENTO A SERVICIOS PRIVADOS
        // =========================================

        sistema.apiGateway -> sistema.inventory "Enruta consultas y operaciones de inventario" "HTTPS/JSON"
        sistema.apiGateway -> sistema.orders "Enruta operaciones de pedidos" "HTTPS/JSON"
        sistema.apiGateway -> sistema.clients "Enruta operaciones de clientes" "HTTPS/JSON"
        sistema.apiGateway -> sistema.payments "Enruta operaciones de pagos" "HTTPS/JSON"
        sistema.apiGateway -> sistema.graphqlGateway "Enruta consultas GraphQL" "HTTPS/GraphQL"

        // =========================================
        // 9. COMUNICACIONES ENTRE SERVICIOS
        // =========================================

        sistema.authService -> sistema.clients "Crea el perfil del cliente al registrarse" "HTTPS/JSON"
        sistema.authService -> correo "Envia enlace de restablecimiento" "Bandeja de salida"
        sistema.orders -> sistema.inventory "Consulta y reserva stock" "gRPC/mTLS"
        sistema.orders -> sistema.clients "Obtiene direccion de entrega y contacto" "HTTPS/JSON"
        sistema.payments -> sistema.orders "Consulta el pedido y confirma el pago" "HTTPS/JSON"
        sistema.payments -> pasarela "Crea sesion de pago" "HTTPS/JSON"
        sistema.analytics -> sistema.orders "Copia los pedidos cada 15 segundos" "HTTPS/JSON"

        // =========================================
        // 10. PERSISTENCIA
        // =========================================

        sistema.authService -> sistema.dbIdentity "Consulta y actualiza identidades" "Acceso a datos"
        sistema.clients -> sistema.dbClients "Lee y escribe perfiles de clientes" "Acceso a datos"
        sistema.inventory -> sistema.dbInventory "Lee y escribe datos de inventario" "Acceso a datos"
        sistema.orders -> sistema.dbOrders "Lee y escribe pedidos" "Acceso a datos"
        sistema.payments -> sistema.dbPayments "Lee y escribe estados de pagos" "Acceso a datos"
        sistema.analytics -> sistema.dbAnalytics "Lee y escribe hechos de venta" "Acceso a datos"

        // =========================================
        // 11. GRAPHQL HACIA SUBSISTEMAS
        // =========================================

        sistema.graphqlGateway -> sistema.orders "Agrega informacion autorizada de pedidos" "HTTPS/JSON"
        sistema.graphqlGateway -> sistema.inventory "Agrega informacion de productos y stock" "HTTPS/JSON"
        sistema.graphqlGateway -> sistema.payments "Agrega estado de pagos" "HTTPS/JSON"
        sistema.graphqlGateway -> sistema.analytics "Obtiene reporte de ventas" "HTTPS/JSON"

        // =========================================
        // 12. COMPONENTES (C3)
        // =========================================

        // C3 API Gateway
        sistema.frontend -> sistema.apiGateway.httpEntry "Envia solicitudes de la interfaz" "HTTPS/JSON"
        pasarela -> sistema.apiGateway.httpEntry "Envia webhook de pago" "HTTPS/Webhook"
        sistema.apiGateway.httpEntry -> sistema.apiGateway.rateLimiter "Verifica limite de uso"
        sistema.apiGateway.rateLimiter -> sistema.apiGateway.identityFilter "Entrega solicitud permitida"
        sistema.apiGateway.identityFilter -> sistema.authService "Solicita validacion de sesion" "HTTPS/JSON"
        sistema.apiGateway.identityFilter -> sistema.apiGateway.routeDispatcher "Entrega solicitud autorizada"
        sistema.apiGateway.routeDispatcher -> sistema.apiGateway.identitySigner "Solicita cabeceras internas"
        sistema.apiGateway.identitySigner -> secretManager "Obtiene secretos de salida y clave de firma" "Canal autenticado"
        sistema.apiGateway.routeDispatcher -> sistema.inventory "Enruta operaciones de inventario" "HTTPS/JSON"
        sistema.apiGateway.routeDispatcher -> sistema.orders "Enruta operaciones de pedidos" "HTTPS/JSON"
        sistema.apiGateway.routeDispatcher -> sistema.clients "Enruta operaciones de clientes" "HTTPS/JSON"
        sistema.apiGateway.routeDispatcher -> sistema.payments "Enruta operaciones de pagos" "HTTPS/JSON"
        sistema.apiGateway.routeDispatcher -> sistema.authService "Enruta registro, login y recuperacion" "HTTPS/JSON"
        sistema.apiGateway.routeDispatcher -> sistema.apiGateway.errorMapper "Informa fallas"
        sistema.apiGateway.rateLimiter -> sistema.apiGateway.errorMapper "Informa exceso de solicitudes"
        sistema.apiGateway.identityFilter -> sistema.apiGateway.errorMapper "Informa acceso denegado"

        // C3 GraphQL
        sistema.apiGateway.routeDispatcher -> sistema.graphqlGateway.graphqlEndpoint "Remite operaciones GraphQL" "HTTPS/GraphQL"
        sistema.graphqlGateway.graphqlEndpoint -> sistema.graphqlGateway.fieldAccess "Verifica llamador e identidad"
        sistema.graphqlGateway.fieldAccess -> secretManager "Obtiene secretos y clave publica" "Canal autenticado"
        sistema.graphqlGateway.fieldAccess -> sistema.graphqlGateway.queryValidator "Entrega consulta autorizada"
        sistema.graphqlGateway.queryValidator -> sistema.graphqlGateway.resolvers "Entrega consulta valida"
        sistema.graphqlGateway.resolvers -> sistema.graphqlGateway.serviceConnectors "Solicita informacion agregada"
        sistema.graphqlGateway.serviceConnectors -> sistema.orders "Consulta pedidos autorizados" "HTTPS/JSON"
        sistema.graphqlGateway.serviceConnectors -> sistema.inventory "Consulta productos y stock bajo" "HTTPS/JSON"
        sistema.graphqlGateway.serviceConnectors -> sistema.payments "Consulta estado de pagos" "HTTPS/JSON"
        sistema.graphqlGateway.serviceConnectors -> sistema.analytics "Consulta reporte de ventas" "HTTPS/JSON"
        sistema.graphqlGateway.resolvers -> sistema.graphqlGateway.responseComposer "Entrega resultados"

        // C3 Auth Service
        sistema.apiGateway.identityFilter -> sistema.authService.authApi "Solicita introspeccion de sesion" "HTTPS/JSON"
        sistema.apiGateway.routeDispatcher -> sistema.authService.authApi "Enruta registro, login y recuperacion" "HTTPS/JSON"
        sistema.authService.authApi -> sistema.authService.callerCheck "Verifica identidad en autorizacion"
        sistema.authService.callerCheck -> sistema.authService.credentialVerifier "Valida credenciales"
        sistema.authService.callerCheck -> sistema.authService.sessionManager "Gestiona sesiones"
        sistema.authService.callerCheck -> sistema.authService.resetManager "Gestiona recuperacion"
        sistema.authService.credentialVerifier -> sistema.authService.identityRepository "Consulta registros permitidos"
        sistema.authService.sessionManager -> sistema.authService.identityRepository "Guarda y consulta sesiones"
        sistema.authService.resetManager -> sistema.authService.identityRepository "Guarda tokens de un solo uso"
        sistema.authService.resetManager -> sistema.authService.mailNotifier "Solicita envio del enlace"
        sistema.authService.credentialVerifier -> sistema.authService.profileConnector "Solicita alta del perfil"
        sistema.authService.identityRepository -> sistema.dbIdentity "Lee y escribe datos de identidad" "Acceso a datos"
        sistema.authService.identityRepository -> sistema.authService.secretClient "Solicita material de conexion"
        sistema.authService.callerCheck -> sistema.authService.secretClient "Obtiene secretos de servicio"
        sistema.authService.secretClient -> secretManager "Obtiene secretos de forma controlada" "Canal autenticado"
        sistema.authService.profileConnector -> sistema.clients "Crea el perfil del cliente" "HTTPS/JSON"
        sistema.authService.mailNotifier -> correo "Envia enlace de restablecimiento" "Bandeja de salida"
    }

    // =========================================
    // 13. VISTAS DE ARQUITECTURA
    // =========================================

    views {

        systemContext sistema "C1_Contexto" "Contexto de negocio: actores y dependencias externas de Mr. Sandwich." {
            title "C1 - Contexto de Mr. Sandwich"
            include *
            autoLayout lr
        }

        container sistema "C2_Contenedores" "Aplicaciones y almacenes de datos de Mr. Sandwich." {
            title "C2 - Contenedores de Mr. Sandwich"
            include *
            autoLayout lr
        }

        container sistema "C2_Consulta_Catalogo" "Contenedores que participan en la consulta del catalogo." {
            title "C2 - Consulta del catalogo"
            include visitante sistema.frontend sistema.apiGateway sistema.inventory sistema.dbInventory secretManager
            autoLayout lr
        }

        dynamic sistema "C2_Registro_Pedido" "Secuencia de compra con delivery y pago." {
            title "C2 - Registro y pago de un pedido"
            cliente -> sistema.frontend "Arma el carrito y confirma el pedido con delivery"
            sistema.frontend -> sistema.apiGateway "POST /api/v1/orders"
            sistema.apiGateway -> sistema.authService "Valida la sesion por introspeccion"
            sistema.apiGateway -> sistema.orders "Reenvia el pedido con identidad firmada"
            sistema.orders -> sistema.clients "Obtiene direccion de entrega y contacto"
            sistema.orders -> sistema.inventory "Reserva el stock (gRPC/mTLS)"
            sistema.orders -> sistema.dbOrders "Guarda el pedido PENDIENTE_PAGO"
            sistema.frontend -> sistema.apiGateway "POST /api/v1/payments"
            sistema.apiGateway -> sistema.payments "Reenvia el inicio del pago"
            sistema.payments -> sistema.orders "Consulta el pedido"
            sistema.payments -> pasarela "Crea la sesion de pago"
            cliente -> pasarela "Paga en la pagina de la pasarela"
            pasarela -> sistema.apiGateway "Webhook firmado con HMAC"
            sistema.apiGateway -> sistema.payments "Reenvia la notificacion"
            sistema.payments -> sistema.dbPayments "Registra el pago aprobado"
            sistema.payments -> sistema.orders "Confirma el pago del pedido"
            autoLayout lr
        }

        component sistema.apiGateway "C3_API_Gateway" "Componentes internos del punto de entrada al backend." {
            title "C3 - API Gateway"
            include *
            autoLayout lr
        }

        component sistema.graphqlGateway "C3_GraphQL_Gateway" "Componentes internos del gateway de consultas GraphQL." {
            title "C3 - GraphQL Gateway"
            include *
            autoLayout lr
        }

        component sistema.authService "C3_AuthService" "Componentes internos del servicio de identidad." {
            title "C3 - Auth Service"
            include *
            autoLayout lr
        }

        styles {
            element "Person" {
                shape Person
                background #4b6478
                color #ffffff
                stroke #3b5063
            }
            element "SistemaEvaluado" {
                background #2c5f86
                color #ffffff
                stroke #234d6d
                shape RoundedBox
            }
            element "Externo" {
                background #3e5866
                color #ffffff
                stroke #2f4652
                shape RoundedBox
            }
            element "Frontend" {
                shape WebBrowser
                background #cfe3f4
                color #1f3b57
                stroke #8fb3d1
            }
            element "Gateway" {
                background #2c5f86
                color #ffffff
                stroke #234d6d
                shape RoundedBox
            }
            element "Identidad" {
                background #3e5866
                color #ffffff
                stroke #2f4652
                shape RoundedBox
            }
            element "Servicio" {
                background #d6e7f2
                color #1f3b57
                stroke #9dbdd3
                shape RoundedBox
            }
            element "BaseDatos" {
                shape Cylinder
                background #e1e5eb
                color #1f3b57
                stroke #b9c1cc
            }
            element "Component" {
                background #ffffff
                color #222222
                stroke #555555
                shape Box
            }
            relationship "Relationship" {
                color #8a8f96
                dashed true
                thickness 1
            }
        }
    }
}
