import { useEffect, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiFetch } from "@/lib/api";
import { LoadingState } from "@/components/portrait/PageShell";

/** Where a tapped notification lands: opens the chat with Reflectra's question already asked. */
export function OpenNudgePage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    (async () => {
      try {
        const res = await apiFetch(`/api/notifications/open/${id}`, { method: "POST" });
        const data = res.ok ? ((await res.json()) as { url?: string }) : {};
        // "from=nudge" lets the chat type the opener in, as if it were being written for you now.
        const url = data.url || "/app/chat?mode=reflection";
        navigate(`${url}${url.includes("?") ? "&" : "?"}from=nudge`, { replace: true });
      } catch {
        navigate("/app/chat?mode=reflection", { replace: true });
      }
    })();
  }, [id, navigate]);

  return <LoadingState label="Opening…" />;
}
