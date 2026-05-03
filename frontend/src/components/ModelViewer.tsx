import { Suspense } from "react";
import { Canvas } from "@react-three/fiber";
import { Bounds, Environment, OrbitControls, useGLTF } from "@react-three/drei";
import { Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import { cn } from "@/lib/utils";

export interface ViewerSource {
  fileId: string;
  fileName: string;
  url: string;
}

interface Props {
  sources: ViewerSource[];
  status: string;
  selected: number;
  onSelect: (i: number) => void;
}

export function ModelViewer({ sources, status, selected, onSelect }: Props) {
  const { t } = useTranslation();

  if (status === "pending") {
    return <ViewerNotice message={t("model.viewer_pending")} spinner />;
  }
  if (status === "conversion_failed") {
    return <ViewerNotice message={t("model.viewer_failed")} />;
  }
  if (sources.length === 0) {
    return <ViewerNotice message={t("model.viewer_pending")} spinner />;
  }

  const current = sources[Math.min(selected, sources.length - 1)];

  return (
    <div className="space-y-3">
      <div className="relative h-[500px] w-full overflow-hidden rounded-lg border border-border bg-bg-subtle">
        <Canvas camera={{ position: [3, 3, 3], fov: 45 }} dpr={[1, 2]}>
          <ambientLight intensity={0.6} />
          <directionalLight position={[5, 10, 5]} intensity={0.8} />
          <Suspense fallback={null}>
            <Bounds fit clip observe margin={1.2}>
              <GLBModel url={current.url} />
            </Bounds>
            <Environment preset="studio" />
          </Suspense>
          <OrbitControls enableDamping makeDefault />
          <gridHelper args={[50, 50, "#d4d4d8", "#e4e4e7"]} />
        </Canvas>
        <div className="pointer-events-none absolute bottom-2 left-2 rounded bg-black/55 px-2 py-0.5 text-xs font-mono text-white">
          {current.fileName}
        </div>
      </div>
      {sources.length > 1 && (
        <div className="flex flex-wrap gap-1.5">
          {sources.map((s, i) => (
            <button
              key={s.fileId}
              type="button"
              onClick={() => onSelect(i)}
              className={cn(
                "rounded-md border px-2.5 py-1 text-xs font-mono transition",
                i === selected
                  ? "border-accent bg-accent-subtle text-accent"
                  : "border-border text-text-muted hover:border-text-muted hover:text-text",
              )}
              title={s.fileName}
            >
              {s.fileName.length > 36 ? s.fileName.slice(0, 33) + "…" : s.fileName}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function GLBModel({ url }: { url: string }) {
  const { scene } = useGLTF(url);
  return <primitive object={scene} />;
}

function ViewerNotice({
  message,
  spinner,
}: {
  message: string;
  spinner?: boolean;
}) {
  return (
    <div className="flex h-[500px] items-center justify-center rounded-lg border border-border bg-bg-subtle text-sm text-text-muted">
      <div className="flex items-center gap-2">
        {spinner && <Loader2 className="h-4 w-4 animate-spin" />}
        <span>{message}</span>
      </div>
    </div>
  );
}
