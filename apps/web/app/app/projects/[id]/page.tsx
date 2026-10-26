"use client";

import { use } from "react";
import ProjectPage from "./project-page";

/** `/app/projects/{id}`: unwraps the route params; project-page.tsx decides
 *  which page this project gets. */
export default function ProjectRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <ProjectPage id={id} />;
}
