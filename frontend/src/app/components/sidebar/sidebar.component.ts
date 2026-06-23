import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { BatchPredictRequest, Options, ZonePrediction } from '../../services/api.service';

export interface FilterEvent { batch: BatchPredictRequest; }

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.css',
})
export class SidebarComponent {
  @Input() options:     Options | null       = null;
  @Input() focusedZone: ZonePrediction | null = null;
  @Input() loading      = false;

  @Output() filterChange = new EventEmitter<FilterEvent>();
  @Output() clearMap     = new EventEmitter<void>();

  // ── filter state ──────────────────────────────────────────────────────────
  selectedDelito:      string = '';
  selectedDistrito:    string | null = null;
  selectedCircuito:    string | null = null;
  selectedSubcircuito: string | null = null;
  selectedHora:        number | null = null;
  validationMsg        = '';

  // ── cascading filter helpers ───────────────────────────────────────────────
  get circuitosFiltered() {
    if (!this.options) return [];
    return this.selectedDistrito
      ? this.options.circuitos.filter(c => c.distrito === this.selectedDistrito)
      : this.options.circuitos;
  }

  get subcircuitosFiltered() {
    if (!this.options) return [];
    return this.selectedCircuito
      ? this.options.subcircuitos.filter(s => s.circuito === this.selectedCircuito)
      : this.options.subcircuitos;
  }

  onDistritoChange():   void { this.selectedCircuito = null; this.selectedSubcircuito = null; }
  onCircuitoChange():   void { this.selectedSubcircuito = null; }

  get gravedadColor(): string {
    const m: Record<string, string> = {
      BAJA: '#22c55e', MEDIA: '#eab308', ALTA: '#f97316', CRITICA: '#ef4444',
    };
    return m[this.focusedZone?.gravedad ?? ''] ?? '#64748b';
  }

  // ── apply / clear ─────────────────────────────────────────────────────────
  apply(): void {
    this.validationMsg = '';
    const missing: string[] = [];
    if (!this.selectedDelito)       missing.push('Tipo de delito');
    if (this.selectedHora === null) missing.push('Rango horario');
    if (missing.length) {
      this.validationMsg = `Selecciona: ${missing.join(' y ')}.`;
      return;
    }
    const now = new Date();
    const d   = now.getDay();
    const dia = d === 0 ? 6 : d - 1;
    this.filterChange.emit({
      batch: {
        hora:              this.selectedHora!,
        mes:               now.getMonth() + 1,
        anio:              now.getFullYear(),
        dia_semana:        dia,
        es_fin_de_semana:  dia >= 5 ? 1 : 0,
        macro_lugar:       'ESPACIO_PUBLICO',
        codigo_iccs:       this.selectedDelito,
        codigo_distrito:   this.selectedDistrito,
        codigo_circuito:   this.selectedCircuito,
        codigo_subcircuito_filtro: this.selectedSubcircuito,
      },
    });
  }

  clear(): void {
    this.selectedDelito      = '';
    this.selectedDistrito    = null;
    this.selectedCircuito    = null;
    this.selectedSubcircuito = null;
    this.selectedHora        = null;
    this.validationMsg       = '';
    this.clearMap.emit();
  }
}
