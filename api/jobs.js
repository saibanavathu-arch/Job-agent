// Live job search endpoint (Vercel serverless function).
// GET /api/jobs?what=product+manager&where=Hyderabad&days=7&page=1
// Keeps your Adzuna keys on the server and returns jobs in the agent's import format.

const OK_TEXT = /^[\p{L}\p{N}\s&.,'/+()-]{2,80}$/u;
const U = "(?:months?|mos?|yrs?|years?)";
const EXP_PATTERNS = [
  new RegExp(`\\d+(?:\\.\\d+)?\\s*${U}?\\s*(?:-|–|to)\\s*\\d+(?:\\.\\d+)?\\s*${U}`, "i"),
  /\d+\s*(?:years?|yrs?)\s*(?:and\s*)?\d+\s*(?:months?|mos?)/i,
  new RegExp(`\\d+(?:\\.\\d+)?\\s*\\+?\\s*${U}(?=\\s*(?:of\\s*)?(?:relevant\\s*)?(?:experience|exp))`, "i"),
];

function expFrom(text) {
  for (const p of EXP_PATTERNS) {
    const m = text.match(p);
    if (m) return m[0].trim();
  }
  return "";
}

const lpa = (v) => (v ? Math.round((v / 100000) * 10) / 10 : 0);

function normalize(r) {
  const desc = r.description || "";
  return {
    title: r.title || "",
    company: (r.company && r.company.display_name) || "",
    location: (r.location && r.location.display_name) || "",
    source: "Adzuna",
    posted: (r.created || "").slice(0, 10),
    salary_min: lpa(r.salary_min),
    salary_max: lpa(r.salary_max),
    salary_predicted: String(r.salary_is_predicted) === "1",
    notice_period: "",
    experience: expFrom(desc),
    skills: desc.slice(0, 400),
    url: r.redirect_url || "",
  };
}

const clamp = (v, lo, hi, d) => Math.min(Math.max(parseInt(v, 10) || d, lo), hi);

module.exports = async function handler(req, res) {
  if (req.method !== "GET") return res.status(405).json({ error: "GET only" });

  // Optional: set ALLOWED_HOST (e.g. myjobs.vercel.app) to reject calls from other sites.
  const allowed = process.env.ALLOWED_HOST;
  if (allowed) {
    const ref = req.headers.referer || req.headers.origin || "";
    if (!ref.includes(allowed)) return res.status(403).json({ error: "forbidden" });
  }

  const what = String(req.query.what || "").trim();
  const where = String(req.query.where || "").trim();
  if (!OK_TEXT.test(what) || (where && !OK_TEXT.test(where))) {
    return res.status(400).json({ error: "invalid search" });
  }
  const days = clamp(req.query.days, 1, 30, 7);
  const page = clamp(req.query.page, 1, 3, 1);

  const id = process.env.ADZUNA_APP_ID;
  const key = process.env.ADZUNA_APP_KEY;
  if (!id || !key) return res.status(500).json({ error: "server not configured" });

  const qs = new URLSearchParams({
    app_id: id,
    app_key: key,
    results_per_page: "50",
    title_only: what.toLowerCase(),
    max_days_old: String(days),
    sort_by: "date",
    "content-type": "application/json",
  });
  if (where) qs.set("where", where);

  try {
    const r = await fetch(`https://api.adzuna.com/v1/api/jobs/in/search/${page}?${qs}`);
    if (!r.ok) return res.status(502).json({ error: `job source returned ${r.status}` });
    const data = await r.json();
    const jobs = (data.results || []).map(normalize).filter((j) => j.url);
    // Same search within an hour is served from the edge cache, which protects your API quota.
    res.setHeader("Cache-Control", "public, s-maxage=3600, stale-while-revalidate=7200");
    return res.status(200).json(jobs);
  } catch (e) {
    return res.status(502).json({ error: "job source unreachable" });
  }
};
