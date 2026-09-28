import Link from "next/link";

import { BrandMark } from "@/components/brand-mark";
import { EarthPreview } from "@/components/home/earth-preview";
import { HomeNavigation } from "@/components/home/home-navigation";
import { Icon, type IconName } from "@/components/icon";

const workflowSteps: Array<{ number: string; title: string; copy: string; icon: IconName }> = [
  {
    number: "01",
    title: "Choose imagery",
    copy: "Start from an identified analytical asset, with its source and usable metadata kept in view.",
    icon: "layers",
  },
  {
    number: "02",
    title: "Ask a question",
    copy: "Describe what you need to investigate in natural language, within a supported analysis workflow.",
    icon: "question",
  },
  {
    number: "03",
    title: "Inspect the evidence",
    copy: "Review the answer beside its spatial evidence, method, assumptions, and explicit limitations.",
    icon: "evidence",
  },
];

const capabilities: Array<{ title: string; copy: string; icon: IconName }> = [
  {
    title: "Satellite-image questions",
    copy: "Connect focused questions to identified imagery rather than asking a model to infer from context alone.",
    icon: "question",
  },
  {
    title: "Spatial grounding",
    copy: "Keep future findings tied to their source image and a declared pixel or geographic coordinate space.",
    icon: "target",
  },
  {
    title: "Change analysis",
    copy: "Prepare compatible before-and-after imagery for defensible comparison with quality checks visible.",
    icon: "activity",
  },
  {
    title: "Optical and SAR interpretation",
    copy: "Support sensor-aware workflows only when inputs, preprocessing, and validated methods are suitable.",
    icon: "spark",
  },
];

const evidenceItems = [
  "Source imagery identity and usable metadata",
  "Spatial evidence with an explicit coordinate space",
  "Methods, parameters, and processing records",
  "Assumptions, uncertainty meaning, and limitations",
];

export function Homepage() {
  return (
    <div className="home-page">
      <HomeNavigation />
      <main id="main-content">
        <section className="hero page-width" aria-labelledby="hero-title">
          <div className="hero-copy">
            <p className="eyebrow">Evidence-minded Earth observation</p>
            <h1 id="hero-title">Turn satellite imagery into answers you can inspect.</h1>
            <p className="hero-intro">
              SatQuery is a unified workspace for asking remote-sensing questions while keeping
              source imagery, spatial evidence, methods, and limitations close to every answer.
            </p>
            <div className="hero-actions">
              <Link className="button button-primary" href="/workspace">
                Open workspace
                <Icon className="button-icon" name="arrow" />
              </Link>
              <a className="button button-secondary" href="#capabilities">
                Explore capabilities
              </a>
            </div>
            <ul className="hero-principles" aria-label="Product principles">
              <li>Identified sources</li>
              <li>Inspectable evidence</li>
              <li>Explicit limits</li>
            </ul>
          </div>
          <EarthPreview />
        </section>

        <section
          className="workflow-section section-block"
          id="workflow"
          aria-labelledby="workflow-title"
        >
          <div className="page-width">
            <div className="section-heading">
              <p className="eyebrow">A traceable workflow</p>
              <h2 id="workflow-title">From a scene to a reviewable answer.</h2>
              <p>
                The intended workflow keeps the analytical input and the evidence chain visible from
                the first question onward.
              </p>
            </div>
            <ol className="workflow-grid">
              {workflowSteps.map((step) => (
                <li key={step.number}>
                  <div className="workflow-card-topline">
                    <span className="feature-icon">
                      <Icon name={step.icon} />
                    </span>
                    <span className="step-number">{step.number}</span>
                  </div>
                  <h3>{step.title}</h3>
                  <p>{step.copy}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section
          className="capabilities-section section-block"
          id="capabilities"
          aria-labelledby="capabilities-title"
        >
          <div className="page-width">
            <div className="section-heading section-heading-row">
              <div>
                <p className="eyebrow">Planned capabilities</p>
                <h2 id="capabilities-title">One workspace, multiple sensing questions.</h2>
              </div>
              <p>
                These product directions are planned, not operational in the current interface. Each
                will require identified data and a validated method before it can return a result.
              </p>
            </div>
            <div className="capability-grid">
              {capabilities.map((capability) => (
                <article className="capability-card" key={capability.title}>
                  <div className="capability-card-topline">
                    <span className="feature-icon">
                      <Icon name={capability.icon} />
                    </span>
                    <span className="planned-badge">Planned</span>
                  </div>
                  <h3>{capability.title}</h3>
                  <p>{capability.copy}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section
          className="evidence-section section-block"
          id="evidence"
          aria-labelledby="evidence-title"
        >
          <div className="page-width evidence-layout">
            <div className="evidence-copy">
              <p className="eyebrow">Evidence before assertion</p>
              <h2 id="evidence-title">A clear path back to what supports an answer.</h2>
              <p>
                SatQuery is designed to separate measured geospatial evidence from narrative
                explanation. When evidence is insufficient or a capability is unavailable, the
                interface should say so plainly.
              </p>
              <ul className="evidence-list">
                {evidenceItems.map((item) => (
                  <li key={item}>
                    <span className="evidence-check" aria-hidden="true">
                      ✓
                    </span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
            <section className="evidence-demo" aria-label="Illustrative evidence panel">
              <div className="evidence-demo-header">
                <span>
                  <Icon name="evidence" /> Evidence record
                </span>
                <span className="preview-label">Illustrative</span>
              </div>
              <dl>
                <div>
                  <dt>Source imagery</dt>
                  <dd>Awaiting an identified asset</dd>
                </div>
                <div>
                  <dt>Spatial evidence</dt>
                  <dd>Unavailable until analysis exists</dd>
                </div>
                <div>
                  <dt>Processing record</dt>
                  <dd>No process has run</dd>
                </div>
                <div>
                  <dt>Limitations</dt>
                  <dd>Shown with any future result</dd>
                </div>
              </dl>
            </section>
          </div>
        </section>

        <section className="closing-section page-width" aria-labelledby="closing-title">
          <div>
            <p className="eyebrow">Start with the workspace</p>
            <h2 id="closing-title">
              Prepare a question without pretending the answer already exists.
            </h2>
          </div>
          <Link className="button button-primary" href="/workspace">
            Open workspace
            <Icon className="button-icon" name="arrow" />
          </Link>
        </section>
      </main>
      <footer className="home-footer">
        <div className="page-width footer-layout">
          <div className="footer-brand">
            <BrandMark />
            <p>A grounded vision-language workspace for multimodal remote-sensing analysis.</p>
          </div>
          <nav aria-label="Footer navigation">
            <a href="#workflow">Workflow</a>
            <a href="#capabilities">Capabilities</a>
            <a href="#evidence">Evidence</a>
            <Link href="/workspace">Workspace</Link>
          </nav>
          <p className="footer-note">Built for inspectable geospatial work.</p>
        </div>
      </footer>
    </div>
  );
}
