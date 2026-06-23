import * as L from 'leaflet';

// El plugin `leaflet.heat` es código UMD legado: registra `L.heatLayer` sobre la
// variable GLOBAL `window.L` (no importa Leaflet). En el build de producción de
// Angular (esbuild) Leaflet queda encapsulado como módulo y NO se expone como
// global, por lo que el plugin no se aplica y el mapa de calor no se dibuja
// (en `ng serve` sí funciona porque ahí Leaflet queda accesible globalmente).
//
// Exponemos la MISMA instancia de Leaflet como global. Este módulo debe
// importarse ANTES de `leaflet.heat` para que el plugin lo encuentre.
(window as unknown as { L: typeof L }).L = L;
