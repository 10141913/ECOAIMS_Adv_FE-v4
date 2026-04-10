## Prometheus & Grafana (FE Observability)

Dokumen ini menyediakan:
- contoh scrape config untuk endpoint `/metrics` pada Frontend
- contoh alert rules: `/metrics` scrape failure, cache hit-rate drop, p95 latency naik
- query Grafana yang siap dipakai untuk dashboard

### 1) Scrape config (Prometheus)

Sesuaikan `targets` dengan URL/port Frontend.

```yaml
scrape_configs:
  - job_name: ecoaims-frontend
    metrics_path: /metrics
    scrape_interval: 15s
    scrape_timeout: 10s
    static_configs:
      - targets:
          - "frontend.example.com:8050"
```

### 2) Alert rules (Prometheus)

File rule siap pakai tersedia di:
- `docs/prometheus/ecoaims_alerts.yml`

### 3) Grafana panel queries

Asumsi `job="ecoaims-frontend"`.

**A) Scrape health**
- Up:
  - `up{job="ecoaims-frontend"}`

**B) Optimization traffic**
- Requests rate:
  - `rate(ecoaims_fe_optimization_requests_total[5m])`

**C) Cache effectiveness**
- Cache hit rate:
  - `rate(ecoaims_fe_optimization_cache_hits_total[5m]) / (rate(ecoaims_fe_optimization_cache_hits_total[5m]) + rate(ecoaims_fe_optimization_cache_misses_total[5m]) + 1e-9)`

**D) Latency p95/p99 (histogram)**
- p95:
  - `histogram_quantile(0.95, sum(rate(ecoaims_fe_optimization_latency_ms_bucket[5m])) by (le))`
- p99:
  - `histogram_quantile(0.99, sum(rate(ecoaims_fe_optimization_latency_ms_bucket[5m])) by (le))`

### 4) Catatan operasional

- Cache hit-rate bisa turun saat traffic kecil atau saat input sangat bervariasi. Gunakan guard `requests_rate` agar alert hanya aktif saat ada load.
- Histogram p95 butuh traffic; untuk traffic sangat rendah, p95 bisa terlihat “spiky”.
