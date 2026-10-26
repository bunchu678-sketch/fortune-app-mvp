"use client";
import { useParams } from "next/navigation";
import OperationsView from "../../operations-view";
export default function Page() { const id = String(useParams<{ organizationId: string }>().organizationId); return <OperationsView view="organization" id={id} />; }
