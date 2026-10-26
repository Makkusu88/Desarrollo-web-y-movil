
const CONSULTA_LOCAL = `
query PedidosLocal($estado: EstadoPedido, $pagina: Int!, $tamano: Int!) {
  pedidosLocal(estado: $estado, pagina: $pagina, tamano: $tamano) {
    total
    items {
      id estado tipoEntrega creadoEn total notas
      items { nombre opcion extras cantidad }
      direccionEntrega { calle numero comuna referencia }
      contacto { nombre telefono }
      pago { estado comprobante }
    }
  }
}`;

const CONSULTA_PANEL = `
query Panel($desde: String, $hasta: String) {
  panelAdmin(desde: $desde, hasta: $hasta) {
    ventas {
      desde hasta totalVentas pedidosPagados ticketPromedio clientesDistintos actualizadoEn
      porDia { dia pedidos ventas }
      topProductos { nombre unidades ventas }
      porEstado { clave cantidad }
      porTipoEntrega { clave cantidad }
    }
    stockBajo { id nombre stock stockMinimo }
  }
}`;

function siguientesEstados(p) {
    switch (p.estado) {
        case "PAGADO": return ["EN_PREPARACION"];
        case "EN_PREPARACION": return ["LISTO"];
        case "LISTO": return [p.tipoEntrega === "DELIVERY" ? "EN_REPARTO" : "ENTREGADO"];
        case "EN_REPARTO": return ["ENTREGADO"];
        default: return [];
    }
}

let sesionAdmin = null;
let temporizadorPedidos = null;

async function cargarPedidosLocal() {
    const contenedor = document.querySelector("[data-pedidos-local]");
    const estado = document.querySelector("[data-filtro-estado]").value || null;
    clearTimeout(temporizadorPedidos);
    try {
        const resp = await graphql(CONSULTA_LOCAL, { estado, pagina: 1, tamano: 20 });
        const pagina = resp.data.pedidosLocal;
        contenedor.replaceChildren(...pagina.items.map(tarjetaPedidoLocal));
        if (!pagina.items.length) contenedor.append(el("p", { class: "nota" }, "No hay pedidos en curso."));
    } catch (err) {
        contenedor.replaceChildren(el("p", { class: "mensaje error" }, mensajeError(err)));
    }
    temporizadorPedidos = setTimeout(cargarPedidosLocal, 10000);
}

function tarjetaPedidoLocal(p) {
    const acciones = el("div", { class: "botonera" });
    for (const destino of siguientesEstados(p)) {
        const boton = el("button", { type: "button", class: "btn-primario btn-chico" }, `Marcar ${NOMBRES_ESTADO[destino].toLowerCase()}`);
        boton.addEventListener("click", async () => {
            boton.disabled = true;
            try {
                await api(`/orders/${encodeURIComponent(p.id)}/status`, { metodo: "PUT", cuerpo: { estado: destino } });
                mostrarAviso(`${p.id}: ${NOMBRES_ESTADO[destino]}`);
                cargarPedidosLocal();
            } catch (err) {
                mostrarAviso(mensajeError(err));
                boton.disabled = false;
            }
        });
        acciones.append(boton);
    }
    if (tieneRol(sesionAdmin, "admin") && ["PENDIENTE_PAGO", "PAGADO"].includes(p.estado)) {
        const anular = el("button", { type: "button", class: "btn-peligro btn-chico" }, "Anular");
        anular.addEventListener("click", async () => {
            if (!confirm(`¿Anular ${p.id}?${p.estado === "PAGADO" ? " Quedará marcado para reembolso." : ""}`)) return;
            try {
                await api(`/orders/${encodeURIComponent(p.id)}/cancel`, { metodo: "POST" });
                cargarPedidosLocal();
            } catch (err) {
                mostrarAviso(mensajeError(err));
            }
        });
        acciones.append(anular);
    }
    const d = p.direccionEntrega;
    return el("article", { class: "tarjeta-pedido" },
        el("div", { class: "cabeza" }, el("strong", {}, `${p.id} · ${formatoFecha(p.creadoEn)}`), chipEstado(p.estado)),
        el("ul", { class: "linea-detalle", style: "margin:0;padding-left:18px" },
            p.items.map((i) => el("li", {}, `${i.cantidad} × ${i.nombre}`, [i.opcion, ...i.extras].filter(Boolean).length
                ? ` (${[i.opcion, ...i.extras].filter(Boolean).join(", ")})` : ""))),
        p.notas ? el("div", { class: "nota" }, `Nota: ${p.notas}`) : null,
        el("div", { class: "linea-detalle" }, p.tipoEntrega === "DELIVERY" && d
            ? `Delivery: ${d.calle} ${d.numero}, ${d.comuna}${d.referencia ? " · " + d.referencia : ""}`
            : "Retiro en el local",
            p.contacto ? ` · ${p.contacto.nombre}${p.contacto.telefono ? " " + p.contacto.telefono : ""}` : ""),
        el("div", { class: "cabeza" }, el("strong", {}, formatoPrecio(p.total)),
            el("span", { class: "nota" }, p.pago ? `Pago ${p.pago.estado.toLowerCase()}` : "")),
        acciones);
}

// --- Productos y stock -> S25-S29 ----------------------------------------------

async function cargarProductos() {
    const cuerpo = document.querySelector("[data-productos]");
    const esAdmin = tieneRol(sesionAdmin, "admin");
    let productos;
    try {
        productos = await api("/admin/products");
    } catch (err) {
        cuerpo.replaceChildren(el("tr", {}, el("td", { colspan: "7" }, mensajeError(err))));
        return;
    }
    cuerpo.replaceChildren(...productos.map((p) => {
        const stock = el("input", { type: "number", min: "0", max: "10000", value: String(p.stock), "aria-label": `Stock de ${p.nombre}` });
        const guardar = el("button", { type: "button", class: "btn-secundario btn-chico" }, "Guardar stock");
        guardar.addEventListener("click", async () => {
            try {
                await api(`/admin/products/${p.id}/stock`, { metodo: "PUT", cuerpo: { stock: Number(stock.value) } });
                mostrarAviso(`Stock de ${p.nombre} actualizado`);
            } catch (err) {
                mostrarAviso(mensajeError(err));
            }
        });
        const acciones = el("div", { class: "botonera" }, guardar);
        if (esAdmin) {
            const editar = el("button", { type: "button", class: "btn-secundario btn-chico" }, "Editar");
            const borrar = el("button", { type: "button", class: "btn-peligro btn-chico" }, "Dar de baja");
            editar.addEventListener("click", () => editarProducto(p));
            borrar.addEventListener("click", async () => {
                if (!confirm(`¿Dar de baja "${p.nombre}"? Los pedidos históricos se conservan.`)) return;
                try {
                    await api(`/admin/products/${p.id}`, { metodo: "DELETE" });
                    cargarProductos();
                } catch (err) {
                    mostrarAviso(mensajeError(err));
                }
            });
            acciones.append(editar, borrar);
        }
        return el("tr", { class: p.stock <= p.stock_minimo ? "stock-bajo" : null },
            el("td", {}, p.id), el("td", {}, p.nombre), el("td", {}, p.categoria), el("td", {}, formatoPrecio(p.precio)),
            el("td", {}, stock, p.stock <= p.stock_minimo ? el("div", { class: "nota" }, "Stock bajo") : null),
            el("td", {}, p.disponible ? "Sí" : "No"), el("td", {}, acciones));
    }));
}

function editarProducto(p) {
    const form = document.querySelector("[data-producto]");
    for (const campo of ["id", "nombre", "categoria", "precio", "descripcion", "imagen", "stock", "stock_minimo"]) {
        form[campo].value = p[campo] ?? "";
    }
    form.disponible.value = String(p.disponible);
    document.querySelector("[data-titulo-producto]").textContent = `Editar producto ${p.id}`;
    form.scrollIntoView({ behavior: "smooth" });
}

async function iniciarFormularioProducto() {
    const form = document.querySelector("[data-producto]");
    const categorias = await api("/categories");
    form.categoria.replaceChildren(...categorias.map((c) => el("option", { value: c.id }, c.nombre)));
    form.addEventListener("reset", () => {
        document.querySelector("[data-titulo-producto]").textContent = "Nuevo producto";
        form.id.value = "";
    });
    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const datos = Object.fromEntries(new FormData(form));
        const id = datos.id;
        const cuerpo = {
            nombre: datos.nombre.trim(), categoria: datos.categoria, precio: Number(datos.precio),
            descripcion: datos.descripcion.trim(), imagen: datos.imagen, disponible: datos.disponible === "true",
            stock: Number(datos.stock), stock_minimo: Number(datos.stock_minimo)
        };
        try {
            if (id) await api(`/admin/products/${id}`, { metodo: "PUT", cuerpo });
            else await api("/admin/products", { metodo: "POST", cuerpo });
            form.reset();
            mostrarAviso("Producto guardado");
            cargarProductos();
        } catch (err) {
            mostrarAviso(mensajeError(err));
        }
    });
}

// --- Reportes -> S30 panelAdmin (analytics + inventory) -------------------------

async function cargarReporte() {
    const contenedor = document.querySelector("[data-reporte]");
    const filtro = document.querySelector("[data-filtro-reporte]");
    const variables = { desde: filtro.desde.value || null, hasta: filtro.hasta.value || null };
    let resp;
    try {
        resp = await graphql(CONSULTA_PANEL, variables);
    } catch (err) {
        contenedor.replaceChildren(el("p", { class: "mensaje error" }, mensajeError(err)));
        return;
    }
    const panel = resp.data?.panelAdmin;
    const partes = [];
    if (resp.errors?.length) {
        partes.push(el("p", { class: "mensaje error" }, "Parte del reporte no está disponible: ",
            resp.errors.map((e) => e.message).join("; ")));
    }
    const v = panel?.ventas;
    if (v) {
        if (!filtro.desde.value) filtro.desde.value = v.desde;
        if (!filtro.hasta.value) filtro.hasta.value = v.hasta;
        const maximo = Math.max(1, ...v.porDia.map((d) => d.ventas));
        partes.push(
            el("div", { class: "indicadores" },
                indicador("Ventas", formatoPrecio(v.totalVentas)), indicador("Pedidos pagados", v.pedidosPagados),
                indicador("Ticket promedio", formatoPrecio(v.ticketPromedio)), indicador("Clientes distintos", v.clientesDistintos)),
            el("h2", {}, "Ventas por día"),
            el("div", { class: "barras" }, v.porDia.length ? v.porDia.map((d) => el("div", { class: "barra" },
                el("span", {}, d.dia.slice(5)),
                el("div", { class: "barra-relleno", style: `width:${Math.round((d.ventas / maximo) * 100)}%`, title: `${d.pedidos} pedidos` }),
                el("span", {}, formatoPrecio(d.ventas)))) : el("p", { class: "nota" }, "Sin ventas en el período.")),
            el("h2", {}, "Productos más vendidos"),
            el("div", { class: "tabla-contenedor" }, el("table", { class: "tabla" },
                el("thead", {}, el("tr", {}, el("th", {}, "Producto"), el("th", {}, "Unidades"), el("th", {}, "Ventas"))),
                el("tbody", {}, v.topProductos.map((t) => el("tr", {}, el("td", {}, t.nombre), el("td", {}, t.unidades),
                    el("td", {}, formatoPrecio(t.ventas))))))),
            el("p", { class: "nota" }, `Pedidos por estado: ${v.porEstado.map((e) => `${NOMBRES_ESTADO[e.clave] || e.clave} ${e.cantidad}`).join(" · ") || "—"}`),
            el("p", { class: "nota" }, `Datos actualizados: ${formatoFecha(v.actualizadoEn)} (la analítica se sincroniza cada pocos segundos).`));
    }
    if (panel?.stockBajo) {
        partes.push(el("h2", {}, "Stock bajo"), el("ul", {}, panel.stockBajo.length
            ? panel.stockBajo.map((p) => el("li", {}, `${p.nombre}: ${p.stock} (mínimo ${p.stockMinimo})`))
            : el("li", {}, "Todo el stock está sobre el mínimo.")));
    }
    contenedor.replaceChildren(...partes);
}

function indicador(titulo, valor) {
    return el("div", { class: "indicador" }, el("span", {}, titulo), el("strong", {}, valor));
}

// --- Pestañas ------------------------------------------------------------------

function activarPestana(nombre) {
    document.querySelectorAll("[data-pestana]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.pestana === nombre)));
    document.querySelectorAll("[data-vista]").forEach((v) => { v.hidden = v.dataset.vista !== nombre; });
    if (nombre === "pedidos") cargarPedidosLocal();
    else clearTimeout(temporizadorPedidos);
    if (nombre === "productos") cargarProductos();
    if (nombre === "reportes") cargarReporte();
}

async function iniciarAdmin() {
    sesionAdmin = await exigirSesion("staff", "admin");
    if (!sesionAdmin) return;
    if (tieneRol(sesionAdmin, "admin")) {
        document.querySelectorAll("[data-solo-admin]").forEach((n) => { n.hidden = false; });
        iniciarFormularioProducto().catch((err) => mostrarAviso(mensajeError(err)));
    }
    document.querySelectorAll("[data-pestana]").forEach((b) => b.addEventListener("click", () => activarPestana(b.dataset.pestana)));
    document.querySelector("[data-cerrar-sesion]").addEventListener("click", cerrarSesion);
    document.querySelector("[data-filtro-estado]").addEventListener("change", cargarPedidosLocal);
    document.querySelector("[data-filtro-reporte]").addEventListener("submit", (e) => {
        e.preventDefault();
        cargarReporte();
    });
    activarPestana("pedidos");
}

document.addEventListener("DOMContentLoaded", () => {
    iniciarCabecera();
    iniciarAdmin();
});
