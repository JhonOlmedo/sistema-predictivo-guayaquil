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
      this.heatLayer = (L as any).heatLayer(heatPoints, {
        radius: 30,
        blur: 25,
        maxZoom: 17,
        max: 1.0,
        minOpacity: 0.35,
        gradient: { 0.2: '#3b82f6', 0.45: '#eab308', 0.7: '#f97316', 1.0: '#ef4444' },
      });
      this.heatLayer!.addTo(this.map);
    }

    this.predictions.forEach(pred => {
      const zone = this.zones.find(z => z.codigo_subcircuito === pred.codigo_subcircuito);
      const marker = L.circleMarker([pred.lat, pred.lng], {
        radius: 11,
        fillOpacity: 0,
        opacity: 0,
        interactive: true,
      });
      marker.on('mouseover', () => this.zoneFocused.emit(pred));
      marker.on('mouseout', () => this.zoneFocused.emit(null));
      marker.on('click', () => this.zoneFocused.emit(pred));   // tap en móvil: fija el detalle
      marker.bindPopup(this.buildPopup(pred, zone));
      marker.addTo(this.map);
      this.interactionMarkers.push(marker);
    });
  }

  private clearLayers(): void {
    if (this.heatLayer) { this.map.removeLayer(this.heatLayer); this.heatLayer = null; }
    this.interactionMarkers.forEach(m => m.remove());
    this.interactionMarkers = [];
  }

  private buildPopup(p: ZonePrediction, z: Zone | undefined): string {
    const colors: Record<string, string> = {
      BAJA: '#22c55e', MEDIA: '#eab308', ALTA: '#f97316', CRITICA: '#ef4444',
    };
    const c = colors[p.gravedad] ?? '#64748b';
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
