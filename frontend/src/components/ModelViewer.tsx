import { Suspense, useEffect, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { Bounds, Environment, OrbitControls, useGLTF } from "@react-three/drei";
import { Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import { api } from "@/lib/api";

interface Props {
  modelIdOrSlug: string;
  status: string;
}

export function ModelViewer({ modelIdOrSlug, status }: Props) {
  const { t } = useTranslation();
  const [glbUrl, setGlbUrl] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (status !== "glb_ready") return;
    let cancelled = false;
    (async () => {
      try {
        // GET /models/:id/glb returns 302 to presigned URL.
        // axios follows redirect by default in the browser, so we just use that.
        const r = await api.get(`/models/${modelIdOrSlug}/glb`, {
          maxRedirects: 0,
          validateStatus: (s) => s === 200 || s === 302,
        });
        const url = (r as unknown as { request: XMLHttpRequest }).request.responseURL;
        if (!cancelled) setGlbUrl(url);
      } catch (e) {
        if (!cancelled) setErr(String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [modelIdOrSlug, status]);

  if (status === "pending") {
    return <ViewerNotice message={t("model.viewer_pending")} spinner />;
  }
  if (status === "conversion_failed") {
    return <ViewerNotice message={t("model.viewer_failed")} />;
  }
  if (err) return <ViewerNotice message={err} />;
  if (!glbUrl) return <ViewerNotice message={t("model.viewer_pending")} spinner />;

  return (
    <div className="relative h-[500px] w-full overflow-hidden rounded-lg border border-border bg-bg-subtle">
      <Canvas camera={{ position: [3, 3, 3], fov: 45 }} dpr={[1, 2]}>
        <ambientLight intensity={0.6} />
        <directionalLight position={[5, 10, 5]} intensity={0.8} />
        <Suspense fallback={null}>
          <Bounds fit clip observe margin={1.2}>
            <GLBModel url={glbUrl} />
          </Bounds>
          <Environment preset="studio" />
        </Suspense>
        <OrbitControls enableDamping makeDefault />
        <gridHelper args={[50, 50, "#d4d4d8", "#e4e4e7"]} />
      </Canvas>
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
