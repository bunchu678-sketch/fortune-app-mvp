import type { ReactNode } from "react";
import { ProductStateProvider } from "./product-state";
import "./product.css";

export default function ProductLayout({ children }: { children: ReactNode }) {
  return <ProductStateProvider><div className="productRoot">{children}</div></ProductStateProvider>;
}
