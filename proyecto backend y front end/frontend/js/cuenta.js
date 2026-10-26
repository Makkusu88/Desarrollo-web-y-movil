
function mensajeEn(form, texto) {
    const m = form.querySelector(".login-mensaje");
    m.textContent = texto;
    m.hidden = !texto;
}

const POLITICA_CLAVE = /^(?=.*[A-Za-z])(?=.*\d).{8,128}$/;


function iniciarRegistro() {
    const form = document.querySelector("[data-registro]");
    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const datos = Object.fromEntries(new FormData(form));
        if (datos.nombre.trim().length < 2) return mensajeEn(form, "Ingresa tu nombre.");
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(datos.email.trim())) return mensajeEn(form, "El email no es válido.");
        if (datos.telefono && !/^\+?\d{8,12}$/.test(datos.telefono.trim())) return mensajeEn(form, "Teléfono inválido (ej: +56912345678).");
        if (!POLITICA_CLAVE.test(datos.password)) return mensajeEn(form, "La contraseña debe tener al menos 8 caracteres, con letras y números.");
        if (datos.password !== datos.password2) return mensajeEn(form, "Las contraseñas no coinciden.");
        const boton = form.querySelector("button[type=submit]");
        boton.disabled = true;
        try {
            await api("/auth/register", { metodo: "POST", cuerpo: {
                nombre: datos.nombre.trim(), email: datos.email.trim(), password: datos.password,
                telefono: datos.telefono.trim() || null
            } });
            await api("/auth/login", { metodo: "POST", cuerpo: { email: datos.email.trim(), password: datos.password } });
            form.reset();
            mensajeEn(form, "¡Cuenta creada! Redirigiendo...");
            setTimeout(() => { window.location.href = "cuenta.html"; }, 800);
        } catch (err) {
            mensajeEn(form, err.status === 409 ? "Ese email ya está registrado." : mensajeError(err));
        } finally {
            boton.disabled = false;
        }
    });
}


function iniciarRestablecer() {
    const solicitar = document.querySelector("[data-solicitar]");
    const confirmar = document.querySelector("[data-confirmar]");
    const token = new URLSearchParams(location.search).get("token");
    if (token) {
        solicitar.hidden = true;
        confirmar.hidden = false;
        history.replaceState(null, "", "restablecer.html");
    }

    solicitar.addEventListener("submit", async (e) => {
        e.preventDefault();
        const email = solicitar.email.value.trim();
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return mensajeEn(solicitar, "El email no es válido.");
        try {
            const r = await api("/auth/password-reset/request", { metodo: "POST", cuerpo: { email } });
            mensajeEn(solicitar, r.mensaje);
        } catch (err) {
            mensajeEn(solicitar, mensajeError(err));
        }
    });

    confirmar.addEventListener("submit", async (e) => {
        e.preventDefault();
        const { password, password2 } = Object.fromEntries(new FormData(confirmar));
        if (!POLITICA_CLAVE.test(password)) return mensajeEn(confirmar, "La contraseña debe tener al menos 8 caracteres, con letras y números.");
        if (password !== password2) return mensajeEn(confirmar, "Las contraseñas no coinciden.");
        try {
            await api("/auth/password-reset/confirm", { metodo: "POST", cuerpo: { token, password } });
            confirmar.reset();
            mensajeEn(confirmar, "Contraseña actualizada. Ya puedes iniciar sesión.");
            setTimeout(() => { window.location.href = "login.html"; }, 1500);
        } catch (err) {
            mensajeEn(confirmar, mensajeError(err));
        }
    });
}


const CONSULTA_MIS_PEDIDOS = `
query MisPedidos($pagina: Int!, $tamano: Int!) {
  misPedidos(pagina: $pagina, tamano: $tamano) {
    total pagina tamano
    items { id estado tipoEntrega creadoEn total pago { estado } items { nombre cantidad producto { imagen } } }
  }
}`;

async function iniciarCuenta() {
    const sesion = await exigirSesion();
    if (!sesion) return;
    if (tieneRol(sesion, "staff", "admin")) {
        document.querySelector("#pedidos").replaceChildren(el("h2", {}, "Cuenta del personal"),
            el("p", {}, "Gestiona los pedidos desde el "), el("a", { href: "admin.html", class: "btn-primario" }, "Panel del local"));
    }

    document.querySelector("[data-cerrar-sesion]").addEventListener("click", cerrarSesion);

    // Perfil
    const formPerfil = document.querySelector("[data-perfil]");
    try {
        const perfil = await api("/clients/me");
        formPerfil.email.value = perfil.email;
        formPerfil.nombre.value = perfil.nombre;
        formPerfil.telefono.value = perfil.telefono || "";
    } catch (err) {
        mostrarAviso(mensajeError(err));
    }
    formPerfil.addEventListener("submit", async (e) => {
        e.preventDefault();
        try {
            await api("/clients/me", { metodo: "PUT", cuerpo: {
                nombre: formPerfil.nombre.value.trim(), telefono: formPerfil.telefono.value.trim() || null } });
            mostrarAviso("Datos actualizados");
        } catch (err) {
            mostrarAviso(mensajeError(err));
        }
    });

    // Direcciones
    const listaDir = document.querySelector("[data-direcciones]");
    const formDir = document.querySelector("[data-direccion]");
    const botonDir = document.querySelector("[data-guardar-direccion]");

    async function cargarDirecciones() {
        const direcciones = await api("/clients/me/addresses");
        listaDir.replaceChildren(...direcciones.map((d) => {
            const editar = el("button", { type: "button", class: "btn-secundario btn-chico" }, "Editar");
            const borrar = el("button", { type: "button", class: "btn-peligro btn-chico" }, "Eliminar");
            editar.addEventListener("click", () => {
                for (const campo of ["id", "alias", "calle", "numero", "comuna", "referencia"]) formDir[campo].value = d[campo] || "";
                botonDir.textContent = "Guardar cambios";
                formDir.scrollIntoView({ behavior: "smooth" });
            });
            borrar.addEventListener("click", async () => {
                if (!confirm(`¿Eliminar la dirección "${d.alias}"?`)) return;
                try {
                    await api(`/clients/me/addresses/${encodeURIComponent(d.id)}`, { metodo: "DELETE" });
                    cargarDirecciones();
                } catch (err) {
                    mostrarAviso(mensajeError(err));
                }
            });
            return el("li", { class: "linea", style: "grid-template-columns:minmax(0,1fr) auto" },
                el("div", {}, el("div", { class: "linea-nombre" }, d.alias),
                    el("div", { class: "linea-detalle" }, `${d.calle} ${d.numero}, ${d.comuna}${d.referencia ? " · " + d.referencia : ""}`)),
                el("div", { class: "botonera" }, editar, borrar));
        }));
        if (!direcciones.length) listaDir.append(el("li", { class: "nota" }, "Aún no tienes direcciones."));
    }

    formDir.addEventListener("reset", () => { botonDir.textContent = "Agregar dirección"; });
    formDir.addEventListener("submit", async (e) => {
        e.preventDefault();
        const datos = Object.fromEntries(new FormData(formDir));
        const id = datos.id;
        delete datos.id;
        datos.referencia = datos.referencia.trim() || null;
        try {
            if (id) await api(`/clients/me/addresses/${encodeURIComponent(id)}`, { metodo: "PUT", cuerpo: datos });
            else await api("/clients/me/addresses", { metodo: "POST", cuerpo: datos });
            formDir.reset();
            mostrarAviso("Dirección guardada");
            cargarDirecciones();
        } catch (err) {
            mostrarAviso(mensajeError(err));
        }
    });
    cargarDirecciones().catch((err) => mostrarAviso(mensajeError(err)));

    if (tieneRol(sesion, "cliente")) cargarPedidos(1);
}

async function cargarPedidos(pagina) {
    const contenedor = document.querySelector("[data-pedidos]");
    const paginacion = document.querySelector("[data-paginacion]");
    const tamano = 5;
    try {
        const resp = await graphql(CONSULTA_MIS_PEDIDOS, { pagina, tamano });
        const datos = resp.data.misPedidos;
        contenedor.replaceChildren(...datos.items.map((p) => el("a", { class: "tarjeta-pedido", href: `pedido.html?id=${p.id}` },
            el("div", { class: "cabeza" }, el("strong", {}, p.id), chipEstado(p.estado)),
            el("div", { class: "linea-detalle" }, `${formatoFecha(p.creadoEn)} · ${p.tipoEntrega === "DELIVERY" ? "Delivery" : "Retiro"}`),
            el("div", {}, p.items.map((i) => `${i.cantidad} × ${i.nombre}`).join(", ")),
            el("div", { class: "cabeza" }, el("strong", {}, formatoPrecio(p.total)),
                el("span", { class: "nota" }, p.pago ? `Pago ${p.pago.estado.toLowerCase()}` : "Sin pago")))));
        if (!datos.items.length) contenedor.append(el("p", { class: "nota" }, "Aún no tienes pedidos."));
        const paginas = Math.max(1, Math.ceil(datos.total / tamano));
        const anterior = el("button", { type: "button", class: "btn-secundario btn-chico", disabled: pagina <= 1 }, "Anterior");
        const siguiente = el("button", { type: "button", class: "btn-secundario btn-chico", disabled: pagina >= paginas }, "Siguiente");
        anterior.addEventListener("click", () => cargarPedidos(pagina - 1));
        siguiente.addEventListener("click", () => cargarPedidos(pagina + 1));
        paginacion.replaceChildren(anterior, el("span", { class: "nota" }, `Página ${pagina} de ${paginas}`), siguiente);
    } catch (err) {
        contenedor.replaceChildren(el("p", { class: "mensaje error" }, mensajeError(err)));
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const pagina = document.body.dataset.pagina;
    if (pagina === "registro") iniciarRegistro();
    else if (pagina === "restablecer") iniciarRestablecer();
    else if (pagina === "cuenta") {
        iniciarCabecera();
        iniciarCuenta();
    }
});
