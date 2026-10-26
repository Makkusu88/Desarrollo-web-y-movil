from urllib.parse import quote_plus

from pymongo import MongoClient
from pymongo.database import Database

from common.config import BASES_DE_DATOS, HOST_INTERNO, PUERTOS
from common.secret_provider import SecretProvider


def conectar(servicio: str, secretos: SecretProvider) -> Database:
    nombre_db = BASES_DE_DATOS[servicio]
    usuario = quote_plus(secretos.get("mongo_user"))
    clave = quote_plus(secretos.get("mongo_password"))
    uri = (f"mongodb://{usuario}:{clave}@{HOST_INTERNO}:{PUERTOS['mongo']}/{nombre_db}"
           f"?authSource={nombre_db}")
    cliente = MongoClient(uri, serverSelectionTimeoutMS=3000, timeoutMS=5000, appname=servicio, tz_aware=True)
    return cliente[nombre_db]
