"use client";
import { useParams } from "next/navigation";
import OperationsView from "../../operations-view";
export default function Page() { const id = String(useParams<{ userId: string }>().userId); return <OperationsView view="user" id={id} />; }
