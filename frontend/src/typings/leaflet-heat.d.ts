import * as L from 'leaflet';

declare module 'leaflet' {
  function heatLayer(
    latlngs: Array<[number, number] | [number, number, number]>,
    options?: {
      minOpacity?: number;
      maxZoom?: number;
      max?: number;
      radius?: number;
      blur?: number;
      gradient?: Record<number, string>;
    }
  ): Layer;
}

// Declara el módulo del plugin para poder cargarlo con import() dinámico.
// Solo tiene efecto secundario (registra L.heatLayer); no exporta nada propio.
declare module 'leaflet.heat';
