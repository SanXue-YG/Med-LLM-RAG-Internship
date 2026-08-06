import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Props = {
  content: string;
  className?: string;
};

/** Render LLM / docs markdown with light styling. */
export function MarkdownView({ content, className }: Props) {
  return (
    <div className={`md-body ${className || ""}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content || ""}</ReactMarkdown>
    </div>
  );
}
