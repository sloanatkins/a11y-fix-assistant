type IssueCluesProps = {
  context: Record<string, string>;
};

type ColorChipProps = {
  label: string;
  color: string;
  background: string;
};

// a color block instead of sample text, so this app doesn't fail contrast itself
function ColorChip({ label, color, background }: ColorChipProps) {
  return (
    <div className="swatch">
      <span className="chip" style={{ background }} aria-hidden="true">
        <span style={{ background: color }} />
      </span>
      <span>
        {label}
        <code>{color}</code>
      </span>
    </div>
  );
}

// shows the things I need to judge a fix that the HTML alone doesn't tell me
function IssueClues({ context }: IssueCluesProps) {
  const {
    image_url: imageUrl,
    link_url: linkUrl,
    nearby_text: nearbyText,
    text_color: textColor,
    background_color: backgroundColor,
    current_ratio: currentRatio,
    required_ratio: requiredRatio,
    suggested_color: suggestedColor,
  } = context;

  if (!imageUrl && !linkUrl && !nearbyText && !textColor) return null;

  return (
    <section className="clues" aria-labelledby="clues-heading">
      <h2 id="clues-heading">What the check found on the page</h2>

      {imageUrl && (
        <figure className="image-preview">
          <img src={imageUrl} alt="The flagged image" />
          <figcaption>{imageUrl}</figcaption>
        </figure>
      )}

      <dl className="clue-list">
        {linkUrl && (
          <div>
            <dt>Link goes to</dt>
            <dd>{linkUrl}</dd>
          </div>
        )}
        {nearbyText && (
          <div>
            <dt>Nearby text</dt>
            <dd>{nearbyText}</dd>
          </div>
        )}
        {textColor && (
          <div>
            <dt>Contrast</dt>
            <dd>
              {currentRatio}:1 now, needs {requiredRatio}:1
            </dd>
          </div>
        )}
      </dl>

      {textColor && (
        <div className="swatches">
          <ColorChip label="Current text color" color={textColor} background={backgroundColor} />
          {suggestedColor && (
            <ColorChip label="Passing text color" color={suggestedColor} background={backgroundColor} />
          )}
        </div>
      )}
    </section>
  );
}

export default IssueClues;
