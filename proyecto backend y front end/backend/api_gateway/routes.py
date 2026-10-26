import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Ruta:
    id: str
    metodo: str
    patron: str                 # ruta externa, con {param}
    destino: str                # servicio interno
    ruta_destino: str           # ruta interna, con los mismos {param}
    acceso: tuple = ("anon",)
    limite: str = "general"     # política de rate limit
    regex: re.Pattern = field(init=False, compare=False)

    def __post_init__(self):
        patron = re.sub(r"\{(\w+)\}", r"(?P<\1>[A-Za-z0-9\-]{1,40})", self.patron)
        object.__setattr__(self, "regex", re.compile(f"^{patron}$"))

    def destino_para(self, params: dict) -> str:
        return self.ruta_destino.format(**params)


CLIENTE = ("cliente",)
STAFF = ("staff", "admin")
ADMIN = ("admin",)
AUTH = ("cliente", "staff", "admin")

RUTAS = [
    # Autenticación (Auth Service)
    Ruta("S03", "POST", "/api/v1/auth/register", "auth", "/register", limite="sensible"),
    Ruta("S04", "POST", "/api/v1/auth/login", "auth", "/login", limite="sensible"),
    Ruta("S05", "POST", "/api/v1/auth/logout", "auth", "/logout", AUTH),
    Ruta("S06", "POST", "/api/v1/auth/password-reset/request", "auth", "/password-reset/request", limite="sensible"),
    Ruta("S07", "POST", "/api/v1/auth/password-reset/confirm", "auth", "/password-reset/confirm", limite="sensible"),
    # Catálogo (inventory)
    Ruta("S01", "GET", "/api/v1/products", "inventory", "/products"),
    Ruta("S02", "GET", "/api/v1/products/{id}", "inventory", "/products/{id}"),
    Ruta("S01b", "GET", "/api/v1/categories", "inventory", "/categories"),
    # Perfil y direcciones (clients)
    Ruta("S09", "GET", "/api/v1/clients/me", "clients", "/me", AUTH),
    Ruta("S10", "PUT", "/api/v1/clients/me", "clients", "/me", AUTH),
    Ruta("S11", "GET", "/api/v1/clients/me/addresses", "clients", "/me/addresses", AUTH),
    Ruta("S12", "POST", "/api/v1/clients/me/addresses", "clients", "/me/addresses", AUTH),
    Ruta("S13", "PUT", "/api/v1/clients/me/addresses/{id}", "clients", "/me/addresses/{id}", AUTH),
    Ruta("S14", "DELETE", "/api/v1/clients/me/addresses/{id}", "clients", "/me/addresses/{id}", AUTH),
    # Pedidos (orders)
    Ruta("S15", "POST", "/api/v1/orders/quote", "orders", "/quote"),
    Ruta("S16", "POST", "/api/v1/orders", "orders", "/orders", CLIENTE),
    Ruta("S17", "GET", "/api/v1/orders/me", "orders", "/orders/me", AUTH),
    Ruta("S18", "GET", "/api/v1/orders/{id}", "orders", "/orders/{id}", AUTH),
    Ruta("S19", "POST", "/api/v1/orders/{id}/cancel", "orders", "/orders/{id}/cancel", AUTH),
    Ruta("S20", "GET", "/api/v1/orders", "orders", "/orders", STAFF),
    Ruta("S21", "PUT", "/api/v1/orders/{id}/status", "orders", "/orders/{id}/status", STAFF),
    # Pagos (payments)
    Ruta("S22", "POST", "/api/v1/payments", "payments", "/payments", CLIENTE),
    Ruta("S23", "GET", "/api/v1/payments/order/{id}", "payments", "/payments/order/{id}", AUTH),
    Ruta("S24", "POST", "/api/v1/payments/webhook", "payments", "/webhook", limite="webhook"),
    # Administración de catálogo y stock (inventory)
    Ruta("S25", "GET", "/api/v1/admin/products", "inventory", "/admin/products", STAFF),
    Ruta("S26", "POST", "/api/v1/admin/products", "inventory", "/admin/products", ADMIN),
    Ruta("S27", "PUT", "/api/v1/admin/products/{id}", "inventory", "/admin/products/{id}", ADMIN),
    Ruta("S28", "DELETE", "/api/v1/admin/products/{id}", "inventory", "/admin/products/{id}", ADMIN),
    Ruta("S29", "PUT", "/api/v1/admin/products/{id}/stock", "inventory", "/admin/products/{id}/stock", STAFF),
    Ruta("S30", "POST", "/api/v1/graphql", "graphql", "/graphql", AUTH, limite="graphql"),
]


def resolver(metodo: str, ruta: str):
    coincide_ruta = False
    for r in RUTAS:
        m = r.regex.match(ruta)
        if m:
            coincide_ruta = True
            if r.metodo == metodo:
                return r, m.groupdict()
    return ("405", None) if coincide_ruta else (None, None)
