import { Component, inject, OnInit, ViewChild } from '@angular/core';
import { forkJoin } from 'rxjs';
import {
  ApiService, BatchPredictRequest, HourlyStat,
  Options, TopDelitosRequest, TopDelitosResponse, Zone, ZonePrediction,
} from './services/api.service';
import { MapComponent } from './components/map/map.component';
import { SidebarComponent, FilterEvent } from './components/sidebar/sidebar.component';
import { ChartsComponent } from './components/charts/charts.component';
import { SummaryCardsComponent } from './components/summary-cards/summary-cards.component';
import { TopDelitosComponent } from './components/top-delitos/top-delitos.component';

function todayParams() {
  const now = new Date();
  const d   = now.getDay();
  const dia = d === 0 ? 6 : d - 1;
  return {
    mes:             now.getMonth() + 1,
    anio:            now.getFullYear(),
    dia_semana:      dia,
    es_fin_de_semana: (dia >= 5 ? 1 : 0) as 0 | 1,
  };
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    MapComponent, SidebarComponent, ChartsComponent,
    SummaryCardsComponent, TopDelitosComponent,
  ],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
})
export class AppComponent implements OnInit {
  @ViewChild(MapComponent) mapComp!: MapComponent;

  private api = inject(ApiService);

  zones:        Zone[]            = [];
  predictions:  ZonePrediction[]  = [];
  options:      Options | null    = null;
  focusedZone:  ZonePrediction | null = null;
  hourly:       HourlyStat[]      = [];
  byGravedad:   Record<string, number> = {};
  topDelitos:   TopDelitosResponse | null = null;
  selectedHora: number = new Date().getHours();

  loading       = true;     // carga inicial / predicción en curso
  topLoading    = false;    // tabla de delitos en curso
  hasQueried    = false;    // ¿el usuario ya ejecutó una consulta?
  filtrosAbiertos = false;  // cajón de filtros (solo móvil)
  errorMsg: string | null = null;

  toggleFiltros(): void { this.filtrosAbiertos = !this.filtrosAbiertos; }
  cerrarFiltros(): void { this.filtrosAbiertos = false; }

  /** No hay zonas resultantes tras una consulta válida (#7). */
  get noData(): boolean {
    return this.hasQueried && !this.loading && this.predictions.length === 0;
  }

  /** La selección incluye parroquias rurales lejanas del cantón Guayaquil. */
  get hasRuralZones(): boolean {
    return this.predictions.some(p => p.es_rural);
  }
  get ruralZoneNames(): string {
    const names = [...new Set(
      this.predictions.filter(p => p.es_rural).map(p => p.parroquia).filter(Boolean),
    )];
    return names.join(', ');
  }

  ngOnInit(): void {
    forkJoin({
      zones: this.api.getZones(),
      opts:  this.api.getOptions(),
      top:   this.api.getTopDelitos({}),   // ranking histórico global de arranque
    }).subscribe({
      next: ({ zones, opts, top }) => {
        this.zones      = zones;
        this.options    = opts;
        this.topDelitos = top;
        this.loading    = false;
      },
      error: () => {
        this.errorMsg = 'No se pudo conectar con el backend. Verifica que esté activo en http://localhost:8000';
        this.loading  = false;
      },
    });
  }

  onFilterChange(ev: FilterEvent): void {
    this.loading    = true;
    this.hasQueried = true;
    this.cerrarFiltros();        // en móvil, cierra el cajón al consultar
    this.runPredict(ev.batch);
  }

  onClear(): void {
    this.predictions = [];
    this.hourly      = [];
    this.byGravedad  = {};
    this.focusedZone = null;
    this.hasQueried  = false;
    this.cerrarFiltros();
    this.mapComp?.resetView();
    // vuelve a mostrar el ranking histórico global
    this.topLoading = true;
    this.api.getTopDelitos({}).subscribe({
      next: top => { this.topDelitos = top; this.topLoading = false; },
      error: () => { this.topLoading = false; },
    });
  }

  onZoneFocused(pred: ZonePrediction | null): void {
    this.focusedZone = pred;
  }

  private runPredict(overrides: Partial<BatchPredictRequest> & { hora: number; codigo_iccs: string }): void {
    const base = todayParams();
    const req: BatchPredictRequest = {
      ...base,
      macro_lugar:              'ESPACIO_PUBLICO',
      codigo_distrito:          null,
      codigo_circuito:          null,
      codigo_subcircuito_filtro: null,
      ...overrides,
    };

    this.selectedHora = req.hora;

    const statsReq = {
      hora:                     req.hora,
      mes:                      req.mes,
      anio:                     req.anio,
      dia_semana:               req.dia_semana,
      es_fin_de_semana:         req.es_fin_de_semana,
      macro_lugar:              req.macro_lugar,
      codigo_iccs:              req.codigo_iccs,
      codigo_distrito:          req.codigo_distrito,
      codigo_circuito:          req.codigo_circuito,
      codigo_subcircuito_filtro: req.codigo_subcircuito_filtro,
    };

    const topReq: TopDelitosRequest = {
      codigo_distrito:           req.codigo_distrito,
      codigo_circuito:           req.codigo_circuito,
      codigo_subcircuito_filtro: req.codigo_subcircuito_filtro,
      hora:                      req.hora,
    };

    this.topLoading = true;
    forkJoin({
      preds: this.api.predictBatch(req),
      stats: this.api.getStats(statsReq),
      top:   this.api.getTopDelitos(topReq),
    }).subscribe({
      next: ({ preds, stats, top }) => {
        this.predictions = preds;
        this.hourly      = stats.hourly;
        this.byGravedad  = stats.by_gravedad;
        this.topDelitos  = top;
        this.loading     = false;
        this.topLoading  = false;

        // Reencuadra SIEMPRE hacia el resultado (1 punto → centra; varios → encuadra
        // todos). Si no hay puntos, fitToBounds conserva la vista y se muestra el
        // mensaje de "sin datos".
        const coords = preds.map(p => [p.lat, p.lng] as [number, number]);
        setTimeout(() => this.mapComp?.fitToBounds(coords), 150);
      },
      error: () => { this.loading = false; this.topLoading = false; },
    });
  }
}
