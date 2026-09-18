type CodeBlockProps = {
  title: string;
  code: string;
};

function CodeBlock({ title, code }: CodeBlockProps) {
  return (
    <figure className="code-block">
      <figcaption>{title}</figcaption>
      {/* tabIndex lets keyboard users scroll long lines of code */}
      <pre tabIndex={0}>
        <code>{code}</code>
      </pre>
    </figure>
  );
}

export default CodeBlock;
