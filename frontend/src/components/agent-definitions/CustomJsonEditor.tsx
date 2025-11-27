import { useCallback, useMemo } from "react";
import Editor from "@monaco-editor/react";
import type { editor as MonacoEditor } from "monaco-editor";

const MONACO_THEME_NAME = "magicAgent";
let monacoThemeDefined = false;

type Monaco = typeof import("monaco-editor");

export interface CustomJsonEditorProps {
  value: string;
  onChange: (value: string) => void;
  height?: string;
}

export function CustomJsonEditor({
  value,
  onChange,
  height = "24rem",
}: CustomJsonEditorProps) {
  const handleBeforeMount = useCallback((monaco: Monaco) => {
    if (!monacoThemeDefined) {
      monaco.editor.defineTheme(MONACO_THEME_NAME, {
        base: "vs",
        inherit: true,
        rules: [
          { token: "comment", foreground: "64748B" },
          { token: "string", foreground: "0F766E" },
          { token: "number", foreground: "B91C1C" },
          { token: "keyword", foreground: "4338CA", fontStyle: "bold" },
        ],
        colors: {
          "editor.background": "#F8FAFC",
          "editor.foreground": "#0F172A",
          "editorCursor.foreground": "#2563EB",
          "editor.lineHighlightBackground": "#E2E8F080",
          "editor.selectionBackground": "#93C5FD66",
          "editor.inactiveSelectionBackground": "#BFDBFE4D",
          "editorLineNumber.foreground": "#94A3B8",
          "editorLineNumber.activeForeground": "#0F172A",
          "editorIndentGuide.background": "#E2E8F0",
          "editorIndentGuide.activeBackground": "#CBD5F5",
          "editorWhitespace.foreground": "#CBD5F5",
          "editorWidget.background": "#FFFFFF",
          "scrollbarSlider.background": "#CBD5F566",
          "scrollbarSlider.hoverBackground": "#94A3B888",
          "scrollbarSlider.activeBackground": "#64748B99",
        },
      });

      monacoThemeDefined = true;
    }

    monaco.editor.setTheme(MONACO_THEME_NAME);
  }, []);

  const editorOptions = useMemo<
    MonacoEditor.IStandaloneEditorConstructionOptions
  >(
    () => ({
      minimap: { enabled: false },
      automaticLayout: true,
      formatOnPaste: true,
      formatOnType: true,
      fontFamily:
        "var(--font-mono, ui-monospace, SFMono-Regular, 'JetBrains Mono', 'Fira Code', Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace)",
      fontSize: 13,
      lineHeight: 20,
      smoothScrolling: true,
      scrollBeyondLastLine: false,
      padding: { top: 16, bottom: 16 },
      renderLineHighlight: "line",
      tabSize: 2,
      scrollbar: {
        verticalScrollbarSize: 12,
        horizontalScrollbarSize: 12,
      },
    }),
    []
  );

  return (
    <div className="rounded-md border border-border">
      <Editor
        height={height}
        defaultLanguage="json"
        theme={MONACO_THEME_NAME}
        value={value}
        beforeMount={handleBeforeMount}
        options={editorOptions}
        onChange={(nextValue: string | undefined) =>
          onChange(nextValue ?? "")
        }
      />
    </div>
  );
}
