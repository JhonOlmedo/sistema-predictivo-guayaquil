import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface Zone {
  codigo_subcircuito: string;
  nombre: string;
  codigo_circuito: string;
  codigo_distrito: string;
  lat: number;
  lng: number;
  freq_subcircuito: number;
  parroquia: string;
  es_rural: boolean;
}

export interface ZonePrediction {
  codigo_subcircuito: string;
  nombre: string;
  lat: number;
  lng: number;
  peligrosidad: number;
  gravedad: string;
  parroquia: string;
  es_rural: boolean;
}

export interface BatchPredictRequest {
  hora: number;
  mes: number;
  anio: number;
  dia_semana: number;
  es_fin_de_semana: 0 | 1;
  macro_lugar: string;
  codigo_iccs: string;
  codigo_distrito?: string | null;
  codigo_circuito?: string | null;
  codigo_subcircuito_filtro?: string | null;
}

export interface StatsRequest {
  hora: number;
  mes: number;
  anio: number;
  dia_semana: number;
  es_fin_de_semana: 0 | 1;
  macro_lugar: string;
  codigo_iccs: string;
  codigo_distrito?: string | null;
  codigo_circuito?: string | null;
  codigo_subcircuito_filtro?: string | null;
}

export interface HourlyStat { hora: number; peligrosidad: number; }

export interface StatsResponse {
  hourly: HourlyStat[];
  by_gravedad: Record<string, number>;
  total_zonas: number;
  peligrosidad_media: number;
}

export interface TopDelitosRequest {
  codigo_distrito?: string | null;
  codigo_circuito?: string | null;
  codigo_subcircuito_filtro?: string | null;
  hora?: number | null;
}

export interface TopDelito {
  delito: string;
  frecuencia: number;
  distrito_predominante: string;
  distrito_codigo: string;
  porcentaje: number;
}

export interface TopDelitosResponse {
  items: TopDelito[];
  total: number;
}

export interface Option  { label: string; value: string | number; }
export interface CircuitOption extends Option { distrito: string; }
export interface SubcircuitOption extends Option { circuito: string; }

export interface Options {
  delitos:         Option[];
  distritos:       Option[];
  circuitos:       (Option & { distrito: string })[];
  subcircuitos:    (Option & { circuito: string })[];
  rangos_horarios: Option[];
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);
  private base = environment.apiUrl;

  getZones():                   Observable<Zone[]>           { return this.http.get<Zone[]>(`${this.base}/zones`); }
  getOptions():                 Observable<Options>          { return this.http.get<Options>(`${this.base}/options`); }
  predictBatch(req: BatchPredictRequest): Observable<ZonePrediction[]>  { return this.http.post<ZonePrediction[]>(`${this.base}/predict/batch`, req); }
  getStats(req: StatsRequest):  Observable<StatsResponse>   { return this.http.post<StatsResponse>(`${this.base}/predict/stats`, req); }
  getTopDelitos(req: TopDelitosRequest): Observable<TopDelitosResponse> { return this.http.post<TopDelitosResponse>(`${this.base}/top-delitos`, req); }
}
