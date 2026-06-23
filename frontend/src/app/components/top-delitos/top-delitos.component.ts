import { Component, Input } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { TopDelito, TopDelitosResponse } from '../../services/api.service';

@Component({
  selector: 'app-top-delitos',
  standalone: true,
  imports: [DecimalPipe],
  templateUrl: './top-delitos.component.html',
  styleUrl: './top-delitos.component.css',
})
export class TopDelitosComponent {
  @Input() data: TopDelitosResponse | null = null;
  @Input() loading = false;

  get items(): TopDelito[] { return this.data?.items ?? []; }
  get total(): number { return this.data?.total ?? 0; }
  get hasData(): boolean { return this.items.length > 0; }
  get maxFreq(): number { return this.items.length ? this.items[0].frecuencia : 1; }

  barWidth(freq: number): number {
    return this.maxFreq ? Math.round((freq / this.maxFreq) * 100) : 0;
  }
}
