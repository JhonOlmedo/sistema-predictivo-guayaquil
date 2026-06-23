import {
  AfterViewInit, Component, ElementRef, Input,
  OnChanges, OnDestroy, SimpleChanges, ViewChild,
} from '@angular/core';
import { Chart, registerables } from 'chart.js';
import { HourlyStat } from '../../services/api.service';

Chart.register(...registerables);

const HORA_LABEL = (h: number) => {
  const suffix = h < 12 ? 'a.m.' : 'p.m.';
  const h12 = h % 12 || 12;
  const next = (h + 1) % 24;
  const ns = next < 12 ? 'a.m.' : 'p.m.';
  const n12 = next % 12 || 12;
  return `${h12} ${suffix} – ${n12} ${ns}`;
};

interface RiskLevel {
  key: string; name: string; color: string; count: number; pct: number;
}

@Component({
  selector: 'app-charts',
  standalone: true,
  templateUrl: './charts.component.html',
  styleUrl: './charts.component.css',
})
export class ChartsComponent implements AfterViewInit, OnChanges, OnDestroy {
  @ViewChild('barCanvas') barCanvas!: ElementRef<HTMLCanvasElement>;

  @Input() hourly: HourlyStat[] = [];
  @Input() byGravedad: Record<string, number> = {};
  @Input() selectedHora = -1;
  @Input() hasQueried = false;

  private barChart!: Chart;
  private ready = false;

  // ── estado / vacíos ─────────────────────────────────────────────────────────
  get hasHourly(): boolean { return this.hourly.some(h => h.peligrosidad > 0); }
  get hasGravedad(): boolean { return Object.values(this.byGravedad).some(v => v > 0); }
  get emptyMsg(): string {
    return this.hasQueried
      ? 'No hay datos disponibles para los filtros seleccionados.'
      : 'Realiza una consulta para visualizar el análisis.';
  }

  // ── cuadro de hora pico (#6) ────────────────────────────────────────────────
  private get peak(): HourlyStat | null {
    if (!this.hourly.length) return null;
    return this.hourly.reduce((a, b) => (b.peligrosidad > a.peligrosidad ? b : a));
  }
  get peakHourLabel(): string { return this.peak ? HORA_LABEL(this.peak.hora) : '—'; }
  get peakPct(): string { return this.peak ? this.peak.peligrosidad.toFixed(1) : '0'; }

  // ── tarjetas por nivel de riesgo (#5) ───────────────────────────────────────
  get riskLevels(): RiskLevel[] {
    const order = [
      { key: 'BAJA',    name: 'Bajo',    color: '#22c55e' },
      { key: 'MEDIA',   name: 'Medio',   color: '#eab308' },
      { key: 'ALTA',    name: 'Alto',    color: '#f97316' },
      { key: 'CRITICA', name: 'Crítico', color: '#ef4444' },
    ];
    const total = order.reduce((s, l) => s + (this.byGravedad[l.key] ?? 0), 0);
    return order.map(l => {
      const count = this.byGravedad[l.key] ?? 0;
      return { ...l, count, pct: total ? Math.round((count / total) * 1000) / 10 : 0 };
    });
  }
  get riskTotal(): number {
    return this.riskLevels.reduce((s, l) => s + l.count, 0);
  }

  // ── ciclo de vida ───────────────────────────────────────────────────────────
  ngAfterViewInit(): void {
    this.initBar();
    this.ready = true;
    if (this.hasHourly) this.updateBar();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (!this.ready) return;
    if (changes['hourly'] || changes['selectedHora']) this.updateBar();
  }

  ngOnDestroy(): void {
    this.barChart?.destroy();
  }

  private initBar(): void {
    this.barChart = new Chart(this.barCanvas.nativeElement, {
      type: 'bar',
      data: {
        labels: Array.from({ length: 24 }, (_, i) => `${i.toString().padStart(2, '0')}h`),
        datasets: [{
          label: 'Peligrosidad',
          data: Array(24).fill(0),
          backgroundColor: Array(24).fill('#3b82f6'),
          borderRadius: 5,
          borderSkipped: false,
          maxBarThickness: 22,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 4, right: 6, bottom: 0, left: 0 } },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#0f172a',
            borderColor: '#334155',
            borderWidth: 1,
            titleColor: '#e2e8f0',
            bodyColor: '#cbd5e1',
            padding: 10,
            displayColors: false,
            callbacks: {
              title: items => HORA_LABEL(items[0].dataIndex),
              label: ctx => `Peligrosidad: ${(ctx.raw as number).toFixed(1)} %`,
            },
          },
        },
        scales: {
          x: {
            ticks: {
              color: '#94a3b8',
              font: { size: 10 },
              autoSkip: true,
              maxTicksLimit: 12,
              maxRotation: 0,
              minRotation: 0,
            },
            grid: { display: false },
            border: { color: '#1e293b' },
          },
          y: {
            ticks: {
              color: '#94a3b8',
              font: { size: 10 },
              callback: v => `${v}%`,
              stepSize: 25,
            },
            grid: { color: '#1e293b' },
            border: { display: false },
            min: 0,
            max: 100,
            title: {
              display: true,
              text: 'Nivel de peligrosidad',
              color: '#64748b',
              font: { size: 10, weight: 'normal' },
            },
          },
        },
      },
    });
  }

  private updateBar(): void {
    const sorted = [...this.hourly].sort((a, b) => a.hora - b.hora);
    const values = sorted.map(h => h.peligrosidad);
    const max = Math.max(...values, 1);
    const colors = sorted.map((h, i) => {
      if (h.hora === this.selectedHora) return '#8b5cf6';          // hora consultada
      const v = values[i];
      if (v >= max * 0.85) return '#ef4444';                       // pico
      if (v >= max * 0.60) return '#f97316';                       // elevado
      return '#3b82f6';                                            // base
    });
    this.barChart.data.datasets[0].data = values;
    (this.barChart.data.datasets[0] as any).backgroundColor = colors;
    this.barChart.resize();   // recalcula tamaño tras reaparecer (estaba display:none)
    this.barChart.update();
  }
}
