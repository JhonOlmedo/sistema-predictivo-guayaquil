import {
  AfterViewInit, Component, ElementRef, EventEmitter,
  Input, OnChanges, OnDestroy, Output, SimpleChanges, ViewChild,
} from '@angular/core';
import * as L from 'leaflet';
import { Zone, ZonePrediction } from '../../services/api.service';

@Component({
  selector: 'app-map',
  standalone: true,
  template: `<div #mapEl style="width:100%;height:100%;"></div>`,
})
export class MapComponent implements AfterViewInit, OnChanges, OnDestroy {
  @ViewChild('mapEl') mapEl!: ElementRef<HTMLDivElement>;
  @Input() zones: Zone[] = [];
  @Input() predictions: ZonePrediction[] = [];
  @Output() zoneFocused = new EventEmitter<ZonePrediction | null>();

  private map!: L.Map;
  private heatLayer: L.Layer | null = null;
  private interactionMarkers: L.CircleMarker[] = [];
  private predMap = new Map<string, ZonePrediction>();
  private ready = false;
  private resizeObs?: ResizeObserver;
  // Renderer de canvas compartido por los 240 círculos: su `tolerance` amplía el
  // área de acierto del tap (clave en móvil, donde el dedo no cae exacto en el punto).
  private markerRenderer!: L.Canvas;
  // Puntero grueso = pantalla táctil: usamos objetivos y tolerancia más grandes.
  private readonly coarsePointer =
    typeof window !== 'undefined' && !!window.matchMedia &&
    window.matchMedia('(pointer: coarse)').matches;

  // Centro inicial (vista general al arrancar / al limpiar)
  private static readonly CENTER: [number, number] = [-2.1894, -79.8891];
  // Caja "sana" del cantón Guayaquil: al encuadrar se descartan coordenadas fuera
  // de ella (los datos traen algún punto erróneo, p.ej. GUASMO 4 con lng -76.26).
  private static readonly CANTON_BOUNDS = L.latLngBounds(
    [-3.05, -80.45], [-1.95, -79.55],
  );
  // Límite de paneo AMPLIO: solo evita perderse fuera de la región; nunca bloquea
  // una zona real ni obliga a quedarse en la vista general de Guayaquil.
  private static readonly MAX_BOUNDS = L.latLngBounds(
    [-3.35, -80.85], [-1.65, -79.15],
  );
  // Colores por nivel de gravedad, compartidos por los puntos del mapa y el popup.
  private static readonly GRAVEDAD_COLORS: Record<string, string> = {
    BAJA: '#22c55e', MEDIA: '#eab308', ALTA: '#f97316', CRITICA: '#ef4444',
  };
  // A partir de este zoom los puntos por zona pasan de invisibles a visibles.
  // Por debajo (vista general y de distrito) solo manda el mapa de calor; los
  // puntos aparecen recién al acercar bastante (nivel de calle).
  private static readonly POINT_ZOOM = 15;

  async ngAfterViewInit(): Promise<void> {
    this.map = L.map(this.mapEl.nativeElement, {
      center: MapComponent.CENTER,
      zoom: 12,
      minZoom: 9,
      maxZoom: 18,
      zoomControl: true,
      maxBounds: MapComponent.MAX_BOUNDS,
      maxBoundsViscosity: 0.4,
    });
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© <a href="https://www.openstreetmap.org">OpenStreetMap</a>',
      maxZoom: 18,
    }).addTo(this.map);

    // Mantiene el lienzo de Leaflet sincronizado con su contenedor de tamaño fijo:
    // ante cualquier reflujo del layout recalcula su tamaño en vez de deformarse.
    this.resizeObs = new ResizeObserver(() => this.map?.invalidateSize());
    this.resizeObs.observe(this.mapEl.nativeElement);

    // Un único canvas para los marcadores de zona. `tolerance` amplía el área de
    // acierto del tap por encima del radio visible (clave en móvil).
    this.markerRenderer = L.canvas({ tolerance: this.coarsePointer ? 14 : 8 });
    // En cada cambio de zoom ajustamos el radio del calor (para que no se disuelva)
    // y el estilo de los puntos (invisibles en vista general, visibles al acercar).
    this.map.on('zoomend', () => this.onZoomEnd());

    // leaflet.heat es un plugin UMD legado que registra `L.heatLayer` sobre la
    // variable global `window.L`. En el build de producción (esbuild) Leaflet no
    // queda como global, por lo que el plugin se aplicaba a otra referencia y
    // fallaba con "heatLayer is not a function". Fijamos NUESTRA instancia como
    // global y cargamos el plugin con import() dinámico: así se ejecuta DESPUÉS
    // (el orden de los imports estáticos no lo garantiza el bundler).
    (window as unknown as { L: typeof L }).L = L;
    // leaflet.heat es JS legado sin tipos; del import() dinámico solo nos importa
    // su efecto secundario (registrar L.heatLayer), no su valor de retorno.
    // @ts-ignore
    await import('leaflet.heat');

    this.ready = true;
    if (this.predictions.length) this.render();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (!this.ready) return;
    if (changes['predictions'] || changes['zones']) this.render();
  }

  ngOnDestroy(): void {
    this.resizeObs?.disconnect();
    this.map?.remove();
  }

  /** Zoom animado hacia el resultado de la consulta. El contenedor NO cambia de
   *  tamaño; solo se reencuadra (fly) la vista del mapa hacia las coordenadas.
   *  - 1 punto  → flyTo centrado con zoom cercano.
   *  - N puntos → flyToBounds (encuadre automático que muestra todos).
   *  Descarta coordenadas fuera del cantón (datos erróneos). Si no queda ningún
   *  punto válido, conserva la vista actual. */
  fitToBounds(coords: Array<[number, number]>): void {
    if (!this.ready) return;
    const valid = coords.filter(c => MapComponent.CANTON_BOUNDS.contains(c));
    if (!valid.length) return;
    this.map.invalidateSize();
    // Reencuadre instantáneo y fiable (las animaciones de "vuelo" de Leaflet
    // dependen de requestAnimationFrame y fallan en contextos sin foco/headless).
    if (valid.length === 1) {
      this.map.setView(valid[0], 15, { animate: false });
    } else {
      this.map.fitBounds(L.latLngBounds(valid), {
        padding: [50, 50],
        maxZoom: 15,
        animate: false,
      });
    }
  }

  /** Reencuadra a toda Guayaquil (usado al limpiar filtros). */
  resetView(): void {
    if (!this.ready) return;
    this.map.invalidateSize();
    this.map.setView(MapComponent.CENTER, 12, { animate: false });
  }

  private render(): void {
    this.predMap.clear();
    this.predictions.forEach(p => this.predMap.set(p.codigo_subcircuito, p));

    this.clearLayers();

    const heatPoints: Array<[number, number, number]> = this.predictions.map(p => [
      p.lat, p.lng, p.peligrosidad / 100,
    ]);

    if (heatPoints.length) {
      // El mapa de calor es la lectura PRINCIPAL a todos los zooms. Opacidad alta y
      // degradado en la paleta de gravedad para que se note; el radio se ajusta al
      // zoom (heatOptionsForZoom) para que la mancha no se disuelva al acercar.
      this.heatLayer = (L as any).heatLayer(heatPoints, {
        ...this.heatOptionsForZoom(this.map.getZoom()),
        maxZoom: 17,
        max: 0.7,
        minOpacity: 0.4,
        gradient: { 0.2: '#22c55e', 0.5: '#eab308', 0.75: '#f97316', 1.0: '#ef4444' },
      });
      this.heatLayer!.addTo(this.map);
      this.disableHeatPointerEvents();
    }

    // Un marcador por subcircuito. En vista general es INVISIBLE (solo manda el
    // calor) pero mantiene un área de toque generosa; al acercar el zoom se vuelve
    // un punto DISCRETO. El estilo lo decide markerStyleForZoom según el zoom.
    const zoom = this.map.getZoom();
    this.predictions.forEach(pred => {
      const zone = this.zones.find(z => z.codigo_subcircuito === pred.codigo_subcircuito);
      const marker = L.circleMarker([pred.lat, pred.lng], {
        renderer: this.markerRenderer,
        interactive: true,
        ...this.markerStyleForZoom(zoom, pred.gravedad),
      });
      marker.on('mouseover', () => this.zoneFocused.emit(pred));
      marker.on('mouseout', () => this.zoneFocused.emit(null));
      marker.on('click', () => this.zoneFocused.emit(pred));   // tap en móvil: fija el detalle
      marker.bindPopup(this.buildPopup(pred, zone));
      marker.addTo(this.map);
      (marker as unknown as { _gravedad: string })._gravedad = pred.gravedad;
      this.interactionMarkers.push(marker);
    });
  }

  private clearLayers(): void {
    if (this.heatLayer) { this.map.removeLayer(this.heatLayer); this.heatLayer = null; }
    this.interactionMarkers.forEach(m => m.remove());
    this.interactionMarkers = [];
  }

  /** Radio/desenfoque (px) del mapa de calor según el zoom. El radio CRECE al
   *  acercar para que la mancha siga siendo continua y visible en vez de
   *  disolverse en puntitos sueltos (que era el motivo de que "no se notara"). */
  private heatOptionsForZoom(zoom: number): { radius: number; blur: number } {
    const radius = Math.min(18 + Math.max(0, zoom - 11) * 7, 60);
    return { radius, blur: Math.round(radius * 0.75) };
  }

  /** Estilo del punto de una zona según el zoom:
   *  - Vista general (zoom < POINT_ZOOM): INVISIBLE, pero con radio + la tolerancia
   *    del canvas mantiene un objetivo de toque amplio (solo se ve el calor).
   *  - Al acercar: punto DISCRETO (pequeño) con borde blanco para resaltar sobre
   *    el calor sin taparlo. */
  private markerStyleForZoom(zoom: number, gravedad: string): L.CircleMarkerOptions {
    const fillColor = MapComponent.GRAVEDAD_COLORS[gravedad] ?? '#64748b';
    if (zoom < MapComponent.POINT_ZOOM) {
      return { radius: this.coarsePointer ? 10 : 8, opacity: 0, fillOpacity: 0, fillColor, color: fillColor };
    }
    const radius = Math.min((this.coarsePointer ? 5 : 4) + (zoom - MapComponent.POINT_ZOOM), this.coarsePointer ? 9 : 7);
    return { radius, fillColor, fillOpacity: 0.9, color: '#ffffff', weight: 1.5, opacity: 0.9 };
  }

  /** En cada cambio de zoom: ajusta el radio del calor y re-estiliza los puntos
   *  (invisibles ↔ visibles y discretos). */
  private onZoomEnd(): void {
    if (!this.ready) return;
    const zoom = this.map.getZoom();
    if (this.heatLayer) {
      (this.heatLayer as unknown as { setOptions?: (o: object) => void })
        .setOptions?.(this.heatOptionsForZoom(zoom));
      this.disableHeatPointerEvents();
    }
    this.interactionMarkers.forEach(m => {
      const st = this.markerStyleForZoom(zoom, (m as unknown as { _gravedad: string })._gravedad);
      m.setStyle(st);
      if (st.radius != null) m.setRadius(st.radius);
    });
  }

  /** El canvas del calor es decorativo y NUNCA debe capturar clics: leaflet.heat lo
   *  reinserta ENCIMA del canvas de puntos en cada render, así que sin esto se
   *  tragaría los taps dirigidos a las zonas de abajo. */
  private disableHeatPointerEvents(): void {
    const c = (this.heatLayer as unknown as { _canvas?: HTMLCanvasElement })._canvas;
    if (c) c.style.pointerEvents = 'none';
  }

  private buildPopup(p: ZonePrediction, z: Zone | undefined): string {
    const c = MapComponent.GRAVEDAD_COLORS[p.gravedad] ?? '#64748b';
    const parroquia = p.parroquia
      ? `<small style="color:#cbd5e1">📍 ${p.parroquia}${p.es_rural
          ? ' <span style="background:#3f2d12;color:#fbbf24;border-radius:4px;padding:0 5px;font-size:10px">Zona rural</span>'
          : ''}</small><br>`
      : '';
    return `<div style="min-width:170px;font-size:12px">
      <b style="font-size:13px">${z?.nombre ?? p.codigo_subcircuito}</b><br>
      <small style="color:#94a3b8">${p.codigo_subcircuito}</small><br>
      ${parroquia}<br>
      Gravedad: <b style="color:${c}">${p.gravedad}</b><br>
      Peligrosidad: <b>${p.peligrosidad.toFixed(1)}%</b>
      <div style="background:#334155;border-radius:4px;height:8px;margin-top:6px;overflow:hidden">
        <div style="background:${c};width:${p.peligrosidad}%;height:100%;border-radius:4px"></div>
      </div>
    </div>`;
  }
}
