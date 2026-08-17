import { useEffect, useState } from "react";

export function PwaStatus() {
  const [installEvent, setInstallEvent] = useState<BeforeInstallPromptEvent | null>(null);
  const [installed, setInstalled] = useState(false);
  useEffect(() => {
    const handler = (event: Event) => { event.preventDefault(); setInstallEvent(event as BeforeInstallPromptEvent); };
    const installedHandler = () => { setInstalled(true); setInstallEvent(null); };
    window.addEventListener("beforeinstallprompt", handler);
    window.addEventListener("appinstalled", installedHandler);
    return () => { window.removeEventListener("beforeinstallprompt", handler); window.removeEventListener("appinstalled", installedHandler); };
  }, []);
  if (installed) return <p className="status-note">Installed as an app</p>;
  if (!installEvent) return null;
  return <button className="quiet-button" type="button" onClick={async () => { await installEvent.prompt(); setInstallEvent(null); }}>Install app</button>;
}

export type BeforeInstallPromptEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: "accepted" | "dismissed" }> };
