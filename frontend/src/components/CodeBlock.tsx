type CodeBlockProps = {
  title: string;
  code: string;
  compareTo?: string;
  changeClass?: "added" | "removed";
};

// finds where two strings stop matching at the start and at the end
function findChange(code: string, other: string) {
  let start = 0;
  while (start < code.length && start < other.length && code[start] === other[start]) {
    start += 1;
  }
  let end = 0;
  while (
    end < code.length - start &&
    end < other.length - start &&
    code[code.length - 1 - end] === other[other.length - 1 - end]
  ) {
    end += 1;
  }
  return { start, stop: code.length - end };
}

function CodeBlock({ title, code, compareTo, changeClass = "added" }: CodeBlockProps) {
  const { start, stop } =
    compareTo === undefined ? { start: 0, stop: 0 } : findChange(code, compareTo);

  return (
    <figure className="code-block">
      <figcaption>{title}</figcaption>
      {/* tabIndex lets keyboard users scroll long lines of code */}
      <pre tabIndex={0}>
        <code>
          {code.slice(0, start)}
          {stop > start && <mark className={changeClass}>{code.slice(start, stop)}</mark>}
          {code.slice(Math.max(start, stop))}
        </code>
      </pre>
    </figure>
  );
}

export default CodeBlock;
