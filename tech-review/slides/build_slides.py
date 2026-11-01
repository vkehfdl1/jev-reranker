"""Build the Technology Review slide deck (HTML) from results_final/final.json.

  python tech-review/slides/build_slides.py        # writes tech-review/slides/slides.html
  tech-review/slides/make_pdf.sh                    # renders slides.pdf with headless Chrome

Numbers in tables come from results_final/final.json (FINAL.md); the score-shape and token
tables come from results_final/ANALYSIS.md and are copied in below (marked ANALYSIS).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "slides.html"
D = json.loads((ROOT / "results_final" / "final.json").read_text())
M, J = D["miracl"], D["jqara"]

SYS = ["jevnoul14", "jev14", "lunanoul", "luna", "cohere", "cohere35", "coherefast"]
LAB = {
    "jevnoul14": "Jev 1.14 &middot; pointwise (Noul)",
    "jev14": "Jev 1.14 &middot; listwise (Choice)",
    "lunanoul": "gpt-6-luna &middot; pointwise (Noul)",
    "luna": "gpt-6-luna &middot; listwise (Choice)",
    "cohere": "Cohere Rerank 4-pro",
    "cohere35": "Cohere Rerank v3.5",
    "coherefast": "Cohere Rerank 4-fast",
}
SHORT = {
    "jevnoul14": "Jev pointwise", "jev14": "Jev listwise", "lunanoul": "luna pointwise",
    "luna": "luna listwise", "cohere": "Cohere 4-pro", "cohere35": "Cohere v3.5",
    "coherefast": "Cohere 4-fast",
}
MEAN = {s: (M[s]["ndcg@10"] + J[s]["ndcg@10"]) / 2 for s in SYS}
RANK_M = {s: i + 1 for i, s in enumerate(sorted(SYS, key=lambda s: -M[s]["ndcg@10"]))}
RANK_J = {s: i + 1 for i, s in enumerate(sorted(SYS, key=lambda s: -J[s]["ndcg@10"]))}
PAIR = {}
for ds, key in (("M", "miracl_pairs"), ("J", "jqara_pairs")):
    for a, b, d, lo, hi in D[key]:
        PAIR[(ds, a, b)] = (d, lo, hi)

N = 15  # number of slides

import re
FIGS = Path(__file__).resolve().parent / "figs"


def svg_file(name):
    """inline a matplotlib SVG, responsive width"""
    t = (FIGS / name).read_text(encoding="utf-8")
    t = re.sub(r"<\?xml.*?\?>\s*", "", t, flags=re.S)
    t = re.sub(r"<!DOCTYPE.*?>\s*", "", t, flags=re.S)
    t = re.sub(r'<svg([^>]*?)\swidth="[^"]+"\s+height="[^"]+"', r'<svg\1 style="width:100%;height:auto;display:block"', t, count=1)
    return t


def _t(x, y, txt, fs=14, anchor="start", fill="#161616", weight="400"):
    return f'<text x="{x}" y="{y}" font-size="{fs}" text-anchor="{anchor}" fill="{fill}" font-weight="{weight}">{txt}</text>'


def _box(x, y, w, h, txt="", fs=14, fill="#fff", stroke="#1f3a5f", sw=1.3, weight="400", color="#161616", rx=3, lines=None, dash=""):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>'
    ls = lines if lines is not None else ([txt] if txt else [])
    n, lh = len(ls), fs * 1.27
    y0 = y + h / 2 - (n - 1) * lh / 2 + fs * 0.34
    for i, l in enumerate(ls):
        s += _t(x + w / 2, round(y0 + i * lh, 1), l, fs, "middle", color, weight)
    return s


def _arrow(x1, y, x2, mid="pa"):
    return f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="#1f3a5f" stroke-width="1.4" marker-end="url(#{mid})"/>'


def _defs(mid):
    return f'<defs><marker id="{mid}" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#1f3a5f"/></marker></defs>'


def _llm(x, y, w=44, h=30):
    return _box(x, y, w, h, "LLM", 13.5, fill="#1f3a5f", color="#fff", weight="700")


def para_svg():
    o = ['<svg viewBox="0 0 1160 200" width="1160" height="200" role="img" aria-label="Pointwise, pairwise, listwise and setwise prompting">', _defs("pa")]
    for title, x0 in (("Pointwise", 0), ("Pairwise", 290), ("Listwise", 580), ("Setwise", 870)):
        o.append(_t(x0 + 4, 20, title, 17, fill="#0e1b2e", weight="700"))
        o.append(f'<line x1="{x0+4}" y1="27" x2="{x0+272}" y2="27" stroke="#cfcfcf" stroke-width="1"/>')
    # pointwise
    for k, (y, d, s) in enumerate(((40, "d&#8321;", "0.92"), (78, "d&#8322;", "0.15"), (116, "d&#8323;", "0.67"))):
        o.append(_box(4, y, 78, 30, f"(q, {d})", 13.5))
        o.append(_arrow(84, y + 15, 112)); o.append(_llm(114, y)); o.append(_arrow(160, y + 15, 186))
        o.append(_box(188, y, 86, 30, f"s{['&#8321;','&#8322;','&#8323;'][k]} = {s}", 13.5))
    o.append(_t(143, 164, "&#8942;", 18, "middle", "#5b5b5b"))
    o.append(_t(143, 188, "independent of the other passages", 13, "middle", "#5b5b5b"))
    # pairwise
    x0 = 290
    for y, a, b, w in ((40, "d&#8321;", "d&#8322;", "d&#8321; &#8827; d&#8322;"), (78, "d&#8321;", "d&#8323;", "d&#8323; &#8827; d&#8321;"), (116, "d&#8322;", "d&#8323;", "d&#8323; &#8827; d&#8322;")):
        o.append(_box(x0 + 4, y, 98, 30, f"(q, {a}, {b})", 13.5))
        o.append(_arrow(x0 + 104, y + 15, x0 + 124)); o.append(_llm(x0 + 126, y)); o.append(_arrow(x0 + 172, y + 15, x0 + 196))
        o.append(_box(x0 + 198, y, 76, 30, w, 13.5))
    o.append(_t(x0 + 143, 164, "&#8942;", 18, "middle", "#5b5b5b"))
    o.append(_t(x0 + 143, 188, "relative judgment, two at a time", 13, "middle", "#5b5b5b"))
    # listwise
    x0 = 580
    o.append(_box(x0 + 4, 38, 100, 134, lines=["q", "d&#8321;", "d&#8322;", "d&#8323;", "&#8942;", "d&#8345;"], fs=14))
    o.append(_arrow(x0 + 106, 105, x0 + 126)); o.append(_llm(x0 + 128, 90))
    o.append(_arrow(x0 + 174, 105, x0 + 192))
    o.append(_box(x0 + 194, 78, 80, 54, lines=["order or", "pick:", "d&#8323; &gt; d&#8321; &gt; &hellip;"], fs=12.5))
    o.append(_t(x0 + 143, 192, "sees every passage at once", 13, "middle", "#5b5b5b"))
    # setwise
    x0 = 870
    for y, s, w in ((40, "{d&#8321;, d&#8322;, d&#8323;}", "best: d&#8322;"), (78, "{d&#8322;, d&#8324;, d&#8325;}", "best: d&#8325;"), (116, "{d&#8325;, d&#8326;, &hellip;}", "best: &hellip;")):
        o.append(_box(x0 + 4, y, 118, 30, f"(q, {s})", 12.5))
        o.append(_arrow(x0 + 124, y + 15, x0 + 140)); o.append(_llm(x0 + 142, y, 38))
        o.append(_arrow(x0 + 182, y + 15, x0 + 198)); o.append(_box(x0 + 200, y, 74, 30, w, 13))
    o.append(_t(x0 + 143, 164, "&#8942;", 18, "middle", "#5b5b5b"))
    o.append(_t(x0 + 143, 188, "winners advance (tournament)", 13, "middle", "#5b5b5b"))
    o.append("</svg>")
    return "".join(o)


def contract_svg():
    o = ['<svg viewBox="0 0 720 420" width="720" height="420" role="img" aria-label="Decision model input and output">', _defs("pc")]
    nav = "#1f3a5f"
    # INPUT
    o.append(_t(0, 16, "INPUT", 13, fill="#5b5b5b", weight="700"))
    o.append(f'<rect x="0" y="24" width="236" height="90" fill="#fff" stroke="{nav}" stroke-width="1.5"/>')
    o.append(_t(12, 47, "state", 19, fill=nav, weight="700"))
    o.append(_t(12, 69, "the content to evaluate", 14.5))
    o.append(_t(12, 90, "text &middot; JSON &middot; arrays", 14.5))
    o.append(_t(12, 107, "images (Jev 1.14)", 14.5))
    o.append(f'<rect x="0" y="132" width="236" height="272" fill="#fff" stroke="{nav}" stroke-width="1.5"/>')
    o.append(_t(12, 155, "questions", 19, fill=nav, weight="700"))
    o.append(_t(12, 174, "one or many, answered in parallel", 13.5, fill="#5b5b5b"))
    fields = [("type", "choice \u00b7 noul \u00b7 score \u00b7 box"),
              ("instructions", "the question, written in words"),
              ("criteria", "the options or levels, in words")]
    y = 200
    for k, v in fields:
        o.append(_box(12, y - 16, 104, 24, k, 13.5, fill="#eef2f7", stroke=nav, weight="700", color=nav))
        o.append(_t(14, y + 25, v, 13.5))
        y += 56
    o.append(_t(12, 372, "The question id is never shown to the", 12.5, fill="#5b5b5b"))
    o.append(_t(12, 388, "model: all meaning is in the words.", 12.5, fill="#5b5b5b"))
    # MODEL
    o.append(_arrow(238, 160, 268, "pc")); o.append(_arrow(238, 272, 268, "pc"))
    o.append(_box(270, 132, 150, 272, fill="#1f3a5f", stroke=nav, color="#fff", lines=[], rx=3))
    for i, (txt, fs, wt) in enumerate((("Decision", 19, "700"), ("model", 19, "700"), ("(System One)", 14.5, "400"), ("", 0, "400"), ("typed output only", 14, "400"), ("no free text", 14, "400"), ("", 0, "400"), ("trained for", 14, "400"), ("calibrated", 14, "400"), ("probabilities", 14, "400"), ("(vendor claim)", 12.5, "400"))):
        if txt:
            o.append(_t(345, 178 + i * 21, txt, fs, "middle", "#fff", wt))
    # OUTPUT
    o.append(_arrow(422, 160, 452, "pc")); o.append(_arrow(422, 330, 452, "pc"))
    o.append(_t(454, 16, "OUTPUT", 13, fill="#5b5b5b", weight="700"))
    o.append(f'<rect x="454" y="24" width="266" height="270" fill="#fff" stroke="{nav}" stroke-width="1.5"/>')
    o.append(_t(466, 47, "answers", 19, fill=nav, weight="700"))
    o.append(_t(540, 47, "one per question id", 13.5, fill="#5b5b5b"))
    ans = [("choice", ["selected option", "probability of every", "option (&Sigma; = 1), confidence"]),
           ("noul", ["P(yes) &mdash; a single number"]),
           ("score", ["probability-weighted level,", "per-level probabilities"]),
           ("box", ["bounding box (Jev 1.14)"])]
    y = 76
    for k, ls in ans:
        o.append(_box(466, y - 17, 62, 26, k, 13.5, fill="#eef2f7", stroke=nav, weight="700", color=nav))
        for i, l in enumerate(ls):
            o.append(_t(538, y + i * 16, l, 13.5))
        y += max(50, 16 * len(ls) + 18)
    o.append(f'<rect x="454" y="312" width="266" height="92" fill="#fff" stroke="{nav}" stroke-width="1.5"/>')
    o.append(_t(466, 335, "usage", 19, fill=nav, weight="700"))
    o.append(_t(466, 358, "input tokens &middot; output tokens", 14))
    o.append(_t(466, 376, "cost in USD per request", 14))
    o.append(_t(466, 394, "(output tokens are free)", 13, fill="#5b5b5b"))
    o.append("</svg>")
    return "".join(o)


def flow_svg(left, right, mid_label="Decision model"):
    o = ['<svg viewBox="0 0 540 92" width="540" height="92" role="img" aria-label="invocation flow">', _defs("pf")]
    o.append(_box(0, 8, 214, 76, lines=left, fs=13.5))
    o.append(_arrow(216, 46, 242, "pf"))
    o.append(_box(244, 24, 84, 44, lines=["Decision", "model"], fs=13.5, fill="#1f3a5f", color="#fff", weight="700"))
    o.append(_arrow(330, 46, 356, "pf"))
    o.append(_box(358, 8, 182, 76, lines=right, fs=13.5))
    o.append("</svg>")
    return "".join(o)



def f3(x):
    return f"{x:.3f}"


def delta(ds, a, b):
    d, lo, hi = PAIR[(ds, a, b)]
    return f"{d:+.3f} [{lo:+.3f}, {hi:+.3f}]".replace("-", "&minus;")


CSS = """
:root{--ink:#161616;--muted:#5b5b5b;--rule:#1f3a5f;--hair:#cfcfcf;--accent:#1f3a5f;}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:#fff;color:var(--ink)}
body{font-family:"Palatino Linotype","Book Antiqua",Palatino,Charter,Georgia,serif;font-size:19px;line-height:1.36}
.slide{width:1280px;height:720px;position:relative;background:#fff;overflow:hidden;padding:34px 60px 0 60px;page-break-after:always;break-after:page}
.part{font-size:12.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin:0 0 3px}
h1{font-size:33px;line-height:1.15;font-weight:700;margin:0 0 14px;padding-bottom:9px;border-bottom:1.6px solid var(--rule);color:#0e1b2e}
h2{font-size:20px;margin:12px 0 5px;font-weight:700;color:#0e1b2e}
h2.sm{font-size:17px;margin:8px 0 3px}
p{margin:5px 0}
ul{margin:4px 0 4px 0;padding-left:21px}
li{margin:3px 0}
.body{height:538px;overflow:hidden}
.foot{position:absolute;left:60px;right:60px;bottom:14px;border-top:.6px solid var(--hair);padding-top:5px;font-size:11.5px;color:var(--muted);display:flex;justify-content:space-between;gap:30px}
.foot .src{flex:1}
.foot .no{white-space:nowrap}
table{border-collapse:collapse;width:100%;font-size:15.5px;font-variant-numeric:tabular-nums;border-top:1.5px solid var(--ink);border-bottom:1.5px solid var(--ink)}
th{font-weight:700;text-align:left;padding:5px 8px;border-bottom:.8px solid var(--ink);vertical-align:bottom;line-height:1.2}
td{padding:4px 8px;vertical-align:top;line-height:1.25}
td.n,th.n{text-align:right;white-space:nowrap}
tr.sep td{border-top:.6px solid var(--hair)}
tr.hl td{font-weight:700}
td.dim{color:var(--muted)}
.cols{display:flex;gap:34px}
.cols>div{flex:1;min-width:0}
.box{border-left:3px solid var(--accent);padding:4px 0 4px 14px;margin:10px 0}
.box.thesis{font-size:20.5px;line-height:1.34}
code,pre{font-family:Menlo,"SF Mono",Consolas,monospace}
pre{font-size:13px;line-height:1.32;margin:4px 0;padding:8px 10px;border:.8px solid var(--hair);white-space:pre;overflow:hidden}
code{font-size:.86em}
.note{font-size:14.5px;color:var(--muted);line-height:1.3}
.tag{font-size:12.5px;font-style:italic;color:var(--muted)}
b.k{color:#0e1b2e}
svg text{font-family:"Palatino Linotype","Book Antiqua",Palatino,Charter,Georgia,serif}
.eq{font-style:italic;margin:6px 0 6px 18px}
.small{font-size:17px}
.tiny{font-size:13.5px}
/* viewing */
.deck{display:block}
@media screen{
  body{background:#e9e9e9}
  .slide{display:none;margin:0;position:absolute;left:0;top:0;transform-origin:0 0;box-shadow:0 0 0 1px #ccc}
  .slide.active{display:block}
}
@media print{
  @page{size:1280px 720px;margin:0}
  body{background:#fff}
  .slide{display:block !important;position:relative;transform:none !important;left:0 !important;top:0 !important;box-shadow:none}
}
"""

JS = """
(function(){
  var slides=[].slice.call(document.querySelectorAll('.slide')),cur=0;
  function fit(){var s=Math.min(innerWidth/1280,innerHeight/720);
    slides.forEach(function(el){el.style.transform='scale('+s+')';el.style.left=((innerWidth-1280*s)/2)+'px';el.style.top=((innerHeight-720*s)/2)+'px';});}
  function show(n){cur=Math.max(0,Math.min(slides.length-1,n));slides.forEach(function(el,i){el.classList.toggle('active',i===cur)});history.replaceState(null,'','#'+(cur+1));}
  addEventListener('resize',fit);
  addEventListener('keydown',function(e){
    if(['ArrowRight','PageDown',' ','Enter'].indexOf(e.key)>=0)show(cur+1);
    else if(['ArrowLeft','PageUp','Backspace'].indexOf(e.key)>=0)show(cur-1);
    else if(e.key==='Home')show(0);else if(e.key==='End')show(slides.length-1);});
  addEventListener('click',function(e){show(e.clientX>innerWidth/2?cur+1:cur-1)});
  fit();show((parseInt(location.hash.slice(1),10)||1)-1);
  /* layout self-check: report slides whose body overflows */
  var bad=[];slides.forEach(function(el,i){var b=el.querySelector('.body');if(b&&b.scrollHeight>b.clientHeight+1)bad.push((i+1)+':'+(b.scrollHeight-b.clientHeight));});
  var r=document.createElement('pre');r.id='overflow';r.style.display='none';r.textContent='OVERFLOW['+bad.join(',')+']';document.body.appendChild(r);
})();
"""

slides = []


def slide(part, title, body, source, extra_class=""):
    n = len(slides) + 1
    slides.append(
        f'<section class="slide {extra_class}"><div class="part">{part}</div><h1>{title}</h1>'
        f'<div class="body">{body}</div>'
        f'<div class="foot"><div class="src">{source}</div><div class="no">Decision-Model Reranking vs. Cross-Encoders &nbsp;|&nbsp; {n} / {N}</div></div></section>'
    )


# ---------------------------------------------------------------- 1 title
slides.append(
    f"""<section class="slide" style="padding-top:175px">
<div class="part">CS410 Text Information Systems &middot; Fall 2026 &middot; Technology Review</div>
<h1 style="font-size:52px;border:none;margin-bottom:6px;padding-bottom:0">Can a Decision Model Rerank?</h1>
<div style="font-size:27px;color:#0e1b2e;margin-bottom:30px;border-bottom:1.6px solid var(--rule);padding-bottom:16px">Decision models versus cross-encoder rerankers on ranking quality, cost, and latency</div>
<p style="font-size:22px;margin-top:26px">Dongkyu Kim &nbsp;&middot;&nbsp; NetID: dongkyu3</p>
<div class="foot"><div class="src">Code, raw per-query results and analysis scripts are in the project repository (<code>results_final/</code>).</div><div class="no">1 / {N}</div></div>
</section>"""
)

# ---------------------------------------------------------------- 2 motivation / thesis
rows = ""
slide(
    "Introduction",
    "Question, approach, and thesis",
    f"""
<h2>Research question</h2>
<p>A <i>decision model</i> returns a typed answer with probabilities instead of generated text. Can such a model serve as the second-stage reranker of a retrieval pipeline &mdash; and at what quality, cost, and latency compared with dedicated cross-encoder rerankers?</p>
<h2>What I did</h2>
<ul>
<li>Compared <b>7 systems</b> under identical conditions: 100 candidates per query, one seeded shuffle, one prompt per mode, no tuning.</li>
<li>Two benchmarks with different label density: MIRACLReranking (2.2 positives/query) and JQaRAReranking (9.7 positives/query).</li>
<li>Measured nDCG@10 (primary), billed cost per 1,000 queries, sequential and 64-way latency; paired bootstrap (10,000 resamples) for every comparison.</li>
<li>Opened the black box: how Jev-style models are trained and called, and what their score distributions look like when used as rankers.</li>
</ul>
<div class="box thesis"><b class="k">Thesis.</b> &ldquo;Does the decision model replace the reranker?&rdquo; is the wrong question. The same Jev 1.14 loses to Cohere Rerank 4-pro on MIRACL ({f3(M['jevnoul14']['ndcg@10'])} vs {f3(M['cohere']['ndcg@10'])}) and wins on JQaRA ({f3(J['jevnoul14']['ndcg@10'])} vs {f3(J['cohere']['ndcg@10'])}). The ranking depends on the data and on how the model is invoked, so the choice has to be measured on one&rsquo;s own data, with cost and latency in the loop.</div>
<p class="note">Related review in the class library: &ldquo;Tech Review: LLM Rerankers as a Second Stage over BM25&rdquo; surveys LLM reranking methods; this review adds measurements and the mechanics of decision models.</p>
""",
    "All numbers: <code>results_final/FINAL.md</code> (K=100, one run per system and dataset).",
)

# ---------------------------------------------------------------- 3 two-stage retrieval
pipeline_svg = """
<svg viewBox="0 0 1160 150" width="1160" height="150" role="img" aria-label="Two-stage retrieval pipeline">
<defs><marker id="ar" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto"><path d="M0,0 L9,4.5 L0,9 z" fill="#1f3a5f"/></marker></defs>
<g font-size="17" fill="#161616" stroke="#1f3a5f" stroke-width="1.3">
<rect x="4" y="30" width="170" height="64" fill="#fff"/><rect x="262" y="30" width="200" height="64" fill="#fff"/>
<rect x="550" y="30" width="170" height="64" fill="#fff"/><rect x="808" y="30" width="200" height="64" fill="#fff"/>
<rect x="1070" y="30" width="86" height="64" fill="#fff"/>
</g>
<g font-size="17" text-anchor="middle" fill="#161616">
<text x="89" y="58">Corpus</text><text x="89" y="80" font-size="14" fill="#5b5b5b">10&#x2075;&ndash;10&#x2079; passages</text>
<text x="362" y="58">First stage</text><text x="362" y="80" font-size="14" fill="#5b5b5b">BM25 / dense embeddings</text>
<text x="635" y="58">Candidates</text><text x="635" y="80" font-size="14" fill="#5b5b5b">top-K, K = 100</text>
<text x="908" y="58">Second stage</text><text x="908" y="80" font-size="14" fill="#5b5b5b">reranker (this review)</text>
<text x="1113" y="58">Top-10</text><text x="1113" y="80" font-size="14" fill="#5b5b5b">nDCG@10</text>
</g>
<g stroke="#1f3a5f" stroke-width="1.5" marker-end="url(#ar)">
<line x1="176" y1="62" x2="258" y2="62"/><line x1="464" y1="62" x2="546" y2="62"/>
<line x1="722" y1="62" x2="804" y2="62"/><line x1="1010" y1="62" x2="1066" y2="62"/></g>
<g font-size="14" fill="#5b5b5b" text-anchor="middle">
<text x="362" y="118">cheap; document representations precomputed</text>
<text x="908" y="118">reads query and candidate together; cost grows with K</text>
</g></svg>
"""
slide(
    "Background",
    "Two-stage retrieval and the role of the reranker",
    f"""
{pipeline_svg}
<div class="cols">
<div>
<h2>Why a second stage</h2>
<ul>
<li>The first stage scores query and document independently, so the index can be built offline and searched quickly &mdash; but it compares them only coarsely.</li>
<li>The reranker reads the query together with each of the K candidates. Per-query cost is therefore proportional to K, and final quality is bounded by first-stage recall.</li>
<li>BEIR reports that re-ranking and late-interaction models give the best zero-shot average, but at high computational cost; ColBERT attributes that cost to pushing every query&ndash;document pair through a large network.</li>
</ul>
</div>
<div>
<h2>What this implies for the comparison</h2>
<ul>
<li>The unit of cost is the <b>candidate list</b> (100 passages per query), not a single document.</li>
<li>Providers price it differently: per input token (decision models) or per search unit of up to 100 documents (Cohere) &mdash; so the cheaper option depends on passage length.</li>
<li>Reference points in our samples: BM25 order gives nDCG@10 {f3(M['__baseline__']['ndcg@10'])} on MIRACL; a random order gives {f3(J['__baseline__']['ndcg@10'])} on JQaRA.</li>
</ul>
</div></div>
""",
    "Khattab &amp; Zaharia, ColBERT (arXiv 2004.12832); Thakur et al., BEIR (arXiv 2104.08663) &mdash; abstracts. Baselines: <code>results_final/FINAL.md</code>.",
)

# ---------------------------------------------------------------- 4 cross-encoders
enc_svg = """
<svg viewBox="0 0 560 250" width="560" height="250" role="img" aria-label="Bi-encoder vs cross-encoder">
<defs><marker id="a2" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#1f3a5f"/></marker></defs>
<g font-size="15" fill="#161616" text-anchor="middle">
<text x="130" y="18" font-weight="700">Bi-encoder (first stage)</text>
<text x="430" y="18" font-weight="700">Cross-encoder (reranker)</text></g>
<g stroke="#1f3a5f" stroke-width="1.3" fill="#fff">
<rect x="20" y="40" width="80" height="34"/><rect x="160" y="40" width="80" height="34"/>
<rect x="20" y="104" width="80" height="34"/><rect x="160" y="104" width="80" height="34"/>
<rect x="90" y="176" width="80" height="34"/>
<rect x="330" y="40" width="200" height="34"/><rect x="330" y="104" width="200" height="34"/>
<rect x="370" y="176" width="120" height="34"/></g>
<g font-size="14" fill="#161616" text-anchor="middle">
<text x="60" y="62">query</text><text x="200" y="62">document</text>
<text x="60" y="126">encoder</text><text x="200" y="126">encoder</text>
<text x="130" y="198">dot product</text>
<text x="430" y="62">[CLS] query [SEP] document</text><text x="430" y="126">transformer, joint attention</text>
<text x="430" y="198">relevance score</text></g>
<g stroke="#1f3a5f" stroke-width="1.4" marker-end="url(#a2)">
<line x1="60" y1="76" x2="60" y2="102"/><line x1="200" y1="76" x2="200" y2="102"/>
<line x1="60" y1="140" x2="110" y2="174"/><line x1="200" y1="140" x2="150" y2="174"/>
<line x1="430" y1="76" x2="430" y2="102"/><line x1="430" y1="140" x2="430" y2="174"/></g>
<g font-size="12.5" fill="#5b5b5b" text-anchor="middle">
<text x="130" y="236">document vectors precomputable</text>
<text x="430" y="236">one pass per pair; not precomputable</text></g>
</svg>
"""
slide(
    "Background",
    "Cross-encoder rerankers",
    f"""
<div class="cols">
<div style="flex:0 0 560px">{enc_svg}
<ul class="small">
<li>Every query token can attend to every passage token, which is why cross-encoders are more accurate than independent encoders &mdash; and why they only run on the top-K.</li>
<li>Scores are <b>pointwise</b>: each candidate is scored on its own, so the result does not depend on candidate order.</li>
</ul></div>
<div>
<table>
<tr><th style="width:27%">Model family</th><th>How the relevance score is produced</th></tr>
<tr><td>BERT reranker<br><span class="tag">Nogueira &amp; Cho, 2019</span></td><td>BERT fine-tuned on (query, passage) pairs; top of the MS MARCO leaderboard and state of the art on TREC-CAR at the time.</td></tr>
<tr class="sep"><td>monoT5<br><span class="tag">Nogueira et al., 2020</span></td><td>T5 is trained to generate the target words &ldquo;true&rdquo; / &ldquo;false&rdquo;; the logits of those words are read as a relevance probability.</td></tr>
<tr class="sep"><td>Qwen3-Reranker-8B<br><span class="tag">open weights, 32K context</span></td><td>Decoder LLM with a chat prompt (<code>&lt;Instruct&gt; &lt;Query&gt; &lt;Document&gt;</code>) and a system rule &ldquo;answer only yes or no&rdquo;. Score = softmax over the <code>no</code>/<code>yes</code> logits at the last position, i.e. P(yes) (model-card code).</td></tr>
<tr class="sep"><td>Cohere Rerank<br><span class="tag">API, 100+ languages</span></td><td>Returns <code>relevance_score</code> per document; billed per search unit. The documentation I read gives no architecture or training details &mdash; treated as a black-box pointwise scorer.</td></tr>
</table>
<div class="box" style="margin-top:14px"><b class="k">Bridge to decision models.</b> Qwen3-Reranker already turns an LLM into a ranker by reading a yes/no probability instead of generating text. Decision models expose that read-out as a typed API.</div>
</div></div>
""",
    "Nogueira &amp; Cho (arXiv 1901.04085), Nogueira, Jiang &amp; Lin (arXiv 2003.06713) &mdash; abstracts; Qwen3-Reranker-8B model card (code read directly); Cohere Rerank overview. Joint-input diagram follows the standard BERT setup.",
)

# ---------------------------------------------------------------- 5 LLM prompting taxonomy
slide(
    "Background",
    "Using LLMs as rerankers: four ways to prompt",
    f"""
{para_svg()}
<table style="margin-top:2px;font-size:14.2px">
<tr><th style="width:10%">Paradigm</th><th style="width:19%">LLM calls per query</th><th style="width:27%">Strength</th><th style="width:30%">Weakness</th><th>Reference</th></tr>
<tr><td><b>Pointwise</b></td><td>N, independent (parallel)</td><td>Independent of other candidates and of input order</td><td>No cross-passage comparison; scores need calibration</td><td>monoT5; Qwen3-Reranker</td></tr>
<tr class="sep"><td><b>Pairwise</b></td><td>up to O(N&sup2;); linear variants exist</td><td>Relative judgments are easier than absolute scores</td><td>High call count and token overhead</td><td>PRP</td></tr>
<tr class="sep"><td><b>Listwise</b></td><td>1 (long lists need chunking)</td><td>One pass; global comparison of all candidates</td><td>Context limit; order sensitivity; output must be parsed</td><td>RankGPT; RankZephyr</td></tr>
<tr class="sep"><td><b>Setwise</b></td><td>fewer inferences than pairwise</td><td>Between pairwise accuracy and pointwise cost</td><td>Needs a sorting procedure over sets</td><td>Setwise paper</td></tr>
</table>
<div class="cols" style="margin-top:4px">
<div>
<h2 class="sm" style="margin-top:2px">What the literature reports</h2>
<ul style="font-size:15.4px;margin-top:2px">
<li>Instructed LLMs can match supervised rankers (RankGPT); pairwise prompting (PRP) makes moderate-sized open models competitive.</li>
<li>Pointwise is efficient but less effective; pairwise is effective but costly (Setwise paper).</li>
</ul></div>
<div>
<h2 class="sm" style="margin-top:4px">Where decision models fit</h2>
<ul style="font-size:15.4px;margin-top:2px">
<li><b>Choice</b> over N options = listwise / setwise selection with a probability for <i>every</i> option.</li>
<li><b>Noul</b> = pointwise P(yes); many Noul questions can share one request.</li>
</ul></div></div>
""",
    "Sun et al., RankGPT (arXiv 2304.09542); Qin et al., PRP (2306.17563); Zhuang et al., Setwise (2310.09497); Pradeep et al., RankZephyr (2312.02724) &mdash; abstracts only; diagrams and call-count column are my summary.",
)

# ---------------------------------------------------------------- 6 decision models
slide(
    "How it works",
    "Decision models (System One): what goes in, what comes out",
    f"""
<div class="cols" style="gap:30px">
<div style="flex:0 0 700px">{contract_svg()}</div>
<div>
<h2 class="sm" style="margin-top:0">Not an LLM that writes answers <span class="tag">(vendor documentation; not independently verified)</span></h2>
<ul style="font-size:16px">
<li>Returns a <b>typed answer with probabilities</b>; the caller fixes the answer space. No generated text.</li>
<li>Trained with <b>RLCD</b> &mdash; reinforcement learning for <i>calibrated decisions</i> &mdash; rather than RLHF or RLVR. Calibration holds across many predictions, not for a single answer.</li>
<li>Questions in one request share a state that is read once and are evaluated in parallel.</li>
<li>Jev 1.14: <b>$0.042 / M input tokens</b>, output free; 262K context on OpenRouter.</li>
<li>Architecture, size and training data are <b>not disclosed</b> in the documents I read.</li>
<li>One API, 22 models from 13 makers &mdash; I switched Jev &rarr; <code>openai/gpt-6-luna-decisions</code> ($0.10 / M) by changing the model name.</li>
</ul>
<div class="box" style="font-size:15.2px"><b class="k">My observation.</b> gpt-6-luna reports <code>output_tokens = 0</code>: consistent with reading probabilities out of one forward pass, like Qwen3-Reranker&rsquo;s yes/no logit. An inference, not documented.</div>
</div></div>
""",
    "TypeSafe docs: System One, AI primer, Models, Choice, Noul; OpenRouter Jev guide. Output-token observation: my own API calls, 2026-11-01.",
)

# ---------------------------------------------------------------- 7 decision model as reranker
slide(
    "How it works",
    "Turning a decision model into a reranker: two invocation modes",
    f"""
<div class="cols" style="gap:34px">
<div>
<h2 style="margin-top:0">Listwise: one Choice question over all 100 passages</h2>
{flow_svg(["query in the state;", "100 passages = the options", "of ONE Choice question"], ["probability over", "the 100 options (&Sigma; = 1)", "score(d&#7522;) = P(option c&#7522;)"])}
<div style="margin-top:6px">{svg_file('example_listwise.svg')}</div>
<ul style="font-size:15.4px;margin-top:4px">
<li>Only <b>~6 candidates</b> (Jev) or <b>~20</b> (luna) get non-zero mass; the rest tie at 0 and keep the presented order.</li>
</ul>
</div>
<div>
<h2 style="margin-top:0">Batched pointwise: 100 Noul questions in one request</h2>
{flow_svg(["query + 100 passages in the state;", "100 Noul questions:", "&ldquo;Is passage c&#7522; relevant?&rdquo;"], ["P(yes) for every passage,", "asked independently", "score(d&#7522;) = P(yes | c&#7522;)"])}
<div style="margin-top:6px">{svg_file('example_pointwise.svg')}</div>
<ul style="font-size:15.4px;margin-top:4px">
<li>Every passage is scored, but at 0.01 resolution <b>~63% tie</b> (Jev); input tokens +18% (Jev) / +99% (luna) vs. listwise.</li>
</ul>
</div></div>
<p class="note" style="margin-top:4px">Bars: one real JQaRA query (<code>test_query831</code>), 100 candidates in the order the model received them; dark = labelled positive. All systems: same seeded shuffle, sort by score, ties broken by presented position, one fixed prompt per mode.</p>
<div class="box" style="font-size:15px;margin:6px 0 0 0"><b class="k">Not strictly pointwise.</b> TypeSafe&rsquo;s own re-ranking cookbook sends one request per (query, candidate) pair; mine puts all 100 passages in one state, so every question can see the whole list. I did not compare the two forms.</div>
""",
    "Implementation: <code>clients.py</code>, <code>jqara_run.py</code>. Measurements: <code>results_final/ANALYSIS.md</code> (A); figure: <code>tech-review/slides/make_figures.py</code>.",
)

# ---------------------------------------------------------------- 8 setup
slide(
    "Experiments",
    "Experimental setup",
    """
<table>
<tr><th style="width:16%"></th><th style="width:42%">MIRACLReranking</th><th>JQaRAReranking</th></tr>
<tr><td><b>Queries</b></td><td>252 = 14 &times; 18 languages (seed 42); only queries with &ge;1 positive in the pool</td><td>1,667 (full test split), Japanese</td></tr>
<tr class="sep"><td><b>Candidates</b></td><td>BM25 top-100</td><td>top-100 from five embedding models fused by RRF</td></tr>
<tr class="sep"><td><b>Positives / query</b></td><td>2.2</td><td>9.7</td></tr>
<tr class="sep"><td><b>Labels</b></td><td>Relevance judgments by native speakers</td><td>Positive if the passage or title contains the answer string; part of the labels filtered by LLM answerability and human review</td></tr>
<tr class="sep"><td><b>Passage text</b></td><td>Truncated per language to 218&ndash;533 characters (to fit Jev&rsquo;s context); identical text for all systems</td><td>Untruncated (about 400 characters or fewer)</td></tr>
</table>
<div class="cols" style="margin-top:12px">
<div>
<h2 class="sm">Systems (7)</h2>
<ul class="small">
<li>Jev 1.14 <code>typesafe/jev-1.14</code>: listwise (Choice), pointwise (Noul)</li>
<li>gpt-6-luna <code>openai/gpt-6-luna-decisions</code>: listwise, pointwise</li>
<li>Cohere Rerank 4-pro, 4-fast, v3.5 via OpenRouter <code>/api/v1/rerank</code></li>
<li><b>Excluded</b> after a 600-query probe: Voyage 2.5/3/lite (429 rate limits), hosted Qwen3-Reranker (503/429, slow), NVIDIA free tier (throttled)</li>
</ul></div>
<div>
<h2 class="sm">Measurement protocol</h2>
<ul class="small">
<li><b>Quality:</b> nDCG@10 (primary), hit@1, MRR@10, recall@10; paired bootstrap over queries, 10,000 resamples, 95% CI.</li>
<li><b>Cost:</b> billed <code>usage.cost</code> from the API response; Cohere is per search unit, decision models per input token.</li>
<li><b>Latency:</b> service time of the successful HTTP call (harness queueing excluded), measured one request at a time (50 queries) and with 64 requests in flight (all queries).</li>
<li>Failed queries (5 luna-listwise refusals) are scored on the presented order.</li>
</ul></div></div>
""",
    "MIRACL: Zhang et al. (arXiv 2210.09984). JQaRA: dataset card (hotchpotch/JQaRA). Setup: <code>data.py</code>, <code>jqara_data.py</code>, <code>jqara_run.py</code>, <code>results_jqara/SUMMARY.md</code>.",
)

# ---------------------------------------------------------------- 10 results (forest plot)
def forest(ds, title, W=520):
    data = M if ds == "M" else J
    order = sorted(SYS, key=lambda s: -data[s]["ndcg@10"])
    x0, x1 = 0.55, 0.92
    left, right = 150, W - 48
    xs = lambda v: left + (v - x0) / (x1 - x0) * (right - left)
    rowh = 31
    h = 56 + rowh * len(order) + 30
    out = [f'<svg viewBox="0 0 {W} {h}" width="{W}" height="{h}" role="img" aria-label="{title}">']
    out.append(f'<text x="0" y="16" font-size="16" font-weight="700" fill="#0e1b2e">{title}</text>')
    for t in (0.6, 0.7, 0.8, 0.9):
        x = xs(t)
        out.append(f'<line x1="{x:.1f}" y1="30" x2="{x:.1f}" y2="{40 + rowh*len(order)}" stroke="#e1e1e1" stroke-width="1"/>')
        out.append(f'<text x="{x:.1f}" y="{54 + rowh*len(order)}" font-size="12.5" text-anchor="middle" fill="#5b5b5b">{t:.1f}</text>')
    out.append(f'<text x="{(left+right)/2:.1f}" y="{h-2}" font-size="12.5" text-anchor="middle" fill="#5b5b5b">nDCG@10 (marker = mean, bar = 95% bootstrap CI)</text>')
    for i, s in enumerate(order):
        y = 46 + i * rowh
        r = data[s]
        lo, hi = r["ndcg_ci"]
        hl = s == "jevnoul14"
        col = "#1f3a5f" if hl else ("#161616" if s == "cohere" else "#7a7a7a")
        wt = "700" if hl or s == "cohere" else "400"
        out.append(f'<text x="0" y="{y+4}" font-size="14" font-weight="{wt}" fill="{col}">{SHORT[s]}</text>')
        out.append(f'<line x1="{xs(lo):.1f}" y1="{y}" x2="{xs(hi):.1f}" y2="{y}" stroke="{col}" stroke-width="2"/>')
        out.append(f'<line x1="{xs(lo):.1f}" y1="{y-4}" x2="{xs(lo):.1f}" y2="{y+4}" stroke="{col}" stroke-width="1.5"/>')
        out.append(f'<line x1="{xs(hi):.1f}" y1="{y-4}" x2="{xs(hi):.1f}" y2="{y+4}" stroke="{col}" stroke-width="1.5"/>')
        out.append(f'<rect x="{xs(r["ndcg@10"])-4.5:.1f}" y="{y-4.5}" width="9" height="9" fill="{col}"/>')
        out.append(f'<text x="{W-44}" y="{y+4}" font-size="14" font-weight="{wt}" fill="{col}" text-anchor="start">{r["ndcg@10"]:.3f}</text>')
    out.append("</svg>")
    return "".join(out)


slide(
    "Results",
    "Ranking quality: the order of systems flips between datasets",
    f"""
<div class="cols" style="gap:40px">
<div>{forest("M", f"MIRACLReranking &middot; 252 queries")}</div>
<div>{forest("J", f"JQaRAReranking &middot; 1,667 queries")}</div>
</div>
<table style="margin-top:8px">
<tr><th style="width:36%">Paired bootstrap on nDCG@10 (&Delta; mean [95% CI])</th><th class="n">MIRACL</th><th class="n">JQaRA</th></tr>
<tr><td>Jev pointwise &minus; Cohere 4-pro</td><td class="n">{delta('M','jevnoul14','cohere')}</td><td class="n">{delta('J','jevnoul14','cohere')}</td></tr>
<tr class="sep"><td>Jev pointwise &minus; Jev listwise</td><td class="n">{delta('M','jevnoul14','jev14')}</td><td class="n">{delta('J','jevnoul14','jev14')}</td></tr>
<tr class="sep"><td>Jev pointwise &minus; luna pointwise</td><td class="n">{delta('M','jevnoul14','lunanoul')}</td><td class="n">{delta('J','jevnoul14','lunanoul')}</td></tr>
<tr class="sep"><td>Jev listwise &minus; luna listwise</td><td class="n">{delta('M','jev14','luna')}</td><td class="n">{delta('J','jev14','luna')}</td></tr>
</table>
<p class="small" style="margin-top:8px">Jev pointwise is 4th of 7 on MIRACL and 1st on JQaRA; Cohere 4-pro is the only system in the top two on both. Cohere v3.5 and 4-fast fall from 1st/3rd to 4th/6th. gpt-6-luna is below Jev in the same mode on both datasets. Reference: BM25 order {f3(M['__baseline__']['ndcg@10'])} (MIRACL), random order {f3(J['__baseline__']['ndcg@10'])} (JQaRA).</p>
""",
    "<code>results_final/FINAL.md</code>: K=100, one run per system and dataset; paired bootstrap over queries, 10,000 resamples.",
)

# ---------------------------------------------------------------- 11 cost latency
slide(
    "Results",
    "Price&ndash;performance and latency&ndash;performance: decision models vs. rerankers",
    f"""
<div class="cols" style="gap:22px">
<div style="flex:0 0 735px">{svg_file('quality_cost_latency.svg')}
</div>
<div>
<h2 class="sm" style="margin-top:0">What the frontiers show</h2>
<ul style="font-size:15.4px;margin-top:2px;padding-left:18px">
<li><b>Frontier</b> (circled): Jev pointwise, Jev listwise and Cohere v3.5 in three of the four panels; v3.5 drops out of the JQaRA latency panel. Cohere 4-pro, 4-fast and gpt-6-luna are on no frontier.</li>
<li><b>JQaRA:</b> Jev pointwise beats 4-pro by 0.066 nDCG@10 and is $1.36 / 1K queries cheaper and 0.42 s faster &mdash; 4-pro is significantly dominated.</li>
<li><b>MIRACL:</b> 4-pro is tied with v3.5 at 2.5&times; the price. Against Jev pointwise: <b>$0.37 saved per 0.01 nDCG@10 given up</b> ($1.61 and 0.41 s saved for &minus;0.044).</li>
<li><b>gpt-6-luna</b> is significantly dominated in all four panels, in both modes.</li>
<li><b>Under load</b> (64 in flight, JQaRA): Jev listwise slows to 2.78 s mean / 6.84 s p95; Cohere 4-pro stays at 1.05 s.</li>
</ul>
<div class="box" style="font-size:14.4px;margin:8px 0 0 0"><b class="k">Cost model.</b> Decision models: input tokens &times; price (Jev $0.042/M, luna $0.10/M). Cohere: flat $0.0025 per query (4-pro). Break-even &asymp; 60K (Jev) / 25K (luna) tokens per query; our 100-passage queries use 11&ndash;36K.</div>
</div></div>
""",
    "<code>results_final/FINAL.md</code>, <code>PARETO.md</code> (dominance uses paired bootstrap CIs); latency = mean service time, one request at a time; bars = 95% bootstrap CI of nDCG@10.",
)

# ---------------------------------------------------------------- 9 score shape
slide(
    "Analysis",
    "What the scores look like when a decision model is used as a ranker",
    f"""
<div class="cols" style="gap:26px">
<div style="flex:0 0 640px">
{svg_file('score_profile.svg')}
<table style="margin-top:6px;font-size:13.6px">
<tr><th style="width:30%">System (mode)</th><th class="n">Non-zero / 100<br>M / J</th><th class="n">Ties<br>M / J</th><th class="n">&Sigma; score<br>M / J</th><th class="n">Positives &gt; 0<br>M / J</th></tr>
<tr><td>Jev &middot; listwise</td><td class="n">6.5 / 6.0</td><td class="n">0.95 / 0.95</td><td class="n">1.0 / 1.0</td><td class="n">83% / 53%</td></tr>
<tr class="sep"><td>luna &middot; listwise</td><td class="n">22.8 / 19.7</td><td class="n">0.94 / 0.95</td><td class="n">1.0 / 1.0</td><td class="n">77% / 55%</td></tr>
<tr class="sep"><td>Jev &middot; pointwise</td><td class="n">100 / 100</td><td class="n">0.65 / 0.63</td><td class="n">24.1 / 22.0</td><td class="n">100% / 100%</td></tr>
<tr class="sep"><td>luna &middot; pointwise</td><td class="n">22.3 / 15.4</td><td class="n">0.85 / 0.89</td><td class="n">10.9 / 8.9</td><td class="n">92% / 82%</td></tr>
<tr class="sep dim"><td class="dim">Positives per query</td><td class="n dim">2.2 / 9.7</td><td colspan="3"></td></tr>
</table>
<p class="tag" style="margin-top:3px">M = MIRACL, J = JQaRA. Ties = 1 &minus; (distinct scores / 100).</p>
</div>
<div>
<h2 class="sm" style="margin-top:0">Listwise (Choice)</h2>
<ul style="font-size:16.4px">
<li>Probability mass 1 sits on <b>about six</b> of 100 candidates (Jev); the other ~94 tie at zero and stay in the shuffled order.</li>
<li>An excellent top-1 selector &mdash; JQaRA hit@1: luna 0.939, Jev 0.935, first and second of all systems &mdash; with no ordering information below it.</li>
<li>With 9.7 positives per query, Jev gives non-zero mass to only 53% of them.</li>
</ul>
<h2 class="sm">Pointwise (Noul)</h2>
<ul style="font-size:16.4px">
<li>Jev scores all 100 candidates, but at 0.01 resolution about 63% tie; ties are broken by presented position.</li>
<li>&Sigma; P(yes) is 22&ndash;24 per query while qrels list 2.2 / 9.7 positives. The prompt&rsquo;s notion of relevance (&ldquo;helps answer the question&rdquo;) is broader than the labels, so this is no proof of mis-calibration &mdash; but P(yes) should be used as a ranking score only.</li>
</ul>
</div></div>
""",
    "Own analysis: <code>results_final/ANALYSIS.md</code> (section A) and per-query scores of the final runs (252 and 1,667 queries); chart: <code>make_figures.py</code>.",
)

# ---------------------------------------------------------------- 12 why flip
slide(
    "Analysis",
    "Why does the ranking flip? What is measured and what is not",
    f"""
<div class="cols">
<div style="flex:1.18">
<h2 style="margin-top:0">Measured</h2>
<table style="font-size:14.5px">
<tr><th>Effect of invocation mode (nDCG@10)</th><th class="n">MIRACL</th><th class="n">JQaRA</th></tr>
<tr><td>Jev: pointwise &minus; listwise</td><td class="n">{delta('M','jevnoul14','jev14')}</td><td class="n">{delta('J','jevnoul14','jev14')}</td></tr>
<tr class="sep"><td>luna: pointwise &minus; listwise</td><td class="n">{delta('M','lunanoul','luna')}</td><td class="n">{delta('J','lunanoul','luna')}</td></tr>
<tr class="sep"><td>Positives per query</td><td class="n">2.2</td><td class="n">9.7</td></tr>
<tr class="sep"><td>Jev listwise: positives with score &gt; 0</td><td class="n">83%</td><td class="n">53%</td></tr>
<tr class="sep"><td>Jev listwise hit@1</td><td class="n">{M['jev14']['hit@1']:.3f}</td><td class="n">{J['jev14']['hit@1']:.3f}</td></tr>
<tr class="sep"><td>Jev pointwise hit@1</td><td class="n">{M['jevnoul14']['hit@1']:.3f}</td><td class="n">{J['jevnoul14']['hit@1']:.3f}</td></tr>
</table>
<ul class="small" style="margin-top:10px">
<li>The gap between modes is negligible on MIRACL and large on JQaRA; at rank 1 the two modes are about equal.</li>
<li>Within one vendor, tiers differ by dataset: Cohere 4-pro {f3(J['cohere']['ndcg@10'])} vs. 4-fast {f3(J['coherefast']['ndcg@10'])} and v3.5 {f3(J['cohere35']['ndcg@10'])} on JQaRA, while on MIRACL 4-pro and v3.5 are tied ({f3(M['cohere']['ndcg@10'])}, {f3(M['cohere35']['ndcg@10'])}) and 4-fast is {f3(M['coherefast']['ndcg@10'])}.</li>
</ul>
</div>
<div>
<h2 style="margin-top:0">Confounded &mdash; not separated by this design</h2>
<ul class="small">
<li><b>Label density:</b> 2.2 vs. 9.7 positives per query. Shallow listwise support costs more when there are more positives to rank.</li>
<li><b>Input truncation:</b> MIRACL passages were cut to 218&ndash;533 characters, JQaRA passages were not.</li>
<li><b>Label semantics:</b> JQaRA marks a passage positive when it contains the answer string (plus filtering); MIRACL uses graded human relevance judgments.</li>
<li><b>Language and domain:</b> 18 languages of Wikipedia queries vs. Japanese quiz questions.</li>
</ul>
<h2 class="sm">Hypotheses (untested)</h2>
<ul class="small">
<li>Quiz questions are answerable from world knowledge, which may help a model judge whether a passage contains the answer.</li>
<li>Vendor documentation says Jev is weaker outside English, yet it is first on Japanese JQaRA &mdash; unexplained.</li>
<li>Possible contamination of any model with JAQKET/Wikipedia material cannot be excluded.</li>
</ul>
</div></div>
""",
    "<code>results_final/FINAL.md</code>, <code>ANALYSIS.md</code>; JQaRA label construction from the dataset card; vendor language statement from TypeSafe &ldquo;Models&rdquo; documentation.",
)

# ---------------------------------------------------------------- 13 limitations
slide(
    "Limitations",
    "Limitations and negative results",
    """
<div class="cols">
<div>
<h2 style="margin-top:0">Threats to validity</h2>
<ul class="small">
<li><b>One run per system and dataset.</b> Re-running MIRACL changed scores by &minus;0.006 to +0.002 (e.g. Jev pointwise 0.7552 &rarr; 0.7496). Latency variance across runs was not measured.</li>
<li><b>Long-context mode.</b> Passage text exceeded 32,000 bytes for 92% (MIRACL) and 97% (JQaRA) of queries. OpenRouter&rsquo;s Jev guide says such requests run in a slower, less accurate long-context mode (vendor claim, unverified); if true, Jev&rsquo;s scores are conservative.</li>
<li><b>One prompt per mode, no tuning;</b> no threshold or instruction search for any system.</li>
<li><b>&ldquo;Pointwise&rdquo; is shared-context</b> (all passages in one state); per-pair requests were not compared. The ordinal <b>Score</b> primitive was not tried.</li>
<li>Cohere Rerank 5, named in Cohere&rsquo;s documentation, was not in the OpenRouter catalog I used.</li>
<li>Costs and latencies are via OpenRouter, not vendor endpoints; results come from a single day.</li>
</ul>
</div>
<div>
<h2 style="margin-top:0">Negative and unexpected results</h2>
<ul class="small">
<li><b>Rank fusion does not help.</b> Reciprocal rank fusion of two systems was significantly worse than the better member on JQaRA in all six pairs tried (e.g. Jev pointwise + Cohere 4-pro: &minus;0.015 [&minus;0.019, &minus;0.010]) and indistinguishable from it on MIRACL. A hybrid pipeline is not supported by this data.</li>
<li><b>Refusals.</b> For 5 of 1,667 JQaRA queries, gpt-6-luna in listwise mode returned &ldquo;OpenAI refused to answer&rdquo; on every retry; those queries were scored on the presented order. Cohere returned a score for every query.</li>
<li><b>Exclusions.</b> Voyage rerank models returned HTTP 429 at sustained volume (2,237 times for the lite model over 1,667 queries) and hosted Qwen3-Reranker was slow or unavailable; their quality is not in the final table.</li>
<li><b>Qrels are incomplete.</b> On MIRACL, 47 of 53 candidates that Jev scored &ge;0.5 but the qrels called non-relevant were judged relevant by an independent LLM judge (phase-1 data, Jev-only) &mdash; absolute scores understate recall of true relevance.</li>
</ul>
</div></div>
""",
    "<code>results_final/ANALYSIS.md</code> (B, C); <code>results_jqara/SUMMARY.md</code> (probe, refusals); OpenRouter Jev guide (long-context note); phase-1 judge run: <code>results/judge_relevance_full.jsonl</code>.",
)

# ---------------------------------------------------------------- 14 conclusion
slide(
    "Conclusion",
    "Conclusion: what I learned",
    f"""
<ul style="font-size:24px;line-height:1.5;margin-top:22px">
<li><b>Rankings do not transfer between datasets.</b> The same Jev 1.14 loses to Cohere 4-pro on MIRACL ({f3(M['jevnoul14']['ndcg@10'])} vs {f3(M['cohere']['ndcg@10'])}) and wins on JQaRA ({f3(J['jevnoul14']['ndcg@10'])} vs {f3(J['cohere']['ndcg@10'])}).</li>
<li><b>A decision model is a score-and-select API, not a drop-in cross-encoder.</b> Listwise piles probability on ~6 of 100 passages (great top-1, shallow ranking); pointwise scores everything but ties a lot; P(yes) is a ranking score, not the probability of relevance.</li>
<li><b>Price structure matters more than list price.</b> Tokens &times; price versus a flat per-query fee: Jev sits on the cost frontier on both datasets, Cohere 4-pro and gpt-6-luna never do.</li>
<li><b>Measure it yourself, and measure carefully.</b> Client-side queueing had inflated my first latency numbers, rate limits removed Voyage, and one run per system is a real limit. Rank fusion of two systems did not help.</li>
<li><b>Practical rule:</b> A/B on 50&ndash;200 of your own queries, with cost and latency in the table.</li>
</ul>
""",
    "Synthesis of slides 7&ndash;13; numbers from <code>results_final/</code>.",
)

# ---------------------------------------------------------------- 15 resources
res = [
    ("Passage Re-ranking with BERT", "Nogueira &amp; Cho, arXiv 1901.04085", "Origin of cross-encoder reranking; MS MARCO state of the art."),
    ("Pretrained Transformers for Text Ranking: BERT and Beyond", "Lin, Nogueira &amp; Yates, arXiv 2010.06467", "Survey of transformer rerankers and the effectiveness&ndash;efficiency trade-off."),
    ("Document Ranking with a Pretrained Sequence-to-Sequence Model", "monoT5, arXiv 2003.06713", "Reads &ldquo;true/false&rdquo; logits as relevance &mdash; ancestor of yes/no scoring."),
    ("Is ChatGPT Good at Search? (RankGPT)", "Sun et al., arXiv 2304.09542", "Listwise LLM reranking and permutation distillation."),
    ("LLMs are Effective Text Rankers with Pairwise Ranking Prompting", "Qin et al., arXiv 2306.17563", "Why pointwise and listwise prompts are hard; pairwise remedy."),
    ("A Setwise Approach for Zero-shot Ranking with LLMs", "Zhuang et al., arXiv 2310.09497", "Compares the three paradigms on effectiveness and cost."),
    ("RankZephyr", "Pradeep et al., arXiv 2312.02724", "Open listwise reranker; robustness to input order."),
    ("ColBERT; BEIR", "arXiv 2004.12832; 2104.08663", "Cost of cross-encoding; zero-shot evaluation of re-ranking."),
    ("Making a MIRACL; JQaRA dataset card", "arXiv 2210.09984; hotchpotch/JQaRA (Hugging Face)", "The two benchmarks, including how labels were built."),
    ("Qwen3-Reranker-8B model card", "Hugging Face; arXiv 2506.05176", "Open yes/no-logit reranker with runnable code."),
    ("Cohere Rerank overview", "docs.cohere.com", "API behaviour and search-unit billing."),
    ("TypeSafe docs (System One, AI primer, Noul, Choice, Re-ranking cookbook)", "docs.typesafe.ai", "Primary source for decision models; vendor claims, read critically."),
    ("OpenRouter: Jev guide and &ldquo;What is Jev?&rdquo;", "openrouter.ai/docs, openrouter.ai/blog", "Decisions API, other decision models, pricing, context notes."),
    ("This project&rsquo;s repository", "code, raw per-query results, analysis scripts", "Reproduces every number in this deck (<code>results_final/</code>)."),
]
rr = "".join(
    f'<tr class="{"sep" if i else ""}"><td>{t}</td><td class="dim">{a}</td><td>{w}</td></tr>' for i, (t, a, w) in enumerate(res)
)
slide(
    "Resources",
    "Resources I found most useful",
    f"""<table style="font-size:14px"><tr><th style="width:36%">Resource</th><th style="width:23%">Source</th><th>Why it is useful</th></tr>{rr}</table>
""",
    "Papers checked via arXiv abstracts; vendor documentation (TypeSafe, OpenRouter, Cohere, Qwen) read for the cited pages and treated as claims, not evidence. Links opened 2026-11.",
)

assert len(slides) == N, len(slides)
html = (
    '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    "<title>Can a Decision Model Rerank? &mdash; CS410 Technology Review</title>"
    f"<style>{CSS}</style></head><body><div class=\"deck\">"
    + "\n".join(slides)
    + f"</div><script>{JS}</script></body></html>"
)
OUT.write_text(html, encoding="utf-8")
print("wrote", OUT, len(html) // 1024, "KB,", len(slides), "slides")
