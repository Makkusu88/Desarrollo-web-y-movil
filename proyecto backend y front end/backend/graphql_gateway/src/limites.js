// Reglas de validación que se aplican antes de ejecutar cualquier operación:
// profundidad máxima y costo estimado (las listas multiplican por su tamaño).
import { GraphQLError, Kind } from 'graphql';

export const PROFUNDIDAD_MAXIMA = 6;
// Holgura sobre la consulta legítima más cara del frontend (pedidosLocal con 20 pedidos ≈ 510).
export const COSTO_MAXIMO = 600;

// Costo base de los campos que llaman a subsistemas. El resto vale 1.
const COSTO_CAMPO = { resumenPedido: 10, misPedidos: 10, pedidosLocal: 10, panelAdmin: 20, producto: 2, pago: 2 };
const LISTAS_PAGINADAS = new Set(['misPedidos', 'pedidosLocal']);

function argumentoEntero(nodo, nombre, porDefecto, variables) {
  const arg = nodo.arguments?.find((a) => a.name.value === nombre);
  if (!arg) return porDefecto;
  if (arg.value.kind === Kind.INT) return Number(arg.value.value);
  if (arg.value.kind === Kind.VARIABLE) return Number(variables?.[arg.value.name.value] ?? porDefecto);
  return porDefecto;
}

function medir(seleccion, fragmentos, variables, profundidad, visitados) {
  let maxProf = profundidad;
  let costo = 0;
  for (const nodo of seleccion?.selections ?? []) {
    if (nodo.kind === Kind.FRAGMENT_SPREAD) {
      const nombre = nodo.name.value;
      if (visitados.has(nombre)) continue;
      const r = medir(fragmentos[nombre]?.selectionSet, fragmentos, variables, profundidad, new Set([...visitados, nombre]));
      maxProf = Math.max(maxProf, r.profundidad);
      costo += r.costo;
    } else if (nodo.kind === Kind.INLINE_FRAGMENT) {
      const r = medir(nodo.selectionSet, fragmentos, variables, profundidad, visitados);
      maxProf = Math.max(maxProf, r.profundidad);
      costo += r.costo;
    } else if (nodo.kind === Kind.FIELD) {
      const nombre = nodo.name.value;
      const hijos = nodo.selectionSet
        ? medir(nodo.selectionSet, fragmentos, variables, profundidad + 1, visitados)
        : { profundidad, costo: 0 };
      const multiplicador = LISTAS_PAGINADAS.has(nombre) ? Math.max(1, argumentoEntero(nodo, 'tamano', 5, variables)) : 1;
      costo += (COSTO_CAMPO[nombre] ?? 1) + hijos.costo * multiplicador;
      maxProf = Math.max(maxProf, hijos.profundidad);
    }
  }
  return { profundidad: maxProf, costo };
}

// Profundidad y costo de cada operación de un documento ya parseado.
export function analizar(document, variables = {}) {
  const fragmentos = {};
  for (const def of document.definitions) if (def.kind === Kind.FRAGMENT_DEFINITION) fragmentos[def.name.value] = def;
  return document.definitions
    .filter((def) => def.kind === Kind.OPERATION_DEFINITION)
    .map((def) => medir(def.selectionSet, fragmentos, variables, 1, new Set()));
}

// Plugin de Apollo: se ejecuta tras el parseo y validación, antes de resolver.
export function pluginLimites() {
  return {
    async requestDidStart() {
      return {
        async didResolveOperation({ document, request }) {
          for (const { profundidad, costo } of analizar(document, request.variables)) {
            if (profundidad > PROFUNDIDAD_MAXIMA) {
              throw new GraphQLError(`Consulta demasiado profunda (${profundidad} > ${PROFUNDIDAD_MAXIMA})`, {
                extensions: { code: 'QUERY_TOO_DEEP', http: { status: 400 } },
              });
            }
            if (costo > COSTO_MAXIMO) {
              throw new GraphQLError(`Consulta demasiado costosa (${costo} > ${COSTO_MAXIMO})`, {
                extensions: { code: 'QUERY_TOO_COSTLY', http: { status: 400 } },
              });
            }
          }
        },
      };
    },
  };
}
