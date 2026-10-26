import datetime
import ipaddress
import json
import secrets
from pathlib import Path

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.x509.oid import NameOID
from pymongo import MongoClient
from pymongo.errors import OperationFailure

SERVICIOS = ["gateway", "auth", "clients", "inventory", "orders", "payments", "analytics", "graphql", "provider", "pruebas"]
BASES = {"auth": "ms_auth", "clients": "ms_clients", "inventory": "ms_inventory", "orders": "ms_orders",
         "payments": "ms_payments", "analytics": "ms_analytics"}

# Quién puede llamar a quién (REST). Cada par recibe su propio secreto.
PARES = [
    ("gateway", "auth"), ("gateway", "clients"), ("gateway", "inventory"), ("gateway", "orders"),
    ("gateway", "payments"), ("gateway", "graphql"),
    ("auth", "clients"), ("orders", "clients"), ("payments", "orders"), ("analytics", "orders"),
    ("graphql", "orders"), ("graphql", "inventory"), ("graphql", "payments"), ("graphql", "analytics"),
]
VERIFICAN_IDENTIDAD = ["clients", "inventory", "orders", "payments", "analytics", "graphql"]


def _pem_clave(clave) -> str:
    return clave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                               serialization.NoEncryption()).decode()


def _certificado(cn: str, clave_publica, emisor_cn: str, clave_emisor, es_ca=False, servidor=False):
    ahora = datetime.datetime.now(datetime.timezone.utc)
    builder = (x509.CertificateBuilder()
               .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)]))
               .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, emisor_cn)]))
               .public_key(clave_publica)
               .serial_number(x509.random_serial_number())
               .not_valid_before(ahora - datetime.timedelta(minutes=5))
               .not_valid_after(ahora + datetime.timedelta(days=1 if not es_ca else 2))
               .add_extension(x509.BasicConstraints(ca=es_ca, path_length=None), critical=True))
    if servidor:
        builder = builder.add_extension(x509.SubjectAlternativeName(
            [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
    return builder.sign(clave_emisor, hashes.SHA256()).public_bytes(serialization.Encoding.PEM).decode()


def generar_pki() -> dict:
    ca_clave = ec.generate_private_key(ec.SECP256R1())
    ca_cert = _certificado("MrSandwich CA interna", ca_clave.public_key(), "MrSandwich CA interna", ca_clave, es_ca=True)
    salida = {"ca": ca_cert}
    for cn, servidor in (("inventory", True), ("orders", False), ("pruebas", False)):
        clave = ec.generate_private_key(ec.SECP256R1())
        salida[cn] = (_certificado(cn, clave.public_key(), "MrSandwich CA interna", ca_clave, servidor=servidor),
                      _pem_clave(clave))
    return salida


def clave_seudonimos(runtime: Path) -> str:
    archivo = runtime / "analytics-pseudonym.key"
    if not archivo.exists():
        archivo.write_text(secrets.token_urlsafe(32), encoding="utf-8")
    return archivo.read_text(encoding="utf-8").strip()


def generar_secretos(runtime: Path) -> dict:
    datos = {s: {} for s in SERVICIOS}
    for llamador, destino in PARES:
        valor = secrets.token_urlsafe(32)
        datos[llamador][f"out_{destino}"] = valor
        datos[destino][f"in_{llamador}"] = valor

    privada = ed25519.Ed25519PrivateKey.generate()
    publica = privada.public_key().public_bytes(serialization.Encoding.PEM,
                                                serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    datos["gateway"]["identity_signing_key"] = _pem_clave(privada)
    for s in VERIFICAN_IDENTIDAD:
        datos[s]["identity_public_key"] = publica

    pki = generar_pki()
    datos["inventory"].update(grpc_ca_cert=pki["ca"], grpc_server_cert=pki["inventory"][0],
                              grpc_server_key=pki["inventory"][1])
    datos["orders"].update(grpc_ca_cert=pki["ca"], grpc_client_cert=pki["orders"][0], grpc_client_key=pki["orders"][1])

    api_key, webhook = f"sk_test_{secrets.token_hex(16)}", f"whsec_{secrets.token_hex(16)}"
    datos["payments"].update(provider_api_key=api_key, provider_webhook_secret=webhook)
    datos["provider"].update(api_key=api_key, webhook_secret=webhook)
    datos["orders"]["analytics_pseudonym_key"] = clave_seudonimos(runtime)

    # Credenciales exclusivas de la suite de pruebas: un certificado válido de la CA
    # pero con CN no autorizado, y la API key del proveedor para simular reenvíos.
    datos["pruebas"].update(grpc_ca_cert=pki["ca"], grpc_client_cert=pki["pruebas"][0],
                            grpc_client_key=pki["pruebas"][1], provider_api_key=api_key)
    return datos


# --- MongoDB ------------------------------------------------------------------

def credencial_admin(runtime: Path, puerto: int) -> dict:
    archivo = runtime / "mongo-admin.json"
    if archivo.exists():
        return json.loads(archivo.read_text(encoding="utf-8"))
    cred = {"usuario": "mrsandwich_admin", "clave": secrets.token_urlsafe(24)}
    cliente = MongoClient(f"mongodb://127.0.0.1:{puerto}/?directConnection=true", serverSelectionTimeoutMS=5000)
    try:
        cliente.admin.command("createUser", cred["usuario"], pwd=cred["clave"], roles=["root"])
    except OperationFailure as exc:
        raise SystemExit("MongoDB ya tiene usuarios pero falta mongo-admin.json. "
                         f"Borra {runtime / 'mongo-data'} para reiniciar los datos.") from exc
    archivo.write_text(json.dumps(cred), encoding="utf-8")
    return cred


def cliente_admin(runtime: Path, puerto: int) -> MongoClient:
    cred = credencial_admin(runtime, puerto)
    return MongoClient(f"mongodb://127.0.0.1:{puerto}/?directConnection=true", username=cred["usuario"],
                       password=cred["clave"], authSource="admin", serverSelectionTimeoutMS=5000, tz_aware=True)


def rotar_usuarios_mongo(cliente: MongoClient, datos: dict):
    for servicio, base in BASES.items():
        usuario, clave = f"svc_{servicio}", secrets.token_urlsafe(24)
        db = cliente[base]
        roles = [{"role": "readWrite", "db": base}]
        try:
            db.command("createUser", usuario, pwd=clave, roles=roles)
        except OperationFailure as exc:
            if exc.code != 51003:  # el usuario ya existe
                raise
            db.command("updateUser", usuario, pwd=clave, roles=roles)
        datos[servicio].update(mongo_user=usuario, mongo_password=clave)


# --- Vault --------------------------------------------------------------------

def publicar_en_vault(vault_addr: str, token_raiz: str, datos: dict) -> dict:
    tokens = {}
    with httpx.Client(base_url=vault_addr, headers={"X-Vault-Token": token_raiz}, timeout=5.0) as v:
        for servicio, valores in datos.items():
            v.post(f"/v1/secret/data/mrsandwich/{servicio}", json={"data": valores}).raise_for_status()
            politica = f'path "secret/data/mrsandwich/{servicio}" {{ capabilities = ["read"] }}'
            v.put(f"/v1/sys/policies/acl/mrsandwich-{servicio}", json={"policy": politica}).raise_for_status()
            r = v.post("/v1/auth/token/create", json={"policies": [f"mrsandwich-{servicio}"], "no_default_policy": True,
                                                      "ttl": "24h", "display_name": servicio, "renewable": False})
            r.raise_for_status()
            tokens[servicio] = r.json()["auth"]["client_token"]
    return tokens


def ejecutar(vault_addr: str, token_raiz: str, runtime: Path, puerto_mongo: int) -> dict:
    datos = generar_secretos(runtime)
    with cliente_admin(runtime, puerto_mongo) as cliente:
        rotar_usuarios_mongo(cliente, datos)
    return publicar_en_vault(vault_addr, token_raiz, datos)
