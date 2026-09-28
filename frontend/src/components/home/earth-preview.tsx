import { Icon } from "@/components/icon";

export function EarthPreview() {
  return (
    <figure className="earth-preview" aria-labelledby="preview-caption">
      <div className="preview-topline">
        <span className="preview-window-dots" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
        <span>Unified workspace</span>
        <span className="preview-label">Illustrative</span>
      </div>
      <div className="preview-layout" aria-hidden="true">
        <div className="preview-sidebar">
          <span className="preview-brand-dot" />
          <span />
          <span />
          <span />
        </div>
        <div className="preview-scene">
          <div className="preview-grid" />
          <div className="preview-orbit preview-orbit-one" />
          <div className="preview-orbit preview-orbit-two" />
          <div className="preview-earth">
            <div className="preview-land preview-land-one" />
            <div className="preview-land preview-land-two" />
          </div>
          <span className="preview-scene-label">Scene area</span>
        </div>
        <div className="preview-assistant">
          <div className="preview-assistant-title">
            <Icon name="spark" />
            <span>Ask SatQuery</span>
          </div>
          <span className="preview-line preview-line-wide" />
          <span className="preview-line" />
          <div className="preview-input">
            <span>Draft a question…</span>
            <i />
          </div>
        </div>
      </div>
      <figcaption id="preview-caption">
        Illustrative interface concept — no satellite scene or analysis result is shown.
      </figcaption>
    </figure>
  );
}
