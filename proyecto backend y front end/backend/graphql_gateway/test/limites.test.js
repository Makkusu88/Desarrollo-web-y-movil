// Pruebas unitarias de las reglas de profundidad y costo (node --test).
// El schema actual no permite superar la profundidad máxima, por lo que la regla
// se valida con documentos sintéticos: protege ante futuras ampliaciones del schema.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parse } from 'graphql';

import { analizar, COSTO_MAXIMO, PROFUNDIDAD_MAXIMA } from '../src/limites.js';

test('mide la profundidad incluyendo fragmentos', () => {
  const doc = parse('{ a { b { ...F } } } fragment F on X { c { d { e { f { g } } } } }');
  const [{ profundidad }] = analizar(doc);
  assert.equal(profundidad, 7);
  assert.ok(profundidad > PROFUNDIDAD_MAXIMA);
});

test('la consulta real más profunda del frontend está dentro del límite', () => {
  const doc = parse('{ misPedidos(tamano: 5) { items { items { producto { imagen } } } } }');
  const [{ profundidad }] = analizar(doc);
  assert.ok(profundidad <= PROFUNDIDAD_MAXIMA);
});

test('las listas paginadas multiplican el costo por su tamaño', () => {
  const chica = analizar(parse('{ misPedidos(tamano: 1) { items { id total } } }'))[0].costo;
  const grande = analizar(parse('{ misPedidos(tamano: 10) { items { id total } } }'))[0].costo;
  const base = 10; // costo propio de misPedidos (no se multiplica)
  assert.equal(grande - base, (chica - base) * 10);
});

test('el tamaño por variable también se considera', () => {
  const doc = parse('query($t: Int!) { pedidosLocal(tamano: $t) { items { id items { nombre producto { id nombre } } } } }');
  const [{ costo }] = analizar(doc, { t: 20 });
  assert.ok(costo <= COSTO_MAXIMO, `costo ${costo}`);
});

test('muchos alias de una operación costosa superan el máximo', () => {
  const campo = 'misPedidos(tamano: 10) { items { id items { nombre producto { id nombre imagen } } pago { estado } } }';
  const doc = parse(`{ ${Array.from({ length: 6 }, (_, i) => `a${i}: ${campo}`).join(' ')} }`);
  assert.ok(analizar(doc)[0].costo > COSTO_MAXIMO);
});
