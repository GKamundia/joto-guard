const LEVEL_STYLE = {
  "suspected fault": "suspect",
  "channel empty": "bad",
  "duplicated export column": "bad",
  "undocumented device code": "quiet",
  "non-standard firmware value": "suspect",
};

export default function Recommendations({ items }) {
  return (
    <section className="card">
      <h2>What we suggest to JHUB</h2>
      <p className="lead">
        Each point appears only because this record shows it, and is worded no more strongly than
        the evidence allows.
      </p>
      {items.length === 0 ? (
        <p>Nothing in this record needs attention.</p>
      ) : (
        items.map((item) => (
          <div className="finding" key={item.title}>
            <h3>{item.title}</h3>
            <p>{item.detail}</p>
            <span className={`pill ${LEVEL_STYLE[item.evidence_level] ?? "quiet"}`}>
              {item.evidence_level}
            </span>{" "}
            <span className="source">
              from {item.rules.join(", ")}
            </span>
          </div>
        ))
      )}
    </section>
  );
}
