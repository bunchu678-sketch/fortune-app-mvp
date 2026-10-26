"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "./auth";
import { useFortuneState } from "./fortune-state";
import { newReadingDestination } from "./member-navigation";
import { productRequest } from "./product-client";

export default function HistoryNewReading() {
  const { user, loading } = useAuth();
  const { setDraft, setSaved } = useFortuneState();
  const [destination, setDestination] = useState<{ owner: string; href: string | null } | null>(null);
  useEffect(() => {
    let active = true;
    setDestination(null);
    if (user && !loading) {
      void newReadingDestination(path => productRequest(path)).then(href => {
        if (active) setDestination({ owner: user.id, href });
      });
    }
    return () => { active = false; };
  }, [user?.id, loading]);
  if (loading || !user || destination?.owner !== user.id || !destination.href) return null;
  return <Link href={destination.href} onClick={() => { setDraft(null); setSaved(null); }}>新しく鑑定する</Link>;
}
