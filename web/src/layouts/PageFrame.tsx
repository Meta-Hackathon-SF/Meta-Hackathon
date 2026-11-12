import type { ReactNode } from "react";
import LeftSidebar from "../components/layout/LeftSidebar";

export default function PageFrame({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <div className="secondary-layout">
      <LeftSidebar />
      <main className="secondary-main" id="main-content">
        <header className="page-heading">
          <h1>{title}</h1>
          {description && <p>{description}</p>}
        </header>
        {children}
        <p className="secondary-prototype-note">
          Unofficial hackathon prototype · Fictional demo content
        </p>
      </main>
    </div>
  );
}
