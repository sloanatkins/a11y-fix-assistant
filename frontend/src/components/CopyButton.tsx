import { useEffect, useState } from "react";

type CopyButtonProps = {
  text: string;
};

function CopyButton({ text }: CopyButtonProps) {
  const [status, setStatus] = useState<"idle" | "copied" | "failed">("idle");

  // puts the label back after a couple of seconds
  useEffect(() => {
    if (status === "idle") return;
    const timer = window.setTimeout(() => setStatus("idle"), 2500);
    return () => window.clearTimeout(timer);
  }, [status]);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setStatus("copied");
    } catch {
      // browsers can block clipboard access
      setStatus("failed");
    }
  }

  return (
    <div className="copy">
      <button type="button" className="secondary" onClick={handleCopy}>
        Copy fix
      </button>
      <span role="status">
        {status === "copied" && "Copied"}
        {status === "failed" && "Couldn't copy. Select the code and copy it by hand."}
      </span>
    </div>
  );
}

export default CopyButton;
