workspace "Mr. Sandwich" "Modelo C4 del backend y frontend de Mr. Sandwich" {

    !identifiers hierarchical

    model {
        visitante = person "Visitante" "Persona que consulta el menú sin iniciar sesión."
        cliente = person "Cliente" "Persona registrada que compra y sigue sus pedidos."
        personal = person "Personal del local" "Prepara y despacha los pedidos."
        administrador = person "Administrador" "Administra productos, stock y reportes."

        proveedorPagos = softwareSystem "Proveedor de pagos" "Procesa los pagos en línea. En este proyecto se usa un simulador (provider_sim)." {
            tags "Externo"
        }

        sistema = softwareSystem "Mr. Sandwich" "Venta de sándwiches, hamburguesas, promociones y bebidas con retiro o delivery." {
            tags "SistemaEvaluado"

            frontend = container "Frontend responsivo" "Pantallas de catálogo, carrito, pedidos, cuenta y panel del local." "HTML, CSS y JavaScript" {
                tags "Frontend"
            }

            apiGateway = container "API Gateway" "Único punto de entrada al backend: rutas, permisos, límites y reenvío." "Python, FastAPI" {
                tags "Gateway"

                httpEntry = component "Adaptador HTTP" "Recibe las solicitudes /api/v1, limita su tamaño y agrega cabeceras seguras a la respuesta." "proxy() en main.py" {
                    tags "EntradaC3"
                }
                rateLimiter = component "Limitador de solicitudes" "Cuenta solicitudes por IP y política (general, sensible, graphql, webhook)." "permitir() en main.py" {
                    tags "ControlC3"
                }
                identityFilter = component "Filtro de acceso" "Distingue rutas públicas y protegidas, valida la sesión, revisa el rol y la cabecera anti-CSRF." "resolver() en routes.py e introspeccionar() en main.py" {
                    tags "ControlC3"
                }
                identitySigner = component "Firmador de identidad" "Firma con Ed25519 la identidad verificada que se reenvía a los servicios internos." "firmar_identidad() en common/security.py" {
                    tags "ControlC3"
                }
                routeDispatcher = component "Despachador de rutas" "Envía cada solicitud al servicio interno declarado en la tabla de rutas, con el secreto de servicio." "RUTAS en routes.py" {
                    tags "AplicacionC3"
                }
                errorMapper = component "Traductor de errores" "Convierte los fallos en respuestas con el mismo formato, sin mostrar detalles internos." "error() en main.py" {
                    tags "ErrorC3"
                }
                secretClient = component "Cliente de secretos" "Lee los secretos del gateway desde Vault y los guarda un tiempo en memoria." "SecretProvider" {
                    tags "IntegracionC3"
                }
            }

            authService = container "Auth Service" "Registro, inicio y cierre de sesión, validación de tokens y recuperación de contraseña." "Python, FastAPI" {
                tags "Seguridad"

                identityApi = component "API de identidad" "Atiende /register, /login, /introspect, /logout y /password-reset; solo acepta al gateway." "Endpoints de main.py" {
                    tags "EntradaC3"
                }
                credentialsVerifier = component "Verificador de credenciales" "Compara la contraseña con su hash scrypt, aplica la política de claves y bloquea tras 5 intentos fallidos." "common/passwords.py" {
                    tags "ControlC3"
                }
                sessionManager = component "Gestor de sesiones" "Crea sesiones con vencimiento, responde la introspección y revoca el token al cerrar sesión." "login(), introspect() y logout()" {
                    tags "AplicacionC3"
                }
                resetManager = component "Recuperación de contraseña" "Genera tokens de un solo uso y deja el correo de recuperación como archivo .eml." "solicitar_reset() y confirmar_reset()" {
                    tags "AplicacionC3"
                }
                identityRepo = component "Repositorio de identidades" "Lee y escribe credenciales, sesiones y tokens de recuperación." "Colecciones de ms_auth" {
                    tags "AccesoDatosC3"
                }
                secretsClient = component "Cliente de secretos" "Obtiene la credencial de la base de datos y los secretos de servicio desde Vault." "SecretProvider" {
                    tags "IntegracionC3"
                }
            }

            secretManager = container "Administrador de secretos" "Guarda los secretos de cada servicio y solo se los entrega a ese servicio." "HashiCorp Vault" {
                tags "Seguridad"
            }

            graphqlGateway = container "GraphQL Gateway" "Agrega información de varios servicios para las pantallas de seguimiento, cuenta y panel." "Node.js, Apollo Server" {
                tags "Gateway"

                graphqlEndpoint = component "Endpoint GraphQL" "Recibe las operaciones GraphQL; la introspección está desactivada." "index.js" {
                    tags "EntradaC3"
                }
                callerCheck = component "Verificador de llamador e identidad" "Acepta solo al API Gateway y verifica la firma Ed25519 de la identidad." "seguridad.js" {
                    tags "ControlC3"
                }
                queryValidator = component "Validador de consultas" "Rechaza consultas con más de 6 niveles de profundidad o un costo mayor a 600." "limites.js" {
                    tags "ControlC3"
                }
                resolvers = component "Resolvers" "Resuelven resumenPedido, misPedidos, pedidosLocal y panelAdmin, revisando el rol en cada campo." "resolvers.js" {
                    tags "AplicacionC3"
                }
                subsystemClient = component "Cliente de subsistemas" "Llama a los servicios internos agrupando las consultas y reenviando la identidad firmada." "subsistemas.js y DataLoader" {
                    tags "IntegracionC3"
                }
                secretsClient = component "Cliente de secretos" "Lee los secretos del GraphQL Gateway desde Vault." "secretos() en seguridad.js" {
                    tags "IntegracionC3"
                }
            }

            inventory = container "inventory" "Catálogo, precios, personalización, stock y reservas." "Python, FastAPI, gRPC" {
                tags "Privado"
            }
            orders = container "orders" "Creación de pedidos, estados, expiración y exportación para analytics." "Python, FastAPI" {
                tags "Privado"
            }
            clients = container "clients" "Perfil y direcciones de entrega." "Python, FastAPI" {
                tags "Privado"
            }
            payments = container "payments" "Inicio de pagos, notificaciones del proveedor y comprobantes." "Python, FastAPI" {
                tags "Privado"
            }
            analytics = container "analytics" "Reportes de ventas sobre una copia de los pedidos sin datos personales." "Python, FastAPI" {
                tags "Privado"
            }

            dbInventory = container "Datos de inventario" "Productos, categorías, personalización y reservas." "MongoDB, ms_inventory" {
                tags "BaseDatos"
            }
            dbOrders = container "Datos de pedidos" "Pedidos y su historial de estados." "MongoDB, ms_orders" {
                tags "BaseDatos"
            }
            dbClients = container "Datos de clientes" "Perfiles y direcciones." "MongoDB, ms_clients" {
                tags "BaseDatos"
            }
            dbPayments = container "Datos de pagos" "Pagos, eventos procesados y contador de comprobantes." "MongoDB, ms_payments" {
                tags "BaseDatos"
            }
            dbIdentity = container "Datos de identidad" "Credenciales, sesiones y tokens de recuperación." "MongoDB, ms_auth" {
                tags "BaseDatos"
            }
            dbAnalytics = container "Datos de analítica" "Copia de los pedidos con el cliente seudonimizado." "MongoDB, ms_analytics" {
                tags "BaseDatos"
            }
        }

        visitante -> sistema.frontend "Consulta el menú" "Navegador web"
        cliente -> sistema.frontend "Compra y sigue sus pedidos" "Navegador web"
        personal -> sistema.frontend "Prepara y despacha pedidos" "Navegador web"
        administrador -> sistema.frontend "Administra productos, stock y reportes" "Navegador web"
        cliente -> proveedorPagos "Paga en la página del proveedor" "Navegador web"

        sistema.frontend -> sistema.apiGateway.httpEntry "Envía las solicitudes de la interfaz" "HTTP/JSON"
        proveedorPagos -> sistema.apiGateway.httpEntry "Notifica el resultado del pago" "Webhook HTTP/JSON firmado con HMAC"

        sistema.apiGateway.httpEntry -> sistema.apiGateway.rateLimiter "Revisa el límite de solicitudes"
        sistema.apiGateway.httpEntry -> sistema.apiGateway.identityFilter "Revisa ruta, sesión y rol"
        sistema.apiGateway.httpEntry -> sistema.apiGateway.routeDispatcher "Entrega la solicitud autorizada"
        sistema.apiGateway.httpEntry -> sistema.apiGateway.errorMapper "Convierte los fallos en respuestas controladas"
        sistema.apiGateway.identityFilter -> sistema.authService.identityApi "Valida el token por introspección" "HTTP/JSON"
        sistema.apiGateway.identityFilter -> sistema.apiGateway.identitySigner "Pide firmar la identidad verificada"
        sistema.apiGateway.identitySigner -> sistema.apiGateway.secretClient "Obtiene la clave de firma"
        sistema.apiGateway.routeDispatcher -> sistema.apiGateway.secretClient "Obtiene los secretos de servicio"
        sistema.apiGateway.secretClient -> sistema.secretManager "Lee sus secretos" "HTTP con token propio"

        sistema.apiGateway.routeDispatcher -> sistema.authService.identityApi "Reenvía registro, inicio y cierre de sesión y recuperación" "HTTP/JSON"
        sistema.apiGateway.routeDispatcher -> sistema.inventory "Reenvía catálogo y administración de productos" "HTTP/JSON"
        sistema.apiGateway.routeDispatcher -> sistema.orders "Reenvía cotizaciones y pedidos" "HTTP/JSON"
        sistema.apiGateway.routeDispatcher -> sistema.clients "Reenvía perfil y direcciones" "HTTP/JSON"
        sistema.apiGateway.routeDispatcher -> sistema.payments "Reenvía pagos y notificaciones" "HTTP/JSON"
        sistema.apiGateway.routeDispatcher -> sistema.graphqlGateway.graphqlEndpoint "Reenvía operaciones GraphQL" "HTTP/GraphQL"

        sistema.authService.identityApi -> sistema.authService.credentialsVerifier "Verifica la contraseña"
        sistema.authService.identityApi -> sistema.authService.sessionManager "Crea, valida y revoca sesiones"
        sistema.authService.identityApi -> sistema.authService.resetManager "Gestiona la recuperación de contraseña"
        sistema.authService.credentialsVerifier -> sistema.authService.identityRepo "Consulta la credencial"
        sistema.authService.sessionManager -> sistema.authService.identityRepo "Guarda y busca sesiones"
        sistema.authService.resetManager -> sistema.authService.identityRepo "Guarda tokens de recuperación"
        sistema.authService.identityRepo -> sistema.authService.secretsClient "Obtiene la credencial de la base de datos"
        sistema.authService.identityRepo -> sistema.dbIdentity "Lee y escribe identidades" "MongoDB"
        sistema.authService.secretsClient -> sistema.secretManager "Lee sus secretos" "HTTP con token propio"
        sistema.authService.identityApi -> sistema.clients "Crea el perfil del cliente al registrarse" "HTTP/JSON"

        sistema.graphqlGateway.graphqlEndpoint -> sistema.graphqlGateway.callerCheck "Verifica el llamador y la identidad"
        sistema.graphqlGateway.graphqlEndpoint -> sistema.graphqlGateway.queryValidator "Revisa profundidad y costo"
        sistema.graphqlGateway.graphqlEndpoint -> sistema.graphqlGateway.resolvers "Ejecuta la operación"
        sistema.graphqlGateway.callerCheck -> sistema.graphqlGateway.secretsClient "Obtiene la clave pública y el secreto del gateway"
        sistema.graphqlGateway.resolvers -> sistema.graphqlGateway.subsystemClient "Pide los datos de cada campo"
        sistema.graphqlGateway.subsystemClient -> sistema.orders "Consulta pedidos autorizados" "HTTP/JSON con identidad firmada"
        sistema.graphqlGateway.subsystemClient -> sistema.inventory "Consulta productos y stock bajo" "HTTP/JSON con identidad firmada"
        sistema.graphqlGateway.subsystemClient -> sistema.payments "Consulta el estado del pago" "HTTP/JSON con identidad firmada"
        sistema.graphqlGateway.subsystemClient -> sistema.analytics "Consulta el reporte de ventas" "HTTP/JSON con identidad firmada"
        sistema.graphqlGateway.secretsClient -> sistema.secretManager "Lee sus secretos" "HTTP con token propio"

        sistema.orders -> sistema.inventory "Cotiza, reserva, libera y confirma stock" "gRPC con mTLS"
        sistema.orders -> sistema.clients "Pide la dirección y el contacto de entrega" "HTTP/JSON"
        sistema.payments -> sistema.orders "Lee el pedido y confirma el pago" "HTTP/JSON"
        sistema.payments -> proveedorPagos "Crea la sesión de pago y verifica su estado" "HTTP/JSON con clave de API"
        sistema.analytics -> sistema.orders "Copia los pedidos cada 15 segundos" "HTTP/JSON"

        sistema.inventory -> sistema.dbInventory "Lee y escribe" "MongoDB"
        sistema.orders -> sistema.dbOrders "Lee y escribe" "MongoDB"
        sistema.clients -> sistema.dbClients "Lee y escribe" "MongoDB"
        sistema.payments -> sistema.dbPayments "Lee y escribe" "MongoDB"
        sistema.analytics -> sistema.dbAnalytics "Lee y escribe" "MongoDB"

        sistema.inventory -> sistema.secretManager "Lee sus secretos" "HTTP con token propio"
        sistema.orders -> sistema.secretManager "Lee sus secretos" "HTTP con token propio"
        sistema.clients -> sistema.secretManager "Lee sus secretos" "HTTP con token propio"
        sistema.payments -> sistema.secretManager "Lee sus secretos" "HTTP con token propio"
        sistema.analytics -> sistema.secretManager "Lee sus secretos" "HTTP con token propio"
    }

    views {
        systemContext sistema "C1_Contexto" "Personas que usan el sistema y sistemas externos" {
            title "C1 - Contexto de Mr. Sandwich"
            include *
            autoLayout lr
        }

        container sistema "C2_Contenedores" "Aplicaciones y bases de datos de Mr. Sandwich" {
            title "C2 - Contenedores de Mr. Sandwich"
            include *
            autoLayout lr
        }

        container sistema "C2_Consulta_Catalogo" "Contenedores que participan en la consulta del catálogo" {
            title "C2 - Consulta del catálogo"
            include visitante sistema.frontend sistema.apiGateway sistema.inventory sistema.dbInventory sistema.secretManager
            autoLayout lr
        }

        container sistema "C2_Registro_Pedido" "Contenedores que participan en el registro y pago de un pedido" {
            title "C2 - Registro y pago de un pedido"
            include cliente sistema.frontend sistema.apiGateway sistema.authService sistema.orders sistema.inventory sistema.clients sistema.payments sistema.dbOrders sistema.dbPayments proveedorPagos
            autoLayout lr
        }

        component sistema.apiGateway "C3_API_Gateway" "Componentes internos del API Gateway" {
            title "C3 - API Gateway"
            include *
            exclude "sistema.authService -> *" "sistema.graphqlGateway -> *" "sistema.inventory -> *" "sistema.orders -> *" "sistema.clients -> *" "sistema.payments -> *"
            autoLayout lr
        }

        component sistema.authService "C3_AuthService" "Componentes internos del Auth Service" {
            title "C3 - Auth Service"
            include *
            exclude "sistema.apiGateway -> sistema.clients" "sistema.clients -> *"
            autoLayout lr
        }

        component sistema.graphqlGateway "C3_GraphQL_Gateway" "Componentes internos del GraphQL Gateway" {
            title "C3 - GraphQL Gateway"
            include *
            exclude "sistema.apiGateway -> sistema.inventory" "sistema.apiGateway -> sistema.orders" "sistema.apiGateway -> sistema.payments" "sistema.inventory -> *" "sistema.orders -> *" "sistema.payments -> *" "sistema.analytics -> *"
            autoLayout lr
        }

        styles {
            element "Person" {
                shape person
                background #56718A
                color #FFFFFF
            }
            element "Software System" {
                shape roundedbox
                background #0C527A
                color #FFFFFF
            }
            element "Externo" {
                background #8A8A8A
                color #FFFFFF
            }
            element "Container" {
                background #DCEBF7
                color #1B2A38
            }
            element "Frontend" {
                shape webbrowser
            }
            element "Gateway" {
                background #2F5D86
                color #FFFFFF
            }
            element "Seguridad" {
                background #3E4F63
                color #FFFFFF
            }
            element "BaseDatos" {
                shape cylinder
                background #E8EAF0
                color #1B2A38
            }
            element "Component" {
                background #FFFFFF
                color #1B2A38
            }
            relationship "Relationship" {
                dashed true
            }
        }
    }
}
