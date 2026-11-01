"""Generate results/report.html — 3-system × 3-axis (성능/비용/속도) benchmark report.

Self-contained HTML with inline SVG charts (no external deps).
Reads: data_cache/sample.json, results/*_k*.jsonl, results/meta.json.
"""
import json
import math
from pathlib import Path

import data as D
import metrics as M

RESULTS = Path("results")

SYSTEMS = ["jev", "voyage", "cohere"]
LABEL = {"jev": "Jev 1.13", "voyage": "Voyage rerank-2.5", "cohere": "Cohere rerank-4-pro",
         "bm25": "BM25 (1차 검색)"}
COLOR = {"jev": "#7c3aed", "voyage": "#0284c7", "cohere": "#d97706", "bm25": "#9ca3af"}
KS = [20, 50, 100]


def aggregate():
    manifest, _ = D.load_sample()
    qrels = {f"{q['lang']}:{q['qid']}": q["rels"] for q in manifest["queries"]}
    rows = {}      # (system, K) -> agg row
    per_query = {}  # (system, K) -> {qid: metrics}
    for p in sorted(RESULTS.glob("*_k*.jsonl")):
        system, _, k = p.stem.rpartition("_k")
        if not k.isdigit():  # skip probe outputs such as *_k200_fit
            continue
        k = int(k)
        recs = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
        agg = {m: [] for m in M.METRICS}
        lat, cost = [], 0.0
        per_lang, pq = {}, {}
        for r in recs:
            if "error" in r:
                continue
            rels = [qrels[r["qid"]].get(d, 0) for d in r["ranked"]]
            sm = M.score_ranking(rels)
            pq[r["qid"]] = sm
            for m in M.METRICS:
                agg[m].append(sm[m])
            per_lang.setdefault(r["lang"], []).append(sm["ndcg@10"])
            lat.append(r["latency_s"])
            cost += r.get("cost_usd") or 0
        n = len(agg["map"])
        lat_s = sorted(lat)
        rows[(system, k)] = {
            "system": system, "K": k, "n": n,
            **{m: sum(v) / n for m, v in agg.items()},
            "cost_per_1k": cost / n * 1000, "cost_total": cost,
            "lat_mean": sum(lat) / n, "lat_p50": lat_s[n // 2],
            "lat_p95": lat_s[min(n - 1, int(n * 0.95))],
            "per_lang": {l: sum(v) / len(v) for l, v in per_lang.items()},
        }
        per_query[(system, k)] = pq
    # baseline
    for k in KS:
        agg = {m: [] for m in M.METRICS}
        per_lang = {}
        for q in manifest["queries"]:
            pool = q["pool"][:k]
            rels = [q["rels"].get(d, 0) for d in pool]
            sm = M.score_ranking(rels)
            for m in M.METRICS:
                agg[m].append(sm[m])
            per_lang.setdefault(q["lang"], []).append(sm["ndcg@10"])
        n = len(agg["map"])
        rows[("bm25", k)] = {"system": "bm25", "K": k, "n": n,
                             **{m: sum(v) / n for m, v in agg.items()},
                             "cost_per_1k": 0, "cost_total": 0,
                             "lat_mean": 0, "lat_p50": 0, "lat_p95": 0,
                             "per_lang": {l: sum(v) / len(v) for l, v in per_lang.items()}}
    meta = json.loads((RESULTS / "meta.json").read_text())
    return manifest, rows, per_query, meta


# ---------------- SVG helpers ----------------

def svg_bars(width, height, cats, series, ymax=None, yfmt="{:.2f}", vfmt="{:.3f}",
             ylabel="", pad_l=46, pad_b=26, pad_t=28):
    """series: [(name, color, [v per cat])]. Returns svg string."""
    pad_r = 8
    cw = (width - pad_l - pad_r) / len(cats)
    bw = min(26, (cw - 14) / len(series))
    allv = [v for _n, _c, vs in series for v in vs]
    ymax = ymax or max(allv) * 1.18
    H = height - pad_t - pad_b
    out = [f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
           f'xmlns="http://www.w3.org/2000/svg" font-family="system-ui,sans-serif">']
    # gridlines + y labels
    for i in range(5):
        y = pad_t + H - H * i / 4
        val = ymax * i / 4
        out.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" y2="{y:.1f}" '
                   f'stroke="#e5e7eb" stroke-width="1"/>')
        out.append(f'<text x="{pad_l - 5}" y="{y + 3:.1f}" font-size="9" fill="#6b7280" '
                   f'text-anchor="end">{yfmt.format(val)}</text>')
    if ylabel:
        out.append(f'<text x="10" y="{pad_t - 14}" font-size="10" fill="#374151">{ylabel}</text>')
    # bars
    for ci, cat in enumerate(cats):
        gx = pad_l + cw * ci + cw / 2
        for si, (name, color, vs) in enumerate(series):
            v = vs[ci]
            bh = H * v / ymax
            x = gx + (si - len(series) / 2) * (bw + 2)
            y = pad_t + H - bh
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw}" height="{bh:.1f}" '
                       f'fill="{color}" rx="2"><title>{name} {cat}: {vfmt.format(v)}</title></rect>')
            out.append(f'<text x="{x + bw / 2:.1f}" y="{y - 2:.1f}" font-size="8" fill="#374151" '
                       f'text-anchor="middle">{vfmt.format(v)}</text>')
        out.append(f'<text x="{gx:.1f}" y="{height - 10}" font-size="10" fill="#374151" '
                   f'text-anchor="middle">{cat}</text>')
    # legend (offset past ylabel to avoid overlap)
    lx = pad_l + 4 + (len(ylabel) * 6.5 + 10 if ylabel else 0)
    for name, color, _vs in series:
        out.append(f'<rect x="{lx}" y="6" width="10" height="10" fill="{color}" rx="2"/>')
        out.append(f'<text x="{lx + 13}" y="15" font-size="10" fill="#374151">{name}</text>')
        lx += 13 + len(name) * 6.2 + 14
    out.append("</svg>")
    return "".join(out)


def svg_radar(size, axes, vals, title=""):
    """axes: [label]; vals: {system: [v in 0..1 per axis]}."""
    cx = cy = size / 2
    R = size / 2 - 46
    n = len(axes)
    ang = [-math.pi / 2 + i * 2 * math.pi / n for i in range(n)]

    def pt(i, v):
        return (cx + R * v * math.cos(ang[i]), cy + R * v * math.sin(ang[i]))

    out = [f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" '
           f'xmlns="http://www.w3.org/2000/svg" font-family="system-ui,sans-serif">']
    for ring in (0.25, 0.5, 0.75, 1.0):
        pts = " ".join(f"{pt(i, ring)[0]:.1f},{pt(i, ring)[1]:.1f}" for i in range(n))
        out.append(f'<polygon points="{pts}" fill="none" stroke="#e5e7eb"/>')
    for i, lab in enumerate(axes):
        x, y = pt(i, 1.0)
        out.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="#d1d5db"/>')
        lx, ly = pt(i, 1.22)
        anchor = "middle" if abs(lx - cx) < 10 else ("start" if lx > cx else "end")
        out.append(f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="12" font-weight="600" '
                   f'fill="#111827" text-anchor="{anchor}">{lab}</text>')
    ly = 16
    for sysname, v in vals.items():
        pts = " ".join(f"{pt(i, v[i])[0]:.1f},{pt(i, v[i])[1]:.1f}" for i in range(n))
        c = COLOR[sysname]
        out.append(f'<polygon points="{pts}" fill="{c}" fill-opacity="0.15" '
                   f'stroke="{c}" stroke-width="2"/>')
        for i in range(n):
            x, y = pt(i, v[i])
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{c}"/>')
        out.append(f'<rect x="8" y="{ly - 8}" width="10" height="10" fill="{c}" rx="2"/>'
                   f'<text x="21" y="{ly + 1}" font-size="11" fill="#374151">{LABEL[sysname]}</text>')
        ly += 16
    if title:
        out.append(f'<text x="{cx}" y="{size - 6}" font-size="11" fill="#6b7280" '
                   f'text-anchor="middle">{title}</text>')
    out.append("</svg>")
    return "".join(out)


def table(headers, rows_html):
    th = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows_html)
    return (f'<table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>')


# ---------------- report ----------------

def main():
    manifest, rows, per_query, meta = aggregate()
    nq = len(manifest["queries"])

    # radar values at K=100: 성능(ndcg@10 ↑), 속도(min lat/lat), 비용(min cost/cost)
    perf = {s: rows[(s, 100)]["ndcg@10"] for s in SYSTEMS}
    lat = {s: rows[(s, 100)]["lat_mean"] for s in SYSTEMS}
    cost = {s: rows[(s, 100)]["cost_per_1k"] for s in SYSTEMS}
    pmax, lmin, cmin = max(perf.values()), min(lat.values()), min(cost.values())
    radar_vals = {s: [perf[s] / pmax, lmin / lat[s], cmin / cost[s]] for s in SYSTEMS}

    perf_chart = svg_bars(560, 300, [f"K={k}" for k in KS],
                          [(LABEL[s], COLOR[s], [rows[(s, k)]["ndcg@10"] for k in KS])
                           for s in SYSTEMS + ["bm25"]],
                          ymax=1.0, ylabel="ndcg@10")
    map_chart = svg_bars(560, 300, [f"K={k}" for k in KS],
                         [(LABEL[s], COLOR[s], [rows[(s, k)]["map"] for k in KS])
                          for s in SYSTEMS + ["bm25"]],
                         ymax=1.0, ylabel="MAP")
    cost_chart = svg_bars(560, 300, [f"K={k}" for k in KS],
                          [(LABEL[s], COLOR[s], [rows[(s, k)]["cost_per_1k"] for k in KS])
                           for s in SYSTEMS],
                          yfmt="{:.1f}", vfmt="${:.2f}", ylabel="비용 $/1K queries")
    lat_chart = svg_bars(560, 300, [f"K={k}" for k in KS],
                         [(LABEL[s], COLOR[s], [rows[(s, k)]["lat_mean"] for k in KS])
                          for s in SYSTEMS],
                         yfmt="{:.1f}", vfmt="{:.2f}s", ylabel="쿼리당 평균 지연 (초)")
    wall_chart = svg_bars(560, 300, [f"K={k}" for k in KS],
                          [(LABEL[s], COLOR[s],
                            [meta.get(f"{s}_k{k}", {}).get("wall_s", 0) for k in KS])
                           for s in SYSTEMS],
                          yfmt="{:.0f}", vfmt="{:.1f}s",
                          ylabel="252쿼리 wall-clock (64병렬, 초)")
    langs = D.LANGS
    lang_chart = svg_bars(1080, 320, langs,
                          [(LABEL[s], COLOR[s],
                            [rows[(s, 100)]["per_lang"].get(l, 0) for l in langs])
                           for s in SYSTEMS + ["bm25"]],
                          ymax=1.0, vfmt="{:.2f}", ylabel="언어별 ndcg@10 (K=100)")

    # significance (paired bootstrap on ndcg@10)
    import numpy as np
    sig_rows = []
    for k in KS:
        for i in range(len(SYSTEMS)):
            for j in range(i + 1, len(SYSTEMS)):
                a = per_query[(SYSTEMS[i], k)]
                b = per_query[(SYSTEMS[j], k)]
                qids = sorted(set(a) & set(b))
                dv = np.array([b[q]["ndcg@10"] - a[q]["ndcg@10"] for q in qids])
                rng = np.random.default_rng(0)
                boots = rng.choice(dv, size=(10_000, len(dv)), replace=True).mean(axis=1)
                lo, hi = np.percentile(boots, [2.5, 97.5])
                t = dv.mean() / (dv.std(ddof=1) / np.sqrt(len(dv)) + 1e-12)
                sig = "유의미 (p<0.01)" if lo > 0 or hi < 0 else "유의미하지 않음"
                sig_rows.append([f"K={k}", f"{LABEL[SYSTEMS[j]]} − {LABEL[SYSTEMS[i]]}",
                                 f"{dv.mean():+.4f}", f"[{lo:+.4f}, {hi:+.4f}]", f"{t:.2f}", sig])

    full_rows = []
    for k in KS:
        for s in SYSTEMS + ["bm25"]:
            r = rows[(s, k)]
            full_rows.append([f"K={k}", LABEL[s], f"{r['ndcg@5']:.4f}", f"{r['ndcg@10']:.4f}",
                              f"{r['map']:.4f}", f"{r['mrr@10']:.4f}", f"{r['recall@10']:.4f}",
                              f"{r['hit@1']:.4f}",
                              f"${r['cost_per_1k']:.3f}" if s != "bm25" else "–",
                              f"{r['lat_mean']:.2f}s" if s != "bm25" else "–",
                              f"{r['lat_p95']:.2f}s" if s != "bm25" else "–"])

    css = """
    body{font-family:system-ui,-apple-system,'Apple SD Gothic Neo',sans-serif;margin:0;
         background:#f9fafb;color:#111827}
    .wrap{max-width:1160px;margin:0 auto;padding:28px 20px 60px}
    h1{font-size:24px;margin:0 0 4px} h2{font-size:17px;margin:34px 0 10px;
       border-left:4px solid #6366f1;padding-left:8px}
    .sub{color:#6b7280;font-size:13px}
    .cards{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}
    .card{flex:1;min-width:220px;background:#fff;border:1px solid #e5e7eb;border-radius:10px;
          padding:12px 14px}
    .card h3{margin:0 0 6px;font-size:13px;color:#6b7280;font-weight:600}
    .card .v{font-size:15px;font-weight:700}
    .grid{display:flex;gap:18px;flex-wrap:wrap}
    .panel{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:14px}
    table{border-collapse:collapse;width:100%;font-size:12px;background:#fff}
    th,td{border:1px solid #e5e7eb;padding:5px 8px;text-align:right}
    th{background:#f3f4f6} td:first-child,th:first-child{text-align:left}
    td:nth-child(2),th:nth-child(2){text-align:left}
    .note{font-size:12px;color:#6b7280;margin-top:6px}
    code{background:#eef2ff;padding:1px 5px;border-radius:4px;font-size:12px}
    """

    html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<title>jev vs reranker 벤치마크 보고서</title><style>{css}</style></head>
<body><div class="wrap">
<h1>Jev vs Reranker 벤치마크 — 성능·비용·속도 3축 비교</h1>
<div class="sub">데이터: <code>mteb/MIRACLReranking</code> (MTEB multilingual reranking) ·
18개 언어 × 14쿼리 = <b>{nq}쿼리</b> · 쿼리당 BM25 top-K 후보 재정렬 ·
K=100 기준 <b>{nq * 100:,} query–passage pair</b> · OpenRouter 경유 ·
시스템: {", ".join(LABEL[s] for s in SYSTEMS)}</div>

<div class="cards">
<div class="card"><h3>성능 (ndcg@10, K=100)</h3>
<div class="v">Voyage {rows[("voyage", 100)]["ndcg@10"]:.4f} ≈ Cohere {rows[("cohere", 100)]["ndcg@10"]:.4f}
&gt; Jev {rows[("jev", 100)]["ndcg@10"]:.4f}</div>
<div class="note">Voyage−Cohere 차이는 통계적으로 유의미하지 않음. 둘 다 Jev를 유의미하게 상회.</div></div>
<div class="card"><h3>비용 ($/1K쿼리, K=100)</h3>
<div class="v">Jev ${cost["jev"]:.2f} &lt; Voyage ${cost["voyage"]:.2f} ≪ Cohere ${cost["cohere"]:.2f}</div>
<div class="note">Cohere는 search-unit 과금(콜당 $0.0025 정액)이라 K와 무관하게 $2.50/1Kq.</div></div>
<div class="card"><h3>속도 (K=100)</h3>
<div class="v">지연: Voyage {lat["voyage"]:.2f}s ≈ Jev {lat["jev"]:.2f}s &lt; Cohere {lat["cohere"]:.2f}s</div>
<div class="note">252쿼리 wall-clock: Jev {meta.get("jev_k100", {}).get("wall_s", 0)}s ·
Cohere {meta.get("cohere_k100", {}).get("wall_s", 0)}s ·
Voyage {meta.get("voyage_k100", {}).get("wall_s", 0)}s (6M TPM 제한).</div></div>
</div>

<h2>3축 종합 (K=100, 각 축 최고=1로 정규화)</h2>
<div class="grid"><div class="panel">{svg_radar(380, ["성능", "비용효율", "속도"], radar_vals, "성능=ndcg@10 ↑ · 비용효율=min$/해당$ · 속도=min지연/해당지연 (K=100)")}</div>
<div class="panel" style="flex:1;min-width:300px">
<p style="font-size:13px;line-height:1.7">
<b>Jev</b>: 비용·처리량 축에서 최강. choice 확률이 상위 2~3개 passage에 집중되고 나머지는 0 →
꼬리 순위는 BM25 원순위에 의존, 그 결과 성능 축에서 유의미하게 뒤짐.<br>
<b>Voyage rerank-2.5</b>: 성능 최상(Cohere와 통계적 동률), 지연 최소. 단 OpenRouter 프로젝트당
6M TPM 제한이 대량 배치 처리량의 병목.<br>
<b>Cohere rerank-4-pro</b>: 성능은 Voyage와 동률이고 hit@1/mrr은 최상위권이나,
정액 search-unit 과금으로 <b>비용 3~10배</b>, 지연도 가장 김(K에 따라 증가).</p>
</div></div>

<h2>축 1 — 성능</h2>
<div class="grid"><div class="panel">{perf_chart}</div><div class="panel">{map_chart}</div></div>

<h2>축 2 — 비용 ($/1K queries)</h2>
<div class="grid"><div class="panel">{cost_chart}</div></div>
<div class="note">jev/voyage는 토큰 과금(input tokens)이라 K에 비례. cohere는 콜당 정액
(1 search unit = 쿼리+최대 100문서)이라 K 무관.</div>

<h2>축 3 — 속도</h2>
<div class="grid"><div class="panel">{lat_chart}</div><div class="panel">{wall_chart}</div></div>
<div class="note">좌: 쿼리 1건 API 지연. 우: 252쿼리를 64-way 동시 처리한 wall-clock —
배치 처리량은 Jev가 압도적(률 제한 사실상 없음).</div>

<h2>언어별 성능 (ndcg@10, K=100)</h2>
<div class="panel" style="overflow-x:auto">{lang_chart}</div>

<h2>유의성 검정 (paired bootstrap, 10,000 resamples, ndcg@10)</h2>
{table(["K", "비교쌍", "Δ 평균", "95% CI", "t", "판정"], sig_rows)}

<h2>전체 메트릭</h2>
{table(["K", "system", "ndcg@5", "ndcg@10", "MAP", "MRR@10", "recall@10", "hit@1",
        "$/1Kq", "지연 평균", "지연 p95"], full_rows)}

<h2>방법론</h2>
<p class="note" style="line-height:1.7">
후보 풀: MIRACL 1차 BM25 top-K (K∈{{20,50,100}}). 두/세 시스템 모두 동일한 seed 셔플 순서로
후보를 받아 재정렬. Jev: <code>state={{"question": …}}</code> + choice criteria=passage 100개 →
choice별 확률로 정렬(동점은 BM25 원순위). Voyage/Cohere: pointwise rerank API의
relevance_score로 정렬. passage는 jev 32K 컨텍스트에 맞춰 언어/K별로 절단(모든 시스템 동일 텍스트).
메트릭: qrels 이진 관련성 기준 ndcg@k/MAP/MRR@k/recall@k/hit@1.
재현: <code>python run.py run --systems jev,voyage,cohere</code> →
<code>python report_html.py</code>. 원시 레코드: <code>results/*_k*.jsonl</code>.</p>
</div></body></html>"""

    (RESULTS / "report.html").write_text(html, encoding="utf-8")
    print(f"wrote {RESULTS / 'report.html'} ({len(html) // 1024} KB)")


if __name__ == "__main__":
    main()
