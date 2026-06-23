import { Component, Input } from '@angular/core';
import { ZonePrediction } from '../../services/api.service';

@Component({
  selector: 'app-summary-cards',
  standalone: true,
  templateUrl: './summary-cards.component.html',
  styleUrl: './summary-cards.component.css',
})
export class SummaryCardsComponent {
  @Input() predictions: ZonePrediction[] = [];
  @Input() hasQueried = false;

  get hasData(): boolean { return this.predictions.length > 0; }

  get totalZonas(): number { return this.predictions.length; }
  get zonasAltas(): number { return this.predictions.filter(p => p.gravedad === 'ALTA').length; }
  get zonasCriticas(): number { return this.predictions.filter(p => p.gravedad === 'CRITICA').length; }
  get peligrosidadMedia(): number {
    if (!this.predictions.length) return 0;
    return this.predictions.reduce((s, p) => s + p.peligrosidad, 0) / this.predictions.length;
  }

  /** Muestra "—" en lugar de 0 cuando aún no hay una consulta válida (#7). */
  fmt(value: number, suffix = ''): string {
    return this.hasData ? `${value}${suffix}` : '—';
  }
}
