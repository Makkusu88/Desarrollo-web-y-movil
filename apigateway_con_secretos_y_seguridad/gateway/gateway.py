import os #selinux enforcing
import secrets
import httpx


from fastapi import FastAPI, Header, HTTPException, Depends, Request, Response

from fastapi.security import(
    HTTPBearer,
    HTTPAuthorizationCredentials
)

security = HTTPBearer(
    auto_error= False
)


AUTH_SERVICE_URL = os.getenv(
    "AUTH_SERVICE_URL",
    "http://127.0.0.1:8100"
)

VAULT_ADDR =os.getenv(
    "VAULT_ADDR", "http://127.0.0.1:8200"
)
VAULT_TOKEN = os.getenv(
    "VAULT_TOKEN" 
)
if not VAULT_TOKEN:
    raise RuntimeError(
        "VAULT TOKEN no esta configurado"
    )
    
async def get_gateway_secrets():
    url =(
        f"{VAULT_ADDR}"
        "/v1/secret/data/gateway"
    )
    Header = {
        "X-Vault-Token": VAULT_TOKEN
    } 
    
    async with httpx.AsyncClient(timeout= 5.0) as client:
        Response = await client.get(
            url,
            headers= Header
        )
    if Response.status_code != 200:
        raise HTTPException(
            status_code= 500,
            detail="No fue posible acceder a Vault"            
        )
    vault_response = Response.json()
    return vault_response["data"]["data"]

async def authenticate_client(
    credetials:
        HTTPAuthorizationCredentials = Depends(security)
):
    if credetials is None:
        raise HTTPException(
            status_code=401,
            detail="Bearer token requerido"
        )
    gateway_secrets = (
            await get_gateway_secrets()
        )
    introspection_secret = (
        gateway_secrets["auth_introspection_secret"]
    )
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response =await client.post(
                f"{AUTH_SERVICE_URL}/introspect",
                json={"token": credetials.credentials},
                headers ={
                    "X-Gateway-Auth-Secret": introspection_secret
                }
            )
    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Authentication service no disponible"
            
        )
    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail = "Error consultado Authentication Service"
        )
    identity = response.json()
    if not identity.get(
        "active",
        False
    ):
        raise HTTPException(
            status_code=401,
            detail="Token invalido o expirado"
        )
    return{
        "user_id": identity["user_id"],
        "username": identity["username"],
        "roles": identity["roles"],
        "backend_secret": gateway_secrets["backend_shared_secret"]
    }

        
app = FastAPI(title="MrSandwich API Gateway")

BACKEND_URL = "http://localhost:9000"
BACKEND_URL2 = "http://localhost:9100"



"""
@app.get("/api/products")
async def products():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BACKEND_URL}/products"
        )
    return response.json()

@app.get("/api/orders")
async def orders():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BACKEND_URL}/orders"
        )
    return response.json()

@app.get("/api/productos")
async def productos():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BACKEND_URL2}/productos"
        )
    return response.json()

@app.get("/api/ordenes")
async def ordenes():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BACKEND_URL2}/ordenes"
        )
    return response.json()
"""

@app.api_route(
    "/api/{path:path}",
    methods =["GET", "POST","PUT", "PATH", "DELETE"]
)

async def proxy(
    path: str,
    request: Request,
    auth = Depends(authenticate_client)
):
    target_url = (
        f"{BACKEND_URL}/{path}"
    )
    body = await request.body()
    gateway_headers ={
        "X-Gateway-Secret":
        auth["backend_secret"],
        "X-Authenticated-Client":
            auth["client_id"],
        "X-Authenticated-User":
            auth["username"],
        "X-Authenticated-Roles":
        ",".join(auth["roles"])
            
    }
    content_type = request.headers.get(
        "content-type"
    )
    if content_type:
        gateway_headers["content_type"] = content_type
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            upstream = await client.request(
                method=request.method,
                url= target_url,
                params =request.query_params,
                content=body,
                headers= gateway_headers
            )
    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail= "Backend no disponible"
        )
    response_headers ={}
    if "content-type" in upstream.headers:
        response_headers["contet-type"] = upstream.headers["content-type"]
    return Response(
        content= upstream.content,
        status_code= upstream.status_code,
        headers=response_headers
    )