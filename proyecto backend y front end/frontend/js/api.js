
const API_BASE = "http://localhost:8000/api/v1";
const CLAVE_CARRITO = "mrsandwich_carrito";

class ApiError extends Error {
    constructor(status, mensaje, detalles) {
        super(mensaje);
        this.status = status;
        this.detalles = detalles || [];
    }
}

async function api(ruta, { metodo = "GET", cuerpo, cabeceras = {} } = {}) {
    let resp;
    try {
        resp = await fetch(API_BASE + ruta, {
            method: metodo,
            credentials: "include",
            headers: {
                "X-Requested-With": "mrsandwich",
                ...(cuerpo !== undefined ? { "Content-Type": "application/json" } : {}),
                ...cabeceras
            },
            body: cuerpo !== undefined ? JSON.stringify(cuerpo) : undefined
        });
    } catch (err) {
        throw new ApiError(0, "No fue posible conectar con el servidor. Intenta nuevamente.");
    }
    if (resp.status === 204) return null;
    const datos = await resp.json().catch(() => null);
    if (!resp.ok) {
        const error = datos && datos.error ? datos.error : {};
        const graphqlMsg = datos && datos.errors && datos.errors[0] ? datos.errors[0].message : null;
        throw new ApiError(resp.status, error.mensaje || graphqlMsg || "Error inesperado", error.detalles);
    }
    return datos;
}

async function graphql(query, variables = {}) {
    const resp = await api("/graphql", { metodo: "POST", cuerpo: { query, variables } });
    if (!resp.data || Object.values(resp.data).every((v) => v === null)) {
        if (resp.errors && resp.errors.length) throw new ApiError(400, resp.errors[0].message);
    }
    return resp;
}

function formatoPrecio(valor) {
    return "$" + Number(valor || 0).toLocaleString("es-CL");
}

function formatoFecha(iso) {
    if (!iso) return "";
    return new Date(iso).toLocaleString("es-CL", { dateStyle: "short", timeStyle: "short" });
}

const NOMBRES_ESTADO = {
    PENDIENTE_PAGO: "Pendiente de pago",
    PAGADO: "Pagado",
    EN_PREPARACION: "En preparación",
    LISTO: "Listo",
    EN_REPARTO: "En reparto",
    ENTREGADO: "Entregado",
    ANULADO: "Anulado"
};

function el(etiqueta, atributos = {}, ...hijos) {
    const nodo = document.createElement(etiqueta);
    for (const [clave, valor] of Object.entries(atributos)) {
        if (valor === null || valor === undefined || valor === false) continue;
        if (clave === "class") nodo.className = valor;
        else if (clave.startsWith("on")) nodo.addEventListener(clave.slice(2), valor);
        else nodo.setAttribute(clave, valor === true ? "" : valor);
    }
    for (const hijo of hijos.flat()) {
        if (hijo === null || hijo === undefined || hijo === false) continue;
        nodo.append(hijo instanceof Node ? hijo : document.createTextNode(String(hijo)));
    }
    return nodo;
}

function mostrarAviso(texto) {
    const aviso = document.querySelector(".aviso");
    if (!aviso) return;
    aviso.textContent = texto;
    aviso.hidden = false;
    clearTimeout(mostrarAviso.timer);
    mostrarAviso.timer = setTimeout(() => { aviso.hidden = true; }, 3500);
}

function chipEstado(estado) {
    return el("span", { class: `chip-estado estado-${estado.toLowerCase()}` }, NOMBRES_ESTADO[estado] || estado);
}

// --- Sesión ------------------------------------------------------------------

let _sesion = null;

async function obtenerSesion() {
    if (_sesion) return _sesion;
    try {
        _sesion = await api("/session");
    } catch (err) {
        _sesion = { autenticado: false };
    }
    return _sesion;
}

function tieneRol(sesion, ...roles) {
    return Boolean(sesion && sesion.autenticado && roles.some((r) => (sesion.roles || []).includes(r)));
}

async function cerrarSesion() {
    try {
        await api("/auth/logout", { metodo: "POST" });
    } catch (err) {
    }
    _sesion = null;
    window.location.href = "index.html";
}

async function exigirSesion(...roles) {
    const sesion = await obtenerSesion();
    if (!sesion.autenticado) {
        window.location.href = "login.html?volver=" + encodeURIComponent(location.pathname.split("/").pop() + location.search);
        return null;
    }
    if (roles.length && !tieneRol(sesion, ...roles)) {
        document.querySelector("main").replaceChildren(
            el("section", { class: "panel" }, el("h1", {}, "Acceso restringido"),
                el("p", {}, "Tu cuenta no tiene permisos para esta sección."),
                el("a", { href: "index.html", class: "btn-primario" }, "Volver al menú")));
        return null;
    }
    return sesion;
}


function leerCarrito() {
    try {
        const datos = JSON.parse(localStorage.getItem(CLAVE_CARRITO) || "[]");
        return Array.isArray(datos) ? datos : [];
    } catch (err) {
        return [];
    }
}

function guardarCarrito(lineas) {
    try {
        localStorage.setItem(CLAVE_CARRITO, JSON.stringify(lineas));
    } catch (err) {
        mostrarAviso("No se pudo guardar el carrito en este navegador.");
    }
    actualizarContadorCarrito();
}

function actualizarContadorCarrito() {
    const total = leerCarrito().reduce((suma, l) => suma + l.qty, 0);
    document.querySelectorAll("[data-carrito-cantidad]").forEach((n) => { n.textContent = total; });
}


async function iniciarCabecera() {
    actualizarContadorCarrito();
    const boton = document.querySelector("[data-sesion]");
    if (!boton) return;
    const sesion = await obtenerSesion();
    if (!sesion.autenticado) return;
    const esPersonal = tieneRol(sesion, "staff", "admin");
    boton.querySelector("span").textContent = esPersonal ? "Panel del local" : "Mi cuenta";
    boton.setAttribute("href", esPersonal ? "admin.html" : "cuenta.html");
}

function iniciarBusqueda(alBuscar) {
    const botonBuscar = document.querySelector('[data-accion="buscar"]');
    const barra = document.querySelector(".barra-busqueda");
    if (!botonBuscar || !barra) return;

    const input = barra.querySelector("input");

    botonBuscar.addEventListener("click", () => {
        barra.hidden = !barra.hidden;
        if (!barra.hidden) input.focus();
    });

    barra.querySelector(".barra-cerrar").addEventListener("click", () => {
        barra.hidden = true;
        input.value = "";
        if (alBuscar) alBuscar("");
    });

    if (alBuscar) {
        barra.addEventListener("submit", (e) => e.preventDefault());
        input.addEventListener("input", () => alBuscar(input.value));
    }
}

function mensajeError(err) {
    if (err instanceof ApiError && err.detalles.length) {
        return err.message + ": " + err.detalles.map((d) => `${d.campo} (${d.mensaje})`).join(", ");
    }
    return err.message || "Error inesperado";
}
